from dataclasses import dataclass
from datetime import datetime
from typing import Optional
import json


@dataclass
class TaskCompletionEvent:
    """Task completion event for webhook notifications"""
    event_id: Optional[int] = None
    task_id: int = None
    workflow_id: str = None
    team_name: str = None
    executor_user_id: str = None
    executor_username: str = None
    executor_role: str = None
    status: str = 'completed'
    priority: int = 3
    completion_time_ms: Optional[int] = None
    tag_ids: Optional[str] = None
    category: Optional[str] = None
    phase: Optional[str] = None
    event_status: str = 'triggered'
    created_at: Optional[datetime] = None
    triggered_at: Optional[datetime] = None
    last_webhook_attempt_at: Optional[datetime] = None

    def get_tag_ids_list(self) -> list[str]:
        """Parse tag_ids JSON to list"""
        if not self.tag_ids:
            return []
        return json.loads(self.tag_ids)

    def set_tag_ids_list(self, tags: list[str]):
        """Set tag_ids from list"""
        self.tag_ids = json.dumps(tags)


@dataclass
class WebhookSubscription:
    """Webhook subscription for task completion events"""
    webhook_id: str = None
    user_id: str = None
    name: str = None
    event_type: str = 'task.completed'
    target_url: str = None
    auth_type: str = 'bearer'
    secret_key_hash: str = None
    is_active: bool = True
    retry_policy: Optional[str] = None
    custom_headers: Optional[str] = None
    trigger_count: int = 0
    success_count: int = 0
    failure_count: int = 0
    last_triggered_at: Optional[datetime] = None
    last_status_code: Optional[int] = None
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None

    def get_retry_policy(self) -> dict:
        """Parse retry_policy JSON"""
        if not self.retry_policy:
            return {"max_retries": 3, "retry_backoff_ms": 1000, "timeout_ms": 5000}
        return json.loads(self.retry_policy)

    def get_custom_headers(self) -> dict:
        """Parse custom_headers JSON"""
        if not self.custom_headers:
            return {}
        return json.loads(self.custom_headers)


@dataclass
class WebhookDeliveryLog:
    """Webhook delivery log for tracking"""
    delivery_id: Optional[int] = None
    webhook_id: str = None
    event_id: int = None
    attempt_number: int = 1
    delivery_status: str = 'pending'
    http_status_code: Optional[int] = None
    response_body: Optional[str] = None
    next_retry_at: Optional[datetime] = None
    last_error_message: Optional[str] = None
    created_at: Optional[datetime] = None
    sent_at: Optional[datetime] = None
