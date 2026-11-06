"""Managed memory is accepted only from a durable, verified control-plane operation."""

from contextlib import contextmanager
from copy import deepcopy
from datetime import datetime, timedelta, timezone
from email.utils import format_datetime
import json
from types import SimpleNamespace
from unittest.mock import Mock

import oci
import pytest

from ai_data_governance import managed_memory as memory
from ai_data_governance.errors import AidpProvisionConflict, AidpProvisionError, AidpProvisionPending


PLATFORM = 'ocid1.aidataplatform.oc1.us-chicago-1.test'
DATABASE = 'ocid1.autonomousdatabase.oc1.us-chicago-1.test'
WORK = 'ocid1.aidataplatformworkrequest.oc1.us-chicago-1.test'
COMPARTMENT = 'ocid1.compartment.oc1..test'
PASSWORD = 'TestOnlyMemory26!'


class Store:
    def __init__(self, receipt=None):
        self.receipt = deepcopy(receipt)
        self.revision = '1' if receipt is not None else None
        self.saves = []
        self.held = False
        self.heartbeats = 0

    def load(self):
        return deepcopy(self.receipt), self.revision

    def save(self, receipt, revision):
        if not self.held or revision != self.revision:
            raise AidpProvisionConflict('Receipt ownership or revision changed')
        self.receipt = deepcopy(receipt)
        self.saves.append(deepcopy(receipt))
        self.revision = str(int(self.revision or '0') + 1)

    def heartbeat(self):
        if not self.held:
            raise AidpProvisionConflict('Lease is not held')
        self.heartbeats += 1

    @contextmanager
    def acquire(self, operation):
        assert not self.held
        self.held = True
        try:
            yield self
        finally:
            self.held = False


class Api:
    def __init__(self, store):
        self.store = store
        self.platform_id = PLATFORM
        self.lifecycle = 'ACTIVE'
        self.compartment = COMPARTMENT
        self.feature = 'DISABLED'
        self.etag = 'platform-before'
        self.work_status = 'IN_PROGRESS'
        self.work_changes = {}
        self.ack = WORK
        self.post_error = None
        self.date = None
        self.posts = []
        self.work_reads = []

    def get_ai_data_platform(self, platform):
        assert platform == PLATFORM
        headers = {'etag': self.etag} if self.etag else {}
        if self.date:
            headers['Date'] = self.date
        return SimpleNamespace(data=SimpleNamespace(id=self.platform_id, lifecycle_state=self.lifecycle,
            ai_feature_status=self.feature, compartment_id=self.compartment),
            headers=headers)

    def enable_ai_feature(self, platform, details, **kwargs):
        assert self.store.held and self.store.receipt['phase'] == 'submitting'
        assert self.store.receipt['submitted_at']
        assert self.store.heartbeats > 0
        self.posts.append((platform, details, kwargs))
        if self.post_error is not None:
            raise self.post_error
        return SimpleNamespace(headers={'opc-work-request-id': self.ack} if self.ack else {})

    def get_work_request(self, key):
        self.work_reads.append(key)
        accepted = datetime.fromisoformat(self.store.receipt['submitted_at']) + timedelta(milliseconds=1)
        values = {'id': WORK, 'operation_type': 'ENABLE_AI_FEATURES', 'compartment_id': COMPARTMENT,
            'resources': [SimpleNamespace(identifier=PLATFORM)], 'time_accepted': accepted,
            'status': self.work_status}
        values.update(self.work_changes)
        return SimpleNamespace(data=SimpleNamespace(**values))


def harness(mode='new', receipt=None):
    store = Store(receipt)
    api = Api(store)
    database = Mock()
    database.get_autonomous_database.return_value.data = SimpleNamespace(id=DATABASE,
        lifecycle_state='AVAILABLE', db_version='26ai', db_workload='DW')
    owner = SimpleNamespace(_oci=oci, _oci_config={'tenancy': 'test-tenancy', 'user': 'test-operator',
        'fingerprint': 'test-fingerprint'}, signer=object(),
        settings=SimpleNamespace(aidp_platform_id=PLATFORM, memory_database_id=DATABASE,
            memory_database_mode=mode, aidp_region='us-chicago-1', deployment_id='test-deployment',
            resource_ownership={'memory_database': 'owned' if mode == 'new' else 'external'}))
    return owner, store, api, database


def manager(parts, command='install', password=None):
    owner, store, api, database = parts
    receipt, revision = store.load()
    return memory.ManagedMemory(owner, store, command, receipt, revision,
        api=api, database=database, password=password or (lambda: PASSWORD))


