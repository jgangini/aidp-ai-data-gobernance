"""Exercise real maintenance orchestration with native/store doubles and fixed bytes."""
from copy import deepcopy
import hashlib
import json
from unittest.mock import Mock
import pytest
from ai_data_governance import governance_source, lifecycle
from ai_data_governance.errors import AidpProvisionConflict, AidpProvisionError, AidpProvisionPending, AidpRequestError
from ai_data_governance.deployment_bundle import ARTIFACT_ROOT, BOOTSTRAP_PATH
from tests.test_lifecycle import harness, finish_install, run

UPDATE = '88888888-8888-4888-8888-888888888888'
ROLLBACK = '99999999-9999-4999-8999-999999999999'
RUNTIME = ARTIFACT_ROOT + '/agents/governance/governance_runtime.py'


def prepared(monkeypatch, *, paused=False):
    owner, store = harness(monkeypatch)
    receipt = finish_install(owner, store)
    owner.job['schedule']['pauseStatus'] = 'PAUSED' if paused else 'UNPAUSED'
    previous = {'files': deepcopy(owner.files), 'workflow': deepcopy(owner.job),
        'resources': deepcopy(receipt['manifest']['resources']), 'calls': len(owner.calls), 'data': [{'id': 1, 'value': 'retain'}]}
    owner.business_rows = deepcopy(previous['data'])
    monkeypatch.setattr(lifecycle, 'candidate_revision', lambda: 'revision-2')
    monkeypatch.setattr(governance_source, '_RUNTIME_PREAMBLE', governance_source._RUNTIME_PREAMBLE + '\n# Candidate packaging revision\n')
    return owner, store, previous


def drive(owner, store, command='update', operation=UPDATE):
    for _ in range(12):
        try:
            return run(owner, store, command, operation)
        except AidpProvisionPending:
            pass
    pytest.fail('Maintenance did not reach a bounded outcome')


def assert_preserved(owner, previous):
    assert owner.files == previous['files']
    assert owner.job == previous['workflow']
    assert owner.business_rows == previous['data']
    assert len(owner.runs) == 2
    calls = owner.calls[previous['calls']:]
    assert not any(call[0] == 'DELETE' for call in calls)
    assert not any(call[0] == 'POST' and call[1].endswith('/jobRuns') for call in calls)
    assert not any('/actions/managePermission' in call[1] for call in calls)


@pytest.mark.parametrize('paused', [False, True])
def test_successful_update_then_explicit_rollback_restores_exact_bytes_and_schedule(monkeypatch, paused):
    owner, store, previous = prepared(monkeypatch, paused=paused)
    updated = drive(owner, store)
    assert updated['manifest']['status'] == 'active'
    assert owner.files[RUNTIME] != previous['files'][RUNTIME]
    assert owner.job['schedule'] == previous['workflow']['schedule']
    reference = updated['recovery_snapshot']
    snapshot = json.loads(store.get_artifact(reference))
    assert len(snapshot['files']) == 16
    assert snapshot['deployments']['test']['agentFlowKey'] == previous['resources']['agent_key']
    result = drive(owner, store, 'rollback', ROLLBACK)
    assert result['outcome']['status'] == 'rollback_complete'
    assert result['effective_revision'] == 'revision-1'
    assert_preserved(owner, previous)
    retained = ('agent_key', 'documentation_agent_key', 'workflow_key', 'cluster_key', 'agent_compute_key')
    assert {k: result['manifest']['resources'][k] for k in retained} == {k: previous['resources'][k] for k in retained}
    calls = deepcopy(owner.calls)
    assert drive(owner, store, 'rollback', ROLLBACK) == result
    assert owner.calls == calls


def fail_second_candidate_write(owner, previous):
    upload = owner._upload_file
    changed = []
    def partial(workspace, path, body, **kwargs):
        if body != previous['files'][path]:
            changed.append(path)
            if len(changed) == 2:
                raise AidpProvisionError('original update failure: secret upstream detail')
        return upload(workspace, path, body, **kwargs)
    owner._upload_file = partial
    return changed


