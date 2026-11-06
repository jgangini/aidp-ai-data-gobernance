locals {
  product_name   = "aidp-governance-${var.deployment_suffix}"
  workspace_name = "governance-${var.deployment_suffix}"
}

# Existing platforms remain outside this stack's resource ownership.
resource "oci_ai_data_platform_ai_data_platform" "governance" {
  count                  = var.aidp_mode == "new" ? 1 : 0
  compartment_id         = var.compartment_ocid
  display_name           = local.product_name
  default_workspace_name = local.workspace_name
  ai_data_platform_type  = "STRUCTURED"
  freeform_tags = {
    managed-by = "deploy-studio"
    product    = "ai_data_governance"
  }
  lifecycle {
    prevent_destroy = true
  }
  timeouts {
    create = "120m"
  }
  depends_on = [time_sleep.aidp_iam_propagation]
}

resource "oci_identity_policy" "aidp_service" {
  provider       = oci.home
  count          = var.aidp_mode == "new" ? 1 : 0
  compartment_id = var.tenancy_ocid
  name           = "${local.product_name}-aidp-service"
  description    = "AIDP service access for the new Governance platform"
  statements = [
    "Allow any-user to {AUTHENTICATION_INSPECT, DOMAIN_INSPECT, DOMAIN_READ, DYNAMIC_GROUP_INSPECT, GROUP_INSPECT, GROUP_MEMBERSHIP_INSPECT, USER_INSPECT, USER_READ} in tenancy where all {request.principal.type='aidataplatform'}",
    "Allow any-user to manage log-groups in compartment id ${var.compartment_ocid} where all {request.principal.type='aidataplatform'}",
    "Allow any-user to read log-content in compartment id ${var.compartment_ocid} where all {request.principal.type='aidataplatform'}",
    "Allow any-user to use metrics in compartment id ${var.compartment_ocid} where all {request.principal.type='aidataplatform', target.metrics.namespace='oracle_aidataplatform'}",
    "Allow any-user to manage buckets in compartment id ${var.compartment_ocid} where all {request.principal.type='aidataplatform', any {request.permission='BUCKET_CREATE', request.permission='BUCKET_INSPECT', request.permission='BUCKET_READ', request.permission='BUCKET_UPDATE'}}",
    "Allow any-user to {TAG_NAMESPACE_USE} in tenancy where all {request.principal.type='aidataplatform'}",
    "Allow any-user to manage objects in compartment id ${var.compartment_ocid} where all {request.principal.id=target.bucket.system-tag.orcl-aidp.governingAidpId}",
    "Allow any-user to read objectstorage-namespaces in tenancy where all {request.principal.type='aidataplatform'}",
    "Allow any-user to use generative-ai-family in compartment id ${var.compartment_ocid} where all {request.principal.type='aidataplatform'}"
  ]
}

# Preserve the bounded IAM replication barrier of the frozen source.
resource "time_sleep" "aidp_iam_propagation" {
  count           = var.aidp_mode == "new" ? 1 : 0
  create_duration = "5m"
  triggers = {
    policy_id         = oci_identity_policy.aidp_service[0].id
    policy_statements = sha256(jsonencode(oci_identity_policy.aidp_service[0].statements))
  }
}

resource "oci_objectstorage_bucket" "artifacts" {
  count          = var.artifacts_mode == "new" ? 1 : 0
  compartment_id = var.compartment_ocid
  namespace      = var.objectstorage_namespace
  name           = var.artifacts_bucket_name
  access_type    = "NoPublicAccess"
  versioning     = "Enabled"
  lifecycle {
    prevent_destroy = true
  }
}
