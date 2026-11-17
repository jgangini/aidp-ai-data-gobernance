"""Deploy Studio entrypoints; credentials stay in the authorized runner environment."""
import argparse
import json
import os
from pathlib import Path
import re
from types import SimpleNamespace
import uuid
from .errors import AidpProvisionPending
from .errors import AidpProvisionConflict
from .managed_memory import ensure_memory, memory_store, preflight_memory


OPERATIONS = frozenset({'install', 'resume', 'update', 'redeploy', 'rollback'})


def _applied_bindings(context, values):
    outputs = context.get('terraform_outputs', {})
    for key in ('aidp_mode', 'admin_user_ocid', 'identity_domain_id', 'model_id', 'artifacts_bucket_name', 'artifacts_mode',
                'autonomous_database_mode'):
        if outputs.get(key) != values[key]:
            raise ValueError('Terraform outputs changed the selected platform or administrator binding')
    ownership = 'owned' if values['aidp_mode'] == 'new' else 'external'
    if outputs.get('resource_ownership', {}).get('platform') != ownership:
        raise ValueError('Platform ownership must match the selected mode')
    if values['aidp_mode'] == 'existing' and (
            outputs.get('ai_data_platform_ocid') != values['existing_ai_data_platform_ocid']
            or outputs.get('workspace_key') != values['existing_workspace_key']):
        raise ValueError('Terraform outputs changed the exact external platform or workspace')
    database_ownership = 'owned' if values['autonomous_database_mode'] == 'new' else 'external'
    if outputs.get('resource_ownership', {}).get('memory_database') != database_ownership:
        raise ValueError('Memory database ownership must match the selected mode')
    database = outputs.get('autonomous_database_id', '')
    if not isinstance(database, str) or not database.startswith('ocid1.autonomousdatabase.'):
        raise ValueError('Terraform must return the exact memory database identity')
    if (values['autonomous_database_mode'] == 'existing'
            and database != values['existing_autonomous_database_ocid']):
        raise ValueError('Terraform changed the selected external memory database')
    return {**values, **outputs}


def _validate_selection(values):
    mode = values['aidp_mode']
    if mode not in {'new', 'existing'}:
        raise ValueError('Invalid platform mode')
    if values.get('governance_operation', 'install') not in OPERATIONS:
        raise ValueError('Invalid Governance operation')
    if values['autonomous_database_mode'] not in {'new', 'existing'}:
        raise ValueError('Invalid memory database mode')
    if values['autonomous_database_mode'] == 'existing':
        if not values.get('existing_autonomous_database_ocid', '').startswith('ocid1.autonomousdatabase.'):
            raise ValueError('An exact external memory database OCID is required')
    elif (values.get('autonomous_database_version') != '26ai'
          or values.get('autonomous_database_workload') != 'DW'):
        raise ValueError('Memory requires the 26ai Lakehouse DW profile')
    domain, admin = values['identity_domain_id'], values['admin_user_ocid']
    if not domain.startswith('ocid1.domain.') or not admin.startswith('ocid1.user.'):
        raise ValueError('Stable domain and user OCIDs are required')


def _native_identity(values):
    platform = values.get('ai_data_platform_ocid') or values.get('existing_ai_data_platform_ocid', '')
    workspace = values.get('workspace_key') or values.get('existing_workspace_key', '')
    if values['aidp_mode'] == 'existing' and (
            not platform.startswith('ocid1.aidataplatform.') or str(uuid.UUID(workspace)) != workspace):
        raise ValueError('An existing platform requires exact platform and workspace identities')
    return platform, workspace


def _compartment_id(context, applied):
    compartment = context['compartment']
    if applied:
        if not isinstance(compartment, dict):
            raise ValueError('Post-apply requires the resolved compartment object')
        value = compartment.get('id')
    else:
        if not isinstance(compartment, str) or not compartment.strip():
            raise ValueError('Preflight requires the requested compartment string')
        mode = context['compartment_mode']
        if mode == 'new':
            return ''
        if mode != 'existing':
            raise ValueError('Invalid requested compartment mode')
        value = compartment
    if not isinstance(value, str) or not value.startswith(('ocid1.compartment.', 'ocid1.tenancy.')):
        raise ValueError('A resolved compartment OCID is required')
    return value


