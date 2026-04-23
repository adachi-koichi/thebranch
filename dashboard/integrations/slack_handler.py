"""Slack webhook signature verification and event parsing."""

import hmac
import hashlib
import time
from typing import Dict, Optional


def verify_slack_signature(
    body: bytes, timestamp: str, signature: str, signing_secret: str
) -> bool:
    """
    Verify Slack webhook signature.

    Args:
        body: Raw request body as bytes
        timestamp: X-Slack-Request-Timestamp header value
        signature: X-Slack-Signature header value
        signing_secret: Slack app signing secret

    Returns:
        True if signature is valid, False otherwise
    """
    try:
        # Check timestamp freshness (must be within 5 minutes)
        request_time = int(timestamp)
        current_time = int(time.time())
        if abs(current_time - request_time) > 300:  # 5 minutes
            return False

        # Create signature base string
        base_string = f"v0:{timestamp}:{body.decode('utf-8')}"

        # Compute expected signature
        expected_signature = (
            "v0=" +
            hmac.new(
                signing_secret.encode(),
                base_string.encode(),
                hashlib.sha256
            ).hexdigest()
        )

        # Constant-time comparison
        return hmac.compare_digest(expected_signature, signature)
    except Exception:
        return False


def parse_slack_event(payload: dict) -> Dict[str, Optional[str]]:
    """
    Parse Slack event payload and extract key information.

    Args:
        payload: Slack event payload

    Returns:
        Dict with event_type, title, message
    """
    result = {
        "event_type": None,
        "title": None,
        "message": None,
    }

    # Handle URL verification challenge
    if payload.get("type") == "url_verification":
        result["event_type"] = "url_verification"
        result["message"] = payload.get("challenge")
        return result

    # Handle event_callback
    if payload.get("type") == "event_callback":
        event = payload.get("event", {})
        event_type_str = event.get("type")

        # Map Slack event types
        if event_type_str == "message":
            result["event_type"] = "slack_message"
            result["title"] = "Message received"
            result["message"] = event.get("text", "")[:200]
        elif event_type_str == "app_mention":
            result["event_type"] = "slack_mention"
            result["title"] = "You were mentioned"
            result["message"] = event.get("text", "")[:200]
        elif event_type_str == "reaction_added":
            result["event_type"] = "slack_reaction"
            result["title"] = "Reaction added"
            result["message"] = f":{event.get('reaction', 'unknown')}:"
        else:
            result["event_type"] = f"slack_{event_type_str or 'unknown'}"
            result["title"] = f"Slack event: {event_type_str or 'unknown'}"
            result["message"] = "Event received"

    return result