def reconcile(parts, command='install', password=None):
    with parts[1].acquire('test-operation'):
        return manager(parts, command, password).reconcile()


def submitted(parts):
    with pytest.raises(AidpProvisionPending):
        reconcile(parts)
    assert parts[1].receipt['phase'] == 'submitted'


def ready(parts):
    submitted(parts)
    parts[2].work_status = 'SUCCEEDED'
    parts[2].feature = 'READY'
    parts[2].etag = 'platform-ready'
    return reconcile(parts, 'resume')


@pytest.mark.parametrize('mode', ['new', 'existing'])
def test_submission_is_journaled_before_conditional_post_and_resume_never_posts_again(mode):
    parts = harness(mode)
    owner, store, api, database = parts
    submitted(parts)
    assert [row['phase'] for row in store.saves] == ['prepared', 'submitting', 'submitted']
    assert store.receipt['identity']['database_ownership'] == ('owned' if mode == 'new' else 'external')
    platform, details, options = api.posts[0]
    assert platform == PLATFORM and details.vector_db_id == DATABASE
    assert details.vector_db_admin_cred == PASSWORD
    assert options['if_match'] == 'platform-before'
    assert options['opc_retry_token'] == store.receipt['retry_token']
    assert isinstance(options['retry_strategy'], oci.retry.NoneRetryStrategy)
    password = Mock(side_effect=AssertionError('Resume must not read a credential'))
    with pytest.raises(AidpProvisionPending):
        reconcile(parts, 'resume', password)
    api.work_status, api.feature, api.etag = 'SUCCEEDED', 'READY', 'platform-ready'
    assert reconcile(parts, 'resume', password) == {'autonomous_database_id': DATABASE, 'memory_status': 'READY'}
    assert store.receipt['phase'] == 'ready' and store.receipt['ready_platform_etag'] == 'platform-ready'
    assert len(api.posts) == 1
    database.get_autonomous_database.assert_called_with(DATABASE)
    assert PASSWORD not in json.dumps(store.saves)
    password.assert_not_called()


@pytest.mark.parametrize('field,value', [('id', 'foreign-database'), ('lifecycle_state', 'STOPPED'),
    ('db_version', '23ai'), ('db_workload', 'OLTP')])
def test_wrong_database_identity_readiness_or_profile_fails_before_any_submission(field, value):
    parts = harness()
    setattr(parts[3].get_autonomous_database.return_value.data, field, value)
    with pytest.raises(AidpProvisionConflict):
        reconcile(parts)
    assert parts[2].posts == [] and parts[1].saves == []


@pytest.mark.parametrize('field,value', [('platform_id', 'foreign-platform'), ('lifecycle', 'DELETING'),
    ('feature', 'UNKNOWN'), ('feature', 'READY'), ('etag', None)])
def test_unowned_ready_or_changed_platform_is_never_adopted(field, value):
    parts = harness()
    setattr(parts[2], field, value)
    with pytest.raises(AidpProvisionConflict):
        reconcile(parts)
    assert parts[2].posts == [] and parts[1].saves == []


@pytest.mark.parametrize('field,value', [('platform_id', 'foreign-platform'), ('database_id', 'foreign-database'),
    ('operator_identity', 'foreign-operator'), ('database_ownership', 'external')])
def test_receipt_identity_drift_blocks_before_mutations(field, value):
    parts = harness()
    submitted(parts)
    parts[1].receipt['identity'][field] = value
    posts, saved = len(parts[2].posts), len(parts[1].saves)
    with pytest.raises(AidpProvisionConflict):
        reconcile(parts, 'resume')
    assert len(parts[2].posts) == posts and len(parts[1].saves) == saved


def test_stale_receipt_revision_fails_cas_before_native_post():
    parts = harness()
    stale = manager(parts)
    parts[1].revision = '2'
    with parts[1].acquire('test-operation'), pytest.raises(AidpProvisionConflict):
        stale.reconcile()
    assert parts[2].posts == []


def test_receipt_readback_drift_after_save_blocks_native_submission(monkeypatch):
    parts = harness()
    original_load = parts[1].load

    def changed_readback():
        receipt, revision = original_load()
        if receipt is not None:
            receipt['deployment_id'] = 'different-deployment'
        return receipt, revision

    monkeypatch.setattr(parts[1], 'load', changed_readback)
    with pytest.raises(AidpProvisionConflict):
        reconcile(parts)
    assert parts[2].posts == []