def _artifact_inputs(context):
    values = dict(context['inputs'])
    mode = values['artifacts_mode']
    if mode not in {'new', 'existing'}:
        raise ValueError('Invalid artifacts bucket mode')
    field = 'artifacts_bucket_name' if mode == 'new' else 'artifacts_existing_bucket_name'
    bucket = values.get(field)
    if not isinstance(bucket, str) or not re.fullmatch(r'[A-Za-z0-9._-]{1,128}', bucket):
        raise ValueError('Select an exact valid artifacts bucket name')
    if mode == 'existing' and values.get('artifacts_bucket_name', bucket) != bucket:
        raise ValueError('The canonical artifacts bucket differs from the selected existing bucket')
    values['artifacts_bucket_name'] = bucket
    return values


def settings_for(context, *, applied=False):
    values = _artifact_inputs(context)
    if applied:
        values = _applied_bindings(context, values)
    _validate_selection(values)
    platform, workspace = _native_identity(values)
    return SimpleNamespace(aidp_mode=values['aidp_mode'], aidp_region=context['region'], aidp_platform_id=platform,
        workspace_key=workspace, aidp_workspace_name=values.get('workspace_name', ''),
        oci_config_file=os.environ.get('DEPLOY_STUDIO_OCI_CONFIG', ''),
        objectstorage_namespace=values.get('objectstorage_namespace', ''),
        artifacts_bucket_name=values['artifacts_bucket_name'], compartment_id=_compartment_id(context, applied),
        artifacts_mode=values['artifacts_mode'],
        agent_model_id=values['model_id'], admin_user_ocid=values['admin_user_ocid'], identity_domain_id=values['identity_domain_id'],
        governance_operation=values.get('governance_operation', 'install'),
        memory_database_mode=values['autonomous_database_mode'],
        memory_database_id=values.get('autonomous_database_id') or values.get('existing_autonomous_database_ocid', ''),
        release_source={key: context.get('source', {}).get(key) for key in ('repository', 'ref', 'commit_sha')},
        deployment_id=context['deployment_id'], resource_ownership=values.get('resource_ownership', {}))


def _failed_operation_fields(outcome):
    fields = {}
    for name in ('failed_operation_id', 'failed_operation_type'):
        if name in outcome:
            value = outcome[name]
            if not isinstance(value, str) or not value or len(value) > 128 or any(char.isspace() for char in value):
                raise ValueError('Invalid failed operation identity')
            fields[name] = value
    if fields.get('failed_operation_type') not in OPERATIONS | {None}:
        raise ValueError('Invalid failed operation type')
    return fields


def _recovery_outputs(outcome):
    if not outcome:
        return {}
    allowed = {'update_failed_restored', 'rollback_complete', 'restore_failed', 'pending'}
    if outcome.get('status') not in allowed:
        raise ValueError('Unknown Governance recovery outcome')
    return {'outcome_status': outcome['status'], **_failed_operation_fields(outcome)}


def _operation_result(receipt, workspace):
    manifest = receipt['manifest']
    outputs = {'governance_status': manifest['status'],
        'validation_stage': manifest['validation_stage'], 'workspace_key': workspace,
        'operation_id': manifest['operation']['operation_id'],
        **_recovery_outputs(receipt.get('outcome', {}))}
    status = outputs.get('outcome_status', manifest['status'])
    messages = {
        'update_failed_restored': ('error', 'Governance update failed; the previous revision was restored and verified. The failed operation remains failed.'),
        'rollback_complete': ('info', 'Governance rollback restored and verified the previous revision; functional acceptance remains separate.'),
        'restore_failed': ('error', 'Governance recovery failed; inspect protected operation evidence before resuming.'),
        'pending': ('warning', 'Governance recovery is pending; resume the same operation and candidate.'),
    }
    level, message = messages.get(status, ('info', 'Governance technical installation verified; functional TEST acceptance remains pending.'))
    return {'outputs': outputs, 'events': [{'level': level, 'message': message}], 'artifacts': []}


def _result_status(result):
    outputs = result.get('outputs', {})
    statuses = {outputs.get('governance_status'), outputs.get('outcome_status')}
    if statuses.intersection({'update_failed_restored', 'restore_failed'}):
        return 1
    return 3 if 'pending' in statuses else 0


def _runner_client(settings, client_factory):
    if client_factory is not None:
        return client_factory(settings)
    for name in ('DEPLOY_STUDIO_OCI_CONFIG', 'DEPLOY_STUDIO_OCI_KEY'):
        value = os.environ.get(name)
        if not value or not Path(value).is_file():
            raise ValueError('The protected runner credential files are required')
    from .native_client import NativeClient
    return NativeClient(settings)


