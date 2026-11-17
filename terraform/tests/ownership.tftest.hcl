mock_provider "oci" {
  mock_resource "oci_ai_data_platform_ai_data_platform" {
    defaults = {
      id = "ocid1.aidataplatform.oc1.test.created"
    }
  }
}
mock_provider "oci" {
  alias = "home"
}
mock_provider "time" {}

variables {
  tenancy_ocid                       = "ocid1.tenancy.oc1..test"
  compartment_ocid                   = "ocid1.compartment.oc1..test"
  region                             = "us-chicago-1"
  home_region                        = "us-ashburn-1"
  objectstorage_namespace            = "testnamespace"
  deployment_suffix                  = "test1234"
  identity_domain_id                 = "ocid1.domain.oc1..test"
  admin_user_ocid                    = "ocid1.user.oc1..test"
  artifacts_bucket_name              = "governance-test-artifacts"
  model_id                           = "ocid1.generativeaimodel.oc1.test.model"
  autonomous_database_admin_password = "TestOnlyPassword26!"
}

run "existing_resources_are_external" {
  command = plan
  assert {
    condition = (
      !issensitive(output.deploy_studio_resource_labels) &&
      toset(keys(output.deploy_studio_resource_labels)) == toset([
        "oci_database_autonomous_database.memory[0]",
      ]) &&
      alltrue([for label in values(output.deploy_studio_resource_labels) : length(label) > 0 && length(label) <= 80])
    )
    error_message = "Display labels must be available during PLAN, nonsensitive, and cover exactly the selected resource and data instances."
  }

  variables {
    aidp_mode                      = "existing"
    artifacts_mode                 = "existing"
    existing_ai_data_platform_ocid = "ocid1.aidataplatform.oc1.test.existing"
    existing_workspace_key         = "11111111-1111-4111-8111-111111111111"
    new_aidp_name                  = "An unrelated platform name"
  }
  assert {
    condition     = length(oci_ai_data_platform_ai_data_platform.governance) == 0 && length(oci_objectstorage_bucket.artifacts) == 0 && length(oci_identity_policy.aidp_service) == 0
    error_message = "Existing resources must not enter this stack's resource ownership."
  }
  assert {
    condition     = output.ai_data_platform_ocid == var.existing_ai_data_platform_ocid && output.workspace_key == var.existing_workspace_key
    error_message = "Existing resource identity must be retained exactly."
  }
  assert {
    condition     = output.resource_ownership.platform == "external" && output.resource_ownership.artifacts == "external"
    error_message = "Existing resources must be declared external."
  }
}

run "new_platform_and_bucket_are_explicit" {
  command = plan
  assert {
    condition     = output.deploy_studio_resource_labels["oci_ai_data_platform_ai_data_platform.governance[0]"] == "AI Data Platform" && output.deploy_studio_resource_labels["oci_database_autonomous_database.memory[0]"] == "Agent memory database"
    error_message = "Plan resource labels must identify the selected infrastructure without exposing instance suffixes."
  }

  assert {
    condition = (
      !issensitive(output.deploy_studio_resource_labels) &&
      toset(keys(output.deploy_studio_resource_labels)) == toset([
        "oci_ai_data_platform_ai_data_platform.governance[0]",
        "oci_identity_policy.aidp_service[0]",
        "time_sleep.aidp_iam_propagation[0]",
        "oci_objectstorage_bucket.artifacts[0]",
        "oci_database_autonomous_database.memory[0]",
      ]) &&
      alltrue([for label in values(output.deploy_studio_resource_labels) : length(label) > 0 && length(label) <= 80])
    )
    error_message = "Display labels must be available during PLAN, nonsensitive, and cover exactly the selected resource and data instances."
  }

  variables {
    aidp_mode      = "new"
    artifacts_mode = "new"
  }
  assert {
    condition     = length(oci_ai_data_platform_ai_data_platform.governance) == 1 && length(oci_objectstorage_bucket.artifacts) == 1
    error_message = "New mode must declare exactly one platform and artifacts bucket."
  }
  assert {
    condition     = oci_ai_data_platform_ai_data_platform.governance[0].default_workspace_name == "governance-test1234" && output.workspace_key == ""
    error_message = "The newly created default workspace must be resolved by exact platform identity after apply."
  }
  assert {
    condition     = oci_ai_data_platform_ai_data_platform.governance[0].display_name == "aidp_governance"
    error_message = "Omitting the new AIDP name must preserve the requested default on the created resource."
  }
  assert {
    condition     = output.resource_ownership.platform == "owned" && output.resource_ownership.workspace == "owned" && output.resource_ownership.artifacts == "owned"
    error_message = "Newly created resources must have explicit ownership."
  }
}

