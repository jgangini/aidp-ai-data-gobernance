locals {
  memory_database_name = upper(substr("GOV${var.deployment_suffix}", 0, 14))
  autonomous_database_id = var.autonomous_database_mode == "new" ? (
    oci_database_autonomous_database.memory[0].id
  ) : data.oci_database_autonomous_database.existing_memory[0].id
}

resource "oci_database_autonomous_database" "memory" {
  count                       = var.autonomous_database_mode == "new" ? 1 : 0
  compartment_id              = var.compartment_ocid
  display_name                = "${local.product_name}-memory"
  db_name                     = local.memory_database_name
  admin_password              = var.autonomous_database_admin_password
  db_version                  = var.autonomous_database_version
  db_workload                 = var.autonomous_database_workload
  compute_model               = "ECPU"
  compute_count               = 4
  is_auto_scaling_enabled     = false
  data_storage_size_in_tbs    = 1
  license_model               = "LICENSE_INCLUDED"
  is_mtls_connection_required = true
  freeform_tags = {
    managed-by = "deploy-studio"
    product    = "ai_data_governance"
    workload   = "agent-memory"
  }
  lifecycle {
    prevent_destroy = true
  }
}

data "oci_database_autonomous_database" "existing_memory" {
  count                  = var.autonomous_database_mode == "existing" ? 1 : 0
  autonomous_database_id = var.existing_autonomous_database_ocid
  lifecycle {
    postcondition {
      condition     = self.id == var.existing_autonomous_database_ocid
      error_message = "The external memory database identity differs from the selected OCID."
    }
    postcondition {
      condition     = self.state == "AVAILABLE"
      error_message = "The existing memory database must be AVAILABLE."
    }
    postcondition {
      condition     = self.db_version == "26ai" && self.db_workload == "DW"
      error_message = "The existing memory database must be 26ai with the DW workload."
    }
  }
}
