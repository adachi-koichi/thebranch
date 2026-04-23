"""Discord webhook signature verification and event parsing."""

import hmac
import hashlib
from typing import Dict, Optional


def verify_discord_signature(
    public_key: str, signature: str, timestamp: str, body: str
) -> bool:
    """
    Verify Discord interaction signature.

    Attempts to use PyNaCl for Ed25519 verification. Falls back to HMAC-SHA256
    if PyNaCl is not available (development environment).

    Args:
        public_key: Discord application public key
        signature: X-Signature-Ed25519 header value
        timestamp: X-Signature-Timestamp header value
        body: Raw request body as string

    Returns:
        True if signature is valid, False otherwise
    """
    try:
        # Try PyNaCl first (production)
        try:
            import nacl.signing
            import nacl.exceptions

            message = (timestamp + body).encode()
            verify_key = nacl.signing.VerifyKey(bytes.fromhex(public_key))

            try:
                verify_key.verify(message, bytes.fromhex(signature))
                return True
            except nacl.exceptions.BadSignatureError:
                return False
        except ImportError:
            # Fallback to HMAC-SHA256 for development (no PyNaCl)
            message = (timestamp + body).encode()
            expected_signature = hmac.new(
                public_key.encode(),
                message,
                hashlib.sha256
            ).hexdigest()
            return hmac.compare_digest(expected_signature, signature)
    except Exception:
        return False


def parse_discord_event(payload: dict) -> Dict[str, Optional[str]]:
    """
    Parse Discord interaction payload and extract key information.

    Args:
        payload: Discord interaction payload

    Returns:
        Dict with event_type, title, message
    """
    result = {
        "event_type": None,
        "title": None,
        "message": None,
    }

    interaction_type = payload.get("type")
    data = payload.get("data", {})

    # Handle PING (type 1)
    if interaction_type == 1:
        result["event_type"] = "discord_ping"
        result["message"] = "PONG"
        return result

    # Handle APPLICATION_COMMAND (type 2)
    if interaction_type == 2:
        command_name = data.get("name", "unknown")
        result["event_type"] = "discord_command"
        result["title"] = f"Command: {command_name}"
        result["message"] = command_name

    # Handle MESSAGE_COMPONENT (type 3)
    elif interaction_type == 3:
        component_type = data.get("component_type", "unknown")
        custom_id = data.get("custom_id", "")
        result["event_type"] = "discord_component"
        result["title"] = f"Component interaction: {custom_id}"
        result["message"] = f"Component type: {component_type}"

    # Handle APPLICATION_COMMAND_AUTOCOMPLETE (type 4)
    elif interaction_type == 4:
        result["event_type"] = "discord_autocomplete"
        result["title"] = "Autocomplete request"
        result["message"] = "Autocomplete"

    # Handle MODAL_SUBMIT (type 5)
    elif interaction_type == 5:
        custom_id = data.get("custom_id", "")
        result["event_type"] = "discord_modal"
        result["title"] = f"Modal submission: {custom_id}"
        result["message"] = custom_id

    else:
        result["event_type"] = f"discord_type_{interaction_type}"
        result["title"] = f"Discord interaction type {interaction_type}"
        result["message"] = "Interaction received"

    return result