run "existing_platform_new_bucket" {
  command = plan
  variables {
    aidp_mode                      = "existing"
    artifacts_mode                 = "new"
    existing_ai_data_platform_ocid = "ocid1.aidataplatform.oc1.test.existing"
    existing_workspace_key         = "11111111-1111-4111-8111-111111111111"
  }
  assert {
    condition     = length(oci_ai_data_platform_ai_data_platform.governance) == 0 && length(oci_objectstorage_bucket.artifacts) == 1
    error_message = "Creating an artifacts bucket must not take ownership of an existing platform."
  }
}

run "invalid_existing_identity_is_rejected" {
  command = plan
  variables {
    aidp_mode                      = "existing"
    existing_ai_data_platform_ocid = "platform-name"
    existing_workspace_key         = ""
  }
  expect_failures = [output.ai_data_platform_ocid, output.workspace_key]
}

run "missing_existing_platform_ocid_is_rejected" {
  command = plan
  variables {
    aidp_mode                      = "existing"
    existing_ai_data_platform_ocid = ""
    existing_workspace_key         = "11111111-1111-4111-8111-111111111111"
  }
  expect_failures = [output.ai_data_platform_ocid]
}

run "missing_existing_workspace_key_is_rejected" {
  command = plan
  variables {
    aidp_mode                      = "existing"
    existing_ai_data_platform_ocid = "ocid1.aidataplatform.oc1.test.existing"
    existing_workspace_key         = ""
  }
  expect_failures = [output.workspace_key]
}

run "noncanonical_existing_workspace_key_is_rejected" {
  command = plan
  variables {
    aidp_mode                      = "existing"
    existing_ai_data_platform_ocid = "ocid1.aidataplatform.oc1.test.existing"
    existing_workspace_key         = "AAAAAAAA-1111-4111-8111-111111111111"
  }
  expect_failures = [output.workspace_key]
}

run "new_platform_existing_bucket" {
  command = plan
  variables {
    aidp_mode      = "new"
    artifacts_mode = "existing"
  }
  assert {
    condition     = length(oci_ai_data_platform_ai_data_platform.governance) == 1 && length(oci_objectstorage_bucket.artifacts) == 0
    error_message = "A new platform must preserve external artifacts bucket ownership."
  }
  assert {
    condition     = output.resource_ownership.platform == "owned" && output.resource_ownership.artifacts == "external"
    error_message = "The installation receipt needs independently selected ownership for platform and bucket."
  }
}

run "custom_name_reaches_only_the_new_platform_display_name" {
  command = plan
  variables {
    aidp_mode     = "new"
    new_aidp_name = "Finance AIDP - QA 01"
  }
  assert {
    condition     = oci_ai_data_platform_ai_data_platform.governance[0].display_name == "Finance AIDP - QA 01"
    error_message = "The selected AIDP display name must reach the created platform without rewriting."
  }
  assert {
    condition     = oci_ai_data_platform_ai_data_platform.governance[0].default_workspace_name == "governance-test1234" && oci_identity_policy.aidp_service[0].name == "aidp-governance-test1234-aidp-service" && oci_database_autonomous_database.memory[0].display_name == "aidp-governance-test1234-memory"
    error_message = "The platform display name must not rename the workspace, IAM policy or memory database."
  }
}

run "empty_new_platform_name_is_rejected" {
  command = plan
  variables {
    new_aidp_name = ""
  }
  expect_failures = [var.new_aidp_name]
}

run "blank_new_platform_name_is_rejected" {
  command = plan
  variables {
    new_aidp_name = "   "
  }
  expect_failures = [var.new_aidp_name]
}

run "control_character_in_new_platform_name_is_rejected" {
  command = plan
  variables {
    new_aidp_name = "governance\nunsafe"
  }
  expect_failures = [var.new_aidp_name]
}

run "path_in_new_platform_name_is_rejected" {
  command = plan
  variables {
    new_aidp_name = "governance/private"
  }
  expect_failures = [var.new_aidp_name]
}

run "overlong_new_platform_name_is_rejected" {
  command = plan
  variables {
    new_aidp_name = join("", [for index in range(256) : "x"])
  }
  expect_failures = [var.new_aidp_name]
}