@pytest.mark.parametrize('paused', [False, True])
def test_partial_update_failure_recovers_but_does_not_report_original_update_as_success(monkeypatch, paused):
    owner, store, previous = prepared(monkeypatch, paused=paused)
    changed = fail_second_candidate_write(owner, previous)
    result = drive(owner, store)
    assert len(changed) == 2
    assert result['manifest']['status'] == 'update_failed_restored'
    assert result['outcome'] == {'status': 'update_failed_restored', 'failed_operation_id': UPDATE, 'failed_operation_type': 'update'}
    assert result['failure']['phase'] == 'write_candidate'
    code = hashlib.sha256(b'AidpProvisionError:original update failure: secret upstream detail').hexdigest()[:16]
    assert result['failure']['error_code'] == result['manifest']['error_code'] == code
    assert 'secret upstream' not in json.dumps(result)
    assert_preserved(owner, previous)
    calls = deepcopy(owner.calls)
    assert drive(owner, store, 'resume')['outcome']['status'] == 'update_failed_restored'
    assert owner.calls == calls


def test_restore_failure_retains_original_cause_then_resume_continues_same_snapshot(monkeypatch):
    owner, store, previous = prepared(monkeypatch)
    fail_second_candidate_write(owner, previous)
    upload = owner._upload_file
    denied = [True]
    def restore_failure(workspace, path, body, **kwargs):
        if denied[0] and path == RUNTIME and body == previous['files'][path]:
            raise AidpProvisionError('restore write denied: secret secondary detail')
        return upload(workspace, path, body, **kwargs)
    owner._upload_file = restore_failure
    result = drive(owner, store)
    assert result['manifest']['status'] == result['outcome']['status'] == 'restore_failed'
    original = deepcopy(result['failure'])
    snapshot = result['recovery_snapshot']
    assert owner.job['schedule']['pauseStatus'] == 'PAUSED'
    assert owner.files[RUNTIME] != previous['files'][RUNTIME]
    assert 'secondary detail' not in json.dumps(result)
    denied[0] = False
    recovered = drive(owner, store, 'resume')
    assert recovered['failure'] == original
    assert recovered['recovery_snapshot'] == snapshot
    assert recovered['outcome']['status'] == 'update_failed_restored'
    assert 'restore_error_code' in recovered
    assert_preserved(owner, previous)


def test_refresh_failure_restores_old_files_and_refreshes_them_with_distinct_retry_scope(monkeypatch):
    owner, store, previous = prepared(monkeypatch)
    request = owner._request
    tokens = []
    def fail_refresh(method, path, **kwargs):
        token = kwargs.get('retry_scope', '')
        if path.endswith('/deployments/actions/redeploy'):
            tokens.append(token)
            if ':candidate:' in token:
                raise AidpProvisionError('candidate deployment rejected')
        return request(method, path, **kwargs)
    owner._request = fail_refresh
    result = drive(owner, store)
    assert result['outcome']['status'] == 'update_failed_restored'
    assert len(tokens) == 2 and tokens[0] != tokens[1]
    assert ':restore:' in tokens[1]
    assert_preserved(owner, previous)


def test_lost_restore_refresh_ack_is_observed_without_second_submission(monkeypatch):
    owner, store, previous = prepared(monkeypatch)
    fail_second_candidate_write(owner, previous)
    request = owner._request
    submissions = []
    def lost_ack(method, path, **kwargs):
        result = request(method, path, **kwargs)
        if path.endswith('/deployments/actions/redeploy') and ':restore:' in kwargs.get('retry_scope', ''):
            submissions.append(path)
            raise AidpProvisionPending('refresh acknowledgement lost', 'refresh')
        return result
    owner._request = lost_ack
    result = drive(owner, store)
    assert result['outcome']['status'] == 'update_failed_restored'
    assert len(submissions) == 1
    assert_preserved(owner, previous)


