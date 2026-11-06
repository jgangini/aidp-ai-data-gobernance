"""Cross-file checks for the distributed hook closure and native resource contract.

Consumer support for oci_aidp_administrators is tested by the coordinating
Deploy Studio repository; these tests do not certify that integration.
"""

import json
from collections import Counter
from pathlib import Path
import re


ROOT = Path(__file__).resolve().parents[2]


def test_form_and_preflight_inputs_exist_in_terraform():
    manifest = json.loads((ROOT / "terraform/deploy-studio.json").read_text("utf-8"))
    declared = set(re.findall(r'variable "([a-z0-9_]+)"', (ROOT / "terraform/b_variables.tf").read_text("utf-8")))
    form = {field["name"] for field in manifest["form"]["fields"]}
    runtime = set(manifest["preflight"]["output_inputs"])
    selection_only = {"artifacts_existing_bucket_name"}
    assert form - declared == selection_only
    assert (form - selection_only) | runtime <= declared
    assert "artifacts_bucket_name" in runtime
    assert not selection_only & runtime
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
    assert password["generate_password"] is True
    assert password["generate_password_when"] == {"field": "autonomous_database_mode", "equals": "new"}
    assert all(type(field.get("generate_password", False)) is bool for field in fields.values())
    assert {name for name, field in fields.items() if field.get("generate_password", False)} == {password["name"]}
    assert {name for name, field in fields.items() if "generate_password_when" in field} == {password["name"]}
    declared_order = list(fields)
    assert declared_order.index(password["generate_password_when"]["field"]) < declared_order.index(password["name"])
    assert manifest["capabilities"]["database_profile"] == "new_or_existing"
    assert manifest["capabilities"]["existing_database_wallet"] == "none"
    assert not {"autonomous_database_wallet_password", "wallet_file"} & fields.keys()
    assert fields["autonomous_database_version"]["transform"] == "database_profile"
    assert fields["autonomous_database_version"]["options"] == [{"value": "26ai:DW", "label": "Oracle AI Database 26ai · AI Lakehouse (DW)"}]
    database = next(group for group in manifest["form"]["groups"] if group["id"] == "database")
    assert {item["name"] for item in database["items"] if item["kind"] == "field"} == {
        name for name in fields if name.startswith(("autonomous_database", "existing_autonomous"))}


def test_installation_form_exposes_service_mode_and_keeps_administration_outside_the_form():
    manifest = json.loads((ROOT / "terraform/deploy-studio.json").read_text("utf-8"))
    fields = {field["name"]: field for field in manifest["form"]["fields"]}
    assert "governance_operation" not in fields
    assert fields["model_id"]["label"] == "Select Model"
    assert fields["model_id"]["default"] == "xai.grok-4.7"
    assert fields["aidp_mode"]["label"] == "Services mode"
    assert fields["aidp_mode"]["default"] == "new"
    assert fields["aidp_mode"]["options"] == [
        {"value": "new", "label": "Create new AIDP"},
        {"value": "existing", "label": "Use existing AIDP"},
    ]
    variables = (ROOT / "terraform/b_variables.tf").read_text("utf-8")
    aidp_mode = variables.split('variable "aidp_mode" {', 1)[1].split('variable ', 1)[0]
    assert 'default = "new"' in aidp_mode
    operation = variables.split('variable "governance_operation" {', 1)[1].split('variable ', 1)[0]
    assert 'default = "install"' in operation
    assert '["install", "resume", "update", "redeploy", "rollback"]' in operation


def test_artifacts_bucket_fields_are_mode_specific_and_map_to_one_canonical_input():
    manifest = json.loads((ROOT / "terraform/deploy-studio.json").read_text("utf-8"))
    fields = {field["name"]: field for field in manifest["form"]["fields"]}
    new = fields["artifacts_bucket_name"]
    existing = fields["artifacts_existing_bucket_name"]
    assert new["type"] == "text" and new["required"] is True
    assert new["visible_when"] == {"field": "artifacts_mode", "equals": "new"}
    assert existing["type"] == "select" and existing["required"] is True
    assert existing["visible_when"] == {"field": "artifacts_mode", "equals": "existing"}
    assert existing["options_source"] == "oci_active_buckets"
    assert new["pattern"] == existing["pattern"] == "^[A-Za-z0-9._-]{1,128}$"
    assert "artifacts_bucket_name" in manifest["preflight"]["output_inputs"]
    database = fields["existing_autonomous_database_ocid"]
    assert database["type"] == "select" and database["options_source"] == "oci_autonomous_databases"
    assert database["visible_when"] == {"field": "autonomous_database_mode", "equals": "existing"}


