"""Install/resume and revision-bound updates without replacing native resources."""
from copy import deepcopy
from datetime import datetime, timezone
import hashlib
import json
from .deploy_studio_install import GovernanceInstaller, DOCUMENTARY_NAME
from .deployment_bundle import build_deployment_bundle
from .constants import RUNTIME_FAMILY
from .errors import AidpProvisionConflict, AidpProvisionError, AidpProvisionPending
from .package_loader import load_package


def candidate_revision():
    from pathlib import Path
    root = Path(__file__).resolve().parent
    metadata = json.loads((root / 'package/lab.json').read_text())
    load_package()
    return hashlib.sha256(json.dumps(metadata['runtime_files'], sort_keys=True).encode()).hexdigest()


class RevisionInstaller(GovernanceInstaller):
    def agents(self):
        if self.manifest['operation']['type'] == 'install':
            return super().agents()
        resources = self.resources
        now = datetime.now(timezone.utc).isoformat()
        # Persist intent before either redeploy. Missing acknowledgements never authorize resubmission.
        for kind in ('documentary', 'test'):
            field = kind + '_revision_submission'
            if field not in resources:
                if kind == 'documentary':
                    current = self.client._agent_deployments(self.prefix + '/agents/' + resources['documentation_agent_key'] + '/deployments')
                else:
                    current = self.test_deployments()
                if len(current) != 1 or current[0].get('lifecycleState') != 'ACTIVE':
                    self.wait('Previous deployment transition must finish before submitting the candidate')
                resources[field] = now
                self.save()
                if kind == 'documentary':
                    self.client._ensure_agent_deployment(self.workspace, resources['documentation_agent_key'],
                        resources['agent_compute_key'], DOCUMENTARY_NAME,
                        redeploy_revision=self.manifest['candidate_revision'])
                else:
                    self.request('POST', self.prefix + '/actions/redeployAgentFlow', legacy=True,
                        payload={'agentFlowKey': resources['agent_key'], 'agentFlowComputeKey': resources['agent_compute_key'],
                                 'deploymentType': 'TEST'}, retry_scope='governance-update:' + self.manifest['operation']['operation_id'])
                self.wait('The candidate revision deployment was submitted; observe this operation')
        documentary = self.client._agent_deployments(self.prefix + '/agents/' + resources['documentation_agent_key'] + '/deployments')
        tests = self.test_deployments()
        for kind, rows in (('documentary', documentary), ('test', tests)):
            self.check_deployment_states(rows)
            active = [row for row in rows if row.get('lifecycleState') == 'ACTIVE']
            if len(active) != 1:
                self.wait('The new candidate deployment is not uniquely ACTIVE yet')
            updated = self.client._timestamp(active[0].get('timeUpdated'))
            submitted = self.client._timestamp(resources[kind + '_revision_submission'])
            if updated is None or updated < submitted:
                self.wait('Native readback has not verified the newly submitted revision')
            if kind == 'test' and active[0].get('agentFlowKey') != resources['agent_key']:
                raise self.error('TEST deployment identity changed')
            if kind == 'documentary' and (active[0].get('agentKey') != resources['documentation_agent_key']
                    or active[0].get('agentComputeKey') != resources['agent_compute_key']):
                raise self.error('Documentary deployment identity changed')
            if not active[0].get('key'):
                raise self.error('Deployment identity is missing')
            resources[kind + '_deployment_key'] = active[0]['key']
        self.save()
        self.permissions()
        self.publish(self.workflow(paused=True))
        self.advance('activation')


