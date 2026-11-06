"""Subprocess-only OCI transport fixture; application CLI and bindings stay real."""

from __future__ import annotations

import base64
import importlib.abc
import io
import json
from pathlib import Path
import re
import socket
import sys
from types import SimpleNamespace
from typing import Any
from urllib.parse import urlsplit


class AgentImportsBlocked(importlib.abc.MetaPathFinder):
    def find_spec(self, fullname, path=None, target=None):
        if fullname.split('.')[0] in {'langgraph', 'langchain_core', 'aidputils'}:
            raise ModuleNotFoundError('Agent runtime libraries are unavailable in the Deploy Studio runner')


def install():
    root = Path(__file__).resolve().parent
    case = json.loads((root / 'runner-case.json').read_text('utf-8'))
    sys.meta_path.insert(0, AgentImportsBlocked())

    def blocked_network(*_args, **_kwargs):
        raise AssertionError('Unexpected network use outside the fixture transport')

    socket.create_connection = blocked_network
    socket.getaddrinfo = blocked_network
    socket.socket.connect = blocked_network
    socket.socket.connect_ex = blocked_network
    import oci
    from oci._vendor import requests

    sys.path.insert(0, str(root / 'src'))
    calls = []

    def record(kind):
        calls.append(kind)
        (root / 'transport-calls.json').write_text(json.dumps(calls), encoding='utf-8')

    def provider_guard():
        if case.get('provider_error'):
            raise RuntimeError('Provider rejected request ' + case['private_marker'])

    class Identity:
        def __init__(self, config, **kwargs):
            record('sdk-identity')

        def get_domain(self, domain):
            provider_guard()
            return SimpleNamespace(data=SimpleNamespace(id=domain, lifecycle_state='ACTIVE',
                url='https://fixture.identity.oraclecloud.com'))

        def get_tenancy(self, tenancy):
            provider_guard()
            return SimpleNamespace(data=SimpleNamespace(home_region_key='ORD'))

        def list_regions(self):
            return SimpleNamespace(data=[SimpleNamespace(key='ORD', name='us-chicago-1')])

    class Objects:
        def __init__(self, config, **kwargs):
            record('sdk-objects')

        def get_object(self, *_args, **_kwargs):
            record('get-owned-receipt')
            raise oci.exceptions.ServiceError(404, 'ObjectNotFound', {}, 'Fixture object is absent')

        def get_namespace(self):
            return SimpleNamespace(data='fixture_namespace')

        def list_objects(self, *_args, **_kwargs):
            record('list-owned-receipts')
            return SimpleNamespace(data=SimpleNamespace(objects=[], next_start_with=None), headers={})

    class Platform:
        def __init__(self, config, **kwargs):
            record('sdk-platform')

        def get_ai_data_platform(self, platform):
            return SimpleNamespace(data=SimpleNamespace(id=platform, lifecycle_state='ACTIVE',
                ai_feature_status='DISABLED', compartment_id=case['compartment_id']), headers={'etag': 'fixture-etag'})

    class Database:
        def __init__(self, config, **kwargs):
            record('sdk-database')

        def get_autonomous_database(self, database):
            return SimpleNamespace(data=SimpleNamespace(id=database, lifecycle_state='AVAILABLE',
                db_version='26ai', db_workload='DW'))

    def response(status, body):
        result = requests.Response()
        result.status_code = status
        result._content = json.dumps(body).encode()
        result.headers = {}
        return result

    def request(session, method, url, **kwargs):
        record('signed-http')
        provider_guard()
        assert isinstance(kwargs.get('auth'), oci.signer.Signer)
        assert method.upper() == 'GET', 'Only readonly HTTP is expected at this test boundary'
        path = urlsplit(url).path
        if path.endswith('/admin/v1/Users'):
            user = json.loads(kwargs['params']['filter'].removeprefix('ocid eq '))
            return response(200, {'totalResults': 1, 'Resources': [{'id': 'fixture-user', 'ocid': user, 'active': True, 'groups': []}]})
        if path.endswith('/roles'):
            return response(200, {'items': [{'key': 'fixture-admin-role', 'displayName': 'AI_DATA_PLATFORM_ADMIN'}]})
        if path.endswith('/roles/fixture-admin-role'):
            return response(200, {'assignees': [{'type': 'USER', 'target': case['admin_user_ocid']},
                {'type': 'USER', 'target': case['operator_user_ocid']}]})
        if '/objects/' in path:
            return response(404, {})
        if path.endswith('/workspaces/' + case['workspace_key']):
            return response(200, {'key': case['workspace_key'], 'lifecycleState': 'ACTIVE'})
        raise AssertionError('Unexpected signed HTTP route')

    oci.identity.IdentityClient = Identity
    oci.object_storage.ObjectStorageClient = Objects
    oci.ai_data_platform.AiDataPlatformClient = Platform
    oci.database.DatabaseClient = Database
    requests.Session.request = request

    # Post-apply tests stop at these two explicit effect boundaries. Authentication,
    # settings, package validation and the CLI result contract execute unchanged.
    if case['phase'] == 'post_apply':
        from ai_data_governance import managed_memory

        def ensure_memory(client, store, command, authorize):
            record('memory-boundary')
            authorize({'phase': 'ready'})
            return {'autonomous_database_id': case['database_id'], 'memory_status': 'READY'}

        managed_memory.ensure_memory = ensure_memory
        from ai_data_governance import lifecycle

        def run_operation(client, store, **kwargs):
            record('lifecycle-boundary')
            assert kwargs['admin'] == case['admin_user_ocid']
            if 'expected_command' in case:
                assert kwargs['command'] == case['expected_command']
            status = case.get('outcome', 'active')
            receipt = {'manifest': {'status': status, 'validation_stage': 'TEST_PENDING',
                'operation': {'operation_id': kwargs['operation_id']}}}
            if status != 'active':
                receipt['outcome'] = {'status': status, 'failed_operation_id': 'fixture-failed-operation',
                    'failed_operation_type': 'update', 'provider_detail': case['private_marker']}
            return receipt

        lifecycle.run_operation = run_operation