@pytest.mark.parametrize('change', ['new_path', 'model', 'foreign_bytes', 'agent_identity', 'model_selection'])
def test_nonreversible_or_unowned_change_fails_before_native_mutation(monkeypatch, change):
    owner, store, previous = prepared(monkeypatch)
    from ai_data_governance import maintenance
    if change in {'new_path', 'model'}:
        build = maintenance.build_deployment_bundle
        def changed(binding):
            value = build(binding)
            if change == 'new_path':
                value['files'][ARTIFACT_ROOT + '/new.py'] = b'print(1)\n'
            else:
                value['files'][BOOTSTRAP_PATH] = value['files'][BOOTSTRAP_PATH].replace(b'AI_DG_SCOPE', b'NEW_DG_SCOPE')
            return value
        monkeypatch.setattr(maintenance, 'build_deployment_bundle', changed)
    if change == 'foreign_bytes':
        owner.files[RUNTIME] = b'foreign source'
    if change == 'agent_identity':
        owner.agents[previous['resources']['agent_key']]['computeKey'] = 'foreign-compute'
    if change == 'model_selection':
        owner.settings.agent_model_id = 'different-model'
    before_files, before_job = deepcopy(owner.files), deepcopy(owner.job)
    with pytest.raises(AidpProvisionConflict):
        run(owner, store, 'update', UPDATE)
    assert owner.files == before_files and owner.job == before_job
    assert not any(call[0] in {'PUT', 'POST', 'DELETE'} for call in owner.calls[previous['calls']:])


def test_backup_failure_does_not_publish_snapshot_or_change_native_resources(monkeypatch):
    owner, store, previous = prepared(monkeypatch)
    store.put_artifact = Mock(side_effect=AidpProvisionError('backup storage unavailable'))
    with pytest.raises(AidpProvisionError):
        run(owner, store, 'update', UPDATE)
    assert 'recovery_snapshot' not in store.load()[0]
    assert_preserved(owner, previous)


def test_rollback_refuses_after_candidate_has_started_a_new_run(monkeypatch):
    owner, store, previous = prepared(monkeypatch)
    drive(owner, store)
    owner.runs['irreversible'] = {'key': 'irreversible', 'state': {'status': 'SUCCESS'}}
    before_files, before_job = deepcopy(owner.files), deepcopy(owner.job)
    before_calls = len(owner.calls)
    result = drive(owner, store, 'rollback', ROLLBACK)
    assert result['outcome']['status'] == 'restore_failed'
    assert owner.files == before_files and owner.job == before_job
    assert not any(call[0] in {'PUT', 'POST', 'DELETE'} for call in owner.calls[before_calls:])


def test_corrupt_durable_backup_blocks_restore_without_overwriting_candidate(monkeypatch):
    owner, store, previous = prepared(monkeypatch)
    receipt = drive(owner, store)
    snapshot = json.loads(store.get_artifact(receipt['recovery_snapshot']))
    reference = snapshot['files'][RUNTIME]['sha256']
    target = store._artifact_name(reference)
    _, version = store.objects.rows[target]
    store.objects.rows[target] = b'corrupt stored bytes', version
    before_files, before_job = deepcopy(owner.files), deepcopy(owner.job)
    result = drive(owner, store, 'rollback', ROLLBACK)
    assert result['outcome']['status'] == 'restore_failed'
    assert owner.files == before_files and owner.job == before_job


def test_lost_restore_file_ack_is_reconciled_by_raw_readback_without_second_write(monkeypatch):
    owner, store, previous = prepared(monkeypatch)
    fail_second_candidate_write(owner, previous)
    upload = owner._upload_file
    restored = []
    def uncertain_write(workspace, path, body, **kwargs):
        result = upload(workspace, path, body, **kwargs)
        if path == RUNTIME and body == previous['files'][path]:
            restored.append(path)
            raise AidpProvisionPending('restore file acknowledgement lost', 'artifacts')
        return result
    owner._upload_file = uncertain_write
    result = drive(owner, store)
    assert result['outcome']['status'] == 'update_failed_restored'
    assert restored == [RUNTIME]
    assert_preserved(owner, previous)


def test_each_generation_retains_a_reachable_versioned_snapshot_after_rollback(monkeypatch):
    owner, store, previous = prepared(monkeypatch)
    first = drive(owner, store)
    reference = first['recovery_snapshot']
    drive(owner, store, 'rollback', ROLLBACK)
    monkeypatch.setattr(lifecycle, 'candidate_revision', lambda: 'revision-3')
    next_operation = 'aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa'
    second = drive(owner, store, 'update', next_operation)
    assert second['snapshot_history'][0]['snapshot'] == reference
    assert json.loads(store.get_artifact(reference))['previous']['candidate_revision'] == 'revision-1'
    assert json.loads(store.get_artifact(second['recovery_snapshot']))['previous']['candidate_revision'] == 'revision-1'
    assert second['effective_revision'] == 'revision-3'
    assert len(owner.runs) == 2


