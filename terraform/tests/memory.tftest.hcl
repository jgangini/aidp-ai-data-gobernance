mock_provider "oci" {
  mock_data "oci_database_autonomous_database" {
    defaults = {
      id          = "ocid1.autonomousdatabase.oc1.test.external"
      state       = "AVAILABLE"
      db_version  = "26ai"
      db_workload = "DW"
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
  aidp_mode                          = "existing"
  existing_ai_data_platform_ocid     = "ocid1.aidataplatform.oc1.test.existing"
  existing_workspace_key             = "11111111-1111-4111-8111-111111111111"
  autonomous_database_admin_password = "TestOnlyPassword26!"
}

run "new_memory_is_a_dw_26ai_ecpu_database" {
  command = plan
  variables {
    autonomous_database_mode = "new"
  }
  assert {
    condition     = length(oci_database_autonomous_database.memory) == 1 && length(data.oci_database_autonomous_database.existing_memory) == 0
    error_message = "New memory requires exactly one owned database, with no existing lookup."
  }
  assert {
    condition     = oci_database_autonomous_database.memory[0].db_version == "26ai" && oci_database_autonomous_database.memory[0].db_workload == "DW"
    error_message = "The created memory database must use the fixed 26ai:DW profile."
  }
  assert {
    condition     = oci_database_autonomous_database.memory[0].compute_model == "ECPU" && oci_database_autonomous_database.memory[0].compute_count == 4 && oci_database_autonomous_database.memory[0].data_storage_size_in_tbs == 1
    error_message = "The memory database must retain the explicit source defaults of four ECPUs and one TB."
  }
  assert {
    condition     = output.autonomous_database_mode == "new" && output.resource_ownership.memory_database == "owned" && issensitive(var.autonomous_database_admin_password)
    error_message = "New memory ownership must be explicit and its credential sensitive."
  }
}

run "existing_memory_is_verified_without_adoption_or_mutation" {
  command = plan
  variables {
    autonomous_database_mode          = "existing"
    existing_autonomous_database_ocid = "ocid1.autonomousdatabase.oc1.test.external"
  }
  assert {
    condition     = length(oci_database_autonomous_database.memory) == 0 && length(data.oci_database_autonomous_database.existing_memory) == 1
    error_message = "Existing memory must be read through a data source, never declared as an owned resource."
  }
  assert {
    condition     = output.autonomous_database_id == var.existing_autonomous_database_ocid && output.autonomous_database_mode == "existing" && output.resource_ownership.memory_database == "external"
    error_message = "An existing memory database retains its exact identity and external ownership."
  }
}

run "existing_memory_without_password_keeps_lookup_only" {
  command = plan
  variables {
    autonomous_database_mode           = "existing"
    existing_autonomous_database_ocid  = "ocid1.autonomousdatabase.oc1.test.external"
    autonomous_database_admin_password = ""
  }
  assert {
    condition     = length(oci_database_autonomous_database.memory) == 0 && output.autonomous_database_id == var.existing_autonomous_database_ocid
    error_message = "Referencing existing memory without a creation credential must not create or modify a database."
  }
}

run "new_memory_without_password_is_rejected" {
  command = plan
  variables {
    autonomous_database_mode           = "new"
    autonomous_database_admin_password = ""
  }
  expect_failures = [oci_database_autonomous_database.memory]
}

run "new_memory_with_weak_password_is_rejected" {
  command = plan
  variables {
    autonomous_database_mode           = "new"
    autonomous_database_admin_password = "Short26!"
  }
  expect_failures = [var.autonomous_database_admin_password]
}

run "password_without_lowercase_is_rejected" {
  command = plan
  variables {
    autonomous_database_admin_password = "TESTONLYPASSWORD26!"
  }
  expect_failures = [var.autonomous_database_admin_password]
}

run "invalid_database_mode_is_rejected" {
  command = plan
  variables {
    autonomous_database_mode = "adopt"
  }
  expect_failures = [var.autonomous_database_mode]
}

run "missing_existing_database_ocid_is_rejected" {
  command = plan
  variables {
    autonomous_database_mode          = "existing"
    existing_autonomous_database_ocid = ""
  }
  expect_failures = [data.oci_database_autonomous_database.existing_memory]
}

run "database_name_cannot_replace_an_existing_ocid" {
  command = plan
  variables {
    autonomous_database_mode          = "existing"
    existing_autonomous_database_ocid = "database-name"
  }
  expect_failures = [data.oci_database_autonomous_database.existing_memory]
}

run "new_23ai_profile_is_rejected" {
  command = plan
  variables {
    autonomous_database_version = "23ai"
  }
  expect_failures = [var.autonomous_database_version]
}

run "new_atp_workload_is_rejected" {
  command = plan
  variables {
    autonomous_database_workload = "OLTP"
  }
  expect_failures = [var.autonomous_database_workload]
}

run "stopped_external_database_is_rejected" {
  command = plan
  variables {
    autonomous_database_mode          = "existing"
    existing_autonomous_database_ocid = "ocid1.autonomousdatabase.oc1.test.external"
  }
  override_data {
    target = data.oci_database_autonomous_database.existing_memory[0]
    values = {
      id          = "ocid1.autonomousdatabase.oc1.test.external"
      state       = "STOPPED"
      db_version  = "26ai"
      db_workload = "DW"
    }
  }
  expect_failures = [data.oci_database_autonomous_database.existing_memory]
}

run "older_external_database_is_rejected" {
  command = plan
  variables {
    autonomous_database_mode          = "existing"
    existing_autonomous_database_ocid = "ocid1.autonomousdatabase.oc1.test.external"
  }
  override_data {
    target = data.oci_database_autonomous_database.existing_memory[0]
    values = {
      id          = "ocid1.autonomousdatabase.oc1.test.external"
      state       = "AVAILABLE"
      db_version  = "23ai"
      db_workload = "DW"
    }
  }
  expect_failures = [data.oci_database_autonomous_database.existing_memory]
}

run "external_atp_database_is_rejected" {
  command = plan
  variables {
    autonomous_database_mode          = "existing"
    existing_autonomous_database_ocid = "ocid1.autonomousdatabase.oc1.test.external"
  }
  override_data {
    target = data.oci_database_autonomous_database.existing_memory[0]
    values = {
      id          = "ocid1.autonomousdatabase.oc1.test.external"
      state       = "AVAILABLE"
      db_version  = "26ai"
      db_workload = "OLTP"
    }
  }
  expect_failures = [data.oci_database_autonomous_database.existing_memory]
}

run "different_external_database_identity_is_rejected" {
  command = plan
  variables {
    autonomous_database_mode          = "existing"
    existing_autonomous_database_ocid = "ocid1.autonomousdatabase.oc1.test.external"
  }
  override_data {
    target = data.oci_database_autonomous_database.existing_memory[0]
    values = {
      id          = "ocid1.autonomousdatabase.oc1.test.foreign"
      state       = "AVAILABLE"
      db_version  = "26ai"
      db_workload = "DW"
    }
  }
  expect_failures = [data.oci_database_autonomous_database.existing_memory]
}
