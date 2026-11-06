"""Check the shipped Terraform with real 1.5.7 and cached providers, without OCI.

Only root .tf files and the lockfile enter the isolated directory. Modern mock
tests are deliberately excluded: Terraform 1.5.7 cannot load their test syntax.
"""

from argparse import ArgumentParser
from contextlib import contextmanager
import hashlib
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import json
import os
from pathlib import Path
import shutil
import subprocess
import tempfile
import threading

from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import rsa


ROOT = Path(__file__).resolve().parents[1]
BASE = {
    'tenancy_ocid': 'ocid1.tenancy.oc1..' + 'a' * 32,
    'compartment_ocid': 'ocid1.compartment.oc1..' + 'c' * 32,
    'region': 'us-chicago-1', 'home_region': 'us-ashburn-1',
    'objectstorage_namespace': 'fixture_namespace', 'deployment_suffix': 'compat157',
    'identity_domain_id': 'ocid1.domain.oc1..fixture',
    'admin_user_ocid': 'ocid1.user.oc1..fixture',
    'artifacts_mode': 'new', 'artifacts_bucket_name': 'terraform-compat-fixture',
    'model_id': 'ocid1.generativeaimodel.oc1.us-chicago-1.fixture',
    'aidp_mode': 'new', 'autonomous_database_mode': 'new',
    'autonomous_database_admin_password': 'TestOnlyPassword26!',
    'existing_ai_data_platform_ocid': 'ocid1.aidataplatform.oc1.us-chicago-1.fixture',
    'existing_workspace_key': '11111111-1111-4111-8111-111111111111',
}
NEW_CREATES = {
    'oci_ai_data_platform_ai_data_platform.governance[0]',
    'oci_identity_policy.aidp_service[0]', 'time_sleep.aidp_iam_propagation[0]',
    'oci_objectstorage_bucket.artifacts[0]', 'oci_database_autonomous_database.memory[0]',
}
EXISTING_CREATES = {'oci_objectstorage_bucket.artifacts[0]', 'oci_database_autonomous_database.memory[0]'}


class NetworkDenied(BaseHTTPRequestHandler):
    def reject(self):
        self.server.attempts.append(self.command)
        self.send_response(502)
        self.end_headers()

    do_CONNECT = reject
    do_GET = reject
    do_POST = reject

    def log_message(self, *_args):
        pass


@contextmanager
def rejecting_proxy():
    server = ThreadingHTTPServer(('127.0.0.1', 0), NetworkDenied)
    server.attempts = []
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        yield server
    finally:
        server.shutdown()
        server.server_close()
        thread.join()


def isolated_environment(directory, proxy):
    home = directory / 'home'
    home.mkdir()
    environment = {name: os.environ[name] for name in ('PATH', 'SYSTEMROOT', 'WINDIR') if name in os.environ}
    environment.update(HOME=str(home), USERPROFILE=str(home), APPDATA=str(home), LOCALAPPDATA=str(home),
        TMP=str(directory), TEMP=str(directory), TMPDIR=str(directory),
        TF_CLI_CONFIG_FILE=str(directory / 'terraform.rc'), TF_DATA_DIR=str(directory / '.terraform'),
        TF_IN_AUTOMATION='1', TF_INPUT='0', CHECKPOINT_DISABLE='1',
        OCI_CONFIG_FILE=str(directory / 'fixture-config'), OCI_CONFIG_PROFILE='DEFAULT')
    endpoint = 'http://127.0.0.1:' + str(proxy.server_address[1])
    for name in ('HTTP_PROXY', 'HTTPS_PROXY', 'ALL_PROXY', 'http_proxy', 'https_proxy', 'all_proxy'):
        environment[name] = endpoint
    environment.update(NO_PROXY='', no_proxy='')
    return environment


