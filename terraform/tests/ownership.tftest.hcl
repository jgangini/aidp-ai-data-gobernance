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
  variables {
    aidp_mode                      = "existing"
    artifacts_mode                 = "existing"
    existing_ai_data_platform_ocid = "ocid1.aidataplatform.oc1.test.existing"
    existing_workspace_key         = "11111111-1111-4111-8111-111111111111"
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
  expect_failures = [var.existing_ai_data_platform_ocid, var.existing_workspace_key]
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
