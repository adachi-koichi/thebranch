from datetime import datetime
from workflow.models.task_completion_event import (
    TaskCompletionEvent, WebhookSubscription, WebhookDeliveryLog
)
from workflow.repositories.base import BaseRepository
import uuid


class TaskCompletionRepository(BaseRepository):
    """Repository for task completion events and webhook management"""

    def create_event(
        self,
        task_id: int,
        workflow_id: str,
        team_name: str,
        executor_user_id: str,
        executor_username: str,
        executor_role: str,
        status: str = 'completed',
        priority: int = 3,
        completion_time_ms: int = None,
        tag_ids: str = None,
        category: str = None,
        phase: str = None
    ) -> TaskCompletionEvent:
        """Create task completion event"""
        now = datetime.now().isoformat()
        query = '''
            INSERT INTO task_completion_events
            (task_id, workflow_id, team_name, executor_user_id, executor_username,
             executor_role, status, priority, completion_time_ms, tag_ids, category,
             phase, event_status, created_at, triggered_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        '''
        event_id = self.execute_insert(
            query,
            (
                task_id, workflow_id, team_name, executor_user_id, executor_username,
                executor_role, status, priority, completion_time_ms, tag_ids, category,
                phase, 'triggered', now, now
            )
        )
        return TaskCompletionEvent(
            event_id=event_id,
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
            phase=phase,
            event_status='triggered',
            created_at=datetime.fromisoformat(now),
            triggered_at=datetime.fromisoformat(now)
        )

    def get_event_by_id(self, event_id: int) -> TaskCompletionEvent | None:
        """Get event by ID"""
        query = 'SELECT * FROM task_completion_events WHERE event_id = ?'
        row = self.execute_one(query, (event_id,))
        return self._row_to_event(row) if row else None

    def get_events_by_task(self, task_id: int) -> list[TaskCompletionEvent]:
        """Get all events for task"""
        query = 'SELECT * FROM task_completion_events WHERE task_id = ? ORDER BY triggered_at DESC'
        rows = self.execute_all(query, (task_id,))
        return [self._row_to_event(row) for row in rows]

    def update_event_status(self, event_id: int, new_status: str) -> None:
        """Update event status"""
        query = 'UPDATE task_completion_events SET event_status = ? WHERE event_id = ?'
        self.execute_insert(query, (new_status, event_id))

    def subscribe_webhook(
        self,
        user_id: str,
        name: str,
        target_url: str,
        auth_type: str = 'bearer',
        secret_key_hash: str = None,
        retry_policy: str = None,
        custom_headers: str = None
    ) -> WebhookSubscription:
        """Create webhook subscription"""
        webhook_id = f"wh_{uuid.uuid4().hex[:20]}"
        now = datetime.now().isoformat()
        default_retry = '{"max_retries": 3, "retry_backoff_ms": 1000, "timeout_ms": 5000}'
        # Generate default hash if not provided
        if secret_key_hash is None:
            secret_key_hash = f"hash_{uuid.uuid4().hex[:20]}"

        query = '''
            INSERT INTO webhook_subscriptions
            (webhook_id, user_id, name, event_type, target_url, auth_type,
             secret_key_hash, is_active, retry_policy, custom_headers, created_at, updated_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        '''
        self.execute_insert(
            query,
            (
                webhook_id, user_id, name, 'task.completed', target_url,
                auth_type, secret_key_hash, 1, retry_policy or default_retry,
                custom_headers, now, now
            )
        )
        return WebhookSubscription(
            webhook_id=webhook_id,
            user_id=user_id,
            name=name,
            target_url=target_url,
            auth_type=auth_type,
            secret_key_hash=secret_key_hash,
            retry_policy=retry_policy or default_retry,
            custom_headers=custom_headers,
            created_at=datetime.fromisoformat(now),
            updated_at=datetime.fromisoformat(now)
        )

    def get_subscriptions_for_task(self, task_id: int) -> list[WebhookSubscription]:
        """Get active subscriptions (currently all active, can be filtered per task later)"""
        query = '''
            SELECT * FROM webhook_subscriptions
            WHERE is_active = 1 AND event_type = 'task.completed'
            ORDER BY created_at DESC
        '''
        rows = self.execute_all(query)
        return [self._row_to_subscription(row) for row in rows]

    def get_subscription_by_id(self, webhook_id: str) -> WebhookSubscription | None:
        """Get subscription by ID"""
        query = 'SELECT * FROM webhook_subscriptions WHERE webhook_id = ?'
        row = self.execute_one(query, (webhook_id,))
        return self._row_to_subscription(row) if row else None

    def update_subscription_stats(
        self,
        webhook_id: str,
        status: str,
        http_code: int = None
    ) -> None:
        """Update subscription trigger stats"""
        now = datetime.now().isoformat()
        if status == 'success':
            query = '''
                UPDATE webhook_subscriptions
                SET trigger_count = trigger_count + 1,
                    success_count = success_count + 1,
                    last_triggered_at = ?,
                    last_status_code = ?,
                    updated_at = ?
                WHERE webhook_id = ?
            '''
        else:
            query = '''
                UPDATE webhook_subscriptions
                SET trigger_count = trigger_count + 1,
                    failure_count = failure_count + 1,
                    last_triggered_at = ?,
                    last_status_code = ?,
                    updated_at = ?
                WHERE webhook_id = ?
            '''
        self.execute_insert(query, (now, http_code, now, webhook_id))

    def log_delivery(
        self,
        webhook_id: str,
        event_id: int,
        attempt_number: int = 1,
        delivery_status: str = 'pending',
        http_status_code: int = None,
        response_body: str = None,
        last_error_message: str = None
    ) -> WebhookDeliveryLog:
        """Log webhook delivery attempt"""
        now = datetime.now().isoformat()
        query = '''
            INSERT INTO webhook_delivery_logs
            (webhook_id, event_id, attempt_number, delivery_status, http_status_code,
             response_body, last_error_message, created_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        '''
        delivery_id = self.execute_insert(
            query,
            (
                webhook_id, event_id, attempt_number, delivery_status,
                http_status_code, response_body, last_error_message, now
            )
        )
        return WebhookDeliveryLog(
            delivery_id=delivery_id,
            webhook_id=webhook_id,
            event_id=event_id,
            attempt_number=attempt_number,
            delivery_status=delivery_status,
            http_status_code=http_status_code,
            response_body=response_body,
            last_error_message=last_error_message,
            created_at=datetime.fromisoformat(now)
        )

    def get_delivery_logs(self, event_id: int) -> list[WebhookDeliveryLog]:
        """Get delivery logs for event"""
        query = '''
            SELECT * FROM webhook_delivery_logs
            WHERE event_id = ?
            ORDER BY created_at DESC
        '''
        rows = self.execute_all(query, (event_id,))
        return [self._row_to_delivery_log(row) for row in rows]

    def update_delivery_status(
        self,
        delivery_id: int,
        new_status: str,
        http_status_code: int = None,
        response_body: str = None,
        error_message: str = None,
        sent_at: str = None
    ) -> None:
        """Update delivery log status"""
        now = datetime.now().isoformat()
        query = '''
            UPDATE webhook_delivery_logs
            SET delivery_status = ?,
                http_status_code = ?,
                response_body = ?,
                last_error_message = ?,
                sent_at = ?
            WHERE delivery_id = ?
        '''
        self.execute_insert(
            query,
            (new_status, http_status_code, response_body, error_message, sent_at or now, delivery_id)
        )

    def _row_to_event(self, row) -> TaskCompletionEvent:
        """Convert DB row to TaskCompletionEvent"""
        return TaskCompletionEvent(
            event_id=row['event_id'],
            task_id=row['task_id'],
            workflow_id=row['workflow_id'],
            team_name=row['team_name'],
            executor_user_id=row['executor_user_id'],
            executor_username=row['executor_username'],
            executor_role=row['executor_role'],
            status=row['status'],
            priority=row['priority'],
            completion_time_ms=row['completion_time_ms'],
            tag_ids=row['tag_ids'],
            category=row['category'],
            phase=row['phase'],
            event_status=row['event_status'],
            created_at=datetime.fromisoformat(row['created_at']) if row['created_at'] else None,
            triggered_at=datetime.fromisoformat(row['triggered_at']) if row['triggered_at'] else None,
            last_webhook_attempt_at=datetime.fromisoformat(row['last_webhook_attempt_at']) if row['last_webhook_attempt_at'] else None
        )

    def _row_to_subscription(self, row) -> WebhookSubscription:
        """Convert DB row to WebhookSubscription"""
        return WebhookSubscription(
            webhook_id=row['webhook_id'],
            user_id=row['user_id'],
            name=row['name'],
            event_type=row['event_type'],
            target_url=row['target_url'],
            auth_type=row['auth_type'],
            secret_key_hash=row['secret_key_hash'],
            is_active=bool(row['is_active']),
            retry_policy=row['retry_policy'],
            custom_headers=row['custom_headers'],
            trigger_count=row['trigger_count'],
            success_count=row['success_count'],
            failure_count=row['failure_count'],
            last_triggered_at=datetime.fromisoformat(row['last_triggered_at']) if row['last_triggered_at'] else None,
            last_status_code=row['last_status_code'],
            created_at=datetime.fromisoformat(row['created_at']) if row['created_at'] else None,
            updated_at=datetime.fromisoformat(row['updated_at']) if row['updated_at'] else None
        )

    def _row_to_delivery_log(self, row) -> WebhookDeliveryLog:
        """Convert DB row to WebhookDeliveryLog"""
        return WebhookDeliveryLog(
            delivery_id=row['delivery_id'],
            webhook_id=row['webhook_id'],
            event_id=row['event_id'],
            attempt_number=row['attempt_number'],
            delivery_status=row['delivery_status'],
            http_status_code=row['http_status_code'],
            response_body=row['response_body'],
            next_retry_at=datetime.fromisoformat(row['next_retry_at']) if row['next_retry_at'] else None,
            last_error_message=row['last_error_message'],
            created_at=datetime.fromisoformat(row['created_at']) if row['created_at'] else None,
            sent_at=datetime.fromisoformat(row['sent_at']) if row['sent_at'] else None
        )
