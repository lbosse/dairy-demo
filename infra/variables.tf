variable "gcp_project_id" {
  description = "GCP project ID. Create one at console.cloud.google.com before running Terraform."
  type        = string
}

variable "gcp_region" {
  description = "GCP region for Firebase resources."
  type        = string
  default     = "us-central1"
}

variable "aws_region" {
  description = "AWS region for SNS."
  type        = string
  default     = "us-east-1"
}

variable "fcm_server_key" {
  description = <<-EOT
    Firebase Cloud Messaging Server key.
    Leave empty ("") on first apply — Firebase resources will be created and google-services.json
    will be written to mobile/. Then retrieve the key from:
      Firebase console → Project Settings → Cloud Messaging → Server key
    Add it to terraform.tfvars and run terraform apply again to create the SNS Platform Application.
  EOT
  type      = string
  default   = ""
  sensitive = true
}
