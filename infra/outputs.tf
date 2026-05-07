output "iam_access_key_id" {
  value       = aws_iam_access_key.dairy_demo.id
  description = "AWS_ACCESS_KEY_ID for the dairy-demo-notifications user"
}

output "iam_secret_access_key" {
  value       = aws_iam_access_key.dairy_demo.secret
  description = "AWS_SECRET_ACCESS_KEY for the dairy-demo-notifications user — only retrievable via terraform output"
  sensitive   = true
}

output "firebase_android_app_id" {
  value       = google_firebase_android_app.dairy_monitor.app_id
  description = "Firebase Android App ID"
}

output "google_services_json_path" {
  value       = local_file.google_services_json.filename
  description = "Path where google-services.json was written — ready for Expo build"
}

output "sns_platform_application_arn" {
  value = (
    length(aws_sns_platform_application.dairy_demo_android) > 0
    ? aws_sns_platform_application.dairy_demo_android[0].arn
    : "Not yet created — set fcm_server_key in terraform.tfvars and re-run terraform apply"
  )
  description = "Set this as SNS_PLATFORM_APP_ARN in the backend environment"
}

output "next_step" {
  value = (
    var.fcm_server_key == ""
    ? "Step 2: Firebase console → Project Settings → Cloud Messaging → copy Server key → add fcm_server_key to terraform.tfvars → run terraform apply"
    : "All done. Export SNS_PLATFORM_APP_ARN from the sns_platform_application_arn output."
  )
  description = "What to do next"
  sensitive   = true
}
