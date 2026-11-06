"""Execute the shipped hooks with the runner's real environment and context shapes.

OCI requests are replaced only at SDK/HTTP transport boundaries. Post-apply stops
at memory/lifecycle effects; CLI parsing, credentials, identity and results stay real.
"""

import ast
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
from types import SimpleNamespace

from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import rsa
import pytest

from tests.fixtures import runner_transport


ROOT = Path(__file__).resolve().parents[2]
OPERATOR = 'ocid1.user.oc1..runneroperatorfixture'
ADMIN = 'ocid1.user.oc1..runneradminfixture'
DOMAIN = 'ocid1.domain.oc1..runnerdomainfixture'
PLATFORM = 'ocid1.aidataplatform.oc1.us-chicago-1.runnerfixture'
DATABASE = 'ocid1.autonomousdatabase.oc1.us-chicago-1.runnerfixture'
COMPARTMENT = 'ocid1.compartment.oc1..runnerfixture'
WORKSPACE = '11111111-1111-4111-8111-111111111111'
PRIVATE_MARKER = 'TEST_ONLY_PRIVATE_PROVIDER_DETAIL'
PASSWORD = 'TestOnlyMemory26!'


@pytest.fixture(scope='module')
def rsa_fixture():
    key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    pem = key.private_bytes(serialization.Encoding.PEM, serialization.PrivateFormat.TraditionalOpenSSL,
        serialization.NoEncryption())
    public = key.public_key().public_bytes(serialization.Encoding.DER, serialization.PublicFormat.SubjectPublicKeyInfo)
    fingerprint = ':'.join(hashlib.md5(public).hexdigest()[i:i + 2] for i in range(0, 32, 2))
    return pem, fingerprint


def context_for(phase, mode='new', operation='install'):
    inputs = {'aidp_mode': mode, 'admin_user_ocid': ADMIN, 'identity_domain_id': DOMAIN,
        'artifacts_mode': 'new', 'artifacts_bucket_name': 'runner-artifacts',
        'model_id': 'ocid1.generativeaimodel.oc1.us-chicago-1.runnerfixture',
        'governance_operation': operation, 'autonomous_database_mode': 'new',
        'autonomous_database_version': '26ai', 'autonomous_database_workload': 'DW'}
    if mode == 'existing':
        inputs.update(existing_ai_data_platform_ocid=PLATFORM, existing_workspace_key=WORKSPACE)
    document = {'schema_version': 1, 'project_id': 'aidp-ai-data-governance',
        'deployment_id': 'runner-operation', 'source': {'repository': 'https://github.com/jgangini/aidp-ai-data-gobernance',
        'ref': 'v0.3.0-runner-test', 'commit_sha': 'a' * 40}, 'region': 'us-chicago-1', 'inputs': inputs}
    if phase == 'preflight':
        document.update(compartment='runner-new-compartment' if mode == 'new' else COMPARTMENT,
            compartment_mode='new' if mode == 'new' else 'existing')
    else:
        document['compartment'] = {'id': COMPARTMENT, 'name': 'runner-compartment'}
        document['terraform_outputs'] = {**inputs, 'ai_data_platform_ocid': PLATFORM,
            'workspace_key': WORKSPACE, 'workspace_name': 'runner-workspace',
            'objectstorage_namespace': 'runner_namespace', 'autonomous_database_id': DATABASE,
            'resource_ownership': {'platform': 'owned' if mode == 'new' else 'external',
                'workspace': 'owned' if mode == 'new' else 'external', 'artifacts': 'owned', 'memory_database': 'owned'}}
    return document


