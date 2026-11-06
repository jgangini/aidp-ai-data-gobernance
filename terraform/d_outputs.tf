output "ai_data_platform_ocid" {
  value = var.aidp_mode == "new" ? oci_ai_data_platform_ai_data_platform.governance[0].id : var.existing_ai_data_platform_ocid
}
output "workspace_key" {
  description = "New platform workspace key is verified by post-apply against its exact newly created platform."
  value       = var.aidp_mode == "existing" ? var.existing_workspace_key : ""
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
    platform  = var.aidp_mode == "new" ? "owned" : "external"
    workspace = var.aidp_mode == "new" ? "owned" : "external"
    artifacts = var.artifacts_mode == "new" ? "owned" : "external"
  }
}
