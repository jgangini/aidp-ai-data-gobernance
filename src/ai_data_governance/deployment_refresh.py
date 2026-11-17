"""Durable refresh intentions, bound to existing agents and compute identities."""
from datetime import datetime, timezone
from .deploy_studio_install import GovernanceInstaller
from .errors import AidpProvisionConflict, AidpProvisionError, AidpProvisionPending, AidpRequestError
from .native_times import at_or_after


class DeploymentRefresh:
    def __init__(self, client, workspace, manifest, journal, save, scope):
        self.client, self.workspace, self.manifest = client, workspace, manifest
        self.resources, self.journal, self.save, self.scope = manifest['resources'], journal, save, scope
        self.prefix = '/workspaces/' + workspace

    def rows(self, kind):
        if kind == 'documentary':
            path = self.prefix + '/agents/' + self.resources['documentation_agent_key'] + '/deployments'
            return self.client._agent_deployments(path)
        installer = GovernanceInstaller(self.client, self.workspace, self.manifest,
            pending=AidpProvisionPending, error=AidpProvisionError)
        return installer.test_deployments()

    def _unique(self, kind):
        rows = self.rows(kind)
        if len(rows) != 1 or not rows[0].get('key'):
            raise AidpProvisionConflict('Refresh requires one recorded native deployment identity')
        value = rows[0]
        agent_field, compute_field = ('agentKey', 'agentComputeKey') if kind == 'documentary' else ('agentFlowKey', 'agentFlowComputeKey')
        key = self.resources['documentation_agent_key' if kind == 'documentary' else 'agent_key']
        if value.get(agent_field) != key or value.get(compute_field) != self.resources['agent_compute_key']:
            raise AidpProvisionConflict('Deployment agent or compute identity differs')
        return value

    def capture(self):
        values = {kind: self._unique(kind) for kind in ('documentary', 'test')}
        if any(value.get('lifecycleState') != 'ACTIVE' for value in values.values()):
            raise AidpProvisionPending('Prior deployments must be ACTIVE before artifact maintenance', 'artifacts')
        return values

    def _submit(self, kind):
        value = self._unique(kind)
        if value.get('lifecycleState') in {'CREATING', 'DEPLOYING', 'UPDATING'}:
            raise AidpProvisionPending('An existing native deployment transition is still running', 'refresh')
        attempts = self.journal.get(kind, {}).get('attempts', 0)
        self.journal[kind] = {'submitted_at': datetime.now(timezone.utc).isoformat(), 'prior_key': value['key'],
                              'attempts': attempts + 1}
        self.save()
        try:
            self._post(kind)
        except AidpRequestError as error:
            self._record_rejection(kind, error)
            raise
        self.journal[kind]['acknowledged'] = True
        self.save()
        raise AidpProvisionPending('The artifact revision refresh was submitted; observe this same operation', 'refresh')

    def _record_rejection(self, kind, error):
        status = error.diagnostic['status_code']
        if 400 <= status < 500 and status not in {408, 409, 429}:
            self.journal[kind]['rejected'] = True
            self.journal[kind]['rejected_status'] = status
            self.save()

    def _post(self, kind):
        resources = self.resources
        token = 'governance-refresh:' + self.manifest['operation']['operation_id'] + ':' + self.scope + ':' + kind
        if kind == 'documentary':
            self.client._request('POST', self.prefix + '/agents/' + resources['documentation_agent_key'] + '/deployments/actions/redeploy',
                payload={'description': 'Governance owned artifact refresh', 'agentComputeKey': resources['agent_compute_key'],
                         'agentKey': resources['documentation_agent_key']}, retry_scope=token, phase='refresh')
        else:
            self.client._request('POST', self.prefix + '/actions/redeployAgentFlow', legacy=True,
                payload={'agentFlowKey': resources['agent_key'], 'agentFlowComputeKey': resources['agent_compute_key'],
                         'deploymentType': 'TEST'}, retry_scope=token, phase='refresh')

    def _verified(self, kind):
        value = self._unique(kind)
        state = value.get('lifecycleState', '')
        if state.endswith('FAILED') or state in {'FAILED', 'INACTIVE', 'DELETING'}:
            raise AidpProvisionError('The owned deployment refresh failed')
        updated = self.client._timestamp(value.get('timeUpdated'))
        submitted = self.client._timestamp(self.journal[kind]['submitted_at'])
        if state != 'ACTIVE' or not at_or_after(updated, submitted):
            raise AidpProvisionPending('Fresh native deployment readback is not verified yet', 'refresh')
        self.resources[kind + '_deployment_key'] = value['key']

    def run(self):
        for kind in ('documentary', 'test'):
            if kind not in self.journal or self.journal[kind].get('rejected'):
                self._submit(kind)
            self._verified(kind)
        self.save()

    def verify(self):
        if set(self.journal) != {'documentary', 'test'}:
            raise AidpProvisionConflict('Both revision refresh intentions must exist before activation')
        for kind in ('documentary', 'test'):
            self._verified(kind)
        self.save()