def test_unknown_refresh_readback_stays_pending_with_schedule_paused(monkeypatch):
    owner, store, previous = prepared(monkeypatch)
    request = owner._request
    submissions = []
    def unavailable_revision(method, path, **kwargs):
        result = request(method, path, **kwargs)
        if path.endswith('/deployments/actions/redeploy'):
            submissions.append(path)
            owner.doc_deployments[0].pop('timeUpdated', None)
        return result
    owner._request = unavailable_revision
    for _ in range(3):
        with pytest.raises(AidpProvisionPending):
            run(owner, store, 'update', UPDATE)
    assert len(submissions) == 1
    assert owner.job['schedule']['pauseStatus'] == 'PAUSED'
    assert store.load()[0]['manifest']['phase'] == 'refresh_candidate'
    assert len(owner.runs) == 2


def test_failed_native_refresh_and_failed_restore_refresh_preserve_both_errors(monkeypatch):
    owner, store, previous = prepared(monkeypatch)
    request = owner._request
    denied = [True]
    def failed_deployment(method, path, **kwargs):
        token = kwargs.get('retry_scope', '')
        if path.endswith('/deployments/actions/redeploy') and ':restore:' in token and denied[0]:
            raise AidpProvisionError('restore refresh rejected')
        result = request(method, path, **kwargs)
        if path.endswith('/deployments/actions/redeploy'):
            owner.doc_deployments[0]['lifecycleState'] = 'FAILED' if ':candidate:' in token else 'ACTIVE'
        return result
    owner._request = failed_deployment
    result = drive(owner, store)
    assert result['outcome']['status'] == 'restore_failed'
    assert result['failure']['phase'] == 'refresh_candidate'
    assert 'restore_error_code' in result
    assert owner.files == previous['files']
    assert owner.job['schedule']['pauseStatus'] == 'PAUSED'
    before = deepcopy(owner.calls)
    # A submitted restore with an uncertain result must never be silently resubmitted.
    denied[0] = False
    again = drive(owner, store, 'resume')
    assert again['outcome']['status'] == 'restore_failed'
    assert again['failure'] == result['failure']
    assert not any(call[0] == 'POST' for call in owner.calls[len(before):])


def test_definitively_rejected_restore_refresh_can_resume_without_discarding_original_failure(monkeypatch):
    owner, store, previous = prepared(monkeypatch)
    fail_second_candidate_write(owner, previous)
    request = owner._request
    denied = [True]
    def rejection(method, path, **kwargs):
        if path.endswith('/deployments/actions/redeploy') and denied[0]:
            raise AidpRequestError('private upstream rejection', method='POST', path=path, phase='restore',
                                   status_code=403, request_id='redacted-request')
        return request(method, path, **kwargs)
    owner._request = rejection
    failed = drive(owner, store)
    assert failed['outcome']['status'] == 'restore_failed'
    failure = deepcopy(failed['failure'])
    assert failed['manifest']['maintenance']['restore_refresh']['documentary']['rejected'] is True
    denied[0] = False
    restored = drive(owner, store, 'resume')
    assert restored['outcome']['status'] == 'update_failed_restored'
    assert restored['failure'] == failure
    assert restored['manifest']['maintenance']['restore_refresh']['documentary']['attempts'] == 2
    assert_preserved(owner, previous)


def test_candidate_reverted_to_prior_bytes_during_refresh_cannot_be_committed_as_healthy(monkeypatch):
    owner, store, previous = prepared(monkeypatch)
    from ai_data_governance.maintenance import ArtifactMaintenance
    commit = ArtifactMaintenance.commit_schedule
    def reverted(self):
        owner.files[RUNTIME] = previous['files'][RUNTIME]
        return commit(self)
    monkeypatch.setattr(ArtifactMaintenance, 'commit_schedule', reverted)
    result = drive(owner, store)
    assert result['outcome']['status'] == 'update_failed_restored'
    assert result['failure']['phase'] == 'commit_schedule'
    assert_preserved(owner, previous)


