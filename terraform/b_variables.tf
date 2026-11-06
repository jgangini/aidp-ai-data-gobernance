variable "tenancy_ocid" {
  type = string
}
variable "compartment_ocid" {
  description = "Compartment resolved and authorized by Deploy Studio."
  type        = string
}
variable "region" {
  type = string
}
variable "home_region" {
  type = string
}
variable "objectstorage_namespace" {
  type = string
}
variable "deployment_suffix" {
  type = string
  validation {
    condition     = can(regex("^[a-z0-9]{4,12}$", var.deployment_suffix))
    error_message = "deployment_suffix must be a stable 4-12 character lowercase deployment identifier."
  }
}
variable "aidp_mode" {
  type    = string
  default = "existing"
  validation {
    condition     = contains(["new", "existing"], var.aidp_mode)
    error_message = "aidp_mode must be new or existing."
  }
}
variable "existing_ai_data_platform_ocid" {
  type    = string
  default = ""
  validation {
    condition     = var.aidp_mode != "existing" || can(regex("^ocid1\\.aidataplatform\\.", var.existing_ai_data_platform_ocid))
    error_message = "An explicit AIDP OCID is required for existing mode."
  }
}
variable "existing_workspace_key" {
  type    = string
  default = ""
  validation {
    condition     = var.aidp_mode != "existing" || can(regex("^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$", var.existing_workspace_key))
    error_message = "An exact canonical workspace UUID is required for existing mode."
  }
}
variable "identity_domain_id" {
  type = string
  validation {
    condition     = can(regex("^ocid1\\.domain\\.", var.identity_domain_id))
    error_message = "Select the exact identity domain."
  }
}
variable "admin_user_ocid" {
  description = "Selected administrator; never changes the operator signer."
  type        = string
  validation {
    condition     = can(regex("^ocid1\\.user\\.", var.admin_user_ocid))
    error_message = "Select an administrator by stable user OCID."
  }
}
variable "artifacts_mode" {
  type    = string
  default = "existing"
  validation {
    condition     = contains(["new", "existing"], var.artifacts_mode)
    error_message = "artifacts_mode must be new or existing."
  }
}
variable "artifacts_bucket_name" {
  type = string
  validation {
    condition     = can(regex("^[A-Za-z0-9._-]{1,128}$", var.artifacts_bucket_name))
    error_message = "Use an explicit artifacts bucket name."
  }
}
variable "model_id" {
  description = "Existing authorized OCI Generative AI model; validated by preflight."
  type        = string
}
variable "governance_operation" {
  type    = string
  default = "install"
  validation {
    condition     = contains(["install", "resume", "update", "redeploy"], var.governance_operation)
    error_message = "Governance operation must be install, resume, update or redeploy."
  }
}
