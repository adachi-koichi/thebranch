"""Tests for task completion event detection and webhook service"""
import pytest
import sqlite3
from datetime import datetime
from workflow.repositories.task_completion_repository import TaskCompletionRepository
from workflow.services.task_completion_service import TaskCompletionService


@pytest.fixture
def db_conn():
    """Create in-memory test database with tables"""
    conn = sqlite3.connect(':memory:')
    conn.row_factory = sqlite3.Row
    conn.execute('PRAGMA foreign_keys = ON')

    # Create tables
    conn.executescript("""
    CREATE TABLE task_completion_events (
        event_id INTEGER PRIMARY KEY AUTOINCREMENT,
        task_id INTEGER NOT NULL,
        workflow_id TEXT NOT NULL,
        team_name TEXT NOT NULL,
        executor_user_id TEXT NOT NULL,
        executor_username TEXT NOT NULL,
        executor_role TEXT NOT NULL CHECK(executor_role IN ('ai-engineer', 'pm', 'em', 'admin')),
        status TEXT NOT NULL DEFAULT 'completed' CHECK(status IN ('pending', 'in_progress', 'completed', 'failed')),
        priority INTEGER NOT NULL DEFAULT 3 CHECK(priority BETWEEN 1 AND 5),
        completion_time_ms INTEGER,
        tag_ids TEXT,
        category TEXT CHECK(category IN ('infra', 'feature', 'design', 'test')),
        phase TEXT CHECK(phase IN ('design', 'implementation', 'test', 'review')),
        event_status TEXT NOT NULL DEFAULT 'triggered' CHECK(event_status IN ('triggered', 'dispatched', 'acked', 'failed')),
        created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
        triggered_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
        last_webhook_attempt_at DATETIME,
        UNIQUE(task_id, triggered_at)
    );

    CREATE TABLE webhook_subscriptions (
        webhook_id TEXT PRIMARY KEY,
        user_id TEXT NOT NULL,
        name TEXT NOT NULL,
        event_type TEXT NOT NULL DEFAULT 'task.completed' CHECK(event_type IN ('task.completed')),
        target_url TEXT NOT NULL,
        auth_type TEXT NOT NULL CHECK(auth_type IN ('bearer', 'hmac-sha256')),
        secret_key_hash TEXT NOT NULL,
        is_active BOOLEAN NOT NULL DEFAULT 1,
        retry_policy TEXT NOT NULL DEFAULT '{"max_retries": 3, "retry_backoff_ms": 1000, "timeout_ms": 5000}',
        custom_headers TEXT,
        trigger_count INTEGER NOT NULL DEFAULT 0,
        success_count INTEGER NOT NULL DEFAULT 0,
        failure_count INTEGER NOT NULL DEFAULT 0,
        last_triggered_at DATETIME,
        last_status_code INTEGER,
        created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
        updated_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP
    );

    CREATE TABLE webhook_delivery_logs (
        delivery_id INTEGER PRIMARY KEY AUTOINCREMENT,
        webhook_id TEXT NOT NULL,
        event_id INTEGER NOT NULL,
        attempt_number INTEGER NOT NULL DEFAULT 1 CHECK(attempt_number >= 1),
        delivery_status TEXT NOT NULL DEFAULT 'pending' CHECK(delivery_status IN ('pending', 'sent', 'acked', 'failed', 'permanent_failure')),
        http_status_code INTEGER,
        response_body TEXT,
        next_retry_at DATETIME,
        last_error_message TEXT,
        created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
        sent_at DATETIME,
        FOREIGN KEY(webhook_id) REFERENCES webhook_subscriptions(webhook_id) ON DELETE CASCADE,
        FOREIGN KEY(event_id) REFERENCES task_completion_events(event_id) ON DELETE CASCADE
    );
    """)
    conn.commit()
    yield conn
    conn.close()


@pytest.fixture
def repo(db_conn):
    """Create repository with test connection"""
    return TaskCompletionRepository(db_conn)


@pytest.fixture
def service(db_conn):
    """Create service with test repository"""
    service = TaskCompletionService(':memory:')
    service.repo = TaskCompletionRepository(db_conn)
    return service


