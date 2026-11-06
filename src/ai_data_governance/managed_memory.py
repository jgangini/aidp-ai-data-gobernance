"""Own the AIDP memory binding without SQL access or unverified adoption."""
from datetime import datetime, timezone
from email.utils import parsedate_to_datetime
import json
import os
from pathlib import Path
import re
import uuid

from .errors import AidpProvisionConflict, AidpProvisionError, AidpProvisionPending
from .receipts import ReceiptStore
from .runtime_identity import identity_hash


PHASES = {'prepared', 'submitting', 'submitted', 'ready', 'rejected', 'failed'}
OCID = re.compile(r'ocid1\.[a-z0-9]+\.[A-Za-z0-9.-]+')
REJECTIONS = {(400, 'InvalidParameter'), (400, 'MissingParameter'), (400, 'CannotParseRequest'),
    (400, 'LimitExceeded'), (400, 'QuotaExceeded'), (401, 'NotAuthenticated'),
    (403, 'NotAuthorized'), (403, 'NotAllowed'), (404, 'NotAuthorizedOrNotFound'),
    (404, 'NotFound'), (412, 'NoEtagMatch'), (422, 'UnprocessableEntity')}


def _timestamp(value):
    if not isinstance(value, str):
        raise ValueError()
    parsed = datetime.fromisoformat(value)
    if parsed.utcoffset() is None or parsed.timestamp() <= 0:
        raise ValueError()
    return parsed


def _etag(value):
    return isinstance(value, str) and 0 < len(value) <= 1024 and not any(ord(c) < 32 for c in value)


def _verify_submission(record):
    try:
        _timestamp(record['submitted_at'])
        _timestamp(record['accepted_after'])
        if record['time_basis'] not in {'server_date', 'runner_clock'}:
            raise ValueError()
    except (KeyError, ValueError, TypeError):
        raise AidpProvisionConflict('The memory submission chronology is invalid') from None


def _verify_work_evidence(record):
    for name in ('work_request_id', 'compartment_id'):
        if not isinstance(record.get(name), str) or not OCID.fullmatch(record[name]):
            raise AidpProvisionConflict('The memory work request provenance is incomplete')
    if record['phase'] == 'ready' and (
            record.get('work_status') != 'SUCCEEDED' or not _etag(record.get('ready_platform_etag'))):
        raise AidpProvisionConflict('The completed memory evidence is incomplete')


def admin_password():
    path = os.environ.get('DEPLOY_STUDIO_SECRETS')
    if not path:
        raise ValueError('A protected memory ADMIN credential is required')
    body = Path(path).read_bytes()
    if len(body) > 1024 * 1024:
        raise ValueError('The protected secrets file exceeds its bound')
    parsed = json.loads(body)
    if not isinstance(parsed, dict) or not isinstance(parsed.get('inputs'), dict):
        raise ValueError('The protected secrets file has an invalid shape')
    value = parsed['inputs'].get('autonomous_database_admin_password')
    if not isinstance(value, str) or not 12 <= len(value) <= 30 or any(c.isspace() or c == '"' for c in value):
        raise ValueError('A valid protected memory ADMIN credential is required')
    return value


def memory_store(client):
    settings = client.settings
    return ReceiptStore(client.object_storage, settings.objectstorage_namespace,
                        settings.artifacts_bucket_name, settings.aidp_platform_id, 'platform-memory')


def sdk_clients(client):
    config = {**client._oci_config, 'region': client.settings.aidp_region}
    options = {'signer': client.signer, 'retry_strategy': client._oci.retry.NoneRetryStrategy()}
    return (client._oci.ai_data_platform.AiDataPlatformClient(config, **options),
            client._oci.database.DatabaseClient(config, **options))


def verify_database(database, database_id):
    if database.id != database_id or database.lifecycle_state != 'AVAILABLE':
        raise AidpProvisionConflict('The exact memory database must be AVAILABLE')
    if database.db_version != '26ai' or database.db_workload != 'DW':
        raise AidpProvisionConflict('Memory requires the selected 26ai Lakehouse DW profile')


