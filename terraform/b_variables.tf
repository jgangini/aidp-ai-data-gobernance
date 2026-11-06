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
    condition     = contains(["install", "resume", "update", "redeploy", "rollback"], var.governance_operation)
    error_message = "Governance operation must be install, resume, update, redeploy or rollback."
  }
}

variable "autonomous_database_mode" {
  description = "Create memory storage or reference an authorized external Autonomous AI Lakehouse."
  type        = string
  default     = "new"
  validation {
    condition     = contains(["new", "existing"], var.autonomous_database_mode)
    error_message = "autonomous_database_mode must be new or existing."
  }
}
variable "existing_autonomous_database_ocid" {
  description = "Exact external Autonomous database OCID; existing resources are never adopted."
  type        = string
  default     = ""
  validation {
    condition     = var.autonomous_database_mode != "existing" || can(regex("^ocid1\\.autonomousdatabase\\.", var.existing_autonomous_database_ocid))
    error_message = "existing_autonomous_database_ocid is required in existing mode."
  }
}
variable "autonomous_database_version" {
  description = "Database version supplied by the Deploy Studio 26ai:DW profile transform."
  type        = string
  default     = "26ai"
  validation {
    condition     = var.autonomous_database_version == "26ai"
    error_message = "Governance memory requires Oracle AI Database 26ai."
  }
}
variable "autonomous_database_workload" {
  description = "The supported memory database workload is DW (AI Lakehouse)."
  type        = string
  default     = "DW"
  validation {
    condition     = var.autonomous_database_workload == "DW"
    error_message = "Governance memory requires the DW workload."
  }
}
variable "autonomous_database_admin_password" {
  description = "ADMIN credential for creation and authorized enableAiFeature; never an output."
  type        = string
  sensitive   = true
  default     = ""
  validation {
    condition = (
      (var.autonomous_database_mode == "existing" && var.autonomous_database_admin_password == "") ||
      (
        length(var.autonomous_database_admin_password) >= 12 &&
        length(var.autonomous_database_admin_password) <= 30 &&
        can(regex("[A-Z]", var.autonomous_database_admin_password)) &&
        can(regex("[a-z]", var.autonomous_database_admin_password)) &&
        can(regex("[0-9]", var.autonomous_database_admin_password)) &&
        !strcontains(lower(var.autonomous_database_admin_password), "admin") &&
        !strcontains(var.autonomous_database_admin_password, "\"") &&
        !strcontains(var.autonomous_database_admin_password, "'")
      )
    )
    error_message = "A new database requires a 12-30 character ADMIN password with upper/lowercase and a number, without quotes or the word admin. Existing mode may omit it."
  }
}