class TestTaskCompletionRepository:
    def test_create_event(self, repo):
        """Test event creation"""
        event = repo.create_event(
            task_id=1,
            workflow_id='wf-001',
            team_name='engineering',
            executor_user_id='user-1',
            executor_username='alice',
            executor_role='ai-engineer',
            category='feature',
            phase='implementation'
        )
        assert event.event_id is not None
        assert event.task_id == 1
        assert event.status == 'completed'
        assert event.event_status == 'triggered'

    def test_get_event_by_id(self, repo):
        """Test retrieving event"""
        created = repo.create_event(
            task_id=2,
            workflow_id='wf-002',
            team_name='design',
            executor_user_id='user-2',
            executor_username='bob',
            executor_role='pm'
        )
        retrieved = repo.get_event_by_id(created.event_id)
        assert retrieved is not None
        assert retrieved.task_id == 2
        assert retrieved.executor_username == 'bob'

    def test_subscribe_webhook(self, repo):
        """Test webhook subscription"""
        sub = repo.subscribe_webhook(
            user_id='user-1',
            name='Test Webhook',
            target_url='https://example.com/webhook',
            auth_type='bearer',
            secret_key_hash='hash123'
        )
        assert sub.webhook_id is not None
        assert sub.name == 'Test Webhook'
        assert sub.is_active is True

    def test_get_subscriptions(self, repo):
        """Test retrieving subscriptions"""
        repo.subscribe_webhook(
            user_id='user-1',
            name='Webhook 1',
            target_url='https://example.com/1'
        )
        repo.subscribe_webhook(
            user_id='user-2',
            name='Webhook 2',
            target_url='https://example.com/2'
        )
        subs = repo.get_subscriptions_for_task(1)
        assert len(subs) == 2

    def test_log_delivery(self, repo):
        """Test delivery logging"""
        event = repo.create_event(
            task_id=1,
            workflow_id='wf-001',
            team_name='eng',
            executor_user_id='user-1',
            executor_username='alice',
            executor_role='ai-engineer'
        )
        sub = repo.subscribe_webhook(
            user_id='user-1',
            name='Test',
            target_url='https://example.com'
        )
        delivery = repo.log_delivery(
            webhook_id=sub.webhook_id,
            event_id=event.event_id,
            delivery_status='pending'
        )
        assert delivery.delivery_id is not None
        assert delivery.delivery_status == 'pending'

    def test_update_delivery_status(self, repo):
        """Test updating delivery status"""
        event = repo.create_event(
            task_id=1,
            workflow_id='wf-001',
            team_name='eng',
            executor_user_id='user-1',
            executor_username='alice',
            executor_role='ai-engineer'
        )
        sub = repo.subscribe_webhook(
            user_id='user-1',
            name='Test',
            target_url='https://example.com'
        )
        delivery = repo.log_delivery(
            webhook_id=sub.webhook_id,
            event_id=event.event_id
        )
        repo.update_delivery_status(
            delivery.delivery_id,
            'sent',
            http_status_code=200
        )
        updated = repo.get_delivery_logs(event.event_id)[0]
        assert updated.delivery_status == 'sent'
        assert updated.http_status_code == 200


class TestTaskCompletionService:
    def test_detect_and_create_event(self, service):
        """Test event detection"""
        event = service.detect_and_create_event(
            task_id=1,
            workflow_id='wf-001',
            team_name='eng',
            executor_user_id='user-1',
            executor_username='alice',
            executor_role='ai-engineer',
            category='feature'
        )
        assert event.event_id is not None
        assert event.task_id == 1

    def test_get_subscriptions(self, service):
        """Test getting subscriptions for event"""
        # Create subscriptions
        service.repo.subscribe_webhook(
            user_id='user-1',
            name='Webhook 1',
            target_url='https://example.com/1'
        )
        service.repo.subscribe_webhook(
            user_id='user-2',
            name='Webhook 2',
            target_url='https://example.com/2'
        )

        event = service.detect_and_create_event(
            task_id=1,
            workflow_id='wf-001',
            team_name='eng',
            executor_user_id='user-1',
            executor_username='alice',
            executor_role='ai-engineer'
        )

        subs = service.get_subscriptions_for_event(event)
        assert len(subs) == 2

    def test_queue_deliveries(self, service):
        """Test queueing webhook deliveries"""
        # Create webhook subscription
        sub = service.repo.subscribe_webhook(
            user_id='user-1',
            name='Test',
            target_url='https://example.com'
        )

        event = service.detect_and_create_event(
            task_id=1,
            workflow_id='wf-001',
            team_name='eng',
            executor_user_id='user-1',
            executor_username='alice',
            executor_role='ai-engineer'
        )

        deliveries = service.queue_webhook_deliveries(event, [sub])
        assert len(deliveries) == 1
        assert deliveries[0][0].webhook_id == sub.webhook_id

    def test_record_delivery_success(self, service):
        """Test recording successful delivery"""
        sub = service.repo.subscribe_webhook(
            user_id='user-1',
            name='Test',
            target_url='https://example.com'
        )
        event = service.detect_and_create_event(
            task_id=1,
            workflow_id='wf-001',
            team_name='eng',
            executor_user_id='user-1',
            executor_username='alice',
            executor_role='ai-engineer'
        )
        delivery = service.repo.log_delivery(
            webhook_id=sub.webhook_id,
            event_id=event.event_id
        )

        service.record_delivery_success(
            delivery.delivery_id,
            sub.webhook_id,
            200,
            'OK'
        )

        logs = service.repo.get_delivery_logs(event.event_id)
        assert logs[0].delivery_status == 'sent'
        assert logs[0].http_status_code == 200

    def test_record_delivery_failure(self, service):
        """Test recording failed delivery"""
        sub = service.repo.subscribe_webhook(
            user_id='user-1',
            name='Test',
            target_url='https://example.com'
        )
        event = service.detect_and_create_event(
            task_id=1,
            workflow_id='wf-001',
            team_name='eng',
            executor_user_id='user-1',
            executor_username='alice',
            executor_role='ai-engineer'
        )
        delivery = service.repo.log_delivery(
            webhook_id=sub.webhook_id,
            event_id=event.event_id
        )

        service.record_delivery_failure(
            delivery.delivery_id,
            sub.webhook_id,
            500,
            'Connection timeout'
        )

        logs = service.repo.get_delivery_logs(event.event_id)
        assert logs[0].delivery_status == 'failed'
        assert logs[0].http_status_code == 500
        assert logs[0].last_error_message == 'Connection timeout'


if __name__ == '__main__':
    pytest.main([__file__, '-v'])
