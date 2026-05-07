# Looks up the current AWS account ID and region so we can build precise ARNs
# without hardcoding them.
data "aws_caller_identity" "current" {}
data "aws_region" "current" {}

locals {
  # ARN of the SNS platform application (known at plan time from naming convention)
  platform_app_arn = "arn:aws:sns:${data.aws_region.current.name}:${data.aws_caller_identity.current.account_id}:app/GCM/dairy-demo-android"

  # All device endpoint ARNs created under that platform application
  endpoint_arn_pattern = "arn:aws:sns:${data.aws_region.current.name}:${data.aws_caller_identity.current.account_id}:endpoint/GCM/dairy-demo-android/*"
}

resource "aws_iam_user" "dairy_demo" {
  name = "dairy-demo-notifications"
  path = "/dairy-demo/"
}

resource "aws_iam_access_key" "dairy_demo" {
  user = aws_iam_user.dairy_demo.name
}

resource "aws_iam_user_policy" "sns_notifications" {
  name = "dairy-demo-sns"
  user = aws_iam_user.dairy_demo.name

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        # CreatePlatformApplication must allow * — the resource doesn't exist yet when creating
        Sid      = "CreatePlatformApplication"
        Effect   = "Allow"
        Action   = ["sns:CreatePlatformApplication"]
        Resource = "*"
      },
      {
        # All other platform app management scoped to exactly this app
        Sid    = "ManagePlatformApplication"
        Effect = "Allow"
        Action = [
          "sns:GetPlatformApplicationAttributes",
          "sns:SetPlatformApplicationAttributes",
          "sns:DeletePlatformApplication",
          "sns:ListEndpointsByPlatformApplication",
        ]
        Resource = local.platform_app_arn
      },
      {
        # Device endpoint registration and notification publishing
        # scoped to endpoints under this app only
        Sid    = "ManageDeviceEndpointsAndPublish"
        Effect = "Allow"
        Action = [
          "sns:CreatePlatformEndpoint",
          "sns:GetEndpointAttributes",
          "sns:SetEndpointAttributes",
          "sns:DeleteEndpoint",
          "sns:Publish",
        ]
        Resource = local.endpoint_arn_pattern
      },
    ]
  })
}