def observed_platform(api, platform_id):
    response = api.get_ai_data_platform(platform_id)
    value = response.data
    if value.id != platform_id or value.lifecycle_state != 'ACTIVE':
        raise AidpProvisionConflict('The exact memory platform must be ACTIVE')
    if value.ai_feature_status not in {'DISABLED', 'ENABLING', 'READY', 'FAILED'}:
        raise AidpProvisionConflict('The platform memory feature state is unsupported')
    return response


def _preflight_receipt(client):
    settings = client.settings
    if not settings.objectstorage_namespace:
        namespace = client.object_storage.get_namespace().data
        if not isinstance(namespace, str) or not re.fullmatch(r'[A-Za-z0-9_-]{1,256}', namespace):
            raise AidpProvisionConflict('The Object Storage namespace could not be verified')
        settings.objectstorage_namespace = namespace
    store = memory_store(client)
    receipt, revision = store.load()
    if receipt is not None and settings.memory_database_mode == 'new':
        if not isinstance(receipt, dict) or receipt.get('deployment_id') != settings.deployment_id:
            raise AidpProvisionConflict('A new database cannot replace an existing memory association')
        identity = receipt.get('identity')
        if not isinstance(identity, dict):
            raise AidpProvisionConflict('The memory receipt identity is invalid')
        settings.memory_database_id = identity.get('database_id', '')
    settings.resource_ownership['memory_database'] = 'owned' if settings.memory_database_mode == 'new' else 'external'
    return store, receipt, revision


def _preflight_admit(manager, platform, etag):
    manager.verify_receipt()
    record = manager.receipt
    if record is None:
        if manager.command != 'install' or platform.ai_feature_status != 'DISABLED' or not _etag(etag):
            raise AidpProvisionConflict('The platform has no compatible owned memory binding')
        admin_password()
        return
    if record['phase'] == 'ready':
        manager.confirm_ready(platform, etag)
        return
    if manager.command not in {'install', 'resume'} or record['phase'] == 'failed':
        raise AidpProvisionConflict('The pending memory association requires its original installation')
    if record['phase'] in {'prepared', 'rejected'}:
        if platform.ai_feature_status != 'DISABLED':
            raise AidpProvisionConflict('The memory binding changed before enablement')
        admin_password()


def preflight_memory(client):
    settings = client.settings
    if settings.aidp_mode == 'new':
        admin_password()
        return
    api, database = sdk_clients(client)
    response = observed_platform(api, settings.aidp_platform_id)
    store, receipt, revision = _preflight_receipt(client)
    manager = ManagedMemory(client, store, settings.governance_operation, receipt, revision, api=api, database=database)
    _preflight_admit(manager, response.data, response.headers.get('etag') or response.headers.get('ETag'))
    if settings.memory_database_mode == 'existing':
        verify_database(database.get_autonomous_database(settings.memory_database_id).data,
                        settings.memory_database_id)


def ensure_memory(client, store, command, authorize):
    with store.acquire('memory-' + str(uuid.uuid5(uuid.NAMESPACE_URL, client.settings.aidp_platform_id))):
        receipt, revision = store.load()
        manager = ManagedMemory(client, store, command, receipt, revision)
        manager.verify_receipt()
        authorize(receipt)
        return manager.reconcile()