def fixture_credentials(directory):
    key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    path = directory / 'fixture-key.pem'
    path.write_bytes(key.private_bytes(serialization.Encoding.PEM,
        serialization.PrivateFormat.TraditionalOpenSSL, serialization.NoEncryption()))
    public = key.public_key().public_bytes(serialization.Encoding.DER, serialization.PublicFormat.SubjectPublicKeyInfo)
    digest = hashlib.md5(public).hexdigest()
    fingerprint = ':'.join(digest[i:i + 2] for i in range(0, 32, 2))
    user = 'ocid1.user.oc1..' + 'b' * 32
    (directory / 'fixture-config').write_text('[DEFAULT]\nuser=' + user + '\ntenancy=' + BASE['tenancy_ocid']
        + '\nfingerprint=' + fingerprint + '\nkey_file=' + str(path) + '\nregion=us-chicago-1\n', encoding='utf-8')
    # Override authentication only. Resource expressions and guards remain exact
    # copies of the shipped root configuration, never reimplemented in this test.
    credentials = '\n'.join('  ' + name + ' = ' + json.dumps(value) for name, value in {
        'tenancy_ocid': BASE['tenancy_ocid'], 'user_ocid': user,
        'fingerprint': fingerprint, 'private_key_path': path.as_posix(), 'auth': 'APIKey'}.items())
    (directory / 'fixture_override.tf').write_text('provider "oci" {\n' + credentials + '\n}\n'
        + 'provider "oci" {\n  alias = "home"\n' + credentials + '\n}\n', encoding='utf-8')


def prepare(directory, provider_cache):
    for source in (ROOT / 'terraform').glob('*.tf'):
        shutil.copyfile(source, directory / source.name)
    shutil.copyfile(ROOT / 'terraform/.terraform.lock.hcl', directory / '.terraform.lock.hcl')
    mirror = provider_cache.resolve().as_posix()
    if not provider_cache.is_dir():
        raise RuntimeError('The installed provider cache is required; this check never downloads dependencies')
    (directory / 'terraform.rc').write_text('provider_installation {\n  filesystem_mirror {\n'
        + '    path = ' + json.dumps(mirror) + '\n  }\n}\n', encoding='utf-8')
    fixture_credentials(directory)


def command(binary, directory, environment, arguments):
    try:
        return subprocess.run([str(binary), *arguments], cwd=directory, env=environment,
            stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, timeout=45)
    except subprocess.TimeoutExpired:
        raise RuntimeError('The offline Terraform command timed out') from None


def events(completed):
    parsed = []
    for line in completed.stdout.splitlines():
        try:
            parsed.append(json.loads(line))
        except json.JSONDecodeError:
            continue
    return parsed


def require_success(completed, stage):
    if completed.returncode:
        raise RuntimeError(stage + ' failed; provider diagnostics were withheld from console output')


def cases():
    return [
        ('new-platform-bucket-memory', {}, NEW_CREATES),
        ('existing-platform-new-memory', {'aidp_mode': 'existing'}, EXISTING_CREATES),
        ('missing-platform', {'aidp_mode': 'existing', 'existing_ai_data_platform_ocid': ''}, 'An explicit AIDP OCID'),
        ('invalid-platform', {'aidp_mode': 'existing', 'existing_ai_data_platform_ocid': 'platform-name'}, 'An explicit AIDP OCID'),
        ('missing-workspace', {'aidp_mode': 'existing', 'existing_workspace_key': ''}, 'An exact canonical workspace UUID'),
        ('invalid-workspace', {'aidp_mode': 'existing', 'existing_workspace_key': 'workspace-name'}, 'An exact canonical workspace UUID'),
        ('missing-memory-id', {'autonomous_database_mode': 'existing', 'existing_autonomous_database_ocid': ''}, 'existing_autonomous_database_ocid is required'),
        ('invalid-memory-id', {'autonomous_database_mode': 'existing', 'existing_autonomous_database_ocid': 'database-name'}, 'existing_autonomous_database_ocid is required'),
        ('new-empty-password', {'autonomous_database_admin_password': ''}, 'A new database requires'),
        ('short-password', {'autonomous_database_admin_password': 'Test26!'}, 'ADMIN password'),
        ('password-no-lowercase', {'autonomous_database_admin_password': 'TESTONLYPASSWORD26!'}, 'ADMIN password'),
        ('password-no-number', {'autonomous_database_admin_password': 'TestOnlyPassword!'}, 'ADMIN password'),
        ('unsupported-version', {'autonomous_database_version': '23ai'}, 'Governance memory requires Oracle AI Database 26ai'),
        ('unsupported-workload', {'autonomous_database_workload': 'OLTP'}, 'Governance memory requires the DW workload'),
    ]


