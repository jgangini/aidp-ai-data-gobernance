"""Reversible artifact update/restore; no resources, permissions, DDL or task runs."""
from copy import deepcopy
import hashlib
import json
from . import artifact_backups as backups
from .deployment_bundle import build_deployment_bundle
from .deployment_refresh import DeploymentRefresh
from .deploy_studio_install import job_matches
from .errors import AidpProvisionConflict, AidpProvisionPending
from .package_loader import load_package

TERMINAL_RUNS = {'SUCCESS', 'SUCCEEDED', 'FAILED', 'CANCELED', 'CANCELLED', 'SKIPPED', 'TIMED_OUT', 'INTERNAL_ERROR', 'TERMINATED'}


class ArtifactMaintenance:
    def __init__(self, client, store, workspace):
        self.client, self.store, self.workspace = client, store, workspace
        self.receipt = client.receipt
        self.manifest = self.receipt['manifest']
        self.state = self.manifest.setdefault('maintenance', {})
        self.job_path = '/workspaces/' + workspace + '/jobs/' + self.manifest['resources']['workflow_key']

    def save(self):
        self.client._write_module_manifest(self.workspace, self.manifest)

    def advance(self, phase):
        self.manifest['phase'] = phase
        self.save()

    def _refresh(self, scope):
        journal = self.state.setdefault(scope + '_refresh', {})
        return DeploymentRefresh(self.client, self.workspace, self.manifest, journal, self.save, scope)

    def _snapshot(self):
        return backups.load_snapshot(self.store, self.receipt['recovery_snapshot'], self.receipt)

    def prepare(self):
        deployments = self._refresh('candidate').capture()
        reference, value = backups.snapshot(self.client, self.store, self.workspace, self.receipt, deployments)
        bindings = value['previous']['resources']['bundle_manifest']['bindings']
        if self.client.settings.agent_model_id != bindings['model_id']:
            raise AidpProvisionConflict('Changing the model requires a separately accepted runtime configuration')
        bundle = build_deployment_bundle(bindings)
        files = backups.compatible_candidate(self.store, value, bundle)
        self.state.update(candidate_files={path: self.store.put_artifact(body) for path, body in files.items()},
            candidate_bundle=bundle['manifest'], candidate_workflow=bundle['workflow'], written={})
        self.receipt['recovery_snapshot'] = reference
        self.state['snapshot_revision'] = value['previous']['candidate_revision']
        self.advance('quiesce')

    def _known_workflows(self, value):
        prior = value['workflow']
        candidate = {**self.state.get('candidate_workflow', prior), 'schedule': prior['schedule']}
        return [prior, self._paused(prior), candidate, self._paused(candidate)]

    @staticmethod
    def _paused(value):
        return {**value, 'schedule': {**value['schedule'], 'pauseStatus': 'PAUSED'}}

    def _publish(self, target, value):
        actual = self.client._request('GET', self.job_path, phase='artifacts')
        if not any(job_matches(actual, known) for known in self._known_workflows(value)):
            raise AidpProvisionConflict('Workflow or schedule changed outside the owned maintenance revision')
        if not job_matches(actual, target):
            self.state['mutated'] = True
            self.save()
            self.client._request('PUT', self.job_path, payload=target, phase='artifacts')
        if not job_matches(self.client._request('GET', self.job_path, phase='artifacts'), target):
            raise AidpProvisionPending('The exact workflow readback is still pending', 'artifacts')

    def _drained_run_keys(self):
        rows = self.client._list('/workspaces/' + self.workspace + '/jobRuns',
            params={'jobKey': self.manifest['resources']['workflow_key']})
        for row in rows:
            state = row.get('state', {})
            status = state.get('status') if isinstance(state, dict) else state
            if status not in TERMINAL_RUNS:
                raise AidpProvisionPending('Managed writers must finish before artifact changes', 'quiesce')
        if any(not isinstance(row.get('key'), str) or not row['key'] for row in rows):
            raise AidpProvisionConflict('Complete drained writer identities are required')
        return sorted(row['key'] for row in rows)

    def quiesce(self):
        value = self._snapshot()
        self._verify_agents(value)
        self._publish(self._paused(value['workflow']), value)
        value['barrier_run_keys'] = self._drained_run_keys()
        reference = self.store.put_artifact(json.dumps(value, sort_keys=True, separators=(',', ':')).encode())
        self.receipt['recovery_snapshot'] = reference
        self.advance('write_candidate')

    def _verify_agents(self, value):
        current = backups.native_agents(self.client, self.workspace, self.manifest['resources'])
        if current != value['agents']:
            raise AidpProvisionConflict('Agent metadata changed outside the owned revision; no artifacts were overwritten')

    def _current_files(self, value):
        current = {}
        for path, item in value['files'].items():
            observed = backups.digest(self.client.read_artifact(self.workspace, path))
            if observed not in {item['sha256'], self.state['candidate_files'][path]}:
                raise AidpProvisionConflict('An artifact has an unowned revision; restore cannot overwrite it')
            current[path] = observed
        return current

    def _write_files(self, value, targets):
        self._verify_agents(value)
        self._current_files(value)
        for path, reference in sorted(targets.items()):
            self._write_file(path, reference, {value['files'][path]['sha256'], self.state['candidate_files'][path]})

    def _write_file(self, path, reference, allowed):
        body = self.store.get_artifact(reference)
        observed = backups.digest(self.client.read_artifact(self.workspace, path))
        if observed not in allowed:
            raise AidpProvisionConflict('The artifact revision changed immediately before overwrite')
        if observed != reference:
            self.state['mutated'] = True
            self.state['written'][path] = {'target_sha256': reference, 'state': 'SUBMITTED'}
            self.save()
            self.client.write_artifact(self.workspace, path, body)
        if backups.digest(self.client.read_artifact(self.workspace, path)) != reference:
            raise AidpProvisionPending('Exact artifact bytes are not visible yet', 'artifacts')
        self.state['written'][path] = {'target_sha256': reference, 'state': 'VERIFIED'}
        self.save()

    def write_candidate(self):
        value = self._snapshot()
        self._no_new_execution(value)
        self._write_files(value, self.state['candidate_files'])
        candidate = {**self.state['candidate_workflow'], 'schedule': value['workflow']['schedule']}
        self._publish(self._paused(candidate), value)
        self.advance('refresh_candidate')

    def refresh_candidate(self):
        self._refresh('candidate').run()
        self.advance('commit_schedule')

    def commit_schedule(self):
        value = self._snapshot()
        if self._current_files(value) != self.state['candidate_files']:
            raise AidpProvisionConflict('The complete candidate artifact revision is not verified before schedule cutover')
        target = {**self.state['candidate_workflow'], 'schedule': value['workflow']['schedule']}
        self._schedule_cutover(target, value, 'cutover_started', 'candidate')
        resources = self.manifest['resources']
        resources.update(bundle_manifest=self.state['candidate_bundle'], workflow_definition=self.state['candidate_workflow'],
                         source_revision=self.state['candidate_bundle']['consultative_revision'])
        self.manifest.update(status='active', phase='active', enabled=target['schedule']['pauseStatus'] == 'UNPAUSED',
            validation_stage='TEST_PENDING', pack_version=load_package().pack_version)
        self.manifest['operation']['phase'] = 'complete'
        self.receipt['effective_revision'] = self.manifest['candidate_revision']
        self.receipt['effective_manifest'] = deepcopy(self.manifest)
        self.save()

    def _no_new_execution(self, value):
        expected = value.get('barrier_run_keys')
        if expected is None or self._drained_run_keys() != expected:
            raise AidpProvisionConflict('Native runs crossed the artifact-only boundary; data reconciliation is required before rollback')

    def _cutover_visible(self, target, intent):
        if not self.state.get(intent) or target['schedule']['pauseStatus'] != 'UNPAUSED':
            return False
        actual = self.client._request('GET', self.job_path, phase='artifacts')
        return job_matches(actual, target)

    def _schedule_cutover(self, target, value, intent, scope):
        self._refresh(scope).verify()
        if not self._cutover_visible(target, intent):
            self._no_new_execution(value)
            self.state[intent] = True
            self.save()
            self._publish(target, value)

    def restore_quiesce(self):
        value = self._snapshot()
        self._verify_agents(value)
        self._current_files(value)
        self._no_new_execution(value)
        self._publish(self._paused(value['workflow']), value)
        self.advance('restore_files')

    def restore_files(self):
        value = self._snapshot()
        self._no_new_execution(value)
        self._write_files(value, {path: item['sha256'] for path, item in value['files'].items()})
        self._publish(self._paused(value['workflow']), value)
        self.advance('restore_refresh')

    def restore_refresh(self):
        self._refresh('restore').run()
        self.advance('restore_schedule')

    def restore_schedule(self):
        value = self._snapshot()
        targets = {path: item['sha256'] for path, item in value['files'].items()}
        if self._current_files(value) != targets:
            raise AidpProvisionConflict('Prior artifact bytes are not fully restored')
        self._schedule_cutover(value['workflow'], value, 'restore_cutover_started', 'restore')
        deployments = {key: item for key, item in self.manifest['resources'].items()
                       if key in {'documentary_deployment_key', 'test_deployment_key'}}
        self.manifest['resources'] = deepcopy(value['previous']['resources'])
        self.manifest['resources'].update(deployments)
        self.manifest.update(phase='restored', enabled=value['workflow']['schedule']['pauseStatus'] == 'UNPAUSED',
                             validation_stage=value['previous']['validation_stage'])
        self.manifest['operation']['phase'] = 'complete'
        self.receipt['effective_revision'] = value['previous']['candidate_revision']
        self.receipt['effective_manifest'] = deepcopy(value['previous'])
        self.receipt['effective_manifest']['resources'] = deepcopy(self.manifest['resources'])
        self.receipt['effective_manifest']['enabled'] = self.manifest['enabled']
        status = 'rollback_complete' if self.manifest['operation']['type'] == 'rollback' else 'update_failed_restored'
        self.manifest['status'] = status
        self.receipt['outcome'] = {**self.receipt.get('outcome', {}), 'status': status}
        self.save()

    def _failure(self, error):
        code = hashlib.sha256((type(error).__name__ + ':' + str(error)).encode()).hexdigest()[:16]
        self.receipt.setdefault('failure', {'error_code': code, 'phase': self.manifest['phase'],
            'operation_id': self.manifest['operation']['operation_id'], 'type': self.manifest['operation']['type']})
        self.manifest['error_code'] = self.receipt['failure']['error_code']

    def _recover(self, error):
        _, current = self.store.load()
        if current != self.client.receipt_revision:
            raise AidpProvisionConflict('Receipt changed concurrently; recovery ownership is not held')
        self.store.heartbeat()
        self._failure(error)
        if not self.state.get('mutated'):
            self.manifest['status'] = 'error'
            self.save()
            raise error
        self.receipt['outcome'] = {'status': 'pending',
            'failed_operation_id': self.receipt['failure']['operation_id'], 'failed_operation_type': self.receipt['failure']['type']}
        self.advance('restore_quiesce')

    def _restore_failed(self, error):
        self._failure(error)
        self.receipt['restore_error_code'] = hashlib.sha256((type(error).__name__ + ':' + str(error)).encode()).hexdigest()[:16]
        self.manifest['status'] = 'restore_failed'
        self.receipt['outcome'] = {**self.receipt.get('outcome', {}), 'status': 'restore_failed'}
        self.save()

    def _drive(self):
        phases = {'prepare_artifacts': self.prepare, 'quiesce': self.quiesce,
            'write_candidate': self.write_candidate, 'refresh_candidate': self.refresh_candidate,
            'commit_schedule': self.commit_schedule, 'restore_quiesce': self.restore_quiesce,
            'restore_files': self.restore_files, 'restore_refresh': self.restore_refresh, 'restore_schedule': self.restore_schedule}
        while self.manifest['phase'] in phases:
            phases[self.manifest['phase']]()
        if self.manifest['phase'] not in {'active', 'restored'}:
            raise AidpProvisionConflict('The artifact operation has an unsupported phase')

    def run(self):
        try:
            self._drive()
        except AidpProvisionPending:
            raise
        except Exception as error:
            if self.manifest['phase'].startswith('restore_'):
                self._restore_failed(error)
                return
            self._recover(error)
            try:
                self._drive()
            except AidpProvisionPending:
                raise
            except Exception as restore_error:
                self._restore_failed(restore_error)
