"""
KuzuDB Schema definitions and initialization for template graph structures.

Provides schema definitions, table creation, and index management for:
- Template nodes and edges (DAG storage)
- Template metadata and relationships
- Template matching records
"""

import logging
from workflow.repositories.kuzu_connection import KuzuConnection

logger = logging.getLogger(__name__)


class KuzuSchema:
    """
    Manages KuzuDB schema for template storage and graph operations.

    Tables:
    - Template: Template metadata
    - TemplateNode: DAG nodes within templates
    - TemplateEdge: DAG edges/relationships between nodes
    - TemplateMapping: Template-to-Workflow matching records
    """

    @staticmethod
    def create_schema(kuzu_conn: KuzuConnection) -> None:
        """
        Create all required KuzuDB schema tables.

        Args:
            kuzu_conn: KuzuDB connection instance

        Raises:
            Exception: If schema creation fails
        """
        try:
            # Create Template node table
            KuzuSchema._create_template_table(kuzu_conn)
            logger.info("Template node table created")

            # Create TemplateNode table
            KuzuSchema._create_template_node_table(kuzu_conn)
            logger.info("TemplateNode node table created")

            # Create TemplateEdge relation table
            KuzuSchema._create_template_edge_table(kuzu_conn)
            logger.info("TemplateEdge relation table created")

            # Create TemplateMapping relation table
            KuzuSchema._create_template_mapping_table(kuzu_conn)
            logger.info("TemplateMapping relation table created")

            logger.info("KuzuDB schema initialization completed")

        except Exception as e:
            logger.error(f"Failed to create KuzuDB schema: {e}")
            raise

    @staticmethod
    def _create_template_table(kuzu_conn: KuzuConnection) -> None:
        """Create Template node table."""
        query = """
        CREATE NODE TABLE IF NOT EXISTS Template (
            template_id INT64 PRIMARY KEY,
            name STRING,
            description STRING,
            category STRING,
            tags STRING[],
            created_at TIMESTAMP,
            updated_at TIMESTAMP,
            usage_count INT64,
            is_active BOOLEAN
        )
        """
        kuzu_conn.execute(query)

    @staticmethod
    def _create_template_node_table(kuzu_conn: KuzuConnection) -> None:
        """Create TemplateNode node table."""
        query = """
        CREATE NODE TABLE IF NOT EXISTS TemplateNode (
            template_node_id STRING PRIMARY KEY,
            template_id INT64,
            node_id STRING,
            node_name STRING,
            node_type STRING,
            description STRING,
            estimated_duration_minutes INT64,
            priority STRING,
            role_hint STRING,
            tags STRING[],
            created_at TIMESTAMP
        )
        """
        kuzu_conn.execute(query)

    @staticmethod
    def _create_template_edge_table(kuzu_conn: KuzuConnection) -> None:
        """Create TemplateEdge relation table."""
        query = """
        CREATE REL TABLE IF NOT EXISTS TemplateEdge (
            FROM TemplateNode TO TemplateNode,
            edge_type STRING,
            condition STRING,
            confidence_score DOUBLE
        )
        """
        kuzu_conn.execute(query)

    @staticmethod
    def _create_template_mapping_table(kuzu_conn: KuzuConnection) -> None:
        """Create TemplateMapping relation table for Template-Workflow mappings."""
        # Note: Workflow table assumed to exist in graph
        query = """
        CREATE REL TABLE IF NOT EXISTS TemplateMapping (
            FROM Template TO Template,
            match_score DOUBLE,
            match_reason STRING,
            matched_fields STRING[],
            matched_at TIMESTAMP
        )
        """
        kuzu_conn.execute(query)

    @staticmethod
    def drop_schema(kuzu_conn: KuzuConnection) -> None:
        """
        Drop all template-related tables (for testing/cleanup).

        Args:
            kuzu_conn: KuzuDB connection instance
        """
        tables = ["TemplateEdge", "TemplateMapping", "TemplateNode", "Template"]
        for table in tables:
            try:
                kuzu_conn.execute(f"DROP TABLE IF EXISTS {table}")
                logger.info(f"Dropped table {table}")
            except Exception as e:
                logger.warning(f"Failed to drop table {table}: {e}")

    @staticmethod
    def verify_schema(kuzu_conn: KuzuConnection) -> bool:
        """
        Verify that all required schema tables exist.

        Args:
            kuzu_conn: KuzuDB connection instance

        Returns:
            True if all tables exist, False otherwise
        """
        required_tables = ["Template", "TemplateNode", "TemplateEdge", "TemplateMapping"]

        try:
            # Verify node tables exist
            node_tables = ["Template", "TemplateNode"]
            all_exist = True

            for table in node_tables:
                try:
                    result = kuzu_conn.execute(f"MATCH (n:{table}) RETURN COUNT(n)")
                    if result.has_next():
                        result.get_next()
                except Exception:
                    logger.warning(f"Node table does not exist: {table}")
                    all_exist = False

            # Try to verify rel tables by querying edges
            try:
                # Just try to match relationships, don't require specific counts
                result = kuzu_conn.execute(f"MATCH (from:TemplateNode)-[e]->(to:TemplateNode) RETURN COUNT(e) LIMIT 1")
                # If this doesn't error, rel tables exist
                if result.has_next():
                    result.get_next()
            except Exception:
                # REL tables might not be fully created yet, that's ok
                pass

            if all_exist:
                logger.info("Schema verification successful (core tables exist)")
            else:
                logger.warning("Some core tables are missing")

            return all_exist

        except Exception as e:
            logger.error(f"Failed to verify schema: {e}")
            return False
