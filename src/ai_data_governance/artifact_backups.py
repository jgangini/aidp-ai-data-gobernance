"""Versioned, content-addressed snapshots of the exact owned maintenance surface."""
import ast
from copy import deepcopy
import hashlib
import json
from pathlib import PurePosixPath
from .deployment_bundle import ARTIFACT_ROOT, BOOTSTRAP_PATH, MANIFEST_PATH
from .deploy_studio_install import job_matches
from .errors import AidpProvisionConflict


def digest(body):
    return hashlib.sha256(body).hexdigest()


def artifact_path(path):
    value = PurePosixPath(path)
    if not path.startswith(ARTIFACT_ROOT + '/') or value.as_posix() != path or '..' in value.parts or '\\' in path:
        raise AidpProvisionConflict('Artifact path is outside the owned Governance publication root')
    return path


def agent_paths():
    return {kind: ARTIFACT_ROOT + '/agents/' + folder for kind, folder in
            (('documentary', 'documentation'), ('test', 'governance'))}


def descriptors(files):
    result = {}
    for kind, root in agent_paths().items():
        entry = root + ('/documentation_agent.py' if kind == 'documentary' else '/governance_agent.py')
        result[root + '/agent-manifest.json'] = json.dumps({'schema_version': 1, 'module_id': 'ai_data_governance',
            'deployment_stage': 'TEST', 'entry_sha256': digest(files[entry])}).encode()
    return result


def native_agents(client, workspace, resources):
    definitions = {}
    for kind, root in agent_paths().items():
        key = resources['documentation_agent_key' if kind == 'documentary' else 'agent_key']
        value = client._request('GET', '/workspaces/' + workspace + '/agents/' + key, phase='artifacts')
        _verify_agent(value, key, root, resources['agent_compute_key'], kind)
        definitions[kind] = {name: deepcopy(value[name]) for name in
            ('key', 'pathInfo', 'type', 'displayName', 'entryFilePath', 'dependenciesFilePath', 'computeKey', 'sessionConfig')}
    return definitions


def _verify_agent(value, key, root, compute, kind):
    entry = 'documentation_agent.py' if kind == 'documentary' else 'governance_agent.py'
    expected = {'key': key, 'pathInfo': root, 'type': 'CODE', 'computeKey': compute,
        'entryFilePath': root + '/' + entry, 'dependenciesFilePath': root + '/requirements.txt',
        'sessionConfig': {'variables': {}},
        'displayName': 'ai_data_governance_sync_master_catalog' if kind == 'documentary' else 'ai_data_governance'}
    if not isinstance(value, dict) or any(value.get(name) != item for name, item in expected.items()):
        raise AidpProvisionConflict('The owned native agent definition or compute identity changed')


def workflow(client, workspace, manifest):
    resources = manifest['resources']
    path = '/workspaces/' + workspace + '/jobs/' + resources['workflow_key']
    actual = client._request('GET', path, phase='artifacts')
    schedule = actual.get('schedule')
    if not isinstance(schedule, dict) or schedule.get('pauseStatus') not in {'PAUSED', 'UNPAUSED'}:
        raise AidpProvisionConflict('The existing workflow schedule is not verifiable')
    expected = {**resources['workflow_definition'], 'schedule': schedule}
    if not job_matches(actual, expected):
        raise AidpProvisionConflict('Recorded workflow drift prevents artifact maintenance')
    return deepcopy(expected)


def run_keys(client, workspace, resources):
    rows = client._list('/workspaces/' + workspace + '/jobRuns', params={'jobKey': resources['workflow_key']})
    if any(not isinstance(row.get('key'), str) or not row['key'] for row in rows):
        raise AidpProvisionConflict('Incomplete native run identities prevent a reversible boundary')
    return sorted(row['key'] for row in rows)


def _prior_files(client, workspace, manifest):
    known = manifest['resources']['bundle_manifest']
    expected = known['files']
    files = {artifact_path(path): client.read_artifact(workspace, path) for path in expected}
    if any(digest(body) != expected[path]['sha256'] for path, body in files.items()):
        raise AidpProvisionConflict('Installed artifact bytes differ from the recorded revision')
    raw_manifest = client.read_artifact(workspace, MANIFEST_PATH)
    if json.loads(raw_manifest) != known:
        raise AidpProvisionConflict('The installed bundle manifest differs from the receipt')
    files[MANIFEST_PATH] = raw_manifest
    for path, expected_body in descriptors(files).items():
        body = client.read_artifact(workspace, path)
        if json.loads(body) != json.loads(expected_body):
            raise AidpProvisionConflict('The owned agent descriptor differs from its recorded entry')
        files[path] = body
    return files


def snapshot(client, store, workspace, receipt, deployments):
    previous = receipt['previous']
    files = _prior_files(client, workspace, previous)
    value = {'schema_version': 1, 'identity': receipt['identity'], 'previous': deepcopy(previous),
        'workflow': workflow(client, workspace, previous),
        'agents': native_agents(client, workspace, previous['resources']),
        'deployments': deployments,
        'run_keys': run_keys(client, workspace, previous['resources']),
        'files': {path: {'sha256': store.put_artifact(body), 'size_bytes': len(body)} for path, body in files.items()}}
    body = json.dumps(value, sort_keys=True, separators=(',', ':')).encode()
    reference = store.put_artifact(body)
    return reference, value


def load_snapshot(store, reference, receipt):
    value = json.loads(store.get_artifact(reference))
    if value.get('schema_version') != 1 or value.get('identity') != receipt['identity']:
        raise AidpProvisionConflict('Artifact snapshot ownership differs from this installation')
    if value['previous'] != receipt['previous']:
        raise AidpProvisionConflict('Artifact snapshot does not match the retained prior revision')
    for path, item in value['files'].items():
        artifact_path(path)
        if len(store.get_artifact(item['sha256'])) != item['size_bytes']:
            raise AidpProvisionConflict('Artifact snapshot length differs')
    return value


def _bootstrap_contract(body):
    tree = ast.parse(body)
    assignments = {node.targets[0].id: node.value for node in tree.body
        if isinstance(node, ast.Assign) and isinstance(node.targets[0], ast.Name)}
    return {key: ast.literal_eval(assignments[key]) for key in ('MODEL', 'NAMESPACE', 'STORAGE_ROOT')}


def compatible_candidate(store, value, bundle):
    files = {**bundle['files'], **descriptors(bundle['files'])}
    if set(files) != set(value['files']):
        raise AidpProvisionConflict('Adding or deleting artifacts needs a separately reversible contract')
    prior = store.get_artifact(value['files'][BOOTSTRAP_PATH]['sha256'])
    if _bootstrap_contract(prior) != _bootstrap_contract(files[BOOTSTRAP_PATH]):
        raise AidpProvisionConflict('Schema or storage changes require a separate data migration before maintenance')
    return files
