from copy import deepcopy
from datetime import datetime, timezone
import json
from unittest.mock import Mock
import pytest
from ai_data_governance import lifecycle
from ai_data_governance.client import AidpClient
from ai_data_governance.native_client import NativeClient
from ai_data_governance.receipts import ReceiptStore
from ai_data_governance.errors import AidpProvisionConflict, AidpProvisionPending
from tests.test_receipts import Objects
from tests.domain.test_ai_dg_deploy_studio_install import Owner, WORKSPACE


OPERATION = '77777777-7777-4777-8777-777777777777'


def harness(monkeypatch):
    monkeypatch.setattr(lifecycle, 'candidate_revision', lambda: 'revision-1')
    owner = Owner()
    owner._oci_config = {'tenancy': 'tenancy', 'user': 'operator', 'fingerprint': 'fingerprint'}
    owner._governance_workspace = lambda: WORKSPACE
    owner._workspace_json = lambda *args: None
    owner._new_module_manifest = lambda *args: AidpClient._new_module_manifest(owner, *args)
    owner._write_module_manifest = lambda *args: NativeClient._write_module_manifest(owner, *args)
    owner.store = owner.receipt = owner.receipt_revision = None
    store = ReceiptStore(Objects(), 'namespace', 'artifacts', owner.settings.aidp_platform_id, WORKSPACE)
    return owner, store


def run(owner, store, command='install', operation=OPERATION):
    return lifecycle.run_operation(owner, store, admin='administrator', domain='domain', operation_id=operation, command=command)


def finish_install(owner, store):
    for _ in range(8):
        try:
            return run(owner, store, 'resume' if owner.runs else 'install')
        except AidpProvisionPending:
            for key in owner.runs:
                owner.complete(key)
    pytest.fail('Installation did not reach technical completion')


def test_install_resume_retains_operation_and_executes_exact_workflow(monkeypatch):
    owner, store = harness(monkeypatch)
    receipt = finish_install(owner, store)
    manifest = receipt['manifest']
    assert manifest['status'] == 'active'
    assert manifest['validation_stage'] == 'TEST_PENDING'
    assert manifest['operation']['operation_id'] == OPERATION
    assert len(owner.runs) == 2
    assert [task['taskKey'] for task in owner.job['tasks']] == ['sync_inventory','document_metadata','publish_metadata','replicate_model']
    writes = len(owner.calls)
    assert run(owner, store, 'resume') == receipt
    assert len(owner.calls) == writes


def test_resume_rejects_changed_administrator_candidate_or_operation_before_mutation(monkeypatch):
    owner, store = harness(monkeypatch)
    with pytest.raises(AidpProvisionPending):
        run(owner, store)
    before = deepcopy(owner.calls)
    with pytest.raises(AidpProvisionConflict, match='original operation'):
        run(owner, store, 'resume', '88888888-8888-4888-8888-888888888888')
    with pytest.raises(AidpProvisionConflict, match='administrator'):
        lifecycle.run_operation(owner, store, admin='foreign', domain='domain', operation_id=OPERATION, command='resume')
    monkeypatch.setattr(lifecycle, 'candidate_revision', lambda: 'changed')
    with pytest.raises(AidpProvisionConflict, match='candidate revision'):
        run(owner, store, 'resume')
    assert owner.calls == before


def test_completed_update_lost_ack_does_not_redeploy_or_overwrite_snapshot(monkeypatch):
    owner, store = harness(monkeypatch)
    receipt = finish_install(owner, store)
    receipt['manifest']['operation']['type'] = 'update'
    receipt['previous'] = {'retained': True}
    _, etag = store.load()
    with store.acquire(OPERATION):
        store.save(receipt, etag)
    before = deepcopy(owner.calls)
    result = run(owner, store, 'update')
    assert result['previous'] == {'retained': True}
    assert owner.calls == before


def test_update_pauses_schedule_and_waits_for_live_writer_before_source_upload(monkeypatch):
    owner, store = harness(monkeypatch)
    finish_install(owner, store)
    before = deepcopy(owner.files)
    owner.runs['live'] = {'state': {'status': 'RUNNING'}}
    monkeypatch.setattr(lifecycle, 'candidate_revision', lambda: 'revision-2')
    with pytest.raises(AidpProvisionPending, match='writers'):
        run(owner, store, 'update', '88888888-8888-4888-8888-888888888888')
    assert owner.job['schedule']['pauseStatus'] == 'PAUSED'
    assert owner.files == before
    assert store.load()[0]['previous']['candidate_revision'] == 'revision-1'


def test_hidden_compute_history_is_never_adopted():
    client = object.__new__(NativeClient)
    client._request = Mock(side_effect=AssertionError('Must not recover by name'))
    assert client._recover_hidden_agent_compute(WORKSPACE) == (None, '')
    client._request.assert_not_called()


@pytest.mark.parametrize('command', ['update', 'redeploy'])
def test_revision_change_reuses_identities_and_requires_new_native_task_evidence(monkeypatch, command):
    owner, store = harness(monkeypatch)
    previous = finish_install(owner, store)
    retained = {key: previous['manifest']['resources'][key] for key in
        ('agent_key','documentation_agent_key','agent_compute_key','cluster_key','workflow_key')}
    # Native fixtures expose the deployment identity fields and subsequent update acknowledgement.
    from tests.domain.test_ai_dg_deploy_studio_install import DOC, COMPUTE
    owner.doc_deployments[0].update(agentKey=DOC, agentComputeKey=COMPUTE)
    original = owner._request
    def request(method, path, **kwargs):
        result = original(method, path, **kwargs)
        if path.endswith('/actions/redeployAgentFlow'):
            owner.test[0]['timeUpdated'] = datetime.now(timezone.utc).isoformat()
        return result
    owner._request = request
    def documentary(*args, **kwargs):
        assert kwargs['redeploy_revision'] == 'revision-2'
        owner.doc_deployments[0]['timeUpdated'] = datetime.now(timezone.utc).isoformat()
        return owner.doc_deployments[0], True
    owner._ensure_agent_deployment = documentary
    monkeypatch.setattr(lifecycle, 'candidate_revision', lambda: 'revision-2')
    operation = '88888888-8888-4888-8888-888888888888'
    for _ in range(10):
        try:
            result = run(owner, store, command, operation)
            break
        except AidpProvisionPending:
            for key in owner.runs:
                owner.complete(key)
    else:
        pytest.fail('Candidate update did not complete')
    assert result['manifest']['status'] == 'active'
    assert result['manifest']['validation_stage'] == 'TEST_PENDING'
    assert result['previous']['candidate_revision'] == 'revision-1'
    assert {key: result['manifest']['resources'][key] for key in retained} == retained
    assert len(owner.runs) == 4
    assert result['manifest']['resources']['test_deployment_key'] == owner.test[0]['key']
    before = deepcopy(owner.calls)
    assert run(owner, store, command, operation) == result
    assert owner.calls == before
