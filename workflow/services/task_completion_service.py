"""Task completion event detection and webhook notification service"""
import logging
from datetime import datetime
from typing import Optional
from workflow.repositories.task_completion_repository import TaskCompletionRepository
from workflow.models.task_completion_event import TaskCompletionEvent, WebhookSubscription

logger = logging.getLogger(__name__)


class TaskCompletionService:
    """Service for detecting task completion and triggering webhooks"""

    def __init__(self, db_path: str):
        self.repo = TaskCompletionRepository(db_path)

    def detect_and_create_event(
        self,
        task_id: int,
        workflow_id: str,
        team_name: str,
        executor_user_id: str,
        executor_username: str,
        executor_role: str,
        status: str = 'completed',
        priority: int = 3,
        completion_time_ms: Optional[int] = None,
        tag_ids: Optional[str] = None,
        category: Optional[str] = None,
        phase: Optional[str] = None
    ) -> TaskCompletionEvent:
        """
        Detect task completion and create event.
        Called when task status changes to 'completed'.
        """
        event = self.repo.create_event(
            task_id=task_id,
            workflow_id=workflow_id,
            team_name=team_name,
            executor_user_id=executor_user_id,
            executor_username=executor_username,
            executor_role=executor_role,
            status=status,
            priority=priority,
            completion_time_ms=completion_time_ms,
            tag_ids=tag_ids,
            category=category,
            phase=phase
        )
        logger.info(f"Created completion event #{event.event_id} for task #{task_id}")
        return event

    def get_subscriptions_for_event(
        self,
        event: TaskCompletionEvent
    ) -> list[WebhookSubscription]:
        """Get all active webhook subscriptions for the event"""
        subscriptions = self.repo.get_subscriptions_for_task(event.task_id)
        logger.info(f"Found {len(subscriptions)} subscriptions for event #{event.event_id}")
        return subscriptions

    def queue_webhook_deliveries(
        self,
        event: TaskCompletionEvent,
        subscriptions: list[WebhookSubscription]
    ) -> list[tuple[WebhookSubscription, int]]:
        """
        Queue webhook deliveries to subscribers.
        Returns list of (subscription, delivery_log_id) tuples.
        """
        deliveries = []
        for subscription in subscriptions:
            try:
                # Log delivery as pending
                delivery_log = self.repo.log_delivery(
                    webhook_id=subscription.webhook_id,
                    event_id=event.event_id,
                    attempt_number=1,
                    delivery_status='pending'
                )
                deliveries.append((subscription, delivery_log.delivery_id))
                logger.info(
                    f"Queued delivery #{delivery_log.delivery_id} "
                    f"for webhook {subscription.webhook_id} (event #{event.event_id})"
                )
            except Exception as e:
                logger.error(
                    f"Failed to queue delivery for webhook {subscription.webhook_id}: {e}"
                )
        return deliveries

    def update_event_status(
        self,
        event_id: int,
        new_status: str
    ) -> None:
        """Update event dispatch status"""
        self.repo.update_event_status(event_id, new_status)
        logger.info(f"Updated event #{event_id} status to {new_status}")

    def record_delivery_success(
        self,
        delivery_log_id: int,
        webhook_id: str,
        http_status_code: int,
        response_body: Optional[str] = None
    ) -> None:
        """Record successful webhook delivery"""
        now = datetime.now().isoformat()
        self.repo.update_delivery_status(
            delivery_log_id,
            'sent',
            http_status_code=http_status_code,
            response_body=response_body,
            sent_at=now
        )
        self.repo.update_subscription_stats(webhook_id, 'success', http_status_code)
        logger.info(
            f"Recorded successful delivery #{delivery_log_id} "
            f"(webhook {webhook_id}, status {http_status_code})"
        )

    def record_delivery_failure(
        self,
        delivery_log_id: int,
        webhook_id: str,
        http_status_code: Optional[int] = None,
        error_message: Optional[str] = None
    ) -> None:
        """Record failed webhook delivery"""
        self.repo.update_delivery_status(
            delivery_log_id,
            'failed',
            http_status_code=http_status_code,
            error_message=error_message
        )
        self.repo.update_subscription_stats(webhook_id, 'failure', http_status_code)
        logger.error(
            f"Recorded failed delivery #{delivery_log_id} "
            f"(webhook {webhook_id}, error: {error_message})"
        )

    def get_event_details(self, event_id: int) -> Optional[TaskCompletionEvent]:
        """Get full event details with delivery history"""
        event = self.repo.get_event_by_id(event_id)
        if event:
            logger.info(f"Retrieved event details for #{event_id}")
        return event

    def get_event_deliveries(self, event_id: int):
        """Get all deliveries for an event"""
        deliveries = self.repo.get_delivery_logs(event_id)
        logger.info(f"Retrieved {len(deliveries)} deliveries for event #{event_id}")
        return deliveries

    def get_webhook_stats(self, webhook_id: str) -> Optional[WebhookSubscription]:
        """Get webhook statistics and status"""
        subscription = self.repo.get_subscription_by_id(webhook_id)
        if subscription:
            logger.info(f"Retrieved stats for webhook {webhook_id}")
        return subscription
