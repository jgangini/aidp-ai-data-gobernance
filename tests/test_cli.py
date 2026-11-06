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
        'artifacts_mode': 'existing', 'artifacts_existing_bucket_name': 'artifacts',
        'autonomous_database_mode': 'existing',
        'existing_autonomous_database_ocid': 'ocid1.autonomousdatabase.oc1.us-chicago-1.test',
        'model_id': 'ocid1.generativeaimodel.oc1.us-chicago-1.test'}}


def preflight_context(compartment_mode='existing'):
    document = context()
    document['compartment'] = (document['compartment']['id'] if compartment_mode == 'existing'
                               else 'aidp-modules-test')
    document['compartment_mode'] = compartment_mode
    return document


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
    result = cli.preflight(preflight_context(), lambda settings: client)
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
    assert cli.settings_for(preflight_context()).admin_user_ocid == document['inputs']['admin_user_ocid']
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


@pytest.mark.parametrize('field', ['aidp_mode', 'identity_domain_id', 'model_id', 'artifacts_bucket_name', 'artifacts_mode'])
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
    client._workspace_json.return_value = None
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


def test_unowned_workspace_receipt_blocks_memory_and_initial_role_grant(monkeypatch):
    client, store, operation, _ = administrator_harness(monkeypatch, existing_receipt=None)
    client._workspace_json.return_value = {'phase': 'active'}
    enable = Mock(side_effect=AssertionError('Unowned workspace must fail before enabling memory'))
    monkeypatch.setattr(cli, 'ensure_memory', enable)
    with pytest.raises(AidpProvisionConflict, match='unowned workspace'):
        cli.apply(bootstrap_context(), client_factory=lambda _: client, store_factory=lambda *_: store)
    client.ensure_selected_admin.assert_not_called()
    enable.assert_not_called()
    operation.assert_not_called()


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


@pytest.mark.parametrize('mode,expected', [('new', ''), ('existing', 'ocid1.compartment.oc1..test')])
def test_preflight_compartment_matches_the_requested_ctn_shape(mode, expected):
    settings = cli.settings_for(preflight_context(mode))
    assert settings.compartment_id == expected


def test_post_apply_uses_only_the_resolved_compartment_object():
    document = bootstrap_context()
    assert cli.settings_for(document, applied=True).compartment_id == document['compartment']['id']
    document['compartment'] = document['compartment']['id']
    with pytest.raises(ValueError, match='resolved compartment object'):
        cli.settings_for(document, applied=True)


def test_preflight_does_not_treat_post_apply_shape_as_an_alias():
    document = preflight_context()
    document['compartment'] = {'id': document['compartment']}
    with pytest.raises(ValueError, match='requested compartment string'):
        cli.settings_for(document)


def test_preflight_context_failure_writes_result_without_using_post_apply_output(tmp_path, monkeypatch, capsys):
    result, other = tmp_path / 'result.json', tmp_path / 'output.json'
    result.write_bytes(b'')
    other.write_text('must remain unchanged')
    monkeypatch.delenv('DEPLOY_STUDIO_CONTEXT', raising=False)
    monkeypatch.setenv('DEPLOY_STUDIO_RESULT', str(result))
    monkeypatch.setenv('DEPLOY_STUDIO_OUTPUT', str(other))
    assert cli.main(['preflight']) == 1
    assert json.loads(result.read_text())['events'][0]['status'] == 'failed'
    assert other.read_text() == 'must remain unchanged'
    assert capsys.readouterr().out == ''


@pytest.mark.parametrize('missing', ['DEPLOY_STUDIO_OCI_CONFIG', 'DEPLOY_STUDIO_OCI_KEY'])
def test_runner_requires_explicit_credential_files_without_default_discovery(tmp_path, monkeypatch, missing):
    for name in ['DEPLOY_STUDIO_OCI_CONFIG', 'DEPLOY_STUDIO_OCI_KEY']:
        path = tmp_path / name
        path.write_text('test fixture')
        monkeypatch.setenv(name, str(path))
    monkeypatch.delenv(missing)
    with pytest.raises(ValueError, match='protected runner credential files'):
        cli._runner_client(SimpleNamespace(), None)


@pytest.mark.parametrize('mode', ['new', 'existing'])
def test_settings_derive_the_canonical_bucket_from_the_selected_mode_without_mutating_input(mode):
    document = preflight_context()
    document['inputs']['artifacts_mode'] = mode
    if mode == 'existing':
        del document['inputs']['artifacts_bucket_name']
        document['inputs']['artifacts_existing_bucket_name'] = 'selected-external-bucket'
    else:
        document['inputs']['artifacts_bucket_name'] = 'selected-new-bucket'
    before = json.dumps(document, sort_keys=True)
    settings = cli.settings_for(document)
    assert settings.artifacts_bucket_name == ('selected-external-bucket' if mode == 'existing' else 'selected-new-bucket')
    assert json.dumps(document, sort_keys=True) == before


@pytest.mark.parametrize('mode,bucket', [('new', 'bad/name'), ('existing', 'bad/name'),
    ('existing', None), ('existing', ''), ('existing', 'x' * 129)], ids=['invalid-new', 'invalid-existing', 'null', 'empty', 'too-long'])
def test_invalid_bucket_selection_stops_before_memory_or_native_access(mode, bucket, monkeypatch):
    document = preflight_context()
    document['inputs']['artifacts_mode'] = mode
    field = 'artifacts_bucket_name' if mode == 'new' else 'artifacts_existing_bucket_name'
    document['inputs'][field] = bucket
    client, memory = Mock(), Mock()
    monkeypatch.setattr(cli, 'preflight_memory', memory)
    with pytest.raises(ValueError, match='valid artifacts bucket name'):
        cli.preflight(document, client)
    client.assert_not_called()
    memory.assert_not_called()


def test_existing_bucket_selector_is_required_even_when_legacy_canonical_name_is_present(monkeypatch):
    document = preflight_context()
    del document['inputs']['artifacts_existing_bucket_name']
    client, memory = Mock(), Mock()
    monkeypatch.setattr(cli, 'preflight_memory', memory)
    with pytest.raises(ValueError):
        cli.preflight(document, client)
    client.assert_not_called()
    memory.assert_not_called()


def test_existing_bucket_canonical_name_cannot_contradict_the_selector(monkeypatch):
    document = preflight_context()
    document['inputs']['artifacts_bucket_name'] = 'different-bucket'
    client, memory = Mock(), Mock()
    monkeypatch.setattr(cli, 'preflight_memory', memory)
    with pytest.raises(ValueError, match='differs from the selected existing bucket'):
        cli.preflight(document, client)
    client.assert_not_called()
    memory.assert_not_called()


@pytest.mark.parametrize('field,value', [('artifacts_bucket_name', 'different-bucket'), ('artifacts_mode', 'new')])
def test_terraform_cannot_redirect_bucket_name_or_mode_before_any_native_action(field, value, monkeypatch):
    document = bootstrap_context()
    document['terraform_outputs'][field] = value
    client, memory = Mock(), Mock()
    monkeypatch.setattr(cli, 'ensure_memory', memory)
    with pytest.raises(ValueError):
        cli.apply(document, client_factory=client)
    client.assert_not_called()
    memory.assert_not_called()