class ManagedMemory:
    def __init__(self, client, store, command, receipt, revision, *, api=None, database=None, password=admin_password):
        self.client, self.store, self.command = client, store, command
        self.receipt, self.revision, self.password = receipt, revision, password
        self.api, self.database = (api, database) if api is not None else sdk_clients(client)
        self.identity = {'platform_id': client.settings.aidp_platform_id,
            'database_id': client.settings.memory_database_id,
            'database_ownership': client.settings.resource_ownership['memory_database'],
            'operator_identity': identity_hash(client._oci_config)}

    def verify_receipt(self):
        if self.receipt is None:
            return
        if (not isinstance(self.receipt, dict) or self.receipt.get('schema_version') != 1
                or self.receipt.get('kind') != 'aidp_managed_memory' or self.receipt.get('identity') != self.identity
                or self.receipt.get('phase') not in PHASES):
            raise AidpProvisionConflict('The owned memory identity or receipt is invalid')
        try:
            if str(uuid.UUID(self.receipt['retry_token'])) != self.receipt['retry_token']:
                raise ValueError()
        except (KeyError, ValueError, TypeError, AttributeError):
            raise AidpProvisionConflict('The memory submission identity is invalid') from None
        if not _etag(self.receipt.get('platform_etag')):
            raise AidpProvisionConflict('The initial memory platform revision is invalid')
        if self.receipt['phase'] != 'prepared':
            _verify_submission(self.receipt)
        if self.receipt['phase'] in {'submitted', 'ready', 'failed'}:
            _verify_work_evidence(self.receipt)
        if self.receipt['phase'] == 'rejected' and (
                self.receipt.get('http_status'), self.receipt.get('error_code')) not in REJECTIONS:
            raise AidpProvisionConflict('The memory rejection has no definite provider evidence')

    def save(self):
        self.store.save(self.receipt, self.revision)
        observed, revision = self.store.load()
        if observed != self.receipt:
            raise AidpProvisionConflict('Memory receipt readback changed')
        self.revision = revision

    def platform(self):
        response = observed_platform(self.api, self.identity['platform_id'])
        self.request_lower_bound, self.time_basis = None, 'runner_clock'
        date = response.headers.get('date') or response.headers.get('Date')
        if date:
            try:
                self.request_lower_bound = parsedate_to_datetime(date).astimezone(timezone.utc).isoformat()
                self.time_basis = 'server_date'
            except (ValueError, TypeError, OverflowError):
                pass
        return response.data, response.headers.get('etag') or response.headers.get('ETag')

    def reconcile(self):
        self.verify_receipt()
        if self.command not in {'install', 'resume'} and (not self.receipt or self.receipt['phase'] != 'ready'):
            raise AidpProvisionConflict('Artifact maintenance cannot enable or repair memory')
        verify_database(self.database.get_autonomous_database(self.identity['database_id']).data,
                        self.identity['database_id'])
        platform, etag = self.platform()
        if self.receipt is None:
            self.prepare(platform, etag)
        return self.advance(platform, etag)

    def prepare(self, platform, etag):
        if self.command != 'install' or platform.ai_feature_status != 'DISABLED' or not _etag(etag):
            raise AidpProvisionConflict('Memory cannot adopt an enabled or unowned platform binding')
        self.receipt = {'schema_version': 1, 'kind': 'aidp_managed_memory', 'identity': self.identity,
            'phase': 'prepared', 'platform_etag': etag, 'retry_token': str(uuid.uuid4()),
            'deployment_id': self.client.settings.deployment_id}
        self.save()

    def advance(self, platform, etag):
        phase = self.receipt['phase']
        if phase == 'ready':
            return self.confirm_ready(platform, etag)
        if phase == 'failed':
            raise AidpProvisionError('The recorded memory enablement failed; protected reconciliation is required')
        if phase == 'submitting':
            raise AidpProvisionPending('Memory submission acknowledgement is uncertain; do not resubmit', 'memory')
        if phase == 'rejected':
            self.prepare_retry(platform, etag)
        if self.receipt['phase'] == 'prepared':
            self.submit(platform, etag)
        return self.observe()

    def prepare_retry(self, platform, etag):
        if self.command not in {'install', 'resume'} or platform.ai_feature_status != 'DISABLED' or not _etag(etag):
            raise AidpProvisionConflict('A rejected memory request cannot change the observed binding')
        rejected = self.receipt.setdefault('rejections', [])
        if len(rejected) >= 100:
            raise AidpProvisionConflict('Memory rejection history requires review')
        rejected.append({'retry_token': self.receipt['retry_token'], 'http_status': self.receipt['http_status']})
        self.receipt.update(phase='prepared', platform_etag=etag, retry_token=str(uuid.uuid4()))
        self.save()

    def submit(self, platform, etag):
        if platform.ai_feature_status != 'DISABLED' or not etag or etag != self.receipt['platform_etag']:
            raise AidpProvisionConflict('Platform revision changed before memory enablement')
        details = self.client._oci.ai_data_platform.models.EnableAiFeatureDetails(
            vector_db_id=self.identity['database_id'], vector_db_admin_cred=self.password())
        submitted = datetime.now(timezone.utc).isoformat()
        self.receipt.update(phase='submitting', submitted_at=submitted,
            accepted_after=self.request_lower_bound or submitted, time_basis=self.time_basis)
        self.save()
        self.store.heartbeat()
        try:
            response = self.api.enable_ai_feature(self.identity['platform_id'], details,
                if_match=etag, opc_retry_token=self.receipt['retry_token'],
                retry_strategy=self.client._oci.retry.NoneRetryStrategy())
        except Exception as error:
            self.submission_error(error)
        work = response.headers.get('opc-work-request-id') or response.headers.get('OPC-Work-Request-Id')
        if not isinstance(work, str) or not OCID.fullmatch(work):
            raise AidpProvisionPending('Memory acknowledgement has no verifiable work request', 'memory')
        self.receipt.update(phase='submitted', work_request_id=work, compartment_id=platform.compartment_id)
        self.save()

    def submission_error(self, error):
        status = getattr(error, 'status', None)
        code = getattr(error, 'code', None)
        if isinstance(error, self.client._oci.exceptions.ServiceError) and (status, code) in REJECTIONS:
            self.receipt.update(phase='rejected', http_status=status, error_code=code)
            self.save()
            raise AidpProvisionError('Memory enablement was rejected; inspect permissions and protected credentials') from None
        raise AidpProvisionPending('Memory enablement outcome is uncertain; no automatic resend', 'memory') from None

    def observe(self):
        key = self.receipt.get('work_request_id')
        if not isinstance(key, str) or not OCID.fullmatch(key):
            raise AidpProvisionConflict('The memory work request identity is invalid')
        work = self.api.get_work_request(key).data
        self.verify_work_request(work, key)
        if work.status in {'FAILED', 'CANCELED', 'NEEDS_ATTENTION'}:
            self.receipt.update(phase='failed', work_status=work.status)
            self.save()
            raise AidpProvisionError('Memory enablement did not complete successfully')
        if work.status != 'SUCCEEDED':
            if work.status not in {'ACCEPTED', 'IN_PROGRESS', 'WAITING', 'CANCELING'}:
                raise AidpProvisionConflict('The memory work request status is unsupported')
            raise AidpProvisionPending('The recorded memory enablement is still running', 'memory')
        platform, etag = self.platform()
        if platform.ai_feature_status == 'FAILED':
            raise AidpProvisionError('The platform reports failed memory enablement')
        if platform.compartment_id != self.receipt['compartment_id']:
            raise AidpProvisionConflict('The memory platform compartment changed during enablement')
        if platform.ai_feature_status != 'READY' or not _etag(etag):
            raise AidpProvisionPending('Memory enablement completed but READY is not observed', 'memory')
        self.receipt.update(phase='ready', work_status='SUCCEEDED', ready_platform_etag=etag)
        self.save()
        return self.result()

    def verify_work_request(self, work, key):
        from .native_times import at_or_after
        from .client import AidpClient
        if (work.id != key or work.operation_type != 'ENABLE_AI_FEATURES'
                or work.compartment_id != self.receipt['compartment_id']
                or not any(r.identifier == self.identity['platform_id']
                           and getattr(r, 'action_type', None) not in {'DELETED', 'FAILED', 'UNKNOWN_ENUM_VALUE'}
                           for r in (work.resources or []))
                or not at_or_after(AidpClient._timestamp(work.time_accepted),
                                   AidpClient._timestamp(self.receipt['accepted_after']))):
            raise AidpProvisionConflict('Memory work request does not match the submitted platform operation')

    def confirm_ready(self, platform, etag):
        if (platform.ai_feature_status != 'READY' or not _etag(etag)
                or platform.compartment_id != self.receipt['compartment_id']
                or etag != self.receipt.get('ready_platform_etag') or self.receipt.get('work_status') != 'SUCCEEDED'):
            raise AidpProvisionConflict('The platform revision changed; its memory association needs reconciliation')
        return self.result()

    def result(self):
        return {'autonomous_database_id': self.identity['database_id'], 'memory_status': 'READY'}