def stage_runner(tmp_path, rsa_fixture, phase, *, mode='new', outcome='active', operation='install'):
    stage = tmp_path / 'repository'
    stage.mkdir()
    shutil.copytree(ROOT / 'src', stage / 'src', ignore=shutil.ignore_patterns('__pycache__', '*.pyc', '.oci', '.local'))
    for relative in ('m_preflight.py', 'hooks/post_apply.py', 'deploy-studio.json'):
        target = stage / 'terraform' / relative
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(ROOT / 'terraform' / relative, target)
    shutil.copyfile(ROOT / 'tests/fixtures/runner_transport.py', stage / 'runner_transport.py')
    (stage / 'sitecustomize.py').write_text('from runner_transport import install\ninstall()\n', encoding='utf-8')
    case = {'phase': phase, 'outcome': outcome, 'private_marker': PRIVATE_MARKER,
        'admin_user_ocid': ADMIN, 'operator_user_ocid': OPERATOR, 'workspace_key': WORKSPACE,
        'compartment_id': COMPARTMENT, 'database_id': DATABASE}
    (stage / 'runner-case.json').write_text(json.dumps(case), encoding='utf-8')
    document = context_for(phase, mode, operation)
    context = tmp_path / 'context.json'
    context.write_text(json.dumps(document), encoding='utf-8')
    secrets = tmp_path / 'secrets.json'
    secrets.write_text(json.dumps({'inputs': {'autonomous_database_admin_password': PASSWORD}}), encoding='utf-8')
    pem, fingerprint = rsa_fixture
    key = tmp_path / 'fixture-key.pem'
    key.write_bytes(pem)
    config = tmp_path / 'fixture-config'
    config.write_text('[DEFAULT]\nuser=' + OPERATOR + '\ntenancy=ocid1.tenancy.oc1..runnerfixture\nfingerprint='
        + fingerprint + '\nkey_file=' + str(key) + '\nregion=us-chicago-1\n', encoding='utf-8')
    result = tmp_path / 'result.json'
    result.write_bytes(b'')
    result_variable = 'DEPLOY_STUDIO_RESULT' if phase == 'preflight' else 'DEPLOY_STUDIO_OUTPUT'
    environment = {'PATH': os.environ.get('PATH', ''), 'PYTHONUNBUFFERED': '1', 'PYTHONPATH': str(stage),
        'DEPLOY_STUDIO_CONTEXT': str(context), 'DEPLOY_STUDIO_SECRETS': str(secrets),
        result_variable: str(result), 'DEPLOY_STUDIO_OCI_CONFIG': str(config), 'DEPLOY_STUDIO_OCI_KEY': str(key)}
    if os.name == 'nt' and os.environ.get('SYSTEMROOT'):
        environment['SYSTEMROOT'] = os.environ['SYSTEMROOT']
    return SimpleNamespace(root=stage, document=document, context=context, case=case, result=result,
        result_variable=result_variable, environment=environment, config=config, key=key)


def execute(runner, phase):
    python = os.environ.get('GOVERNANCE_RUNNER_PYTHON', sys.executable)
    script = 'terraform/m_preflight.py' if phase == 'preflight' else 'terraform/hooks/post_apply.py'
    return subprocess.run([python, script], cwd=runner.root, env=runner.environment,
        stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, timeout=60)


def read_result(runner, completed):
    assert runner.result.stat().st_size, 'The actual runner requires JSON in its phase-specific output file'
    result = json.loads(runner.result.read_text('utf-8'))
    assert isinstance(result, dict)
    assert PRIVATE_MARKER not in str(result) + completed.stdout + completed.stderr
    assert PASSWORD not in str(result) + completed.stdout + completed.stderr
    assert 'PRIVATE KEY' not in str(result) + completed.stdout + completed.stderr
    assert 'Error in sitecustomize' not in completed.stderr
    return result


@pytest.mark.parametrize('mode', ['new', 'existing'])
def test_actual_preflight_entrypoint_returns_json_for_real_string_compartment_contract(mode, tmp_path, rsa_fixture):
    runner = stage_runner(tmp_path, rsa_fixture, 'preflight', mode=mode)
    completed = execute(runner, 'preflight')
    result = read_result(runner, completed)
    assert completed.returncode == 0, result
    assert result['inputs'] == {'home_region': 'us-chicago-1'}
    assert result['events'][0]['status'] == 'passed'
    calls = json.loads((runner.root / 'transport-calls.json').read_text())
    assert 'signed-http' in calls
    assert 'lifecycle-boundary' not in calls


@pytest.mark.parametrize('phase', ['preflight', 'post_apply'])
def test_installation_form_without_an_operation_uses_the_install_default(phase, tmp_path, rsa_fixture):
    runner = stage_runner(tmp_path, rsa_fixture, phase)
    del runner.document['inputs']['governance_operation']
    runner.document.get('terraform_outputs', {}).pop('governance_operation', None)
    runner.context.write_text(json.dumps(runner.document))
    runner.case['expected_command'] = 'install'
    (runner.root / 'runner-case.json').write_text(json.dumps(runner.case))
    completed = execute(runner, phase)
    result = read_result(runner, completed)
    assert completed.returncode == 0, result
    if phase == 'post_apply':
        assert result['outputs']['governance_status'] == 'active'


class ConsumerStore:
    def __init__(self):
        self.events = []
        self.deployment = {}

    def add_event(self, deployment, level, message):
        self.events.append((level, message))

    def get(self, deployment):
        return {'id': deployment}

    def save(self, deployment):
        self.deployment = deployment

    def put_artifact_bytes(self, *_args):
        raise AssertionError('The tested hook does not return artifacts')