def test_form_labels_options_and_stages_match_the_requested_english_contract():
    manifest = json.loads((ROOT / "terraform/deploy-studio.json").read_text("utf-8"))
    fields = {field["name"]: field for field in manifest["form"]["fields"]}
    assert {name: field["label"] for name, field in fields.items()} == {
        "aidp_mode": "Services mode", "new_aidp_name": "New AIDP name", "existing_ai_data_platform_ocid": "Existing AIDP",
        "existing_workspace_key": "Existing workspace", "identity_domain_id": "Identity Domain",
        "admin_user_ocid": "AIDP administrator", "artifacts_mode": "Artifacts bucket mode",
        "artifacts_bucket_name": "New artifacts bucket name", "artifacts_existing_bucket_name": "Existing artifacts bucket",
        "model_id": "Select Model", "autonomous_database_mode": "Database mode",
        "autonomous_database_version": "Database profile", "existing_autonomous_database_ocid": "Existing Autonomous Database",
        "autonomous_database_admin_password": "Database admin password",
    }
    assert fields["artifacts_mode"]["options"] == [
        {"value": "new", "label": "Create new bucket"}, {"value": "existing", "label": "Use existing bucket"}]
    assert fields["autonomous_database_mode"]["options"] == [
        {"value": "new", "label": "Create new database"}, {"value": "existing", "label": "Use existing database"}]
    assert [(step["key"], step["label"]) for step in manifest["run_steps"]] == [
        ("queue", "Queued"), ("credentials", "Validate identity and access"),
        ("plan", "Review resources"), ("apply", "Prepare platform and artifacts"),
        ("artifacts", "Install and verify resources"), ("complete", "TEST candidate installed")]
    assert manifest["preflight"]["runtime_fields"][0]["label"] == "Tenancy home region"


def test_new_aidp_name_is_adjacent_to_mode_and_has_the_same_terraform_default_and_bounds():
    manifest = json.loads((ROOT / "terraform/deploy-studio.json").read_text("utf-8"))
    fields = {field["name"]: field for field in manifest["form"]["fields"]}
    mode, name = fields["aidp_mode"], fields["new_aidp_name"]
    assert len(fields) == 14
    platform_group = next(group for group in manifest["form"]["groups"] if group["id"] == "aidp_platform")
    ordered = platform_group["items"]
    mode_item = next(item for item in ordered if item["kind"] == "field" and item["name"] == mode["name"])
    name_item = next(item for item in ordered if item["kind"] == "field" and item["name"] == name["name"])
    assert ordered.index(name_item) == ordered.index(mode_item) + 1
    assert mode_item["span"] == name_item["span"] == 1
    assert name["type"] == "text" and name["required"] is True
    assert name["default"] == "aidp_governance"
    assert name["visible_when"] == {"field": "aidp_mode", "equals": "new"}
    assert (name["min_length"], name["max_length"]) == (1, 255)
    assert name["pattern"] == "^[A-Za-z0-9][A-Za-z0-9._ -]{0,254}$"
    variables = (ROOT / "terraform/b_variables.tf").read_text("utf-8")
    definition = variables.split('variable "new_aidp_name" {', 1)[1].split('variable ', 1)[0]
    assert re.search(r'\bdefault\s*=\s*"aidp_governance"', definition)
    assert name["pattern"] in definition


def test_schema_two_requires_explicit_nonempty_groups_with_unique_ids():
    manifest = json.loads((ROOT / "terraform/deploy-studio.json").read_text("utf-8"))
    assert type(manifest["schema_version"]) is int and manifest["schema_version"] == 2
    groups = manifest["form"]["groups"]
    assert isinstance(groups, list) and groups
    ids = [group["id"] for group in groups]
    assert len(ids) == len(set(ids))
    assert all(isinstance(name, str) and name.strip() for name in ids)
    assert all(isinstance(group["title"], str) and group["title"].strip() for group in groups)
    assert all(isinstance(group["items"], list) and group["items"] for group in groups)


