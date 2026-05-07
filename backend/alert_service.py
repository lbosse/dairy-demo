"""SNS → FCM push notification delivery."""

import os
import boto3
from botocore.exceptions import ClientError

_sns = boto3.client("sns", region_name=os.environ.get("AWS_REGION", "us-east-1"))
PLATFORM_APP_ARN = os.environ.get("SNS_PLATFORM_APP_ARN", "")

# In-memory registry: fcm_token → endpoint_arn
_endpoints: dict[str, str] = {}


def register_device(fcm_token: str) -> str:
    """Create or retrieve an SNS platform endpoint for a device FCM token."""
    if fcm_token in _endpoints:
        return _endpoints[fcm_token]

    if not PLATFORM_APP_ARN:
        print("WARNING: SNS_PLATFORM_APP_ARN not set — push notifications disabled")
        return ""

    try:
        resp = _sns.create_platform_endpoint(
            PlatformApplicationArn=PLATFORM_APP_ARN,
            Token=fcm_token,
        )
        arn = resp["EndpointArn"]
        _endpoints[fcm_token] = arn
        return arn
    except ClientError as e:
        print(f"SNS endpoint creation failed: {e}")
        return ""


def send_alert(cow_id: int, down_minutes: float):
    """Send a push notification to all registered devices."""
    if not _endpoints:
        print(f"[ALERT] Cow #{cow_id} down {down_minutes:.1f} min — no devices registered")
        return

    message = f"Cow #{cow_id} has been down for {down_minutes:.1f} minutes"
    for token, arn in list(_endpoints.items()):
        if not arn:
            continue
        try:
            _sns.publish(
                TargetArn=arn,
                Message=message,
                Subject="Down Cow Alert",
                MessageStructure="string",
            )
            print(f"[ALERT SENT] {message}")
        except ClientError as e:
            print(f"SNS publish failed for {arn}: {e}")