def run_operation(client, store, *, admin, domain, operation_id, command):
    if command not in {'install', 'resume', 'update', 'redeploy'}:
        raise AidpProvisionConflict('Unsupported Governance operation')
    revision = candidate_revision()
    source = getattr(client.settings, 'release_source', {})
    workspace = client._governance_workspace()
    with store.acquire(operation_id):
        receipt, etag = store.load()
        from .runtime_identity import identity_hash
        identity = {'platform_id': client.settings.aidp_platform_id, 'workspace_key': workspace,
                    'admin_user_ocid': admin, 'identity_domain_id': domain,
                    'operator_identity': identity_hash(client._oci_config)}
        if receipt:
            if receipt.get('schema_version') != 1 or receipt.get('identity') != identity:
                raise AidpProvisionConflict('Receipt ownership or selected administrator changed')
            manifest = receipt['manifest']
            if manifest.get('runtime_family') != RUNTIME_FAMILY:
                raise AidpProvisionConflict('Unsupported installation family; no adoption was performed')
            operation = manifest['operation']
            if operation['operation_id'] == operation_id and manifest['phase'] == 'active':
                if (manifest.get('candidate_revision') != revision or manifest.get('candidate_source', {}) != source
                        or command not in {operation['type'], 'resume'}):
                    raise AidpProvisionConflict('An operation identity cannot select another candidate or action')
                return receipt
            if manifest['phase'] != 'active':
                if operation['operation_id'] != operation_id or manifest.get('candidate_revision') != revision:
                    raise AidpProvisionConflict('Resume requires the original operation and candidate revision')
                if command not in {operation['type'], 'resume'}:
                    raise AidpProvisionConflict('Resume cannot change the original operation type')
                if manifest.get('candidate_source', {}) != source:
                    raise AidpProvisionConflict('Resume requires the original immutable package source')
            elif command == 'resume':
                if operation['operation_id'] != operation_id:
                    raise AidpProvisionConflict('Resume requires the original operation')
                return receipt
            elif command == 'install':
                if manifest.get('candidate_revision') != revision:
                    raise AidpProvisionConflict('An installed candidate requires explicit update')
                return receipt
            else:
                previous = deepcopy(manifest)
                manifest.update(phase='quiesce', status='updating', candidate_revision=revision, candidate_source=source,
                    operation={'operation_id': operation_id, 'type': command, 'phase': 'started'})
                receipt['previous'] = previous
                receipt['previous_revision'] = previous.get('candidate_revision')
        else:
            if command != 'install':
                raise AidpProvisionConflict('No owned installation exists for this operation')
            from .client import MODULE_MANIFEST_PATH
            if client._workspace_json(workspace, MODULE_MANIFEST_PATH, 'Unowned Governance control receipt') is not None:
                raise AidpProvisionConflict('A workspace Governance installation has no matching product receipt; transition is required')
            manifest = client._new_module_manifest(operation_id, 'install')
            manifest['candidate_revision'] = revision
            manifest['candidate_source'] = source
            receipt = {'schema_version': 1, 'identity': identity, 'manifest': manifest,
                'deployment_id': getattr(client.settings, 'deployment_id', None),
                'resource_ownership': deepcopy(getattr(client.settings, 'resource_ownership', {}))}
        client.store, client.receipt, client.receipt_revision = store, receipt, etag
        client._write_module_manifest(workspace, manifest)
        if manifest['phase'] == 'quiesce':
            resources = manifest['resources']
            job = client._request('GET', '/workspaces/' + workspace + '/jobs/' + resources['workflow_key'])
            expected = resources.get('workflow_definition', {})
            from .deploy_studio_install import job_matches
            if not job_matches(job, {**expected, 'schedule': job.get('schedule')}):
                raise AidpProvisionConflict('Recorded workflow drift prevents candidate update')
            paused = {**expected, 'schedule': {**job['schedule'], 'pauseStatus': 'PAUSED'}}
            client._request('PUT', '/workspaces/' + workspace + '/jobs/' + resources['workflow_key'], payload=paused)
            readback = client._request('GET', '/workspaces/' + workspace + '/jobs/' + resources['workflow_key'])
            if readback.get('schedule', {}).get('pauseStatus') != 'PAUSED':
                raise AidpProvisionPending('Schedule pause is not visible yet', 'quiesce')
            runs = client._list('/workspaces/' + workspace + '/jobRuns', params={'jobKey': resources['workflow_key']})
            terminal = {'SUCCESS', 'SUCCEEDED', 'FAILED', 'CANCELED', 'CANCELLED', 'SKIPPED', 'TIMED_OUT', 'INTERNAL_ERROR', 'TERMINATED'}
            for run in runs:
                state = run.get('state', {})
                if (state.get('status') if isinstance(state, dict) else state) not in terminal:
                    raise AidpProvisionPending('Managed writers must finish before updating sources', 'quiesce')
            for key in ('bootstrap_run', 'initial_workflow_run', 'documentary_deploy_submitted', 'test_deploy_submitted',
                        'documentary_revision_submission', 'test_revision_submission'):
                resources.pop(key, None)
            manifest['phase'] = 'control'
            client._write_module_manifest(workspace, manifest)
        RevisionInstaller(client, workspace, manifest, pending=AidpProvisionPending, error=AidpProvisionError).reconcile()
        return client.receipt
