"""Lease-bound entrypoint for installation and reversible artifact maintenance."""
import hashlib
import json
from copy import deepcopy
from pathlib import Path
from .deploy_studio_install import GovernanceInstaller
from .errors import AidpProvisionConflict, AidpProvisionError, AidpProvisionPending
from .operation_receipts import admit, new_install
from .package_loader import load_package
from .runtime_identity import identity_hash


def candidate_revision():
    root = Path(__file__).resolve().parent
    metadata = json.loads((root / 'package/lab.json').read_text())
    load_package()
    return hashlib.sha256(json.dumps(metadata['runtime_files'], sort_keys=True).encode()).hexdigest()


def run_operation(client, store, *, admin, domain, operation_id, command):
    if command not in {'install', 'resume', 'update', 'redeploy', 'rollback'}:
        raise AidpProvisionConflict('Unsupported Governance operation')
    request = {'id': operation_id, 'command': command, 'revision': candidate_revision(),
        'source': getattr(client.settings, 'release_source', {})}
    workspace = client._governance_workspace()
    identity = {'platform_id': client.settings.aidp_platform_id, 'workspace_key': workspace,
        'admin_user_ocid': admin, 'identity_domain_id': domain, 'operator_identity': identity_hash(client._oci_config)}
    with store.acquire(operation_id):
        receipt, etag = store.load()
        execute = admit(receipt, identity, request) if receipt else True
        receipt = receipt or new_install(client, workspace, identity, request)
        if not execute:
            return receipt
        client.store, client.receipt, client.receipt_revision = store, receipt, etag
        client._write_module_manifest(workspace, receipt['manifest'])
        return _execute(client, store, workspace)


def _execute(client, store, workspace):
    manifest = client.receipt['manifest']
    if manifest['operation']['type'] == 'install':
        GovernanceInstaller(client, workspace, manifest, pending=AidpProvisionPending, error=AidpProvisionError).reconcile()
        if manifest['phase'] != 'active' or manifest['status'] != 'active':
            raise AidpProvisionConflict('The installation has no supported completed phase')
        client.receipt['effective_manifest'] = deepcopy(manifest)
        client._write_module_manifest(workspace, manifest)
    else:
        from .maintenance import ArtifactMaintenance
        ArtifactMaintenance(client, store, workspace).run()
    return client.receipt
