"""Cross-file checks for the distributed hook closure and native resource contract.

Consumer support for oci_aidp_administrators is tested by the coordinating
Deploy Studio repository; these tests do not certify that integration.
"""

import json
from pathlib import Path
import re


ROOT = Path(__file__).resolve().parents[2]


def test_form_and_preflight_inputs_exist_in_terraform():
    manifest = json.loads((ROOT / "terraform/deploy-studio.json").read_text("utf-8"))
    declared = set(re.findall(r'variable "([a-z0-9_]+)"', (ROOT / "terraform/b_variables.tf").read_text("utf-8")))
    form = {field["name"] for field in manifest["form"]["fields"]}
    runtime = set(manifest["preflight"]["output_inputs"])
    assert form | runtime <= declared
    assert "admin_user_ocid" in form and "identity_domain_id" in form
    assert not {"admin_username", "admin_password", "admin_password_hash"} & form
    assert manifest["project_id"] == "aidp-ai-data-governance"


def test_hook_distribution_has_the_unique_model_and_agent_sources():
    manifest = json.loads((ROOT / "terraform/deploy-studio.json").read_text("utf-8"))
    paths = manifest["post_apply"]["include_paths"]
    assert "src/ai_data_governance" in paths
    assert "requirements.txt" in paths
    for relative in paths:
        path = (ROOT / relative).resolve()
        assert path.is_relative_to(ROOT) and path.exists()
        assert not {".oci", ".local", ".git", "frontend"} & set(path.parts)
    package = ROOT / "src/ai_data_governance"
    model = json.loads((package / "aidp/manifest.json").read_text("utf-8"))
    assert len(model["model"]["tables"]) == 18
    assert len(model["agents"]) == 2
    assert len(model["workflows"]) == 1
    for resource in model["model"]["tables"] + model["agents"] + model["workflows"] + model["compute"]:
        assert (package / resource).is_file()


def test_existing_selection_has_explicit_native_identity_fields():
    manifest = json.loads((ROOT / "terraform/deploy-studio.json").read_text("utf-8"))
    fields = {field["name"]: field for field in manifest["form"]["fields"]}
    assert fields["existing_ai_data_platform_ocid"]["visible_when"] == {"field": "aidp_mode", "equals": "existing"}
    assert fields["existing_workspace_key"]["visible_when"] == {"field": "aidp_mode", "equals": "existing"}
    assert fields["existing_workspace_key"]["type"] == "select"
    assert fields["existing_workspace_key"]["label"] == "Existing workspace"
    assert fields["existing_workspace_key"]["options_source"] == "oci_aidp_workspaces"
    assert fields["existing_workspace_key"]["required"] is True
    assert fields["existing_workspace_key"]["pattern"] == "^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$"
    assert fields["admin_user_ocid"]["options_source"] == "oci_aidp_administrators"
    assert manifest["preflight"]["requires_oci_credentials"] is True
    assert manifest["post_apply"]["requires_oci_credentials"] is True
    assert manifest["preflight"]["secret_inputs"] == ["autonomous_database_admin_password"]
    assert manifest["post_apply"]["secret_inputs"] == ["autonomous_database_admin_password"]
    assert {field["name"] for field in fields.values() if field.get("secret")} == {"autonomous_database_admin_password"}
    password = fields["autonomous_database_admin_password"]
    assert password["type"] == "password" and password["required"] is False and "default" not in password
    assert manifest["capabilities"]["database_profile"] == "new_or_existing"
    assert manifest["capabilities"]["existing_database_wallet"] == "none"
    assert not {"autonomous_database_wallet_password", "wallet_file"} & fields.keys()
    assert fields["autonomous_database_version"]["transform"] == "database_profile"
    assert fields["autonomous_database_version"]["options"] == [{"value": "26ai:DW", "label": "Oracle AI Database 26ai · AI Lakehouse (DW)"}]
    assert all(field["group"] == "database" for name, field in fields.items()
               if name.startswith(("autonomous_database", "existing_autonomous")))


def test_installation_form_exposes_service_mode_and_keeps_administration_outside_the_form():
    manifest = json.loads((ROOT / "terraform/deploy-studio.json").read_text("utf-8"))
    fields = {field["name"]: field for field in manifest["form"]["fields"]}
    assert "governance_operation" not in fields
    assert fields["aidp_mode"]["label"] == "Services mode"
    assert fields["aidp_mode"]["options"] == [
        {"value": "new", "label": "Create new AIDP"},
        {"value": "existing", "label": "Use existing AIDP"},
    ]
    variables = (ROOT / "terraform/b_variables.tf").read_text("utf-8")
    operation = variables.split('variable "governance_operation" {', 1)[1].split('variable ', 1)[0]
    assert 'default = "install"' in operation
    assert '["install", "resume", "update", "redeploy", "rollback"]' in operation
