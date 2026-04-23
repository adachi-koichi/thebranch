"""
Template synchronization manager between SQLite and KuzuDB.

Synchronizes template data from SQLite (primary storage) to KuzuDB (graph storage)
for advanced querying and relationship analysis.
"""

import logging
import sqlite3
from typing import Optional, Dict, Tuple

from workflow.repositories.kuzu_connection import KuzuConnection
from workflow.repositories.kuzu_template_repository import KuzuTemplateRepository

logger = logging.getLogger(__name__)


class TemplateSyncManager:
    """
    Manages synchronization between SQLite and KuzuDB template storage.

    Ensures templates, nodes, and edges are consistently maintained in both
    databases for operational (SQLite) and analytical (KuzuDB) use cases.
    """

    def __init__(self, sqlite_conn: sqlite3.Connection, kuzu_conn: KuzuConnection):
        """
        Initialize sync manager.

        Args:
            sqlite_conn: SQLite database connection
            kuzu_conn: KuzuDB connection instance
        """
        self.sqlite_conn = sqlite_conn
        self.kuzu_conn = kuzu_conn
        self.kuzu_repo = KuzuTemplateRepository(kuzu_conn)

    def sync_template_to_kuzu(self, template_id: int) -> bool:
        """
        Synchronize a single template from SQLite to KuzuDB.

        Args:
            template_id: Template ID to sync

        Returns:
            True if sync successful, False otherwise
        """
        try:
            # Read from SQLite
            sqlite_cursor = self.sqlite_conn.cursor()
            sqlite_cursor.row_factory = sqlite3.Row

            # Get template
            sqlite_cursor.execute("SELECT * FROM templates WHERE id = ?", (template_id,))
            template_row = sqlite_cursor.fetchone()

            if not template_row:
                logger.warning(f"Template not found in SQLite: {template_id}")
                return False

            # Get nodes
            sqlite_cursor.execute(
                "SELECT * FROM template_nodes WHERE template_id = ? ORDER BY id",
                (template_id,)
            )
            node_rows = sqlite_cursor.fetchall()

            # Get edges
            sqlite_cursor.execute(
                "SELECT * FROM template_edges WHERE template_id = ? ORDER BY id",
                (template_id,)
            )
            edge_rows = sqlite_cursor.fetchall()

            # Transform to KuzuDB format
            template_data = {
                "template_id": template_row["id"],
                "name": template_row["name"],
                "description": template_row["description"],
                "category": template_row["category"],
                "tags": [],  # SQLite template doesn't have tags column yet
                "nodes": [
                    {
                        "node_id": node_row["task_id"],
                        "name": node_row["name"],
                        "description": node_row["description"],
                        "type": node_row["type"],
                        "estimated_duration_minutes": node_row["estimated_duration_minutes"],
                        "priority": node_row["priority"],
                        "role_hint": node_row["role_hint"],
                        "tags": []
                    }
                    for node_row in node_rows
                ],
                "edges": [
                    {
                        "from": edge_row["from_task_id"],
                        "to": edge_row["to_task_id"],
                        "type": edge_row["edge_type"],
                        "condition": edge_row["condition"],
                        "confidence_score": 1.0
                    }
                    for edge_row in edge_rows
                ]
            }

            # Check if template already exists in KuzuDB
            existing = self.kuzu_repo.get_template(template_id)
            if existing:
                logger.info(f"Template already in KuzuDB: {template_id}")
                # Delete and recreate to ensure consistency
                self.kuzu_repo.delete_template(template_id)

            # Save to KuzuDB
            self.kuzu_repo.save_template(template_data)

            logger.info(f"Synced template {template_id} to KuzuDB: "
                       f"{len(template_data['nodes'])} nodes, {len(template_data['edges'])} edges")
            return True

        except Exception as e:
            logger.error(f"Failed to sync template {template_id} to KuzuDB: {e}")
            return False

    def sync_all_templates(self) -> Dict[str, int]:
        """
        Synchronize all templates from SQLite to KuzuDB.

        Returns:
            Dict with sync statistics:
            {
                "total": int,
                "successful": int,
                "failed": int,
                "skipped": int
            }
        """
        try:
            sqlite_cursor = self.sqlite_conn.cursor()
            sqlite_cursor.execute("SELECT id FROM templates ORDER BY id")
            template_ids = [row[0] for row in sqlite_cursor.fetchall()]

            stats = {
                "total": len(template_ids),
                "successful": 0,
                "failed": 0,
                "skipped": 0
            }

            for template_id in template_ids:
                try:
                    if self.sync_template_to_kuzu(template_id):
                        stats["successful"] += 1
                    else:
                        stats["failed"] += 1
                except Exception as e:
                    logger.warning(f"Error syncing template {template_id}: {e}")
                    stats["failed"] += 1

            logger.info(f"Sync complete: {stats}")
            return stats

        except Exception as e:
            logger.error(f"Failed to sync all templates: {e}")
            return {
                "total": 0,
                "successful": 0,
                "failed": 0,
                "skipped": 0
            }

    def verify_sync_integrity(self, template_id: int) -> bool:
        """
        Verify that template data is consistent between SQLite and KuzuDB.

        Args:
            template_id: Template ID to verify

        Returns:
            True if sync integrity verified, False otherwise
        """
        try:
            # Get counts from SQLite
            sqlite_cursor = self.sqlite_conn.cursor()

            sqlite_cursor.execute("SELECT COUNT(*) FROM template_nodes WHERE template_id = ?", (template_id,))
            sqlite_node_count = sqlite_cursor.fetchone()[0]

            sqlite_cursor.execute("SELECT COUNT(*) FROM template_edges WHERE template_id = ?", (template_id,))
            sqlite_edge_count = sqlite_cursor.fetchone()[0]

            # Get counts from KuzuDB
            kuzu_template = self.kuzu_repo.get_template(template_id)
            if not kuzu_template:
                logger.warning(f"Template not found in KuzuDB: {template_id}")
                return False

            kuzu_node_count = len(kuzu_template.get("nodes", []))
            kuzu_edge_count = len(kuzu_template.get("edges", []))

            # Compare
            if sqlite_node_count != kuzu_node_count:
                logger.error(f"Node count mismatch for template {template_id}: "
                           f"SQLite={sqlite_node_count}, KuzuDB={kuzu_node_count}")
                return False

            if sqlite_edge_count != kuzu_edge_count:
                logger.error(f"Edge count mismatch for template {template_id}: "
                           f"SQLite={sqlite_edge_count}, KuzuDB={kuzu_edge_count}")
                return False

            logger.info(f"Sync integrity verified for template {template_id}: "
                       f"{sqlite_node_count} nodes, {sqlite_edge_count} edges")
            return True

        except Exception as e:
            logger.error(f"Failed to verify sync integrity for template {template_id}: {e}")
            return False

    def verify_all_sync_integrity(self) -> Dict[str, int]:
        """
        Verify sync integrity for all templates.

        Returns:
            Dict with verification statistics:
            {
                "total": int,
                "verified": int,
                "failed": int
            }
        """
        try:
            sqlite_cursor = self.sqlite_conn.cursor()
            sqlite_cursor.execute("SELECT id FROM templates ORDER BY id")
            template_ids = [row[0] for row in sqlite_cursor.fetchall()]

            stats = {
                "total": len(template_ids),
                "verified": 0,
                "failed": 0
            }

            for template_id in template_ids:
                if self.verify_sync_integrity(template_id):
                    stats["verified"] += 1
                else:
                    stats["failed"] += 1

            logger.info(f"Integrity verification complete: {stats}")
            return stats

        except Exception as e:
            logger.error(f"Failed to verify all sync integrity: {e}")
            return {
                "total": 0,
                "verified": 0,
                "failed": 0
            }

    def sync_incremental(self, since_timestamp: str) -> Dict[str, int]:
        """
        Synchronize templates modified since a given timestamp (incremental sync).

        Args:
            since_timestamp: ISO format timestamp (e.g., "2024-04-24T12:00:00")

        Returns:
            Dict with sync statistics
        """
        try:
            sqlite_cursor = self.sqlite_conn.cursor()
            sqlite_cursor.execute(
                "SELECT id FROM templates WHERE updated_at > ? ORDER BY id",
                (since_timestamp,)
            )
            template_ids = [row[0] for row in sqlite_cursor.fetchall()]

            stats = {
                "total": len(template_ids),
                "successful": 0,
                "failed": 0
            }

            for template_id in template_ids:
                try:
                    if self.sync_template_to_kuzu(template_id):
                        stats["successful"] += 1
                    else:
                        stats["failed"] += 1
                except Exception as e:
                    logger.warning(f"Error syncing template {template_id}: {e}")
                    stats["failed"] += 1

            logger.info(f"Incremental sync complete (since {since_timestamp}): {stats}")
            return stats

        except Exception as e:
            logger.error(f"Failed to perform incremental sync: {e}")
            return {
                "total": 0,
                "successful": 0,
                "failed": 0
            }

    def get_sync_status(self) -> Dict[str, any]:
        """
        Get current sync status between SQLite and KuzuDB.

        Returns:
            Dict with sync statistics:
            {
                "sqlite_template_count": int,
                "kuzu_template_count": int,
                "sync_complete": bool,
                "last_verified": str (timestamp)
            }
        """
        try:
            # Count in SQLite
            sqlite_cursor = self.sqlite_conn.cursor()
            sqlite_cursor.execute("SELECT COUNT(*) FROM templates")
            sqlite_count = sqlite_cursor.fetchone()[0]

            # Count in KuzuDB
            stats = self.kuzu_repo.get_template_statistics()
            kuzu_count = stats.get("total_templates", 0)

            return {
                "sqlite_template_count": sqlite_count,
                "kuzu_template_count": kuzu_count,
                "sync_complete": sqlite_count == kuzu_count,
                "last_verified": str(datetime.now().isoformat())
            }

        except Exception as e:
            logger.error(f"Failed to get sync status: {e}")
            return {
                "sqlite_template_count": 0,
                "kuzu_template_count": 0,
                "sync_complete": False,
                "last_verified": None
            }


from datetime import datetime