@pytest.mark.parametrize('failure', ['lost-ack', 'missing-work-id', 'conflict-409', 'unknown-403'])
def test_unknown_submission_acknowledgement_is_pending_and_never_resent(failure):
    parts = harness()
    if failure == 'lost-ack':
        parts[2].post_error = TimeoutError(PASSWORD)
    elif failure == 'missing-work-id':
        parts[2].ack = None
    elif failure == 'conflict-409':
        parts[2].post_error = oci.exceptions.ServiceError(409, 'Conflict', {}, PASSWORD)
    else:
        parts[2].post_error = oci.exceptions.ServiceError(403, 'UnknownProviderCode', {}, PASSWORD)
    with pytest.raises(AidpProvisionPending) as caught:
        reconcile(parts)
    assert PASSWORD not in str(caught.value)
    assert parts[1].receipt['phase'] == 'submitting'
    with pytest.raises(AidpProvisionPending):
        reconcile(parts, 'resume')
    assert len(parts[2].posts) == 1 and parts[2].work_reads == []
    assert PASSWORD not in json.dumps(parts[1].saves)


def test_definite_403_is_durable_and_retries_only_when_explicitly_resumed():
    parts = harness()
    parts[2].post_error = oci.exceptions.ServiceError(403, 'NotAuthorized', {}, PASSWORD)
    with pytest.raises(AidpProvisionError) as caught:
        reconcile(parts)
    assert PASSWORD not in str(caught.value)
    rejected = deepcopy(parts[1].receipt)
    assert rejected['phase'] == 'rejected' and rejected['http_status'] == 403
    assert len(parts[2].posts) == 1
    parts[2].post_error = None
    with pytest.raises(AidpProvisionPending):
        reconcile(parts, 'resume')
    assert len(parts[2].posts) == 2
    assert parts[1].receipt['retry_token'] != rejected['retry_token']
    assert parts[1].receipt['rejections'] == [{'retry_token': rejected['retry_token'], 'http_status': 403}]
    assert PASSWORD not in json.dumps(parts[1].saves)


@pytest.mark.parametrize('field,value', [('id', 'foreign-work'), ('operation_type', 'DELETE_PLATFORM'),
    ('compartment_id', 'foreign-compartment'), ('resources', [SimpleNamespace(identifier='foreign-platform')]),
    ('time_accepted', datetime(2020, 1, 1, tzinfo=timezone.utc)), ('time_accepted', None), ('status', 'UNKNOWN')])
def test_unrelated_work_request_never_proves_memory_ready(field, value):
    parts = harness()
    submitted(parts)
    parts[2].work_changes[field] = value
    with pytest.raises(AidpProvisionConflict):
        reconcile(parts, 'resume')
    assert parts[1].receipt['phase'] == 'submitted'
    assert len(parts[2].posts) == 1


@pytest.mark.parametrize('status', ['FAILED', 'CANCELED', 'NEEDS_ATTENTION'])
def test_terminal_work_request_failure_preserves_identity_and_prevents_resubmission(status):
    parts = harness()
    submitted(parts)
    request = parts[1].receipt['work_request_id']
    parts[2].work_status = status
    with pytest.raises(AidpProvisionError):
        reconcile(parts, 'resume')
    assert parts[1].receipt['phase'] == 'failed'
    assert parts[1].receipt['work_status'] == status
    assert parts[1].receipt['work_request_id'] == request
    with pytest.raises(AidpProvisionError):
        reconcile(parts, 'resume')
    assert len(parts[2].posts) == 1


def test_succeeded_work_request_is_not_ready_until_platform_readback_is_ready():
    parts = harness()
    submitted(parts)
    parts[2].work_status = 'SUCCEEDED'
    with pytest.raises(AidpProvisionPending):
        reconcile(parts, 'resume')
    assert parts[1].receipt['phase'] == 'submitted'
    assert len(parts[2].posts) == 1


@pytest.mark.parametrize('etag', [1, 'header\ninjection', 'x' * 1025], ids=['not-string', 'control-character', 'oversized'])
def test_successful_work_request_cannot_accept_an_invalid_ready_revision_header(etag):
    parts = harness()
    submitted(parts)
    parts[2].work_status, parts[2].feature, parts[2].etag = 'SUCCEEDED', 'READY', etag
    with pytest.raises((AidpProvisionConflict, AidpProvisionPending)):
        reconcile(parts, 'resume')
    assert parts[1].receipt['phase'] == 'submitted'
    assert len(parts[2].posts) == 1


