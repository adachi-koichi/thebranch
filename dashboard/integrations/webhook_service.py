"""Webhook service for storing events and creating notifications."""

import json
import logging
from typing import Optional, Tuple
from datetime import datetime
import aiosqlite
import httpx

logger = logging.getLogger(__name__)


async def record_webhook_event(
    db: aiosqlite.Connection,
    event_id: str,
    integration_config_id: Optional[int],
    event_type: str,
    event_source: str,
    raw_payload: dict,
    parsed_data: Optional[dict] = None,
    processing_status: str = "received",
) -> int:
    """
    Record a webhook event in webhook_events table.

    Args:
        db: Database connection
        event_id: Unique event identifier
        integration_config_id: Associated integration config ID
        event_type: Type of event (e.g., 'message', 'command')
        event_source: Source ('slack' or 'discord')
        raw_payload: Raw payload as dict
        parsed_data: Parsed event data as dict
        processing_status: Current status

    Returns:
        Row ID of inserted event
    """
    cursor = await db.execute(
        """
        INSERT INTO webhook_events (
            event_id, integration_config_id, event_type, event_source,
            raw_payload, parsed_data, processing_status, received_at
        ) VALUES (?, ?, ?, ?, ?, ?, ?, datetime('now','localtime'))
        """,
        (
            event_id,
            integration_config_id,
            event_type,
            event_source,
            json.dumps(raw_payload),
            json.dumps(parsed_data) if parsed_data else None,
            processing_status,
        ),
    )
    await db.commit()
    return cursor.lastrowid


async def find_integration_config_for_webhook(
    db: aiosqlite.Connection,
    webhook_url: str,
    integration_type: str,
) -> Optional[dict]:
    """
    Find integration config by webhook URL and type.

    Args:
        db: Database connection
        webhook_url: Webhook URL
        integration_type: 'slack' or 'discord'

    Returns:
        Config row as dict or None
    """
    db.row_factory = aiosqlite.Row
    cursor = await db.execute(
        """
        SELECT * FROM integration_configs
        WHERE webhook_url = ? AND integration_type = ? AND is_active = 1
        LIMIT 1
        """,
        (webhook_url, integration_type),
    )
    row = await cursor.fetchone()
    return dict(row) if row else None


async def create_notification_from_webhook(
    db: aiosqlite.Connection,
    title: str,
    message: str,
    notification_type: str,
    integration_config_id: int,
    webhook_event_id: int,
    severity: str = "info",
    slack_message_id: Optional[str] = None,
    discord_message_id: Optional[str] = None,
) -> Optional[int]:
    """
    Create a notification_log entry from a webhook event.

    Args:
        db: Database connection
        title: Notification title
        message: Notification message
        notification_type: Type of notification
        integration_config_id: Associated integration config
        webhook_event_id: Associated webhook event
        severity: Severity level
        slack_message_id: Optional Slack message ID
        discord_message_id: Optional Discord message ID

    Returns:
        Notification ID or None on failure
    """
    try:
        import uuid

        notification_key = f"notif-{uuid.uuid4()}"
        now = datetime.now().isoformat()

        cursor = await db.execute(
            """
            INSERT INTO notification_logs (
                notification_key, notification_type, title, message, severity,
                slack_message_id, discord_message_id, integration_config_id,
                status, created_at, updated_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                notification_key,
                notification_type,
                title,
                message,
                severity,
                slack_message_id,
                discord_message_id,
                integration_config_id,
                "unread",
                now,
                now,
            ),
        )
        await db.commit()

        # Update webhook event with notification ID
        notif_id = cursor.lastrowid
        await db.execute(
            "UPDATE webhook_events SET notification_id = ? WHERE id = ?",
            (notif_id, webhook_event_id),
        )
        await db.commit()

        return notif_id
    except Exception as e:
        logger.error(f"Failed to create notification from webhook: {e}")
        return None


async def verify_webhook_url(webhook_url: str, timeout: float = 5.0) -> Tuple[bool, Optional[str]]:
    """
    Verify that a webhook URL is reachable.

    Sends an empty POST request and checks for 2xx or 3xx response.

    Args:
        webhook_url: URL to verify
        timeout: Request timeout in seconds

    Returns:
        Tuple of (success: bool, error_message: Optional[str])
    """
    try:
        async with httpx.AsyncClient(timeout=timeout) as client:
            response = await client.post(webhook_url, json={})
            if 200 <= response.status_code < 400:
                return True, None
            else:
                return False, f"HTTP {response.status_code}"
    except httpx.TimeoutException:
        return False, "Request timeout"
    except httpx.RequestError as e:
        return False, str(e)
    except Exception as e:
        return False, str(e)
