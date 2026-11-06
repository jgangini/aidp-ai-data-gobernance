import json
from types import SimpleNamespace
from unittest.mock import Mock
import pytest
from ai_data_governance import cli
from ai_data_governance.errors import AidpProvisionConflict, AidpProvisionError, AidpProvisionPending


def context():
    return {'schema_version': 1, 'project_id': 'aidp-ai-data-governance', 'deployment_id': 'test-operation',
        'region': 'us-chicago-1', 'compartment': {'id': 'ocid1.compartment.oc1..test'},
        'inputs': {'aidp_mode': 'existing', 'existing_ai_data_platform_ocid': 'ocid1.aidataplatform.oc1.us-chicago-1.test',
        'existing_workspace_key': '11111111-1111-4111-8111-111111111111', 'identity_domain_id': 'ocid1.domain.oc1..test',
        'admin_user_ocid': 'ocid1.user.oc1..test', 'artifacts_bucket_name': 'artifacts',
        'autonomous_database_mode': 'existing',
        'existing_autonomous_database_ocid': 'ocid1.autonomousdatabase.oc1.us-chicago-1.test',
        'model_id': 'ocid1.generativeaimodel.oc1.us-chicago-1.test'}}


@pytest.mark.parametrize('field,value', [('aidp_mode','adopt'),('existing_workspace_key','foreign'),('admin_user_ocid','email@example.com'),('governance_operation','delete')])
def test_invalid_bindings_fail_before_credential_or_network_access(field, value):
    document = context()
    document['inputs'][field] = value
    factory = Mock()
    with pytest.raises(ValueError):
        cli.preflight(document, factory)
    factory.assert_not_called()


def test_preflight_verifies_selected_user_and_effective_roles(monkeypatch):
    verify = Mock()
    monkeypatch.setattr('ai_data_governance.administrators.verify_administrator', verify)
    memory = Mock()
    monkeypatch.setattr(cli, 'preflight_memory', memory)
    iam = Mock()
    iam.get_tenancy.return_value.data.home_region_key = 'ORD'
    iam.list_regions.return_value.data = [SimpleNamespace(key='ORD', name='us-chicago-1')]
    client = Mock()
    client._oci_config = {'tenancy': 'tenancy', 'user': 'operator'}
    client._role_principal_ocids.return_value = ({'operator'}, set())
    client._oci.identity.IdentityClient.return_value = iam
    result = cli.preflight(context(), lambda settings: client)
    assert result['inputs']['home_region'] == 'us-chicago-1'
    verify.assert_called_once_with(client, 'ocid1.domain.oc1..test', 'ocid1.user.oc1..test', require_roles=True)
    client._request.assert_not_called()
    memory.assert_called_once_with(client)


def test_runner_pending_is_not_success_and_never_prints_provider_secrets(tmp_path, monkeypatch, capsys):
    path = tmp_path / 'context.json'
    path.write_text(json.dumps(context()))
    monkeypatch.setattr(cli, 'apply', Mock(side_effect=AidpProvisionPending('secret-key upstream raw text', 'agent')))
    assert cli.main(['resume', '--context', str(path)]) == 3
    result = json.loads(capsys.readouterr().out)
    assert result['outputs'] == {}
    assert 'secret-key' not in str(result)


@pytest.mark.parametrize('change', ['workspace_key', 'admin_user_ocid', 'platform'])
def test_changed_terraform_binding_fails_before_native_client_creation(change):
    document = context()
    selected = document['inputs']
    document['terraform_outputs'] = {**selected,
        'ai_data_platform_ocid': selected['existing_ai_data_platform_ocid'],
        'workspace_key': selected['existing_workspace_key'],
        'resource_ownership': {'platform': 'external'}}
    if change == 'platform':
        document['terraform_outputs']['resource_ownership']['platform'] = 'owned'
    else:
        document['terraform_outputs'][change] = 'foreign'
    factory = Mock()
    with pytest.raises(ValueError):
        cli.apply(document, client_factory=factory)
    factory.assert_not_called()


@pytest.mark.parametrize('command', ['rollback', 'apply'])
def test_rollback_dispatch_uses_the_existing_runner_contract(command, tmp_path, monkeypatch, capsys):
    document = context()
    document['inputs']['governance_operation'] = 'rollback'
    path = tmp_path / 'context.json'
    path.write_text(json.dumps(document))
    apply = Mock(return_value={'outputs': {'governance_status': 'rollback_complete'}, 'events': [], 'artifacts': []})
    monkeypatch.setattr(cli, 'apply', apply)
    assert cli.settings_for(document).admin_user_ocid == document['inputs']['admin_user_ocid']
    assert cli.main([command, '--context', str(path)]) == 0
    apply.assert_called_once_with(document, 'rollback')
    assert json.loads(capsys.readouterr().out)['outputs']['governance_status'] == 'rollback_complete'


