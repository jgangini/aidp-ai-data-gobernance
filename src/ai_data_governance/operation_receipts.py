"""Admission and immutable identities of installation and maintenance operations."""
from copy import deepcopy
from uuid import UUID
from .client import MODULE_MANIFEST_PATH
from .constants import RUNTIME_FAMILY
from .errors import AidpProvisionConflict


def verify_receipt(receipt, identity):
    if receipt.get('schema_version') != 1 or receipt.get('identity') != identity:
        raise AidpProvisionConflict('Receipt ownership or selected administrator changed')
    if receipt['manifest'].get('runtime_family') != RUNTIME_FAMILY:
        raise AidpProvisionConflict('Unsupported installation family; no adoption was performed')
    _verify_native_keys(receipt['manifest'])
    _verify_terminal_status(receipt['manifest'])
    _verify_operation(receipt['manifest']['operation'])


def _verify_operation(operation):
    if operation.get('type') not in {'install', 'update', 'redeploy', 'rollback'}:
        raise AidpProvisionConflict('Unsupported recorded operation type')
    try:
        canonical = str(UUID(operation.get('operation_id')))
    except (ValueError, TypeError, AttributeError):
        raise AidpProvisionConflict('The recorded operation identity is invalid') from None
    if canonical != operation['operation_id']:
        raise AidpProvisionConflict('The recorded operation identity is not canonical')


def _verify_native_keys(manifest):
    keys = ('agent_key', 'documentation_agent_key', 'workflow_key', 'cluster_key', 'agent_compute_key')
    resources = manifest.get('resources', {})
    for name in keys:
        if name in resources:
            try:
                canonical = str(UUID(resources[name]))
            except (ValueError, TypeError, AttributeError):
                raise AidpProvisionConflict('The recorded native resource identity is invalid') from None
            if canonical != resources[name]:
                raise AidpProvisionConflict('The recorded native resource identity is not canonical')


def _verify_terminal_status(manifest):
    terminal = {'active': {'active'}, 'restored': {'rollback_complete', 'update_failed_restored'}}
    allowed = terminal.get(manifest.get('phase'))
    if allowed is not None and manifest.get('status') not in allowed:
        raise AidpProvisionConflict('The terminal operation phase and status disagree')


def verify_resume(manifest, request):
    operation = manifest['operation']
    if operation['operation_id'] != request['id'] or manifest.get('candidate_revision') != request['revision']:
        raise AidpProvisionConflict('Resume requires the original operation and candidate revision')
    if request['command'] not in {operation['type'], 'resume'}:
        raise AidpProvisionConflict('Resume cannot change the original operation type')
    if manifest.get('candidate_source', {}) != request['source']:
        raise AidpProvisionConflict('Resume requires the original immutable package source')


def new_install(client, workspace, identity, request):
    if request['command'] != 'install':
        raise AidpProvisionConflict('No owned installation exists for this operation')
    if client._workspace_json(workspace, MODULE_MANIFEST_PATH, 'Unowned Governance control receipt') is not None:
        raise AidpProvisionConflict('A workspace Governance installation has no matching product receipt; transition is required')
    manifest = client._new_module_manifest(request['id'], 'install')
    manifest.update(candidate_revision=request['revision'], candidate_source=request['source'])
    return {'schema_version': 1, 'identity': identity, 'manifest': manifest,
        'deployment_id': getattr(client.settings, 'deployment_id', None),
        'resource_ownership': deepcopy(getattr(client.settings, 'resource_ownership', {}))}


def begin_update(receipt, request):
    reference = receipt.get('recovery_snapshot')
    history = receipt.setdefault('snapshot_history', [])
    if len(history) >= 100:
        raise AidpProvisionConflict('Snapshot history needs an explicit retention review before another update')
    if reference:
        history.append({'snapshot': reference, 'operation_id': receipt['manifest']['operation']['operation_id'],
            'candidate_revision': receipt['manifest']['candidate_revision'], 'failure': deepcopy(receipt.get('failure')),
            'outcome': deepcopy(receipt.get('outcome'))})
    previous = deepcopy(receipt.get('effective_manifest', receipt['manifest']))
    receipt['previous'] = previous
    receipt['previous_revision'] = previous.get('candidate_revision')
    receipt['manifest'].update(phase='prepare_artifacts', status='updating', candidate_revision=request['revision'],
        candidate_source=request['source'], maintenance={},
        operation={'operation_id': request['id'], 'type': request['command'], 'phase': 'started'})
    receipt.pop('outcome', None)
    receipt.pop('failure', None)
    receipt.pop('recovery_snapshot', None)
    receipt['manifest'].pop('error_code', None)


def begin_rollback(receipt, request):
    if not receipt.get('recovery_snapshot') or not receipt.get('previous'):
        raise AidpProvisionConflict('No verified prior artifact snapshot exists for rollback')
    receipt['manifest'].update(phase='restore_quiesce', status='rolling_back', candidate_revision=request['revision'],
        candidate_source=request['source'],
        maintenance={**receipt['manifest'].get('maintenance', {}), 'restore_refresh': {}, 'restore_cutover_started': False},
        operation={'operation_id': request['id'], 'type': 'rollback', 'phase': 'started'})
    receipt.pop('outcome', None)


def _terminal_admission(receipt, request):
    manifest = receipt['manifest']
    if request['command'] in {'install', 'resume'}:
        if request['command'] == 'resume':
            verify_resume(manifest, request)
        elif receipt.get('effective_manifest', manifest).get('candidate_revision') != request['revision']:
            raise AidpProvisionConflict('An installed candidate requires explicit update')
        return False
    if request['command'] == 'rollback':
        begin_rollback(receipt, request)
    else:
        if manifest['phase'] != 'active' and not receipt.get('effective_manifest'):
            raise AidpProvisionConflict('A failed maintenance operation must be recovered before another update')
        begin_update(receipt, request)
    return True


def admit(receipt, identity, request):
    verify_receipt(receipt, identity)
    manifest = receipt['manifest']
    if manifest['operation']['operation_id'] == request['id']:
        verify_resume(manifest, request)
        return manifest['phase'] not in {'active', 'restored'}
    if manifest['phase'] not in {'active', 'restored'}:
        raise AidpProvisionConflict('Resume requires the original operation and candidate revision')
    return _terminal_admission(receipt, request)