HOOK_ARTIFACTS_MAX_BYTES = 8 * 1024 * 1024
ARTIFACT_NAME_PATTERN = re.compile(r'^[A-Za-z0-9][A-Za-z0-9._-]{0,127}$')


def contains_sensitive_value(value, secrets):
    if isinstance(value, bytes):
        value = value.decode('utf-8', errors='replace')
    return any(secret in str(value) for secret in secrets)


def redact_sensitive_values(value, secrets):
    for secret in secrets:
        value = str(value).replace(secret, '[redacted]')
    return value


# Reviewed CTN consumer function snapshot; dependencies above are standalone test boundaries.
CTN_RESULT_SOURCE_SHA256 = 'a5a6765d194d4b62ffdbcbf4c3e3b1804bf10d3a5c84e10b7b03122b8de73c17'

def _apply_hook_events(
    *,
    store: DeploymentStore,
    deployment_id: str,
    result: dict[str, Any],
    secret_values: set[str],
) -> list[str]:
    events = result.get("events", [])
    if not isinstance(events, list):
        raise RuntimeError("Project post-apply hook events are invalid")
    error_messages: list[str] = []
    for event in events:
        if not isinstance(event, dict):
            raise RuntimeError("Project post-apply hook event is invalid")
        level = str(event.get("level") or "info")
        message = str(event.get("message") or "")
        if level not in {"error", "info", "success", "warning"} or not message or len(message) > 2000:
            raise RuntimeError("Project post-apply hook event is invalid")
        safe_message = redact_sensitive_values(message, secret_values)
        store.add_event(deployment_id, level, safe_message)
        if level == "error":
            error_messages.append(safe_message)
    return error_messages

def _apply_hook_result(
    *,
    store: DeploymentStore,
    deployment_id: str,
    source: ResolvedDeploymentSource,
    result: dict[str, Any],
    secret_values: set[str],
) -> dict[str, Any]:
    _apply_hook_events(
        store=store,
        deployment_id=deployment_id,
        result=result,
        secret_values=secret_values,
    )

    artifact_bytes = 0
    allowed_artifacts = set(source.manifest.artifacts)
    for artifact in result.get("artifacts", []):
        if not isinstance(artifact, dict):
            raise RuntimeError("Project post-apply hook artifact is invalid")
        name = str(artifact.get("name") or "")
        if not ARTIFACT_NAME_PATTERN.fullmatch(name) or name not in allowed_artifacts:
            raise RuntimeError("Project post-apply hook returned an undeclared artifact")
        try:
            content = base64.b64decode(str(artifact.get("content_b64") or ""), validate=True)
        except ValueError as exc:
            raise RuntimeError("Project post-apply hook artifact is not valid base64") from exc
        artifact_bytes += len(content)
        if artifact_bytes > HOOK_ARTIFACTS_MAX_BYTES:
            raise RuntimeError("Project post-apply hook artifacts exceed the size limit")
        if contains_sensitive_value(name, secret_values) or contains_sensitive_value(content, secret_values):
            raise RuntimeError("Project post-apply hook artifact contains a secret value")
        store.put_artifact_bytes(
            deployment_id,
            name,
            content,
            str(artifact.get("content_type") or "application/octet-stream")[:128],
        )

    outputs = result.get("outputs", {})
    if not isinstance(outputs, dict) or set(outputs) - set(source.manifest.outputs):
        raise RuntimeError("Project post-apply hook returned undeclared outputs")
    if contains_sensitive_value(json.dumps(outputs, sort_keys=True), secret_values):
        raise RuntimeError("Project post-apply hook output contains a secret value")
    deployment = store.get(deployment_id)
    if deployment and outputs:
        deployment["hook_outputs"] = outputs
        store.save(deployment)
    return outputs