@pytest.mark.parametrize('status,exit_code,level', [
    ('update_failed_restored', 1, 'error'),
    ('rollback_complete', 0, 'info'),
    ('restore_failed', 1, 'error'),
    ('pending', 3, 'warning'),
])
def test_recovery_keeps_the_original_outcome_and_runner_exit_status(status, exit_code, level, tmp_path, monkeypatch, capsys):
    receipt = {'manifest': {'status': status, 'validation_stage': 'TEST_PENDING',
        'operation': {'operation_id': 'original-operation'}},
        'outcome': {'status': status, 'failed_operation_id': 'original-failed-operation',
            'failed_operation_type': 'update', 'provider_message': 'private-api-key upstream text'},
        'provider_error': {'token': 'private-api-key'}}
    result = cli._operation_result(receipt, 'workspace')
    path = tmp_path / 'context.json'
    path.write_text(json.dumps(context()))
    monkeypatch.setattr(cli, 'apply', Mock(return_value=result))
    assert cli.main(['resume', '--context', str(path)]) == exit_code
    observed = json.loads(capsys.readouterr().out)
    assert observed['outputs'] == {'governance_status': status, 'validation_stage': 'TEST_PENDING',
        'workspace_key': 'workspace', 'operation_id': 'original-operation', 'outcome_status': status,
        'failed_operation_id': 'original-failed-operation', 'failed_operation_type': 'update'}
    assert observed['events'][0]['level'] == level
    assert 'private-api-key' not in str(observed)
    if status != 'rollback_complete':
        assert 'technical installation verified' not in str(observed)


@pytest.mark.parametrize('field,value', [
    ('failed_operation_id', {'token': 'secret'}),
    ('failed_operation_type', 'provider-secret'),
    ('status', 'unrecognized-success'),
])
def test_recovery_rejects_unrecognized_or_unstructured_outcome_fields(field, value):
    receipt = {'manifest': {'status': 'restore_failed', 'validation_stage': 'TEST_PENDING',
        'operation': {'operation_id': 'original-operation'}},
        'outcome': {'status': 'restore_failed', field: value}}
    with pytest.raises(ValueError):
        cli._operation_result(receipt, 'workspace')


@pytest.mark.parametrize('field', ['aidp_mode', 'identity_domain_id', 'model_id', 'artifacts_bucket_name'])
def test_other_selected_bindings_cannot_be_rewritten_by_terraform(field):
    document = context()
    selected = document['inputs']
    document['terraform_outputs'] = {**selected,
        'ai_data_platform_ocid': selected['existing_ai_data_platform_ocid'],
        'workspace_key': selected['existing_workspace_key'], 'resource_ownership': {'platform': 'external'}}
    document['terraform_outputs'][field] = 'foreign'
    with pytest.raises(ValueError, match='selected platform or administrator binding'):
        cli.settings_for(document, applied=True)


def bootstrap_context(mode='new'):
    document = context()
    document['inputs']['aidp_mode'] = mode
    document['terraform_outputs'] = {**document['inputs'],
        'ai_data_platform_ocid': document['inputs']['existing_ai_data_platform_ocid'],
        'workspace_key': document['inputs']['existing_workspace_key'],
        'autonomous_database_id': document['inputs']['existing_autonomous_database_ocid'],
        'objectstorage_namespace': 'namespace',
        'resource_ownership': {'platform': 'owned' if mode == 'new' else 'external',
                               'memory_database': 'external'}}
    return document


def administrator_harness(monkeypatch, *, existing_receipt, memory_receipt=None):
    client, store = Mock(), Mock()
    users = {'operator'}
    events = []
    client._oci_config = {'user': 'operator'}
    client._role_principal_ocids.side_effect = lambda _: (users, set())
    client._governance_workspace.side_effect = lambda: events.append('workspace') or 'workspace'
    store.load.side_effect = lambda: events.append('receipt') or (existing_receipt, 'revision')

    def grant(user):
        events.append('grant')
        users.add(user)

    client.ensure_selected_admin.side_effect = grant
    monkeypatch.setattr('ai_data_governance.administrators.domain_user',
        lambda *_args: ({'groups': []}, 'https://domain.oraclecloud.com'))
    operation = Mock(return_value={'manifest': {'status': 'active', 'validation_stage': 'TEST_PENDING',
        'operation': {'operation_id': 'original-operation'}}})
    monkeypatch.setattr('ai_data_governance.lifecycle.run_operation', operation)
    monkeypatch.setattr(cli, 'memory_store', lambda _: object())

    def memory(_client, _store, _command, authorize):
        authorize(memory_receipt)
        return {'autonomous_database_id': 'ocid1.autonomousdatabase.oc1.us-chicago-1.test',
                'memory_status': 'READY'}

    monkeypatch.setattr(cli, 'ensure_memory', memory)
    return client, store, operation, events