def preflight(context, client_factory=None):
    from .administrators import verify_administrator, verify_operator
    from .package_loader import load_package
    settings = settings_for(context)
    client = _runner_client(settings, client_factory)
    try:
        load_package()
        verify_administrator(client, settings.identity_domain_id, settings.admin_user_ocid,
                             require_roles=settings.aidp_mode == 'existing')
        preflight_memory(client)
        if settings.aidp_mode == 'existing':
            verify_operator(client, settings.identity_domain_id)
            client._workspace()
        iam = client._oci.identity.IdentityClient(client._oci_config)
        tenancy = iam.get_tenancy(client._oci_config['tenancy']).data
        region_key = tenancy.home_region_key
        regions = iam.list_regions().data
        home = [item.name for item in regions if item.key == region_key]
        if len(home) != 1:
            raise ValueError('The tenancy home region could not be verified')
        return {'inputs': {'home_region': home[0], 'artifacts_bucket_name': settings.artifacts_bucket_name},
            'events': [{'name': 'governance_preflight', 'status': 'passed',
            'message': 'Package and selected domain identity verified; platform roles are checked after bootstrap for a new platform.'}]}
    finally:
        client.session.close()


def _authorize_memory(client, settings, command, owned_receipt, memory_receipt):
    from .administrators import verify_administrator
    if (settings.aidp_mode == 'new' and command == 'install'
            and owned_receipt is None and memory_receipt is None):
        client.ensure_selected_admin(settings.admin_user_ocid)
    verify_administrator(client, settings.identity_domain_id, settings.admin_user_ocid)


def apply(context, command='install', client_factory=None, store_factory=None):
    from .receipts import ReceiptStore
    from .administrators import verify_administrator, verify_operator
    from .lifecycle import run_operation
    settings = settings_for(context, applied=True)
    if not settings.aidp_platform_id or not settings.objectstorage_namespace:
        raise ValueError('Terraform must return the selected native platform and storage bindings')
    client = _runner_client(settings, client_factory)
    try:
        verify_administrator(client, settings.identity_domain_id, settings.admin_user_ocid, require_roles=False)
        verify_operator(client, settings.identity_domain_id)
        workspace = client._governance_workspace()
        store = (store_factory or ReceiptStore)(client.object_storage, settings.objectstorage_namespace,
            settings.artifacts_bucket_name, settings.aidp_platform_id, workspace)
        owned_receipt, _ = store.load()
        if owned_receipt is None:
            from .client import MODULE_MANIFEST_PATH
            if client._workspace_json(workspace, MODULE_MANIFEST_PATH, 'Unowned Governance control receipt') is not None:
                raise AidpProvisionConflict('An unowned workspace installation cannot enable memory or grant roles')
        memory = ensure_memory(client, memory_store(client), command,
            lambda memory_receipt: _authorize_memory(client, settings, command, owned_receipt, memory_receipt))
        operation_id = str(uuid.uuid5(uuid.NAMESPACE_URL, context['project_id'] + ':' + context['deployment_id']))
        receipt = run_operation(client, store, admin=settings.admin_user_ocid, domain=settings.identity_domain_id,
                                operation_id=operation_id, command=command)
        result = _operation_result(receipt, workspace)
        result['outputs'].update(autonomous_database_id=memory['autonomous_database_id'],
                                 memory_status=memory['memory_status'])
        return result
    finally:
        client.session.close()


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('command', choices=['preflight', 'apply', *sorted(OPERATIONS)])
    parser.add_argument('--context', default=os.environ.get('DEPLOY_STUDIO_CONTEXT'))
    args = parser.parse_args(argv)
    result_path = os.environ.get('DEPLOY_STUDIO_RESULT' if args.command == 'preflight' else 'DEPLOY_STUDIO_OUTPUT')
    result, status = {}, 0
    try:
        if not args.context:
            raise ValueError('Deploy Studio context path is required')
        context = json.loads(Path(args.context).read_text(encoding='utf-8'))
        result = preflight(context) if args.command == 'preflight' else apply(context,
            context['inputs'].get('governance_operation', 'install') if args.command == 'apply' else args.command)
        status = _result_status(result)
    except Exception as error:
        pending = isinstance(error, AidpProvisionPending)
        # Provider text may contain request data: expose only a bounded error category.
        message = ('Governance operation is pending; resume the same deployment and candidate.' if pending else
                   'Governance validation or operation failed closed; inspect the protected operation evidence.')
        status = 3 if pending else 1
        result = ({'inputs': {}, 'events': [{'name': 'governance_preflight', 'status': 'failed', 'message': message}]}
                  if args.command == 'preflight' else {'outputs': {}, 'events': [{'level': 'error', 'message': message}], 'artifacts': []})
    content = json.dumps(result, sort_keys=True) + '\n'
    if result_path:
        Path(result_path).write_text(content, encoding='utf-8')
    else:
        print(content, end='')
    return status


if __name__ == '__main__':
    raise SystemExit(main())
