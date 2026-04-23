"""
Template management and catalog service.

Provides template CRUD operations, matching, searching, and catalog management.
Supports keyword matching, semantic similarity, and structural pattern matching.
"""

import logging
import sqlite3
import json
import uuid
from datetime import datetime
from typing import Optional
from difflib import SequenceMatcher

from workflow.models.template import (
    TemplateMetadata,
    TemplateMatch,
    TemplateNotFoundError,
    TemplateValidationError,
)

logger = logging.getLogger(__name__)


class TemplateService:
    """
    Template CRUD and catalog management service.

    Responsibilities:
    - Create/update/delete templates
    - Manage template metadata
    - Query and list templates
    - Validate template schema
    - Support template discovery and matching
    """

    def __init__(self, db_path: str, kuzu_db_connection=None) -> None:
        """
        Initialize template service.

        Args:
            db_path: Path to SQLite database
            kuzu_db_connection: Optional KuzuDB connection for graph operations
        """
        self.db_path = db_path
        self.kuzu_db = kuzu_db_connection
        self._ensure_tables()
        logger.info(f"TemplateService initialized with db_path={db_path}")

    def _ensure_tables(self) -> None:
        """Create template-related tables if they don't exist."""
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()

                # Templates table
                cursor.execute("""
                    CREATE TABLE IF NOT EXISTS templates (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        name TEXT NOT NULL UNIQUE,
                        description TEXT,
                        category TEXT,
                        usage_count INTEGER DEFAULT 0,
                        created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                        updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
                    )
                """)

                # Template nodes table (DAG nodes)
                cursor.execute("""
                    CREATE TABLE IF NOT EXISTS template_nodes (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        template_id INTEGER NOT NULL REFERENCES templates(id) ON DELETE CASCADE,
                        task_id TEXT NOT NULL,
                        name TEXT NOT NULL,
                        description TEXT,
                        type TEXT CHECK(type IN ('task', 'step', 'milestone')) DEFAULT 'task',
                        estimated_duration_minutes INTEGER DEFAULT 0,
                        priority TEXT CHECK(priority IN ('high', 'medium', 'low')) DEFAULT 'medium',
                        role_hint TEXT,
                        created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                        UNIQUE(template_id, task_id)
                    )
                """)

                # Template edges table (DAG edges)
                cursor.execute("""
                    CREATE TABLE IF NOT EXISTS template_edges (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        template_id INTEGER NOT NULL REFERENCES templates(id) ON DELETE CASCADE,
                        from_task_id TEXT NOT NULL,
                        to_task_id TEXT NOT NULL,
                        edge_type TEXT CHECK(edge_type IN ('depends_on', 'blocks', 'triggers')) DEFAULT 'depends_on',
                        condition TEXT,
                        created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                        FOREIGN KEY (template_id) REFERENCES templates(id)
                    )
                """)

                # Create indices
                cursor.execute("""CREATE INDEX IF NOT EXISTS idx_templates_category ON templates(category)""")
                cursor.execute("""CREATE INDEX IF NOT EXISTS idx_template_nodes_template_id ON template_nodes(template_id)""")
                cursor.execute("""CREATE INDEX IF NOT EXISTS idx_template_edges_template_id ON template_edges(template_id)""")

                conn.commit()
                logger.info("Template tables ensured")
        except sqlite3.Error as e:
            logger.error(f"Failed to create template tables: {e}")
            raise TemplateValidationError(f"Database initialization failed: {e}")

    # ===== CREATE =====

    def create_template(
        self,
        name: str,
        description: str = "",
        nodes: list[dict] = None,
        edges: list[dict] = None,
        category: str = None,
    ) -> TemplateMetadata:
        """
        Create a new template with nodes and edges.

        Args:
            name: Template name (unique)
            description: Template description
            nodes: List of node definitions (task_id, name, description, etc.)
            edges: List of edge definitions (from, to, type, condition)
            category: Template category for filtering

        Returns:
            TemplateMetadata object

        Raises:
            TemplateValidationError: If validation fails
        """
        nodes = nodes or []
        edges = edges or []

        # Validate inputs
        if not name or len(name.strip()) == 0:
            raise TemplateValidationError("Template name is required")

        validation_errors = self._validate_template_schema(
            nodes=nodes,
            edges=edges,
        )
        if validation_errors:
            raise TemplateValidationError(
                f"Template validation failed: {', '.join(validation_errors)}"
            )

        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()

                # Insert template
                cursor.execute(
                    """
                    INSERT INTO templates (name, description, category, created_at, updated_at)
                    VALUES (?, ?, ?, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)
                    """,
                    (name, description, category),
                )
                template_id = cursor.lastrowid

                # Insert nodes
                for node in nodes:
                    cursor.execute(
                        """
                        INSERT INTO template_nodes
                        (template_id, task_id, name, description, type, estimated_duration_minutes, priority, role_hint, created_at)
                        VALUES (?, ?, ?, ?, ?, ?, ?, ?, CURRENT_TIMESTAMP)
                        """,
                        (
                            template_id,
                            node.get("task_id"),
                            node.get("name"),
                            node.get("description", ""),
                            node.get("type", "task"),
                            node.get("estimated_duration_minutes", 0),
                            node.get("priority", "medium"),
                            node.get("role_hint"),
                        ),
                    )

                # Insert edges
                for edge in edges:
                    cursor.execute(
                        """
                        INSERT INTO template_edges
                        (template_id, from_task_id, to_task_id, edge_type, condition, created_at)
                        VALUES (?, ?, ?, ?, ?, CURRENT_TIMESTAMP)
                        """,
                        (
                            template_id,
                            edge.get("from"),
                            edge.get("to"),
                            edge.get("type", "depends_on"),
                            edge.get("condition"),
                        ),
                    )

                conn.commit()
                logger.info(f"Created template: id={template_id}, name={name}")

                return TemplateMetadata(
                    template_id=template_id,
                    name=name,
                    description=description,
                    category=category,
                    usage_count=0,
                    created_at=datetime.now(),
                    updated_at=datetime.now(),
                )

        except sqlite3.IntegrityError as e:
            logger.error(f"Failed to create template: {e}")
            raise TemplateValidationError(f"Template creation failed: {e}")
        except Exception as e:
            logger.error(f"Unexpected error creating template: {e}")
            raise

    # ===== READ =====

    def get_template(self, template_id: int) -> dict:
        """
        Get a template with all nodes and edges.

        Args:
            template_id: Template ID

        Returns:
            Dictionary with template metadata and DAG structure

        Raises:
            TemplateNotFoundError: If template not found
        """
        try:
            with sqlite3.connect(self.db_path) as conn:
                conn.row_factory = sqlite3.Row
                cursor = conn.cursor()

                # Get template
                cursor.execute("SELECT * FROM templates WHERE id = ?", (template_id,))
                template_row = cursor.fetchone()

                if not template_row:
                    raise TemplateNotFoundError(f"Template {template_id} not found")

                # Get nodes
                cursor.execute(
                    "SELECT * FROM template_nodes WHERE template_id = ? ORDER BY created_at",
                    (template_id,),
                )
                nodes = [dict(row) for row in cursor.fetchall()]

                # Get edges
                cursor.execute(
                    "SELECT * FROM template_edges WHERE template_id = ? ORDER BY created_at",
                    (template_id,),
                )
                edges = [dict(row) for row in cursor.fetchall()]

                return {
                    "id": template_row["id"],
                    "name": template_row["name"],
                    "description": template_row["description"],
                    "category": template_row["category"],
                    "usage_count": template_row["usage_count"],
                    "created_at": template_row["created_at"],
                    "updated_at": template_row["updated_at"],
                    "nodes": nodes,
                    "edges": edges,
                }

        except TemplateNotFoundError:
            raise
        except Exception as e:
            logger.error(f"Failed to get template {template_id}: {e}")
            raise

    def list_templates(
        self,
        category: str = None,
        page: int = 1,
        limit: int = 20,
    ) -> list[TemplateMetadata]:
        """
        List templates with optional filtering.

        Args:
            category: Filter by category (optional)
            page: Page number (1-indexed)
            limit: Results per page

        Returns:
            List of TemplateMetadata objects
        """
        try:
            with sqlite3.connect(self.db_path) as conn:
                conn.row_factory = sqlite3.Row
                cursor = conn.cursor()

                if category:
                    cursor.execute(
                        """
                        SELECT id, name, description, category, usage_count, created_at, updated_at
                        FROM templates
                        WHERE category = ?
                        ORDER BY updated_at DESC
                        LIMIT ? OFFSET ?
                        """,
                        (category, limit, (page - 1) * limit),
                    )
                else:
                    cursor.execute(
                        """
                        SELECT id, name, description, category, usage_count, created_at, updated_at
                        FROM templates
                        ORDER BY updated_at DESC
                        LIMIT ? OFFSET ?
                        """,
                        (limit, (page - 1) * limit),
                    )

                rows = cursor.fetchall()
                return [
                    TemplateMetadata(
                        template_id=row["id"],
                        name=row["name"],
                        description=row["description"],
                        category=row["category"],
                        usage_count=row["usage_count"],
                        created_at=row["created_at"],
                        updated_at=row["updated_at"],
                    )
                    for row in rows
                ]

        except Exception as e:
            logger.error(f"Failed to list templates: {e}")
            raise

    # ===== UPDATE =====

    def update_template(
        self, template_id: int, **updates
    ) -> TemplateMetadata:
        """
        Update template metadata, nodes, and edges.

        Args:
            template_id: Template ID
            **updates: Fields to update (name, description, category, nodes, edges)

        Returns:
            Updated TemplateMetadata

        Raises:
            TemplateNotFoundError: If template not found
            TemplateValidationError: If validation fails
        """
        try:
            with sqlite3.connect(self.db_path) as conn:
                conn.row_factory = sqlite3.Row
                cursor = conn.cursor()

                # Verify template exists
                cursor.execute("SELECT * FROM templates WHERE id = ?", (template_id,))
                template_row = cursor.fetchone()

                if not template_row:
                    raise TemplateNotFoundError(f"Template {template_id} not found")

                # Extract special fields (nodes, edges)
                nodes = updates.pop("nodes", None)
                edges = updates.pop("edges", None)

                # Validate if nodes/edges are provided
                if nodes is not None or edges is not None:
                    validation_errors = self._validate_template_schema(
                        nodes=nodes or [],
                        edges=edges or [],
                    )
                    if validation_errors:
                        raise TemplateValidationError(
                            f"Template validation failed: {', '.join(validation_errors)}"
                        )

                # Build update query for metadata
                allowed_fields = {"name", "description", "category"}
                update_fields = {k: v for k, v in updates.items() if k in allowed_fields}

                if update_fields:
                    set_clause = ", ".join([f"{k} = ?" for k in update_fields.keys()])
                    values = list(update_fields.values()) + [template_id]

                    cursor.execute(
                        f"""
                        UPDATE templates
                        SET {set_clause}, updated_at = CURRENT_TIMESTAMP
                        WHERE id = ?
                        """,
                        values,
                    )

                # Update nodes if provided
                if nodes is not None:
                    # Delete existing nodes
                    cursor.execute(
                        "DELETE FROM template_nodes WHERE template_id = ?",
                        (template_id,)
                    )

                    # Insert new nodes
                    for node in nodes:
                        cursor.execute(
                            """
                            INSERT INTO template_nodes
                            (template_id, task_id, name, description, type, estimated_duration_minutes, priority, role_hint, created_at)
                            VALUES (?, ?, ?, ?, ?, ?, ?, ?, CURRENT_TIMESTAMP)
                            """,
                            (
                                template_id,
                                node.get("task_id"),
                                node.get("name"),
                                node.get("description", ""),
                                node.get("type", "task"),
                                node.get("estimated_duration_minutes", 0),
                                node.get("priority", "medium"),
                                node.get("role_hint"),
                            ),
                        )

                # Update edges if provided
                if edges is not None:
                    # Delete existing edges
                    cursor.execute(
                        "DELETE FROM template_edges WHERE template_id = ?",
                        (template_id,)
                    )

                    # Insert new edges
                    for edge in edges:
                        cursor.execute(
                            """
                            INSERT INTO template_edges
                            (template_id, from_task_id, to_task_id, edge_type, condition, created_at)
                            VALUES (?, ?, ?, ?, ?, CURRENT_TIMESTAMP)
                            """,
                            (
                                template_id,
                                edge.get("from"),
                                edge.get("to"),
                                edge.get("type", "depends_on"),
                                edge.get("condition"),
                            ),
                        )

                conn.commit()

                # Fetch updated template
                cursor.execute("SELECT * FROM templates WHERE id = ?", (template_id,))
                updated_row = cursor.fetchone()

                logger.info(f"Updated template {template_id}")

                return TemplateMetadata(
                    template_id=updated_row["id"],
                    name=updated_row["name"],
                    description=updated_row["description"],
                    category=updated_row["category"],
                    usage_count=updated_row["usage_count"],
                    created_at=updated_row["created_at"],
                    updated_at=updated_row["updated_at"],
                )

        except TemplateNotFoundError:
            raise
        except TemplateValidationError:
            raise
        except Exception as e:
            logger.error(f"Failed to update template {template_id}: {e}")
            raise

    # ===== DELETE =====

    def delete_template(self, template_id: int) -> bool:
        """
        Delete a template and all its nodes and edges.

        Args:
            template_id: Template ID

        Returns:
            True if deleted, False if not found
        """
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()

                # Verify exists
                cursor.execute("SELECT id FROM templates WHERE id = ?", (template_id,))
                if not cursor.fetchone():
                    logger.warning(f"Template {template_id} not found for deletion")
                    return False

                # Delete (cascade will handle nodes and edges)
                cursor.execute("DELETE FROM templates WHERE id = ?", (template_id,))
                conn.commit()

                logger.info(f"Deleted template {template_id}")
                return True

        except Exception as e:
            logger.error(f"Failed to delete template {template_id}: {e}")
            raise

    # ===== MATCHING & SEARCH =====

    def match_by_keywords(self, input_text: str) -> list[TemplateMatch]:
        """
        Match templates by keyword overlap.

        Calculates overlap score based on keyword matching in template name and description.

        Args:
            input_text: User input text or query

        Returns:
            List of TemplateMatch objects sorted by score (descending)
        """
        try:
            with sqlite3.connect(self.db_path) as conn:
                conn.row_factory = sqlite3.Row
                cursor = conn.cursor()

                cursor.execute(
                    "SELECT id, name, description FROM templates ORDER BY name"
                )
                templates = cursor.fetchall()

                matches = []
                input_lower = input_text.lower()

                for template in templates:
                    name = (template["name"] or "").lower()
                    description = (template["description"] or "").lower()
                    template_text = f"{name} {description}"

                    # Check if input text appears in template
                    name_match = input_lower in name
                    desc_match = input_lower in description

                    matched_fields = []
                    if name_match:
                        matched_fields.append("name")
                    if desc_match:
                        matched_fields.append("description")

                    # Calculate similarity score
                    if matched_fields:
                        similarity = SequenceMatcher(None, input_lower, template_text).ratio()
                        matches.append(
                            TemplateMatch(
                                template_id=template["id"],
                                name=template["name"],
                                match_score=similarity,
                                match_reason=f"キーワード照合: {', '.join(matched_fields)}",
                                matched_fields=matched_fields,
                            )
                        )

                # Sort by score descending
                matches.sort(key=lambda m: m.match_score, reverse=True)
                return matches

        except Exception as e:
            logger.error(f"Failed to match by keywords: {e}")
            raise

    def match_by_semantic_similarity(self, input_text: str) -> list[TemplateMatch]:
        """
        Match templates by semantic similarity.

        Uses simple string similarity metric (SequenceMatcher).
        In production, consider using vector embeddings (e.g., Anthropic's embeddings API).

        Args:
            input_text: User input text or query

        Returns:
            List of TemplateMatch objects sorted by score (descending)
        """
        try:
            with sqlite3.connect(self.db_path) as conn:
                conn.row_factory = sqlite3.Row
                cursor = conn.cursor()

                cursor.execute(
                    "SELECT id, name, description FROM templates ORDER BY name"
                )
                templates = cursor.fetchall()

                matches = []

                for template in templates:
                    name = template["name"]
                    description = template["description"] or ""
                    template_text = f"{name} {description}"

                    # Calculate similarity ratio (0.0 ~ 1.0)
                    similarity = SequenceMatcher(
                        None, input_text.lower(), template_text.lower()
                    ).ratio()

                    if similarity > 0.2:  # Threshold
                        matches.append(
                            TemplateMatch(
                                template_id=template["id"],
                                name=template["name"],
                                match_score=similarity,
                                match_reason=f"意味的相似度: {similarity:.2%}",
                                matched_fields=["content"],
                            )
                        )

                # Sort by score descending
                matches.sort(key=lambda m: m.match_score, reverse=True)
                return matches

        except Exception as e:
            logger.error(f"Failed to match by semantic similarity: {e}")
            raise

    def match_by_structure(
        self, nodes: list[dict], edges: list[dict]
    ) -> list[TemplateMatch]:
        """
        Match templates by structural similarity.

        Compares number of nodes, edges, and dependency patterns.

        Args:
            nodes: List of node definitions
            edges: List of edge definitions

        Returns:
            List of TemplateMatch objects sorted by score (descending)
        """
        try:
            input_node_count = len(nodes)
            input_edge_count = len(edges)

            with sqlite3.connect(self.db_path) as conn:
                conn.row_factory = sqlite3.Row
                cursor = conn.cursor()

                cursor.execute("SELECT id, name FROM templates")
                templates = cursor.fetchall()

                matches = []

                for template in templates:
                    template_id = template["id"]

                    # Count nodes and edges
                    cursor.execute(
                        "SELECT COUNT(*) as count FROM template_nodes WHERE template_id = ?",
                        (template_id,),
                    )
                    template_node_count = cursor.fetchone()["count"]

                    cursor.execute(
                        "SELECT COUNT(*) as count FROM template_edges WHERE template_id = ?",
                        (template_id,),
                    )
                    template_edge_count = cursor.fetchone()["count"]

                    # Calculate structural similarity
                    # Based on node/edge count difference
                    node_diff = abs(input_node_count - template_node_count)
                    edge_diff = abs(input_edge_count - template_edge_count)

                    # Normalize to 0-1 range
                    max_node_diff = max(input_node_count, template_node_count)
                    max_edge_diff = max(input_edge_count, template_edge_count)

                    node_similarity = (
                        1.0 - (node_diff / max_node_diff) if max_node_diff > 0 else 0.0
                    )
                    edge_similarity = (
                        1.0 - (edge_diff / max_edge_diff) if max_edge_diff > 0 else 0.0
                    )

                    # Average similarity
                    score = (node_similarity + edge_similarity) / 2.0

                    if score > 0.4:  # Threshold
                        matches.append(
                            TemplateMatch(
                                template_id=template_id,
                                name=template["name"],
                                match_score=score,
                                match_reason=f"構造的相似度: ノード {template_node_count}, エッジ {template_edge_count}",
                                matched_fields=["structure"],
                            )
                        )

                # Sort by score descending
                matches.sort(key=lambda m: m.match_score, reverse=True)
                return matches

        except Exception as e:
            logger.error(f"Failed to match by structure: {e}")
            raise

    def rank_templates(self, matches: list[TemplateMatch]) -> list[TemplateMatch]:
        """
        Rank and sort templates by match score.

        Args:
            matches: List of TemplateMatch objects

        Returns:
            Sorted list (highest score first)
        """
        return sorted(matches, key=lambda m: m.match_score, reverse=True)

    # ===== VALIDATION =====

    def _validate_template_schema(
        self, nodes: list[dict], edges: list[dict]
    ) -> list[str]:
        """
        Validate template DAG schema.

        Returns:
            List of validation error messages (empty if valid)
        """
        errors = []

        # Check nodes
        if not nodes:
            errors.append("At least one node is required")
            return errors

        # Validate node structure
        node_ids = set()
        for i, node in enumerate(nodes):
            if "task_id" not in node or not node["task_id"]:
                errors.append(f"Node {i}: task_id is required")
            else:
                node_ids.add(node["task_id"])

            if "name" not in node or not node["name"]:
                errors.append(f"Node {i}: name is required")

        # Validate edges
        for i, edge in enumerate(edges):
            if "from" not in edge or not edge["from"]:
                errors.append(f"Edge {i}: from is required")
            elif edge["from"] not in node_ids:
                errors.append(f"Edge {i}: from '{edge['from']}' not found in nodes")

            if "to" not in edge or not edge["to"]:
                errors.append(f"Edge {i}: to is required")
            elif edge["to"] not in node_ids:
                errors.append(f"Edge {i}: to '{edge['to']}' not found in nodes")

        # Check for cycles using DFS
        if not errors and edges:
            if self._has_cycle(nodes, edges):
                errors.append("Circular dependency detected in edges")

        return errors

    def _has_cycle(self, nodes: list[dict], edges: list[dict]) -> bool:
        """
        Detect cycle in DAG using DFS.

        Args:
            nodes: List of nodes
            edges: List of edges

        Returns:
            True if cycle found, False otherwise
        """
        # Build adjacency list
        graph = {node["task_id"]: [] for node in nodes}
        for edge in edges:
            graph[edge["from"]].append(edge["to"])

        # DFS for cycle detection
        visited = set()
        rec_stack = set()

        def has_cycle_dfs(node):
            visited.add(node)
            rec_stack.add(node)

            for neighbor in graph.get(node, []):
                if neighbor not in visited:
                    if has_cycle_dfs(neighbor):
                        return True
                elif neighbor in rec_stack:
                    return True

            rec_stack.remove(node)
            return False

        for node_id in graph:
            if node_id not in visited:
                if has_cycle_dfs(node_id):
                    return True

        return False

    def instantiate_template(self, template_id: int) -> dict:
        """
        Generate a new workflow instance from a template.

        Creates a fresh copy of the template with a new generation_id.
        Useful for creating new workflow instances based on established patterns.

        Args:
            template_id: Template ID

        Returns:
            Dictionary with:
            - generation_id: Unique instance identifier
            - workflow: Full workflow DAG with nodes and edges
            - template_id: Original template ID (for reference)
            - created_at: Instantiation timestamp

        Raises:
            TemplateNotFoundError: If template not found
        """
        try:
            # Get the template
            template_data = self.get_template(template_id)

            # Generate unique instance ID
            generation_id = str(uuid.uuid4())

            # Create workflow instance
            workflow_instance = {
                "name": template_data["name"],
                "description": template_data["description"],
                "category": template_data["category"],
                "nodes": [
                    {
                        "task_id": node["task_id"],
                        "name": node["name"],
                        "type": node["type"],
                        "description": node["description"],
                        "estimated_duration_minutes": node["estimated_duration_minutes"],
                        "priority": node["priority"],
                        "role_hint": node["role_hint"],
                    }
                    for node in template_data.get("nodes", [])
                ],
                "edges": [
                    {
                        "from": edge["from_task_id"],
                        "to": edge["to_task_id"],
                        "type": edge["edge_type"],
                        "condition": edge["condition"],
                    }
                    for edge in template_data.get("edges", [])
                ],
            }

            logger.info(f"Instantiated template {template_id} with generation_id {generation_id}")

            return {
                "generation_id": generation_id,
                "workflow": workflow_instance,
                "template_id": template_id,
                "created_at": datetime.now().isoformat(),
            }

        except TemplateNotFoundError:
            raise
        except Exception as e:
            logger.error(f"Failed to instantiate template {template_id}: {e}")
            raise

    def normalize_template_structure(self, template_data: dict) -> dict:
        """
        Normalize template DAG structure.

        Performs:
        - Node deduplication
        - Transitive closure detection
        - Topological level assignment

        Args:
            template_data: Dictionary with 'nodes' and 'edges'

        Returns:
            Normalized template structure
        """
        nodes = template_data.get("nodes", [])
        edges = template_data.get("edges", [])

        # Deduplicate nodes by task_id
        node_dict = {node["task_id"]: node for node in nodes}
        unique_nodes = list(node_dict.values())

        # Remove self-loops
        unique_edges = [
            e for e in edges if e["from"] != e["to"]
        ]

        # Assign topological levels using Kahn's algorithm
        node_ids = {n["task_id"] for n in unique_nodes}
        in_degree = {nid: 0 for nid in node_ids}
        graph = {nid: [] for nid in node_ids}

        for edge in unique_edges:
            if edge["to"] in in_degree:
                in_degree[edge["to"]] += 1
            if edge["from"] in graph:
                graph[edge["from"]].append(edge["to"])

        # Topological sort with level assignment
        levels = {nid: 0 for nid in node_ids}
        queue = [nid for nid in node_ids if in_degree[nid] == 0]

        while queue:
            node_id = queue.pop(0)

            for neighbor in graph.get(node_id, []):
                # Update level: neighbor's level is parent's level + 1
                levels[neighbor] = max(levels[neighbor], levels[node_id] + 1)
                in_degree[neighbor] -= 1
                if in_degree[neighbor] == 0:
                    queue.append(neighbor)

        # Assign levels to nodes
        for node in unique_nodes:
            node["level"] = levels.get(node["task_id"], 0)

        return {
            "nodes": unique_nodes,
            "edges": unique_edges,
            "metadata": {
                "node_count": len(unique_nodes),
                "edge_count": len(unique_edges),
                "is_normalized": True,
            },
        }