@pytest.mark.parametrize('outcome,operation,code,level', [
    ('active', 'install', 0, 'info'), ('update_failed_restored', 'update', 1, 'error'),
    ('rollback_complete', 'rollback', 0, 'info'), ('restore_failed', 'resume', 1, 'error'),
    ('pending', 'resume', 3, 'warning'),
])
def test_post_apply_entrypoint_outputs_pass_the_exact_ctn_consumer_snapshot(outcome, operation, code, level, tmp_path, rsa_fixture):
    runner = stage_runner(tmp_path, rsa_fixture, 'post_apply', mode='existing', outcome=outcome, operation=operation)
    completed = execute(runner, 'post_apply')
    result = read_result(runner, completed)
    assert completed.returncode == code, result
    assert result['outputs']['governance_status'] == outcome
    assert result['outputs']['memory_status'] == 'READY'
    manifest = json.loads((runner.root / 'terraform/deploy-studio.json').read_text('utf-8'))
    store = ConsumerStore()
    source = SimpleNamespace(manifest=SimpleNamespace(outputs=manifest['outputs'], artifacts=manifest['artifacts']))
    consumed = runner_transport._apply_hook_result(store=store, deployment_id='test', source=source,
        result=result, secret_values={PRIVATE_MARKER, PASSWORD})
    assert consumed == result['outputs']
    assert store.events[0][0] == level
    assert store.deployment['hook_outputs'] == result['outputs']
    calls = json.loads((runner.root / 'transport-calls.json').read_text())
    assert 'memory-boundary' in calls and 'lifecycle-boundary' in calls and 'signed-http' in calls


@pytest.mark.parametrize('phase', ['preflight', 'post_apply'])
@pytest.mark.parametrize('failure', ['missing-context', 'malformed-json', 'wrong-compartment-shape',
    'missing-config', 'missing-key', 'invalid-config', 'invalid-key', 'provider-error'])
def test_real_entrypoints_fail_closed_in_the_output_file_without_credential_fallback(phase, failure, tmp_path, rsa_fixture):
    runner = stage_runner(tmp_path, rsa_fixture, phase, mode='existing')
    if failure == 'missing-context':
        del runner.environment['DEPLOY_STUDIO_CONTEXT']
    elif failure == 'malformed-json':
        runner.context.write_text('{ malformed ' + PRIVATE_MARKER)
    elif failure == 'wrong-compartment-shape':
        runner.document['compartment'] = {'id': COMPARTMENT} if phase == 'preflight' else COMPARTMENT
        runner.context.write_text(json.dumps(runner.document))
    elif failure in {'missing-config', 'missing-key'}:
        del runner.environment['DEPLOY_STUDIO_OCI_CONFIG' if failure == 'missing-config' else 'DEPLOY_STUDIO_OCI_KEY']
    elif failure == 'invalid-config':
        runner.config.write_text('[DEFAULT]\ninvalid=' + PRIVATE_MARKER)
    elif failure == 'invalid-key':
        runner.key.write_text(PRIVATE_MARKER)
    else:
        runner.case['provider_error'] = True
        (runner.root / 'runner-case.json').write_text(json.dumps(runner.case))
    completed = execute(runner, phase)
    result = read_result(runner, completed)
    assert completed.returncode != 0
    assert result.get('inputs' if phase == 'preflight' else 'outputs') == {}
    assert result['events'][0].get('status' if phase == 'preflight' else 'level') == ('failed' if phase == 'preflight' else 'error')


@pytest.mark.parametrize('phase', ['preflight', 'post_apply'])
def test_an_output_variable_from_the_other_phase_is_never_used_as_fallback(phase, tmp_path, rsa_fixture):
    runner = stage_runner(tmp_path, rsa_fixture, phase, mode='existing')
    destination = runner.environment.pop(runner.result_variable)
    runner.environment['DEPLOY_STUDIO_OUTPUT' if phase == 'preflight' else 'DEPLOY_STUDIO_RESULT'] = destination
    completed = execute(runner, phase)
    assert runner.result.read_bytes() == b''
    with pytest.raises(json.JSONDecodeError):
        json.loads(runner.result.read_text())
    assert json.loads(completed.stdout)
    assert PRIVATE_MARKER not in completed.stdout + completed.stderr


def test_consumer_snapshot_matches_its_reviewed_source_hash():
    source = Path(runner_transport.__file__).read_text('utf-8')
    names = {'_apply_hook_events', '_apply_hook_result'}
    pieces = [ast.get_source_segment(source, node) for node in ast.parse(source).body
        if isinstance(node, ast.FunctionDef) and node.name in names]
    assert len(pieces) == 2
    assert hashlib.sha256(('\n\n'.join(pieces) + '\n').encode()).hexdigest() == runner_transport.CTN_RESULT_SOURCE_SHA256