def test_credentials_are_the_first_group_and_contain_only_config_and_key_controls_once():
    manifest = json.loads((ROOT / "terraform/deploy-studio.json").read_text("utf-8"))
    groups = manifest["form"]["groups"]
    assert groups[0]["id"] == "credentials"
    assert [(item["kind"], item["name"]) for item in groups[0]["items"]] == [
        ("control", "oci_config"), ("control", "oci_key")]
    controls = Counter(item["name"] for group in groups for item in group["items"] if item["kind"] == "control")
    assert controls["oci_config"] == controls["oci_key"] == 1


def test_group_field_and_file_references_match_all_declarations_exactly_once():
    manifest = json.loads((ROOT / "terraform/deploy-studio.json").read_text("utf-8"))
    form = manifest["form"]
    fields = [field["name"] for field in form["fields"]]
    files = [file["name"] for file in form.get("files", [])]
    assert len(fields) == len(set(fields)) and len(files) == len(set(files))
    assert not set(fields) & set(files)
    items = [item for group in form["groups"] for item in group["items"]]
    assert {item["kind"] for item in items} <= {"field", "file", "control"}
    references = Counter((item["kind"], item["name"]) for item in items if item["kind"] in {"field", "file"})
    declared = Counter([("field", name) for name in fields] + [("file", name) for name in files])
    assert references == declared


def test_group_controls_match_capabilities_without_unknown_unused_or_duplicate_controls():
    manifest = json.loads((ROOT / "terraform/deploy-studio.json").read_text("utf-8"))
    capabilities = manifest["capabilities"]
    controls = [item for group in manifest["form"]["groups"] for item in group["items"] if item["kind"] == "control"]
    names = [item["name"] for item in controls]
    known = {"oci_config", "oci_key", "oci_region", "compartment_mode", "new_compartment", "existing_compartment", "database_wallet"}
    assert set(names) <= known and len(names) == len(set(names))
    expected = {"oci_config", "oci_key"}
    if capabilities["region_selection"] == "subscribed_compatible":
        expected.add("oci_region")
    if len(capabilities["compartment_modes"]) > 1:
        expected.add("compartment_mode")
    compartment_controls = {"new": "new_compartment", "existing": "existing_compartment"}
    expected.update(compartment_controls[mode] for mode in capabilities["compartment_modes"])
    if capabilities["existing_database_wallet"] != "none":
        expected.add("database_wallet")
    assert set(names) == expected
    assert capabilities["existing_database_wallet"] == "none" and "database_wallet" not in names


def test_control_labels_and_compartment_options_have_the_declared_shape_and_unique_modes():
    manifest = json.loads((ROOT / "terraform/deploy-studio.json").read_text("utf-8"))
    services = next(group for group in manifest["form"]["groups"] if group["id"] == "services")
    assert [item["name"] for item in services["items"]] == [
        "oci_region", "compartment_mode", "new_compartment", "existing_compartment"]
    assert services["items"][0]["span"] == 2
    controls = {item["name"]: item for group in manifest["form"]["groups"] for item in group["items"] if item["kind"] == "control"}
    assert {name: item["label"] for name, item in controls.items()} == {
        "oci_config": "OCI config", "oci_key": "API private key", "oci_region": "OCI Region",
        "compartment_mode": "Compartment mode", "new_compartment": "New compartment name",
        "existing_compartment": "Existing compartment"}
    options = controls["compartment_mode"]["options"]
    assert isinstance(options, list) and options
    assert all(set(option) == {"value", "label"} for option in options)
    assert all(isinstance(option["label"], str) and option["label"].strip() for option in options)
    values = [option["value"] for option in options]
    assert len(values) == len(set(values))
    assert values == manifest["capabilities"]["compartment_modes"]
    assert not any("options" in item for name, item in controls.items() if name != "compartment_mode")
