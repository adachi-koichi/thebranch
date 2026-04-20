"""KuzuDB connection manager for graph operations"""
from pathlib import Path
import kuzu


class KuzuConnection:
    """Manages KuzuDB connection and lifecycle"""

    def __init__(self, db_path: str | Path = ':memory:'):
        """Initialize KuzuDB connection"""
        self.db_path = str(db_path)
        self.db = kuzu.Database(self.db_path)
        self.conn = kuzu.Connection(self.db)

    def execute(self, query: str, param_map: dict = None) -> 'kuzu.QueryResult':
        """Execute Cypher query"""
        if param_map is None:
            param_map = {}
        return self.conn.execute(query, param_map)

    def close(self):
        """Close connection"""
        if self.conn:
            self.conn.close()

    def __enter__(self):
        """Context manager entry"""
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        """Context manager exit"""
        self.close()
