from abc import ABC, abstractmethod
from contextlib import contextmanager
import sqlite3
from pathlib import Path


class BaseRepository(ABC):
    """Abstract base repository for SQLite access"""

    def __init__(self, db_path: str | Path | sqlite3.Connection = ':memory:'):
        """Initialize repository with database path or connection"""
        if isinstance(db_path, sqlite3.Connection):
            self.db_path = None
            self._connection = db_path
            self._connection.row_factory = sqlite3.Row
            self._connection.execute('PRAGMA foreign_keys = ON')
        else:
            self.db_path = str(db_path)
            self._connection = None

    def _get_connection(self) -> sqlite3.Connection:
        """Get database connection with row factory"""
        if self._connection:
            return self._connection
        is_uri = self.db_path.startswith('file:')
        conn = sqlite3.connect(self.db_path, uri=is_uri)
        conn.row_factory = sqlite3.Row
        conn.execute('PRAGMA foreign_keys = ON')
        return conn

    @contextmanager
    def transaction(self):
        """Context manager for database transactions"""
        conn = self._get_connection()
        should_close = self._connection is None
        try:
            yield conn
            conn.commit()
        except Exception as e:
            conn.rollback()
            raise
        finally:
            if should_close:
                conn.close()

    def execute_one(self, query: str, params: tuple = ()) -> sqlite3.Row | None:
        """Execute query and return single row"""
        conn = self._get_connection()
        should_close = self._connection is None
        try:
            cursor = conn.cursor()
            cursor.execute(query, params)
            return cursor.fetchone()
        finally:
            if should_close:
                conn.close()

    def execute_all(self, query: str, params: tuple = ()) -> list[sqlite3.Row]:
        """Execute query and return all rows"""
        conn = self._get_connection()
        should_close = self._connection is None
        try:
            cursor = conn.cursor()
            cursor.execute(query, params)
            return cursor.fetchall()
        finally:
            if should_close:
                conn.close()

    def execute_insert(self, query: str, params: tuple = ()) -> int:
        """Execute insert query and return last insert row id"""
        conn = self._get_connection()
        should_close = self._connection is None
        try:
            cursor = conn.cursor()
            cursor.execute(query, params)
            conn.commit()
            return cursor.lastrowid
        finally:
            if should_close:
                conn.close()

    def execute_update(self, query: str, params: tuple = ()) -> int:
        """Execute update query and return affected rows"""
        conn = self._get_connection()
        should_close = self._connection is None
        try:
            cursor = conn.cursor()
            cursor.execute(query, params)
            conn.commit()
            return cursor.rowcount
        finally:
            if should_close:
                conn.close()

    def init_db(self, schema: str) -> None:
        """Initialize database with schema"""
        conn = self._get_connection()
        should_close = self._connection is None
        try:
            cursor = conn.cursor()
            cursor.executescript(schema)
            conn.commit()
        finally:
            if should_close:
                conn.close()