@pytest.mark.parametrize('stage', ['completion', 'maintenance'])
def test_platform_compartment_drift_cannot_reuse_old_work_request_provenance(stage):
    parts = harness()
    if stage == 'maintenance':
        ready(parts)
    else:
        submitted(parts)
        parts[2].work_status, parts[2].feature, parts[2].etag = 'SUCCEEDED', 'READY', 'platform-ready'
    parts[2].compartment = 'ocid1.compartment.oc1..foreign'
    with pytest.raises(AidpProvisionConflict):
        reconcile(parts, 'resume' if stage == 'completion' else 'rollback')
    assert len(parts[2].posts) == 1


@pytest.mark.parametrize('command', ['update', 'redeploy', 'rollback'])
def test_artifact_maintenance_verifies_memory_without_enabling_or_loading_password(command):
    parts = harness()
    ready(parts)
    password = Mock(side_effect=AssertionError('Maintenance cannot access a database ADMIN credential'))
    assert reconcile(parts, command, password)['memory_status'] == 'READY'
    assert len(parts[2].posts) == 1
    password.assert_not_called()
    parts[2].etag = 'platform-external-change'
    with pytest.raises(AidpProvisionConflict):
        reconcile(parts, command, password)
    assert len(parts[2].posts) == 1


@pytest.mark.parametrize('field,value', [
    ('work_request_id', None), ('work_request_id', 'not-an-ocid'),
    ('submitted_at', None), ('submitted_at', 'invalid-timestamp'),
    ('submitted_at', '2026-11-05T00:00:00'),
    ('compartment_id', 'not-an-ocid'), ('ready_platform_etag', None),
    ('work_status', 'IN_PROGRESS'),
])
def test_ready_receipt_requires_complete_successful_native_operation_evidence(field, value):
    parts = harness()
    ready(parts)
    parts[1].receipt[field] = value
    with pytest.raises(AidpProvisionConflict):
        reconcile(parts, 'rollback')
    assert len(parts[2].posts) == 1


def test_ready_phase_cannot_be_fabricated_from_prepared_receipt():
    parts = harness()
    submitted(parts)
    parts[1].receipt['phase'] = 'ready'
    parts[1].receipt['work_status'] = 'SUCCEEDED'
    parts[1].receipt['ready_platform_etag'] = 'platform-ready'
    del parts[1].receipt['work_request_id']
    parts[2].feature, parts[2].etag = 'READY', 'platform-ready'
    with pytest.raises(AidpProvisionConflict):
        reconcile(parts, 'resume')
    assert len(parts[2].posts) == 1


@pytest.mark.parametrize('command', ['update', 'redeploy', 'rollback'])
def test_maintenance_without_owned_ready_memory_cannot_bootstrap_it(command):
    parts = harness()
    with pytest.raises(AidpProvisionConflict):
        reconcile(parts, command)
    assert parts[2].posts == [] and parts[1].saves == []


def test_default_ensure_authorizes_only_inside_the_acquired_lease_before_reconcile(monkeypatch):
    owner, store, _, _ = harness()
    order = []

    class Manager:
        def __init__(self, client, received_store, command, receipt, revision):
            assert client is owner and received_store is store and store.held

        def verify_receipt(self):
            assert store.held
            order.append('verify')

        def reconcile(self):
            assert store.held and order == ['verify', 'authorize']
            order.append('reconcile')
            return {'memory_status': 'READY'}

    def authorize(receipt):
        assert store.held and receipt is None
        order.append('authorize')

    monkeypatch.setattr(memory, 'ManagedMemory', Manager)
    assert memory.ensure_memory(owner, store, 'install', authorize) == {'memory_status': 'READY'}
    assert order == ['verify', 'authorize', 'reconcile'] and not store.held


def test_authorization_failure_under_lease_never_enters_reconciliation(monkeypatch):
    owner, store, _, _ = harness()
    instance = Mock()
    monkeypatch.setattr(memory, 'ManagedMemory', Mock(return_value=instance))

    def authorize(receipt):
        assert store.held
        raise AidpProvisionConflict('Administrator was revoked')

    with pytest.raises(AidpProvisionConflict):
        memory.ensure_memory(owner, store, 'resume', authorize)
    instance.reconcile.assert_not_called()
    assert not store.held


