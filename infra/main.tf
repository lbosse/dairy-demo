terraform {
  required_version = ">= 1.6"

  required_providers {
    google = {
      source  = "hashicorp/google"
      version = "~> 5.0"
    }
    google-beta = {
      source  = "hashicorp/google-beta"
      version = "~> 5.0"
    }
    aws = {
      source  = "hashicorp/aws"
      version = "~> 5.0"
    }
    local = {
      source  = "hashicorp/local"
      version = "~> 2.0"
    }
  }
}

provider "google" {
  project = var.gcp_project_id
  region  = var.gcp_region
}

provider "google-beta" {
  project = var.gcp_project_id
  region  = var.gcp_region
}

provider "aws" {
  region = var.aws_region
}

# ── Google APIs ───────────────────────────────────────────────────────────────

resource "google_project_service" "firebase" {
  project            = var.gcp_project_id
  service            = "firebase.googleapis.com"
  disable_on_destroy = false
}

resource "google_project_service" "fcm" {
  project            = var.gcp_project_id
  service            = "fcm.googleapis.com"
  disable_on_destroy = false
}

# ── Firebase project ──────────────────────────────────────────────────────────

resource "google_firebase_project" "dairy_demo" {
  provider   = google-beta
  project    = var.gcp_project_id
  depends_on = [google_project_service.firebase]
}

# ── Android app registration ──────────────────────────────────────────────────

resource "google_firebase_android_app" "dairy_monitor" {
  provider     = google-beta
  project      = var.gcp_project_id
  display_name = "Dairy Monitor"
  package_name = "com.dairydemo.monitor"
  depends_on   = [google_firebase_project.dairy_demo]
}

# Fetches the google-services.json content after the app is registered.
data "google_firebase_android_app_config" "dairy_monitor" {
  provider = google-beta
  app_id   = google_firebase_android_app.dairy_monitor.app_id
}

# Writes google-services.json directly into the mobile app directory.
resource "local_file" "google_services_json" {
  filename = "${path.module}/../mobile/google-services.json"
  content  = base64decode(data.google_firebase_android_app_config.dairy_monitor.config_file_contents)
}

# ── AWS SNS Platform Application ─────────────────────────────────────────────
#
# Skipped on the first apply (when fcm_server_key is empty string).
#
# After step 1 completes:
#   Firebase console → Project Settings → Cloud Messaging → copy Server key
#   Add it to terraform.tfvars, then run: terraform apply
#
resource "aws_sns_platform_application" "dairy_demo_android" {
  count               = var.fcm_server_key != "" ? 1 : 0
  name                = "dairy-demo-android"
  platform            = "GCM"
  platform_credential = var.fcm_server_key
}
