"""Operator-signed native adapter with conditional installation ownership."""
from datetime import datetime, timezone
from urllib.parse import quote
from .client import AidpClient
from .errors import AidpProvisionConflict, AidpProvisionError, AidpProvisionPending


class NativeClient(AidpClient):
    def __init__(self, settings):
        super().__init__(settings)
        self.store, self.receipt, self.receipt_revision = None, None, None

    def _request(self, method, path, **kwargs):
        if self.store and method.upper() != 'GET':
            self.store.heartbeat()
        return super()._request(method, path, **kwargs)

    def _workspace(self):
        key = getattr(self.settings, 'workspace_key', '')
        if key:
            result = self._request('GET', '/workspaces/' + quote(key, safe=''), phase='workspace')
            if result.get('key') != key:
                raise AidpProvisionConflict('The external workspace identity changed')
            return self._require_operational_state(result, {'ACTIVE'}, 'workspace', 'workspace')
        if self.settings.aidp_mode != 'new':
            raise AidpProvisionConflict('An existing platform requires an explicit workspace key')
        return super()._workspace()

    def _write_module_manifest(self, workspace_key, manifest):
        if not self.store or not self.receipt:
            raise AidpProvisionConflict('Durable installation ownership is required')
        manifest['updated_at'] = datetime.now(timezone.utc).isoformat()
        self.receipt['manifest'] = manifest
        self.store.save(self.receipt, self.receipt_revision)
        observed, revision = self.store.load()
        if observed != self.receipt:
            raise AidpProvisionConflict('The durable receipt readback differs from the intended revision')
        self.receipt_revision = revision

    def _module_manifest(self, workspace_key):
        return self.receipt.get('manifest') if self.receipt else None

    def read_artifact(self, workspace_key, path):
        body, headers = self._request('GET', '/workspaces/' + workspace_key + '/objects/' + quote(path, safe=''),
            headers={'Accept': 'application/octet-stream'}, include_headers=True, allow_not_found=True,
            raw_response=True, phase='artifacts')
        if not isinstance(body, bytes) or self._workspace_object_type(body, headers) == 'FOLDER':
            raise AidpProvisionConflict('An owned artifact has no verifiable raw file bytes')
        return body

    def write_artifact(self, workspace_key, path, content):
        if self.read_artifact(workspace_key, path) == content:
            return False
        self._request('POST', '/workspaces/' + workspace_key + '/objects', data=content,
            headers={'Accept': '*/*', 'path': path, 'type': 'FILE', 'is-overwrite': 'true',
                     'Content-Type': 'application/octet-stream'}, phase='artifacts')
        if self.read_artifact(workspace_key, path) != content:
            raise AidpProvisionPending('Exact artifact bytes are not published yet', 'artifacts')
        return True

    def _ensure_governance_bucket(self):
        # Terraform owns creation; the installer never creates/adopts a bucket.
        self.object_storage.head_bucket(self.settings.objectstorage_namespace, self.settings.artifacts_bucket_name)
        return False

    def _shared_compute(self, workspace_key):
        from .client import SHARED_COMPUTE_NAME
        from pathlib import Path
        import json
        path = '/workspaces/' + workspace_key + '/clusters'
        rows = [item for item in self._list(path, phase='workspace') if self._resource_name(item) == SHARED_COMPUTE_NAME]
        resources = self.receipt['manifest'].setdefault('resources', {})
        expected = resources.get('cluster_key')
        if len(rows) > 1 or (expected and (not rows or rows[0].get('key') != expected)):
            raise AidpProvisionConflict('The shared Spark Compute identity changed or is ambiguous')
        if rows:
            if str(rows[0].get('type') or '').upper() != 'USER':
                raise AidpProvisionConflict('Shared compute is not the expected Spark resource type')
            resources['spark_ownership'] = 'owned' if resources.get('spark_creation_submitted') else 'external'
            return self._require_operational_state(rows[0], {'ACTIVE', 'STOPPED'}, 'compute', 'workspace')
        if self.settings.aidp_mode != 'new':
            raise AidpProvisionConflict('Existing platform requires its shared Spark Compute; none was created')
        if resources.get('spark_creation_submitted'):
            raise AidpProvisionPending('Spark creation is uncertain; observe before another POST', 'workspace')
        resources['spark_creation_submitted'] = True
        self._write_module_manifest(workspace_key, self.receipt['manifest'])
        definition = json.loads((Path(__file__).parent / 'aidp/workspaces/default/compute/aidp_cluster_shared_compute.json').read_text())
        self._request('POST', path, payload=definition['payload'], phase='workspace',
            retry_scope='governance-spark:' + self.receipt['manifest']['operation']['operation_id'])
        raise AidpProvisionPending('The selected platform Spark Compute is being created', 'workspace')

    def _ensure_agent_compute(self, workspace_key):
        resources = self.receipt['manifest'].setdefault('resources', {})
        matches = [item for item in self._list('/workspaces/' + workspace_key + '/clusters', phase='agent')
                   if self._resource_name(item) == self._agent_compute_name
                   and str(item.get('type') or item.get('sourceApi') or '').upper() == 'AI_COMPUTE']
        expected = resources.get('agent_compute_key')
        if matches and (len(matches) != 1 or (expected and matches[0].get('key') != expected)
                        or (not expected and not resources.get('compute_creation_submitted'))):
            raise AidpProvisionConflict('An unowned or changed AI Compute cannot be adopted')
        if expected and not matches:
            raise AidpProvisionConflict('The recorded AI Compute is missing; replacement is forbidden')
        if not matches and resources.get('compute_creation_submitted'):
            raise AidpProvisionPending('AI Compute creation is uncertain; reconcile before another POST', 'agent')
        if not matches:
            resources['compute_creation_submitted'] = True
            self._write_module_manifest(workspace_key, self.receipt['manifest'])
        return super()._ensure_agent_compute(workspace_key)

    def _remove_failed_agent_compute(self, workspace_key, compute):
        if compute and str(compute.get('lifecycleState') or compute.get('state') or '').upper() in {'FAILED', 'CREATE_FAILED'}:
            raise AidpProvisionConflict('Failed AI Compute is retained; automatic deletion is forbidden')

    def _recover_hidden_agent_compute(self, workspace_key):
        # Name-only async history cannot prove ownership of an invisible resource.
        return None, ''

    def ensure_selected_admin(self, user_ocid):
        users, _ = self._role_principal_ocids('AI_DATA_PLATFORM_ADMIN')
        if user_ocid in users:
            return
        if self.settings.aidp_mode != 'new':
            raise AidpProvisionConflict('Existing platform administration must be granted before installation')
        if self._oci_config['user'] not in users:
            raise AidpProvisionConflict('The signing operator cannot assign platform administration')
        role = self._role('AI_DATA_PLATFORM_ADMIN')
        self._request('POST', '/roles/' + quote(role['key'], safe='') + '/actions/addMember',
            payload={'assignees': [{'type': 'USER', 'target': user_ocid}]},
            phase='permissions', retry_scope='governance-admin:' + user_ocid)
        if user_ocid not in self._role_user_ocids('AI_DATA_PLATFORM_ADMIN'):
            raise AidpProvisionPending('The selected administrator assignment is not effective yet', 'permissions')