def test_new_platform_initial_install_grants_only_after_a_verified_missing_receipt(monkeypatch):
    client, store, operation, events = administrator_harness(monkeypatch, existing_receipt=None)
    result = cli.apply(bootstrap_context(), client_factory=lambda _: client, store_factory=lambda *_: store)
    assert events == ['workspace', 'receipt', 'grant']
    client.ensure_selected_admin.assert_called_once_with('ocid1.user.oc1..test')
    assert result['outputs']['governance_status'] == 'active'
    assert operation.call_args.kwargs['command'] == 'install'
    client.session.close.assert_called_once()


@pytest.mark.parametrize('command', ['install', 'resume', 'update', 'redeploy', 'rollback'])
@pytest.mark.parametrize('existing_receipt', [{}, {'manifest': {}}], ids=['empty-invalid', 'recorded'])
def test_revoked_administrator_on_owned_installation_is_not_regranted_even_in_new_mode(command, existing_receipt, monkeypatch):
    client, store, operation, events = administrator_harness(monkeypatch, existing_receipt=existing_receipt)
    with pytest.raises(AidpProvisionConflict, match='effective AI_DATA_PLATFORM_ADMIN'):
        cli.apply(bootstrap_context(), command, lambda _: client, lambda *_: store)
    assert events == ['workspace', 'receipt']
    client.ensure_selected_admin.assert_not_called()
    operation.assert_not_called()
    client.session.close.assert_called_once()


@pytest.mark.parametrize('command', ['resume', 'update', 'redeploy', 'rollback'])
def test_missing_receipt_does_not_authorize_grant_for_non_install_commands(command, monkeypatch):
    client, store, operation, _ = administrator_harness(monkeypatch, existing_receipt=None)
    with pytest.raises(AidpProvisionConflict):
        cli.apply(bootstrap_context(), command, lambda _: client, lambda *_: store)
    client.ensure_selected_admin.assert_not_called()
    operation.assert_not_called()


def test_receipt_lookup_failure_blocks_initial_admin_assignment(monkeypatch):
    client, store, operation, _ = administrator_harness(monkeypatch, existing_receipt=None)
    store.load.side_effect = AidpProvisionError('receipt unavailable')
    with pytest.raises(AidpProvisionError):
        cli.apply(bootstrap_context(), client_factory=lambda _: client, store_factory=lambda *_: store)
    client.ensure_selected_admin.assert_not_called()
    operation.assert_not_called()
    client.session.close.assert_called_once()


def test_external_platform_never_receives_bootstrap_admin_assignment(monkeypatch):
    client, store, operation, _ = administrator_harness(monkeypatch, existing_receipt=None)
    with pytest.raises(AidpProvisionConflict):
        cli.apply(bootstrap_context('existing'), client_factory=lambda _: client, store_factory=lambda *_: store)
    client.ensure_selected_admin.assert_not_called()
    operation.assert_not_called()


def test_pending_memory_blocks_role_regrant_before_the_business_receipt_exists(monkeypatch):
    client, store, operation, events = administrator_harness(monkeypatch, existing_receipt=None,
        memory_receipt={'phase': 'submitted'})
    with pytest.raises(AidpProvisionConflict, match='effective AI_DATA_PLATFORM_ADMIN'):
        cli.apply(bootstrap_context(), client_factory=lambda _: client, store_factory=lambda *_: store)
    client.ensure_selected_admin.assert_not_called()
    operation.assert_not_called()
    assert events == ['workspace', 'receipt']


@pytest.mark.parametrize('field,value', [('autonomous_database_id', 'ocid1.autonomousdatabase.oc1..foreign'),
                                       ('autonomous_database_mode', 'new')])
def test_changed_memory_terraform_binding_blocks_native_access(field, value):
    document = bootstrap_context()
    document['terraform_outputs'][field] = value
    factory = Mock()
    with pytest.raises(ValueError):
        cli.apply(document, client_factory=factory)
    factory.assert_not_called()


def test_ctn_output_environment_receives_the_hook_result(tmp_path, monkeypatch, capsys):
    path, output = tmp_path / 'context.json', tmp_path / 'output.json'
    path.write_text(json.dumps(context()))
    expected = {'outputs': {'memory_status': 'READY'}, 'events': [], 'artifacts': []}
    monkeypatch.setenv('DEPLOY_STUDIO_OUTPUT', str(output))
    monkeypatch.setattr(cli, 'apply', Mock(return_value=expected))
    assert cli.main(['apply', '--context', str(path)]) == 0
    assert json.loads(output.read_text()) == expected
    assert capsys.readouterr().out == ''
