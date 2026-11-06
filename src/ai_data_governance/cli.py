"""Deploy Studio entrypoints; credentials stay in the authorized runner environment."""
import argparse
from dataclasses import dataclass
import json
import os
from pathlib import Path
from types import SimpleNamespace
import uuid
from .errors import AidpProvisionConflict, AidpProvisionPending


def settings_for(context, *, applied=False):
    values = dict(context['inputs'])
    if applied:
        outputs = context.get('terraform_outputs', {})
        for key in ('aidp_mode', 'admin_user_ocid', 'identity_domain_id', 'model_id', 'artifacts_bucket_name'):
            if outputs.get(key) != values[key]:
                raise ValueError('Terraform outputs changed the selected platform or administrator binding')
        if outputs.get('resource_ownership', {}).get('platform') != ('owned' if values['aidp_mode'] == 'new' else 'external'):
            raise ValueError('Platform ownership must match the selected mode')
        if values['aidp_mode'] == 'existing' and (
                outputs.get('ai_data_platform_ocid') != values['existing_ai_data_platform_ocid']
                or outputs.get('workspace_key') != values['existing_workspace_key']):
            raise ValueError('Terraform outputs changed the exact external platform or workspace')
        values.update(outputs)
    mode = values['aidp_mode']
    if mode not in {'new', 'existing'}:
        raise ValueError('Invalid platform mode')
    if values.get('governance_operation', 'install') not in {'install', 'resume', 'update', 'redeploy'}:
        raise ValueError('Invalid Governance operation')
    domain, admin = values['identity_domain_id'], values['admin_user_ocid']
    if not domain.startswith('ocid1.domain.') or not admin.startswith('ocid1.user.'):
        raise ValueError('Stable domain and user OCIDs are required')
    platform = values.get('ai_data_platform_ocid') or values.get('existing_ai_data_platform_ocid', '')
    workspace = values.get('workspace_key') or values.get('existing_workspace_key', '')
    if mode == 'existing' and (not platform.startswith('ocid1.aidataplatform.') or str(uuid.UUID(workspace)) != workspace):
        raise ValueError('An existing platform requires exact platform and workspace identities')
    return SimpleNamespace(aidp_mode=mode, aidp_region=context['region'], aidp_platform_id=platform,
        workspace_key=workspace, aidp_workspace_name=values.get('workspace_name', ''),
        oci_config_file=os.environ.get('DEPLOY_STUDIO_OCI_CONFIG', ''),
        objectstorage_namespace=values.get('objectstorage_namespace', ''),
        artifacts_bucket_name=values['artifacts_bucket_name'], compartment_id=context['compartment']['id'],
        agent_model_id=values['model_id'], admin_user_ocid=admin, identity_domain_id=domain,
        release_source={key: context.get('source', {}).get(key) for key in ('repository', 'ref', 'commit_sha')},
        deployment_id=context['deployment_id'], resource_ownership=values.get('resource_ownership', {}))


def preflight(context, client_factory=None):
    from .native_client import NativeClient
    from .administrators import verify_administrator, verify_operator
    from .package_loader import load_package
    settings = settings_for(context)
    client = (client_factory or NativeClient)(settings)
    try:
        load_package()
        verify_administrator(client, settings.identity_domain_id, settings.admin_user_ocid,
                             require_roles=settings.aidp_mode == 'existing')
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
        return {'inputs': {'home_region': home[0]}, 'events': [{'name': 'governance_preflight', 'status': 'passed',
            'message': 'Package and selected domain identity verified; platform roles are checked after bootstrap for a new platform.'}]}
    finally:
        client.session.close()


def apply(context, command='install', client_factory=None, store_factory=None):
    from .native_client import NativeClient
    from .receipts import ReceiptStore
    from .administrators import verify_administrator, verify_operator
    from .lifecycle import run_operation
    settings = settings_for(context, applied=True)
    if not settings.aidp_platform_id or not settings.objectstorage_namespace:
        raise ValueError('Terraform must return the selected native platform and storage bindings')
    client = (client_factory or NativeClient)(settings)
    try:
        # Verify domain identity before assignment, then roles after new-platform bootstrap.
        verify_administrator(client, settings.identity_domain_id, settings.admin_user_ocid, require_roles=False)
        verify_operator(client, settings.identity_domain_id)
        if settings.aidp_mode == 'new':
            client.ensure_selected_admin(settings.admin_user_ocid)
        verify_administrator(client, settings.identity_domain_id, settings.admin_user_ocid)
        workspace = client._governance_workspace()
        store = (store_factory or ReceiptStore)(client.object_storage, settings.objectstorage_namespace,
            settings.artifacts_bucket_name, settings.aidp_platform_id, workspace)
        operation_id = str(uuid.uuid5(uuid.NAMESPACE_URL, context['project_id'] + ':' + context['deployment_id']))
        receipt = run_operation(client, store, admin=settings.admin_user_ocid, domain=settings.identity_domain_id,
                                operation_id=operation_id, command=command)
        return {'outputs': {'governance_status': receipt['manifest']['status'],
            'validation_stage': receipt['manifest']['validation_stage'], 'workspace_key': workspace,
            'operation_id': receipt['manifest']['operation']['operation_id']},
            'events': [{'level': 'info', 'message': 'Governance technical installation verified; functional TEST acceptance remains pending.'}], 'artifacts': []}
    finally:
        client.session.close()


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('command', choices=['preflight', 'apply', 'install', 'resume', 'update', 'redeploy'])
    parser.add_argument('--context', default=os.environ.get('DEPLOY_STUDIO_CONTEXT'))
    args = parser.parse_args(argv)
    if not args.context:
        parser.error('Deploy Studio context path is required')
    result_path = os.environ.get('DEPLOY_STUDIO_RESULT')
    result, status = {}, 0
    try:
        context = json.loads(Path(args.context).read_text(encoding='utf-8'))
        result = preflight(context) if args.command == 'preflight' else apply(context,
            context['inputs'].get('governance_operation', 'install') if args.command == 'apply' else args.command)
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