class TemplateMatcher:
    """
    Template matching coordinator.

    Combines keyword, semantic, and structural matching
    to find the best matching templates.
    """

    def __init__(self, template_service: TemplateService):
        self.template_service = template_service

    def find_best_match(
        self,
        input_text: str = None,
        nodes: list[dict] = None,
        edges: list[dict] = None,
        top_k: int = 5,
    ) -> list[TemplateMatch]:
        """
        Find best matching templates using multiple strategies.

        Args:
            input_text: Natural language query
            nodes: Node structure (optional)
            edges: Edge structure (optional)
            top_k: Number of top matches to return

        Returns:
            List of top matching templates
        """
        matches_by_strategy = []

        # Strategy 1: Keyword matching
        if input_text:
            keyword_matches = self.template_service.match_by_keywords(input_text)
            matches_by_strategy.extend(keyword_matches)

        # Strategy 2: Semantic similarity
        if input_text:
            semantic_matches = self.template_service.match_by_semantic_similarity(input_text)
            matches_by_strategy.extend(semantic_matches)

        # Strategy 3: Structural matching
        if nodes and edges:
            struct_matches = self.template_service.match_by_structure(nodes, edges)
            matches_by_strategy.extend(struct_matches)

        # Aggregate and rank
        aggregated = {}
        for match in matches_by_strategy:
            key = match.template_id
            if key not in aggregated:
                aggregated[key] = match
            else:
                # Combine scores
                aggregated[key].match_score = (
                    aggregated[key].match_score + match.match_score
                ) / 2

        final_matches = list(aggregated.values())
        final_matches.sort(key=lambda m: m.match_score, reverse=True)

        return final_matches[:top_k]