def check_plan(binary, directory, environment, proxy, case):
    name, overrides, expectation = case
    inputs = directory / 'fixture-inputs.json'
    inputs.write_text(json.dumps({**BASE, **overrides}), encoding='utf-8')
    completed = command(binary, directory, environment,
        ['plan', '-refresh=false', '-lock=false', '-input=false', '-detailed-exitcode', '-json', '-var-file=' + str(inputs)])
    if proxy.attempts:
        raise RuntimeError(name + ': the provider attempted network access; offline proof failed')
    messages = events(completed)
    if isinstance(expectation, str):
        diagnostics = [item.get('diagnostic', {}).get('detail', '') for item in messages]
        if completed.returncode != 1 or not any(expectation in detail for detail in diagnostics):
            raise RuntimeError(name + ': the expected shipped guard did not reject the invalid input')
    else:
        changes = [item['change'] for item in messages if item.get('type') == 'planned_change']
        creates = {change['resource']['addr'] for change in changes if change['action'] == 'create'}
        if completed.returncode != 2 or creates != expectation or any(change['action'] != 'create' for change in changes):
            raise RuntimeError(name + ': the offline create-only plan differs from the expected resource scope')
    print(json.dumps({'case': name, 'status': 'passed', 'network_requests': 0}), flush=True)


def run(binary, provider_cache):
    base = ROOT / '.local'
    base.mkdir(exist_ok=True)
    with tempfile.TemporaryDirectory(prefix='terraform-compat-', dir=base) as work, rejecting_proxy() as proxy:
        directory = Path(work).resolve()
        if not directory.is_relative_to(base.resolve()):
            raise RuntimeError('The isolated check must remain inside the ignored project workspace')
        environment = isolated_environment(directory, proxy)
        version = command(binary, directory, environment, ['version', '-json'])
        require_success(version, 'Terraform version')
        if json.loads(version.stdout)['terraform_version'] != '1.5.7':
            raise RuntimeError('This regression check requires the real Terraform 1.5.7 executable')
        prepare(directory, provider_cache)
        initialized = command(binary, directory, environment, ['init', '-backend=false', '-input=false', '-lockfile=readonly', '-no-color'])
        require_success(initialized, 'Offline locked provider initialization')
        require_success(command(binary, directory, environment, ['validate', '-no-color']), 'Terraform 1.5.7 validate')
        for case in cases():
            check_plan(binary, directory, environment, proxy, case)
        if proxy.attempts:
            raise RuntimeError('A Terraform command attempted network access')
    print(json.dumps({'terraform_version': '1.5.7', 'cases': len(cases()), 'status': 'passed',
        'network_requests': 0, 'limitation': 'Positive existing-database lookup requires OCI and is covered by modern provider mocks only.'}))


def executable_path(value):
    if not value.is_absolute() and value.parent == Path('.'):
        found = shutil.which(str(value))
        if not found:
            raise RuntimeError('The requested Terraform executable is not available on PATH')
        value = Path(found)
    if not value.is_file():
        raise RuntimeError('The Terraform executable must resolve to a file')
    return value.resolve()


def main():
    parser = ArgumentParser(description=__doc__)
    parser.add_argument('--terraform', type=Path, default=ROOT / '.local/terraform-1.5.7/terraform.exe')
    parser.add_argument('--provider-cache', type=Path, default=ROOT / 'terraform/.terraform/providers')
    arguments = parser.parse_args()
    try:
        run(executable_path(arguments.terraform), arguments.provider_cache.resolve())
    except (OSError, ValueError, RuntimeError) as error:
        # Never echo raw provider stdout/stderr, which may contain request metadata.
        print(json.dumps({'status': 'failed', 'reason': str(error) if isinstance(error, RuntimeError) else type(error).__name__}))
        return 1
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
