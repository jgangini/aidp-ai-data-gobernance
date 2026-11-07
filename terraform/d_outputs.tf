output "ai_data_platform_ocid" {
  value = var.aidp_mode == "new" ? oci_ai_data_platform_ai_data_platform.governance[0].id : var.existing_ai_data_platform_ocid
  precondition {
    condition     = var.aidp_mode != "existing" || can(regex("^ocid1\\.aidataplatform\\.", var.existing_ai_data_platform_ocid))
    error_message = "An explicit AIDP OCID is required for existing mode."
  }
}
output "workspace_key" {
  description = "New platform workspace key is verified by post-apply against its exact newly created platform."
  value       = var.aidp_mode == "existing" ? var.existing_workspace_key : ""
  precondition {
    condition     = var.aidp_mode != "existing" || can(regex("^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$", var.existing_workspace_key))
    error_message = "An exact canonical workspace UUID is required for existing mode."
  }
}
output "workspace_name" {
  value = var.aidp_mode == "new" ? local.workspace_name : ""
}
output "aidp_mode" {
  value = var.aidp_mode
}
output "artifacts_bucket_name" {
  value      = var.artifacts_bucket_name
  depends_on = [oci_objectstorage_bucket.artifacts]
}
output "artifacts_mode" {
  value = var.artifacts_mode
}
output "objectstorage_namespace" {
  value = var.objectstorage_namespace
}
output "compartment_ocid" {
  value = var.compartment_ocid
}
output "region" {
  value = var.region
}
output "identity_domain_id" {
  value = var.identity_domain_id
}
output "admin_user_ocid" {
  value = var.admin_user_ocid
}
output "model_id" {
  value = var.model_id
}
output "resource_ownership" {
  value = {
    platform        = var.aidp_mode == "new" ? "owned" : "external"
    workspace       = var.aidp_mode == "new" ? "owned" : "external"
    artifacts       = var.artifacts_mode == "new" ? "owned" : "external"
    memory_database = var.autonomous_database_mode == "new" ? "owned" : "external"
  }
}
output "autonomous_database_id" {
  value = local.autonomous_database_id
}
output "autonomous_database_mode" {
  value = var.autonomous_database_mode
}

output "deploy_studio_resource_labels" {
  description = "Plan-known display labels keyed by exact Terraform instance address; execution and ordering come from OCI Resource Manager."
  value = merge(
    { for index, instance in oci_ai_data_platform_ai_data_platform.governance : "oci_ai_data_platform_ai_data_platform.governance[${index}]" => "AI Data Platform" },
    { for index, instance in oci_identity_policy.aidp_service : "oci_identity_policy.aidp_service[${index}]" => "AIDP service permissions" },
    { for index, instance in time_sleep.aidp_iam_propagation : "time_sleep.aidp_iam_propagation[${index}]" => "IAM permission propagation" },
    { for index, instance in oci_objectstorage_bucket.artifacts : "oci_objectstorage_bucket.artifacts[${index}]" => "Artifacts bucket" },
    { for index, instance in oci_database_autonomous_database.memory : "oci_database_autonomous_database.memory[${index}]" => "Agent memory database" },
    { for index, instance in data.oci_database_autonomous_database.existing_memory : "data.oci_database_autonomous_database.existing_memory[${index}]" => "Existing agent memory database" }
  )
}
