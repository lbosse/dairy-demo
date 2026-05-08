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

variable "fcm_service_account_json_path" {
  description = <<-EOT
    Path to the Firebase service account private key JSON file.
    Leave empty ("") on first apply — Firebase resources will be created and google-services.json
    will be written to mobile/. Then retrieve the file from:
      Firebase console → Project Settings → Service accounts → Generate new private key
    Set this to the path of the downloaded JSON file and run terraform apply again.
  EOT
  type    = string
  default = ""
}
