"""
Tests for lock-free task queue.

Covers idempotent enqueuing, version-aware dequeuing, conflict resolution.
"""

import sqlite3
import tempfile
import threading
import time
import pytest
from workflow.services.lock_free_queue import LockFreeTaskQueue


@pytest.fixture
def temp_db():
    """Create temporary database for testing."""
    with tempfile.NamedTemporaryFile(suffix='.sqlite', delete=False) as f:
        db_path = f.name
    yield db_path
    import os
    os.unlink(db_path)


class TestIdempotentEnqueue:
    """Test idempotent enqueuing."""

    def test_enqueue_single_task(self, temp_db):
        """Enqueue single task returns task ID."""
        queue = LockFreeTaskQueue(temp_db)
        task_def = {'title': 'task1', 'assignee': 'alice', 'phase': 'impl'}

        task_id = queue.enqueue_idempotent(task_def)
        assert task_id > 0

    def test_enqueue_duplicate_task_returns_same_id(self, temp_db):
        """Enqueuing identical task twice returns same ID."""
        queue = LockFreeTaskQueue(temp_db)
        task_def = {'title': 'task1', 'assignee': 'alice', 'phase': 'impl'}

        id1 = queue.enqueue_idempotent(task_def)
        id2 = queue.enqueue_idempotent(task_def)
        assert id1 == id2

    def test_enqueue_multiple_different_tasks(self, temp_db):
        """Enqueuing different tasks returns different IDs."""
        queue = LockFreeTaskQueue(temp_db)
        task1 = {'title': 'task1', 'assignee': 'alice', 'phase': 'impl'}
        task2 = {'title': 'task2', 'assignee': 'alice', 'phase': 'impl'}

        id1 = queue.enqueue_idempotent(task1)
        id2 = queue.enqueue_idempotent(task2)
        assert id1 != id2


class TestVersionedDequeue:
    """Test version-aware dequeuing."""

    def test_dequeue_returns_pending_task(self, temp_db):
        """Dequeue returns task with version."""
        queue = LockFreeTaskQueue(temp_db)
        task_def = {'title': 'task1', 'assignee': 'alice', 'phase': 'impl'}
        queue.enqueue_idempotent(task_def)

        result = queue.dequeue_and_acquire('worker1')
        assert result is not None
        assert result['id'] > 0
        assert result['version'] == 1

    def test_dequeue_sets_in_progress_status(self, temp_db):
        """Dequeue sets task status to in_progress."""
        queue = LockFreeTaskQueue(temp_db)
        task_def = {'title': 'task1', 'assignee': 'alice', 'phase': 'impl'}
        queue.enqueue_idempotent(task_def)

        result = queue.dequeue_and_acquire('worker1')
        task = queue.get_task(result['id'])
        assert task['status'] == 'in_progress'

    def test_dequeue_empty_queue_returns_none(self, temp_db):
        """Dequeue from empty queue returns None."""
        queue = LockFreeTaskQueue(temp_db)
        result = queue.dequeue_and_acquire('worker1')
        assert result is None

    def test_dequeue_skips_in_progress_task(self, temp_db):
        """Dequeue skips already acquired task."""
        queue = LockFreeTaskQueue(temp_db)
        task_def = {'title': 'task1', 'assignee': 'alice', 'phase': 'impl'}
        queue.enqueue_idempotent(task_def)

        result1 = queue.dequeue_and_acquire('worker1')
        result2 = queue.dequeue_and_acquire('worker2')
        assert result2 is None


class TestRelease:
    """Test release with version checking."""

    def test_release_with_correct_version_succeeds(self, temp_db):
        """Release with correct version succeeds."""
        queue = LockFreeTaskQueue(temp_db)
        task_def = {'title': 'task1', 'assignee': 'alice', 'phase': 'impl'}
        queue.enqueue_idempotent(task_def)

        result = queue.dequeue_and_acquire('worker1')
        success = queue.release_with_version(result['id'], result['version'], 'completed')
        assert success is True

    def test_release_with_wrong_version_fails(self, temp_db):
        """Release with wrong version fails (conflict)."""
        queue = LockFreeTaskQueue(temp_db)
        task_def = {'title': 'task1', 'assignee': 'alice', 'phase': 'impl'}
        queue.enqueue_idempotent(task_def)

        result = queue.dequeue_and_acquire('worker1')
        success = queue.release_with_version(result['id'], 0, 'completed')
        assert success is False

    def test_release_updates_status(self, temp_db):
        """Release updates task status."""
        queue = LockFreeTaskQueue(temp_db)
        task_def = {'title': 'task1', 'assignee': 'alice', 'phase': 'impl'}
        queue.enqueue_idempotent(task_def)

        result = queue.dequeue_and_acquire('worker1')
        queue.release_with_version(result['id'], result['version'], 'completed')

        task = queue.get_task(result['id'])
        assert task['status'] == 'completed'


class TestMultithread:
    """Test concurrent access."""

    def test_concurrent_dequeue_no_duplicates(self, temp_db):
        """Multiple workers dequeuing doesn't create duplicate acquisitions."""
        queue = LockFreeTaskQueue(temp_db)

        # Enqueue 5 tasks
        task_ids = []
        for i in range(5):
            task_def = {'title': f'task{i}', 'assignee': 'alice', 'phase': 'impl'}
            task_ids.append(queue.enqueue_idempotent(task_def))

        acquired = []
        lock = threading.Lock()

        def worker():
            for _ in range(5):
                result = queue.dequeue_and_acquire(f'worker_{threading.current_thread().name}')
                if result:
                    with lock:
                        acquired.append(result['id'])

        # 3 workers dequeue
        threads = [threading.Thread(target=worker) for _ in range(3)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        # Each task should be acquired exactly once
        assert len(acquired) == 5
        assert len(set(acquired)) == 5  # all unique

    def test_concurrent_release_handles_conflicts(self, temp_db):
        """Concurrent release attempts handle version conflicts."""
        queue = LockFreeTaskQueue(temp_db)
        task_def = {'title': 'task1', 'assignee': 'alice', 'phase': 'impl'}
        queue.enqueue_idempotent(task_def)

        result = queue.dequeue_and_acquire('worker1')
        task_id = result['id']
        version = result['version']

        results = []
        lock = threading.Lock()

        def try_release(worker_id):
            success = queue.release_with_version(task_id, version, 'completed')
            with lock:
                results.append(success)

        # 2 threads try to release with same version
        threads = [
            threading.Thread(target=try_release, args=(f'worker{i}',))
            for i in range(2)
        ]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        # Only one should succeed
        assert sum(results) == 1


class TestCounters:
    """Test queue status counters."""

    def test_pending_count(self, temp_db):
        """Pending count reflects enqueued tasks."""
        queue = LockFreeTaskQueue(temp_db)
        task_def = {'title': 'task1', 'assignee': 'alice', 'phase': 'impl'}
        queue.enqueue_idempotent(task_def)
        queue.enqueue_idempotent({'title': 'task2', 'assignee': 'alice', 'phase': 'impl'})

        assert queue.get_pending_count() == 2

    def test_in_progress_count(self, temp_db):
        """In-progress count reflects acquired tasks."""
        queue = LockFreeTaskQueue(temp_db)
        task_def = {'title': 'task1', 'assignee': 'alice', 'phase': 'impl'}
        queue.enqueue_idempotent(task_def)

        queue.dequeue_and_acquire('worker1')
        assert queue.get_in_progress_count() == 1
