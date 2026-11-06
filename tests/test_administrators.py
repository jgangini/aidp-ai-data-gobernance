from types import SimpleNamespace
from unittest.mock import Mock
import pytest
from ai_data_governance.administrators import verify_administrator
from ai_data_governance.native_client import NativeClient
from ai_data_governance.errors import AidpProvisionConflict, AidpProvisionPending


def client():
    value = Mock()
    value._oci_config = {'tenancy': 'tenancy', 'user': 'operator'}
    value._oci.identity.IdentityClient.return_value.get_domain.return_value.data = SimpleNamespace(
        id='domain', lifecycle_state='ACTIVE', url='https://domain.identity.oraclecloud.com')
    response = Mock(status_code=200)
    response.json.return_value = {'totalResults': 1, 'Resources': [{'ocid': 'selected', 'active': True, 'groups': []}]}
    value.session.get.return_value = response
    value._role_principal_ocids.return_value = ({'selected'}, set())
    return value


def test_inactive_or_foreign_domain_user_never_reaches_role_admission():
    value = client()
    value.session.get.return_value.json.return_value['Resources'][0]['active'] = False
    with pytest.raises(AidpProvisionConflict, match='active user'):
        verify_administrator(value, 'domain', 'selected')
    value._role_principal_ocids.assert_not_called()


def test_active_user_without_role_is_not_accepted_as_administrator():
    value = client()
    value._role_principal_ocids.return_value = ({'operator'}, set())
    with pytest.raises(AidpProvisionConflict, match='effective'):
        verify_administrator(value, 'domain', 'selected')
    value._request.assert_not_called()


def test_role_assignment_new_platform_is_signed_by_operator_and_verified():
    value = client()
    value.settings.aidp_mode = 'new'
    value._role_principal_ocids.return_value = ({'operator'}, set())
    value._role.return_value = {'key': 'admin-role'}
    value._role_user_ocids.return_value = {'operator','selected'}
    NativeClient.ensure_selected_admin(value, 'selected')
    call = value._request.call_args
    assert call.args == ('POST', '/roles/admin-role/actions/addMember')
    assert call.kwargs['payload'] == {'assignees': [{'type': 'USER', 'target': 'selected'}]}
    assert value._oci_config['user'] == 'operator'


@pytest.mark.parametrize('mode,operator', [('existing',True),('new',False)])
def test_no_permission_assignment_on_external_platform_or_unprivileged_operator(mode, operator):
    value = client()
    value.settings.aidp_mode = mode
    value._role_principal_ocids.return_value = ({'operator'} if operator else set(), set())
    with pytest.raises(AidpProvisionConflict):
        NativeClient.ensure_selected_admin(value, 'selected')
    value._request.assert_not_called()