def test_protected_password_loader_uses_only_secret_inputs_and_never_exports_the_secret(tmp_path, monkeypatch):
    path = tmp_path / 'secrets.json'
    path.write_text(json.dumps({'inputs': {'autonomous_database_admin_password': PASSWORD}}))
    monkeypatch.setenv('DEPLOY_STUDIO_SECRETS', str(path))
    assert memory.admin_password() == PASSWORD
    path.write_text(json.dumps({'autonomous_database_admin_password': PASSWORD}))
    with pytest.raises(ValueError) as caught:
        memory.admin_password()
    assert PASSWORD not in str(caught.value)


def test_sdk_clients_disable_retries_and_keep_the_existing_operator_signer(monkeypatch):
    owner, _, _, _ = harness()
    api_factory, db_factory = Mock(), Mock()
    monkeypatch.setattr(oci.ai_data_platform, 'AiDataPlatformClient', api_factory)
    monkeypatch.setattr(oci.database, 'DatabaseClient', db_factory)
    memory.sdk_clients(owner)
    for factory in (api_factory, db_factory):
        assert factory.call_args.kwargs['signer'] is owner.signer
        assert isinstance(factory.call_args.kwargs['retry_strategy'], oci.retry.NoneRetryStrategy)
        assert factory.call_args.args[0]['user'] == 'test-operator'
        assert factory.call_args.args[0]['region'] == 'us-chicago-1'


def preflight_bindings(parts, monkeypatch):
    owner, store, api, database = parts
    owner.settings.aidp_mode = 'existing'
    owner.settings.governance_operation = 'install'
    owner.settings.objectstorage_namespace = 'namespace'
    monkeypatch.setattr(memory, 'sdk_clients', lambda _: (api, database))
    monkeypatch.setattr(memory, 'memory_store', lambda _: store)


@pytest.mark.parametrize('feature', ['READY', 'ENABLING'])
def test_preflight_rejects_foreign_binding_before_credentials_or_database_creation(feature, monkeypatch):
    parts = harness()
    preflight_bindings(parts, monkeypatch)
    parts[2].feature = feature
    password = Mock(side_effect=AssertionError('Foreign platform must fail before credential loading'))
    monkeypatch.setattr(memory, 'admin_password', password)
    with pytest.raises(AidpProvisionConflict):
        memory.preflight_memory(parts[0])
    parts[3].get_autonomous_database.assert_not_called()
    password.assert_not_called()
    assert parts[2].posts == [] and parts[1].saves == []


def test_preflight_owned_ready_external_database_requires_no_admin_credential(monkeypatch):
    parts = harness('existing')
    ready(parts)
    preflight_bindings(parts, monkeypatch)
    password = Mock(side_effect=AssertionError('Owned READY memory does not need an ADMIN credential'))
    monkeypatch.setattr(memory, 'admin_password', password)
    before = deepcopy(parts[1].receipt)
    memory.preflight_memory(parts[0])
    password.assert_not_called()
    assert parts[1].receipt == before and len(parts[2].posts) == 1


def test_preflight_new_database_cannot_replace_another_deployments_memory(monkeypatch):
    parts = harness()
    ready(parts)
    preflight_bindings(parts, monkeypatch)
    parts[0].settings.deployment_id = 'different-deployment'
    parts[3].get_autonomous_database.reset_mock()
    password = Mock(side_effect=AssertionError('Mismatched ownership must fail first'))
    monkeypatch.setattr(memory, 'admin_password', password)
    with pytest.raises(AidpProvisionConflict):
        memory.preflight_memory(parts[0])
    password.assert_not_called()
    parts[3].get_autonomous_database.assert_not_called()
    assert len(parts[2].posts) == 1


def test_server_date_lower_bound_accepts_valid_work_despite_runner_clock_skew():
    parts = harness()
    server = datetime.now(timezone.utc).replace(microsecond=0) - timedelta(seconds=3)
    parts[2].date = format_datetime(server, usegmt=True)
    parts[2].work_changes['time_accepted'] = server + timedelta(milliseconds=100)
    submitted(parts)
    receipt = parts[1].receipt
    assert receipt['time_basis'] == 'server_date'
    assert datetime.fromisoformat(receipt['accepted_after']) == server
    assert parts[2].work_changes['time_accepted'] < datetime.fromisoformat(receipt['submitted_at'])
    parts[2].work_status, parts[2].feature, parts[2].etag = 'SUCCEEDED', 'READY', 'platform-ready'
    assert reconcile(parts, 'resume')['memory_status'] == 'READY'
    assert len(parts[2].posts) == 1
