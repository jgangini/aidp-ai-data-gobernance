import json
from types import SimpleNamespace
from unittest.mock import Mock
import pytest
from ai_data_governance import cli
from ai_data_governance.errors import AidpProvisionPending


def context():
    return {'schema_version': 1, 'project_id': 'aidp-ai-data-governance', 'deployment_id': 'test-operation',
        'region': 'us-chicago-1', 'compartment': {'id': 'ocid1.compartment.oc1..test'},
        'inputs': {'aidp_mode': 'existing', 'existing_ai_data_platform_ocid': 'ocid1.aidataplatform.oc1.us-chicago-1.test',
        'existing_workspace_key': '11111111-1111-4111-8111-111111111111', 'identity_domain_id': 'ocid1.domain.oc1..test',
        'admin_user_ocid': 'ocid1.user.oc1..test', 'artifacts_bucket_name': 'artifacts',
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
