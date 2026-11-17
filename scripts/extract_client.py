"""One-time, reviewed method extraction from the frozen source, not runtime loading."""
import ast
import json
from pathlib import Path
import subprocess
from extract_frozen import ROOT, SOURCE, REVISION

METHODS = '''_module_root _module_manifest_path __init__ close _request_headers _response_body
_safe_diagnostic_fragment _request_error_message _request _page_items _list _workspace _catalog
_ensure_catalog _shared_compute _agent_compute_async_operations _async_operation_status
_operation_retry_scope _deleted_agent_compute_retry_scope _hidden_agent_compute _recover_hidden_agent_compute
_remove_failed_agent_compute _ensure_agent_compute _agents _agent_entry_path _ensure_agent
_agent_deployments _ensure_agent_deployment _require_operational_state _workspace_object
_workspace_object_exists _workspace_object_type _content_matches _ensure_folder _upload_file
_workspace_object_key _workspace_json _ensure_workspace_layout _job_key _create_job _permission_grantee
_role_permission_matches _ensure_role_permission _role _role_principal_ocids _role_user_ocids
platform_admin_user_ocids platform_admin_principals is_platform_admin _ensure_governance_bucket
_credential_payload _ensure_governance_credential _shared_oci_credential _governance_oci_config _timestamp
_module_manifest_valid _module_manifest _write_module_manifest _module_status _governance_enabled
list_modules governance_agent_endpoint _new_module_manifest _governance_workspace _start_governance_install
_resume_governance_operation _assert_governance_operation_available _reconcile_governance_module
install_governance_module _record_module_error _run_module_operation redeploy_governance_module
_delete_governance_module delete_governance_module _resource_name _job_contract_is_visible'''.split()


def frozen(path):
    return subprocess.check_output(['git', '-C', str(SOURCE), 'show', REVISION + ':' + path]).decode('utf-8')


def segment(text, node):
    start = min([node.lineno, *[item.lineno for item in getattr(node, 'decorator_list', [])]])
    return '\n'.join(text.splitlines()[start - 1:node.end_lineno])


def main():
    text = frozen('apps/backend/app/services/oci/aidp.py')
    tree = ast.parse(text)
    client = next(node for node in tree.body if isinstance(node, ast.ClassDef) and node.name == 'AidpClient')
    selected = [node for node in client.body if getattr(node, 'name', '') in METHODS]
    assert {node.name for node in selected} == set(METHODS)
    header = '''"""Governance-only OCI capabilities extracted from the frozen implementation."""
from __future__ import annotations
import asyncio
import hashlib
import json
import re
import threading
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable
from urllib.parse import quote
from oci._vendor import requests
from .errors import AidpProvisionPending, AidpProvisionError, AidpRequestError, AidpProvisionConflict
from .constants import (GOVERNANCE_AGENT_COMPUTE_NAME, GOVERNANCE_AGENT_NAME,
    GOVERNANCE_CREDENTIAL_NAME, GOVERNANCE_DISPLAY_NAME, GOVERNANCE_JOB_NAME, GOVERNANCE_MODULE_ID,
    RUNTIME_FAMILY, governance_compute_payload)
from .package_loader import load_package
from .runtime_identity import identity_hash, shared_credential
API_VERSION = "20260430"
SHARED_COMPUTE_NAME = "aidp_cluster_shared_compute"
AGENT_COMPUTE_NAME = GOVERNANCE_AGENT_COMPUTE_NAME
CATALOG_NAME = "oci_medallion"
WORKSPACE_ROOT = "/Workspace"
CONTROL_ROOT = WORKSPACE_ROOT + "/.control"
MODULE_CONTROL_ROOT = CONTROL_ROOT + "/modules"
MODULE_ROOT = MODULE_CONTROL_ROOT + "/ai_data_governance"
MODULE_MANIFEST_PATH = MODULE_ROOT + "/manifest.json"
'''
    payload = next(node for node in tree.body if isinstance(node, ast.FunctionDef) and node.name == '_module_payload')
    output = header + '\n' + segment(text, payload) + '\n\nclass AidpClient:\n' + '\n\n'.join(segment(text, node) for node in selected) + '\n'
    output = output.replace('app.modules.ai_data_governance', 'ai_data_governance')
    (ROOT / 'src/ai_data_governance/client.py').write_text(output, encoding='utf-8')
    text = frozen('apps/backend/app/services/oci/contracts.py')
    nodes = [node for node in ast.parse(text).body if isinstance(node, ast.ClassDef) and node.name in
             {'AidpProvisionPending', 'AidpProvisionError', 'AidpRequestError', 'AidpProvisionConflict'}]
    (ROOT / 'src/ai_data_governance/errors.py').write_text('import re\n\n' + '\n\n'.join(segment(text, node) for node in nodes) + '\n', encoding='utf-8')
    text = frozen('apps/backend/app/modules/ai_gods_eye_view/runtime/runtime_secrets.py')
    nodes = [node for node in ast.parse(text).body if isinstance(node, ast.FunctionDef) and node.name in {'identity_hash', 'shared_credential'}]
    (ROOT / 'src/ai_data_governance/runtime_identity.py').write_text('import hashlib\nimport json\nOCI_CREDENTIALS = ("AidpRuntime",)\n\n' + '\n\n'.join(segment(text, node) for node in nodes) + '\n', encoding='utf-8')
    text = frozen('apps/backend/app/packages/aidp.py').replace('"ai_data_governance", "ai_market_intelligence"', '"ai_data_governance"')
    (ROOT / 'src/ai_data_governance/aidp_contract.py').write_text(text, encoding='utf-8')


if __name__ == '__main__':
    main()
