"""
Lock-free task queue using SQLite optimistic locking.

Implements task queue with idempotent enqueuing and CAS-based dequeuing.
Uses version fields for optimistic locking (no database locks).
"""

import sqlite3
import time
import hashlib
from datetime import datetime
from typing import Optional


class LockFreeTaskQueue:
    """
    SQLite-based task queue with optimistic locking.

    Provides idempotent enqueuing and version-aware dequeuing.
    No exclusive locks — uses version fields for conflict detection.
    """

    def __init__(self, db_path: str):
        """Initialize queue with database path."""
        self.db_path = db_path
        self._ensure_queue_table()

    def _get_db(self) -> sqlite3.Connection:
        """Get database connection with row factory."""
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        return conn

    def _ensure_queue_table(self) -> None:
        """Create queue table if not exists."""
        conn = self._get_db()
        try:
            cursor = conn.cursor()
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS task_queue (
                    id                  INTEGER PRIMARY KEY AUTOINCREMENT,
                    task_def_hash       TEXT NOT NULL,
                    task_def            TEXT NOT NULL,
                    status              TEXT DEFAULT 'pending',
                    version             INTEGER DEFAULT 0,
                    worker_id           TEXT,
                    enqueued_at         TEXT NOT NULL DEFAULT (datetime('now','localtime')),
                    dequeued_at         TEXT,
                    completed_at        TEXT,
                    UNIQUE(task_def_hash)
                )
            ''')
            cursor.execute('''
                CREATE INDEX IF NOT EXISTS idx_task_queue_status
                    ON task_queue(status)
            ''')
            cursor.execute('''
                CREATE INDEX IF NOT EXISTS idx_task_queue_enqueued_at
                    ON task_queue(enqueued_at)
            ''')
            conn.commit()
        finally:
            conn.close()

    def _hash_task_def(self, task_def: dict) -> str:
        """Generate hash for task definition (for deduplication)."""
        task_key = (task_def.get('title', ''), task_def.get('assignee', ''), task_def.get('phase', ''))
        return hashlib.md5(str(task_key).encode()).hexdigest()

    def enqueue_idempotent(self, task_def: dict) -> int:
        """
        Enqueue task idempotently.

        Returns task ID (reuses existing if found).
        Uses IF NOT EXISTS to avoid duplicate entries.
        """
        conn = self._get_db()
        try:
            cursor = conn.cursor()
            task_hash = self._hash_task_def(task_def)
            task_def_str = str(task_def)
            now = datetime.now().isoformat()

            cursor.execute('''
                INSERT OR IGNORE INTO task_queue
                (task_def_hash, task_def, status, version, enqueued_at)
                VALUES (?, ?, ?, ?, ?)
            ''', (task_hash, task_def_str, 'pending', 0, now))

            cursor.execute('SELECT id FROM task_queue WHERE task_def_hash = ?', (task_hash,))
            row = cursor.fetchone()
            task_id = row['id']

            conn.commit()
            return task_id
        finally:
            conn.close()

    def dequeue_and_acquire(
        self,
        worker_id: str,
        max_retries: int = 3
    ) -> Optional[dict]:
        """
        Dequeue next pending task and acquire it.

        Returns task with (id, task_def, version) or None if empty.
        Uses version-aware UPDATE (CAS pattern) with automatic retry.
        """
        for attempt in range(max_retries):
            conn = self._get_db()
            try:
                cursor = conn.cursor()

                # Get next pending task
                cursor.execute('''
                    SELECT id, task_def, version FROM task_queue
                    WHERE status = 'pending'
                    ORDER BY enqueued_at ASC
                    LIMIT 1
                ''')
                row = cursor.fetchone()
                if not row:
                    return None

                task_id = row['id']
                current_version = row['version']
                task_def_str = row['task_def']

                # Try to acquire with version check (CAS)
                now = datetime.now().isoformat()
                cursor.execute('''
                    UPDATE task_queue
                    SET status = 'in_progress', version = ?, worker_id = ?, dequeued_at = ?
                    WHERE id = ? AND version = ?
                ''', (current_version + 1, worker_id, now, task_id, current_version))

                if cursor.rowcount > 0:
                    conn.commit()
                    return {
                        'id': task_id,
                        'task_def': task_def_str,
                        'version': current_version + 1
                    }
                else:
                    # Version conflict — another worker acquired it
                    conn.rollback()
                    if attempt < max_retries - 1:
                        time.sleep(0.1 * (2 ** attempt))  # exponential backoff
                        continue
            finally:
                conn.close()

        return None

    def release_with_version(
        self,
        task_id: int,
        current_version: int,
        new_status: str
    ) -> bool:
        """
        Release/complete task using version-aware update (CAS).

        Returns True if successful, False on version conflict.
        """
        conn = self._get_db()
        try:
            cursor = conn.cursor()
            now = datetime.now().isoformat()

            cursor.execute('''
                UPDATE task_queue
                SET status = ?, version = ?, completed_at = ?
                WHERE id = ? AND version = ?
            ''', (new_status, current_version + 1, now, task_id, current_version))

            success = cursor.rowcount > 0
            conn.commit()
            return success
        finally:
            conn.close()

    def get_task(self, task_id: int) -> Optional[dict]:
        """Get task by ID."""
        conn = self._get_db()
        try:
            cursor = conn.cursor()
            cursor.execute('''
                SELECT id, task_def, status, version FROM task_queue
                WHERE id = ?
            ''', (task_id,))
            row = cursor.fetchone()
            if not row:
                return None
            return dict(row)
        finally:
            conn.close()

    def get_pending_count(self) -> int:
        """Get count of pending tasks."""
        conn = self._get_db()
        try:
            cursor = conn.cursor()
            cursor.execute('SELECT COUNT(*) as count FROM task_queue WHERE status = ?', ('pending',))
            row = cursor.fetchone()
            return row['count'] if row else 0
        finally:
            conn.close()

    def get_in_progress_count(self) -> int:
        """Get count of in-progress tasks."""
        conn = self._get_db()
        try:
            cursor = conn.cursor()
            cursor.execute('SELECT COUNT(*) as count FROM task_queue WHERE status = ?', ('in_progress',))
            row = cursor.fetchone()
            return row['count'] if row else 0
        finally:
            conn.close()
