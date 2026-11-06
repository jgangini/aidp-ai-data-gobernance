"""Verify the selected domain identity using the authorized operator signer."""
import json
from urllib.parse import urlsplit
from .errors import AidpProvisionConflict, AidpProvisionError


def domain_user(client, domain_id, user_ocid):
    iam = client._oci.identity.IdentityClient(client._oci_config)
    domain = iam.get_domain(domain_id).data
    if domain.id != domain_id or domain.lifecycle_state != 'ACTIVE':
        raise AidpProvisionConflict('The selected identity domain is not active')
    endpoint = domain.url.rstrip('/')
    parsed = urlsplit(endpoint)
    if parsed.scheme != 'https' or not parsed.hostname or not parsed.hostname.endswith('.oraclecloud.com') or parsed.username:
        raise AidpProvisionError('Identity Domain returned an untrusted SCIM endpoint')
    response = client.session.get(endpoint + '/admin/v1/Users', auth=client.signer,
        params={'filter': 'ocid eq ' + json.dumps(user_ocid), 'attributes': 'id,ocid,active,groups', 'count': 100}, timeout=(10, 60))
    if response.status_code != 200:
        raise AidpProvisionConflict('The operator cannot verify the selected domain user')
    body = response.json()
    rows = body.get('Resources', [])
    if body.get('totalResults') != 1 or len(rows) != 1 or rows[0].get('ocid') != user_ocid or rows[0].get('active') is not True:
        raise AidpProvisionConflict('The selected administrator is not an active user in this domain')
    return rows[0], endpoint


def verify_administrator(client, domain_id, user_ocid, *, require_roles=True):
    user, endpoint = domain_user(client, domain_id, user_ocid)
    if not require_roles:
        return
    users, groups = client._role_principal_ocids('AI_DATA_PLATFORM_ADMIN')
    if user_ocid in users:
        return
    memberships = user.get('groups', [])
    if not isinstance(memberships, list) or len(memberships) > 1000:
        raise AidpProvisionConflict('Domain group membership could not be verified completely')
    from urllib.parse import quote
    for membership in memberships:
        key = membership.get('value')
        if not isinstance(key, str) or not key:
            raise AidpProvisionConflict('Domain returned invalid group membership')
        response = client.session.get(endpoint + '/admin/v1/Groups/' + quote(key, safe=''), auth=client.signer,
            params={'attributes': 'id,ocid'}, timeout=(10, 60))
        if response.status_code != 200:
            raise AidpProvisionConflict('Effective administrator group could not be verified')
        if response.json().get('ocid') in groups:
            return
    raise AidpProvisionConflict('The selected user has no effective AI_DATA_PLATFORM_ADMIN role')


def verify_operator(client, domain_id):
    operator = client._oci_config['user']
    users, _ = client._role_principal_ocids('AI_DATA_PLATFORM_ADMIN')
    if operator not in users:
        # Group-only admission requires proof of the signing user's own membership.
        verify_administrator(client, domain_id, operator)