@pytest.mark.parametrize('candidate,accepted', [('revision-1', True), ('revision-2', False)])
def test_install_after_recovery_compares_effective_revision_not_failed_candidate(monkeypatch, candidate, accepted):
    owner, store, previous = prepared(monkeypatch)
    fail_second_candidate_write(owner, previous)
    drive(owner, store)
    monkeypatch.setattr(lifecycle, 'candidate_revision', lambda: candidate)
    before = deepcopy(owner.calls)
    if accepted:
        result = run(owner, store, 'install', ROLLBACK)
        assert result['effective_revision'] == 'revision-1'
    else:
        with pytest.raises(AidpProvisionConflict, match='explicit update'):
            run(owner, store, 'install', ROLLBACK)
    assert owner.calls == before


@pytest.mark.parametrize('restore', [False, True])
def test_own_schedule_cutover_lost_ack_reconciles_even_after_legitimate_run_starts(monkeypatch, restore):
    owner, store, previous = prepared(monkeypatch)
    if restore:
        drive(owner, store)
    request = owner._request
    applied = []
    expected_phase = 'restore_schedule' if restore else 'commit_schedule'
    def lost_ack(method, path, **kwargs):
        result = request(method, path, **kwargs)
        active_phase = owner.receipt['manifest']['phase']
        if method == 'PUT' and '/jobs/' in path and active_phase == expected_phase:
            if kwargs['payload']['schedule']['pauseStatus'] == 'UNPAUSED':
                applied.append(path)
                owner.runs['own-cutover-run'] = {'key': 'own-cutover-run', 'state': {'status': 'RUNNING'}}
                owner.business_rows.append({'id': 2, 'value': 'legitimate scheduled output'})
                raise AidpProvisionPending('Schedule cutover acknowledgement lost', 'artifacts')
        return result
    owner._request = lost_ack
    result = drive(owner, store, 'rollback' if restore else 'update', ROLLBACK if restore else UPDATE)
    expected = 'rollback_complete' if restore else 'active'
    assert result['manifest']['status'] == expected
    assert len(applied) == 1
    assert owner.runs['own-cutover-run']['state']['status'] == 'RUNNING'
    assert owner.job['schedule']['pauseStatus'] == 'UNPAUSED'
    assert owner.business_rows[-1]['value'] == 'legitimate scheduled output'


def test_new_writer_between_drain_and_artifact_write_is_not_incorporated_as_drained(monkeypatch):
    owner, store, previous = prepared(monkeypatch)
    list_rows = owner._list
    observations = []
    def racing_writer(path, **kwargs):
        if path.endswith('/jobRuns'):
            observations.append(path)
            if len(observations) == 3:
                owner.runs['raced'] = {'key': 'raced', 'state': {'status': 'RUNNING'}}
        return list_rows(path, **kwargs)
    owner._list = racing_writer
    with pytest.raises(AidpProvisionPending, match='writers'):
        run(owner, store, 'update', UPDATE)
    receipt = store.load()[0]
    snapshot = json.loads(store.get_artifact(receipt['recovery_snapshot']))
    assert 'raced' not in snapshot['barrier_run_keys']
    assert receipt['manifest']['phase'] == 'write_candidate'
    assert owner.files == previous['files']
    assert owner.job['schedule']['pauseStatus'] == 'PAUSED'


@pytest.mark.parametrize('corruption', ['terminal_status', 'resource_key', 'unknown_phase', 'operation_type', 'operation_id'])
def test_corrupt_control_receipt_never_reports_success_or_mutates_native_resources(monkeypatch, corruption):
    owner, store, previous = prepared(monkeypatch)
    receipt, etag = store.load()
    if corruption == 'terminal_status':
        receipt['manifest']['status'] = 'updating'
    elif corruption == 'resource_key':
        receipt['manifest']['resources']['workflow_key'] = '../foreign'
    elif corruption == 'unknown_phase':
        receipt['manifest'].update(phase='unknown_future_phase', status='installing')
    elif corruption == 'operation_type':
        receipt['manifest']['operation']['type'] = 'unsupported'
    else:
        receipt['manifest']['operation']['operation_id'] = 'not-an-operation'
    with store.acquire(receipt['manifest']['operation']['operation_id']):
        store.save(receipt, etag)
    from tests.test_lifecycle import OPERATION
    monkeypatch.setattr(lifecycle, 'candidate_revision', lambda: 'revision-1')
    before = deepcopy(owner.calls)
    with pytest.raises(AidpProvisionConflict):
        run(owner, store, 'resume', OPERATION)
    assert owner.calls == before
    assert owner.files == previous['files']
