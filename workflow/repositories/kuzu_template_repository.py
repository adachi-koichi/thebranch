"""
KuzuDB-based template repository for persistent storage of template graphs.

Provides CRUD operations for templates, nodes, edges, and template matching records
using KuzuDB's graph database capabilities.
"""

import logging
import uuid
from datetime import datetime
from typing import Optional, List, Dict, Tuple

from workflow.repositories.kuzu_connection import KuzuConnection

logger = logging.getLogger(__name__)


class KuzuTemplateRepository:
    """
    Repository for managing templates in KuzuDB.

    Handles:
    - Template CRUD operations
    - Template node/edge management
    - Template matching and similarity search
    - Template usage statistics and history
    """

    def __init__(self, kuzu_conn: KuzuConnection):
        """
        Initialize KuzuDB template repository.

        Args:
            kuzu_conn: KuzuDB connection instance
        """
        self.conn = kuzu_conn

    # ===== TEMPLATE CRUD =====

    def save_template(self, template_data: dict) -> int:
        """
        Save a template with nodes and edges to KuzuDB.

        Args:
            template_data: Dict with template metadata, nodes, and edges:
                {
                    "template_id": int,
                    "name": str,
                    "description": str (optional),
                    "category": str (optional),
                    "tags": list[str] (optional),
                    "nodes": [{"node_id": str, "name": str, ...}],
                    "edges": [{"from": str, "to": str, "type": str, ...}]
                }

        Returns:
            template_id (int)

        Raises:
            Exception: If insertion fails
        """
        try:
            template_id = template_data.get("template_id")
            name = template_data.get("name")
            description = template_data.get("description", "")
            category = template_data.get("category", "")
            tags = template_data.get("tags", [])
            nodes = template_data.get("nodes", [])
            edges = template_data.get("edges", [])

            # Insert Template node
            tags_str = f"[{', '.join(repr(t) for t in tags)}]" if tags else "[]"
            now_str = datetime.now().isoformat()
            insert_template_query = f"""
            CREATE (t:Template {{
                template_id: {template_id},
                name: {repr(name)},
                description: {repr(description)},
                category: {repr(category)},
                tags: {tags_str},
                created_at: timestamp({repr(now_str)}),
                updated_at: timestamp({repr(now_str)}),
                usage_count: 0,
                is_active: true
            }})
            """
            self.conn.execute(insert_template_query)
            logger.info(f"Inserted template node: id={template_id}")

            # Insert TemplateNode nodes
            node_id_map = {}  # Map from node_id to template_node_id
            for node in nodes:
                template_node_id = f"{template_id}_{node.get('node_id', '')}"
                node_id_map[node.get("node_id")] = template_node_id
                node_name = node.get("name", "")
                node_type = node.get("type", "task")
                node_desc = node.get("description", "")
                duration = node.get("estimated_duration_minutes", 0)
                priority = node.get("priority", "medium")
                role_hint = node.get("role_hint", "")
                node_tags = node.get("tags", [])

                node_tags_str = f"[{', '.join(repr(t) for t in node_tags)}]" if node_tags else "[]"

                now_str = datetime.now().isoformat()
                # Build properties dict, excluding None values
                props = {
                    "template_node_id": template_node_id,
                    "template_id": template_id,
                    "node_id": node.get('node_id', ''),
                    "node_name": node_name,
                    "node_type": node_type,
                    "estimated_duration_minutes": duration,
                    "priority": priority,
                    "tags": node_tags_str,
                    "created_at": f"timestamp({repr(now_str)})"
                }
                if node_desc:
                    props["description"] = node_desc
                if role_hint:
                    props["role_hint"] = role_hint

                props_str = ", ".join(
                    f"{k}: {repr(v) if not (k in ['tags', 'created_at'] or k.endswith('_at')) else v}"
                    for k, v in props.items()
                )
                insert_node_query = f"""
                CREATE (n:TemplateNode {{{props_str}}})
                """
                self.conn.execute(insert_node_query)
            logger.info(f"Inserted {len(nodes)} template nodes")

            # Insert TemplateEdge relations
            for edge in edges:
                from_node_id = node_id_map.get(edge.get("from"), f"{template_id}_{edge.get('from')}")
                to_node_id = node_id_map.get(edge.get("to"), f"{template_id}_{edge.get('to')}")
                edge_type = edge.get("type", "depends_on")
                condition = edge.get("condition", "")
                confidence = edge.get("confidence_score", 1.0)

                # Build edge properties, excluding None/empty values
                edge_props = {
                    "edge_type": edge_type,
                    "confidence_score": confidence
                }
                if condition:
                    edge_props["condition"] = condition

                props_str = ", ".join(
                    f"{k}: {repr(v) if not (k in ['confidence_score']) else v}"
                    for k, v in edge_props.items()
                )

                insert_edge_query = f"""
                MATCH (from:TemplateNode {{template_node_id: {repr(from_node_id)}}})
                MATCH (to:TemplateNode {{template_node_id: {repr(to_node_id)}}})
                CREATE (from)-[e:TemplateEdge {{{props_str}}}]->(to)
                """
                try:
                    self.conn.execute(insert_edge_query)
                except Exception as e:
                    logger.warning(f"Failed to create edge {from_node_id} -> {to_node_id}: {e}")

            logger.info(f"Inserted {len(edges)} template edges")
            return template_id

        except Exception as e:
            logger.error(f"Failed to save template: {e}")
            raise

    def get_template(self, template_id: int) -> Optional[dict]:
        """
        Retrieve a template with all nodes and edges.

        Args:
            template_id: Template ID

        Returns:
            Dict with template metadata, nodes, and edges, or None if not found
        """
        try:
            # Get template node
            template_query = f"""
            MATCH (t:Template {{template_id: {template_id}}})
            RETURN t.template_id, t.name, t.description, t.category, t.tags,
                   t.created_at, t.updated_at, t.usage_count, t.is_active
            """
            result = self.conn.execute(template_query)

            if not result.has_next():
                logger.warning(f"Template not found: {template_id}")
                return None

            row = result.get_next()
            template_info = {
                "template_id": row[0],
                "name": row[1],
                "description": row[2],
                "category": row[3],
                "tags": row[4] if row[4] else [],
                "created_at": str(row[5]),
                "updated_at": str(row[6]),
                "usage_count": row[7],
                "is_active": row[8],
                "nodes": [],
                "edges": []
            }

            # Get template nodes
            nodes_query = f"""
            MATCH (n:TemplateNode {{template_id: {template_id}}})
            RETURN n.template_node_id, n.node_id, n.node_name, n.node_type,
                   n.description, n.estimated_duration_minutes, n.priority, n.role_hint, n.tags,
                   n.created_at
            ORDER BY n.created_at
            """
            result = self.conn.execute(nodes_query)

            while result.has_next():
                row = result.get_next()
                node = {
                    "template_node_id": row[0],
                    "node_id": row[1],
                    "node_name": row[2],
                    "node_type": row[3],
                    "description": row[4],
                    "estimated_duration_minutes": row[5],
                    "priority": row[6],
                    "role_hint": row[7],
                    "tags": row[8] if row[8] else []
                }
                template_info["nodes"].append(node)

            # Get template edges
            edges_query = f"""
            MATCH (from:TemplateNode {{template_id: {template_id}}})-[e:TemplateEdge]->(to:TemplateNode {{template_id: {template_id}}})
            RETURN from.node_id, to.node_id, e.edge_type, e.condition, e.confidence_score
            """
            result = self.conn.execute(edges_query)

            while result.has_next():
                row = result.get_next()
                edge = {
                    "from": row[0],
                    "to": row[1],
                    "edge_type": row[2],
                    "condition": row[3],
                    "confidence_score": row[4]
                }
                template_info["edges"].append(edge)

            logger.info(f"Retrieved template {template_id} with {len(template_info['nodes'])} nodes and {len(template_info['edges'])} edges")
            return template_info

        except Exception as e:
            logger.error(f"Failed to get template {template_id}: {e}")
            return None

    def list_templates(self, category: Optional[str] = None, page: int = 1, limit: int = 20) -> Tuple[List[dict], int]:
        """
        List templates with optional category filtering and pagination.

        Args:
            category: Filter by category (optional)
            page: Page number (1-indexed)
            limit: Results per page

        Returns:
            Tuple of (templates list, total count)
        """
        try:
            offset = (page - 1) * limit

            # Count total
            if category:
                count_query = f"""
                MATCH (t:Template {{category: {repr(category)}}})
                RETURN COUNT(t) as cnt
                """
            else:
                count_query = "MATCH (t:Template) RETURN COUNT(t) as cnt"

            result = self.conn.execute(count_query)
            total_count = result.get_next()[0] if result.has_next() else 0

            # Get templates
            if category:
                list_query = f"""
                MATCH (t:Template {{category: {repr(category)}}})
                RETURN t.template_id, t.name, t.description, t.category, t.usage_count, t.is_active
                ORDER BY t.updated_at DESC
                SKIP {offset} LIMIT {limit}
                """
            else:
                list_query = f"""
                MATCH (t:Template)
                RETURN t.template_id, t.name, t.description, t.category, t.usage_count, t.is_active
                ORDER BY t.updated_at DESC
                SKIP {offset} LIMIT {limit}
                """

            result = self.conn.execute(list_query)
            templates = []

            while result.has_next():
                row = result.get_next()
                template = {
                    "template_id": row[0],
                    "name": row[1],
                    "description": row[2],
                    "category": row[3],
                    "usage_count": row[4],
                    "is_active": row[5]
                }
                templates.append(template)

            logger.info(f"Listed {len(templates)} templates (page {page}, limit {limit})")
            return templates, total_count

        except Exception as e:
            logger.error(f"Failed to list templates: {e}")
            return [], 0

    def update_template(self, template_id: int, updates: dict) -> bool:
        """
        Update template metadata.

        Args:
            template_id: Template ID
            updates: Dict with fields to update (name, description, category, is_active, etc.)

        Returns:
            True if update successful, False otherwise
        """
        try:
            update_parts = []
            for key, value in updates.items():
                if key in ["name", "description", "category"]:
                    update_parts.append(f"t.{key} = {repr(str(value))}")
                elif key in ["is_active"]:
                    update_parts.append(f"t.{key} = {str(value).lower()}")
                elif key in ["usage_count"]:
                    update_parts.append(f"t.{key} = {value}")

            if not update_parts:
                logger.warning(f"No valid fields to update for template {template_id}")
                return False

            now_str = datetime.now().isoformat()
            update_query = f"""
            MATCH (t:Template {{template_id: {template_id}}})
            SET {', '.join(update_parts)}, t.updated_at = timestamp({repr(now_str)})
            RETURN t.template_id
            """
            result = self.conn.execute(update_query)

            if result.has_next():
                logger.info(f"Updated template {template_id}")
                return True
            else:
                logger.warning(f"Template not found for update: {template_id}")
                return False

        except Exception as e:
            logger.error(f"Failed to update template {template_id}: {e}")
            return False

    def delete_template(self, template_id: int) -> bool:
        """
        Delete a template and all related nodes and edges (cascade).

        Args:
            template_id: Template ID

        Returns:
            True if deletion successful, False otherwise
        """
        try:
            # Delete all edges first
            delete_edges_query = f"""
            MATCH (from:TemplateNode {{template_id: {template_id}}})-[e:TemplateEdge]->(to:TemplateNode {{template_id: {template_id}}})
            DELETE e
            """
            self.conn.execute(delete_edges_query)
            logger.info(f"Deleted edges for template {template_id}")

            # Delete all nodes
            delete_nodes_query = f"""
            MATCH (n:TemplateNode {{template_id: {template_id}}})
            DELETE n
            """
            self.conn.execute(delete_nodes_query)
            logger.info(f"Deleted nodes for template {template_id}")

            # Delete template
            delete_template_query = f"""
            MATCH (t:Template {{template_id: {template_id}}})
            DELETE t
            """
            self.conn.execute(delete_template_query)
            logger.info(f"Deleted template {template_id}")

            return True

        except Exception as e:
            logger.error(f"Failed to delete template {template_id}: {e}")
            return False

    # ===== SEARCH & ANALYSIS =====

    def find_templates_by_category(self, category: str) -> List[dict]:
        """
        Find all templates in a specific category.

        Args:
            category: Category name

        Returns:
            List of template metadata dicts
        """
        try:
            query = f"""
            MATCH (t:Template {{category: {repr(category)}}})
            RETURN t.template_id, t.name, t.description, t.usage_count
            ORDER BY t.usage_count DESC
            """
            result = self.conn.execute(query)
            templates = []

            while result.has_next():
                row = result.get_next()
                template = {
                    "template_id": row[0],
                    "name": row[1],
                    "description": row[2],
                    "usage_count": row[3]
                }
                templates.append(template)

            logger.info(f"Found {len(templates)} templates in category '{category}'")
            return templates

        except Exception as e:
            logger.error(f"Failed to find templates by category: {e}")
            return []

    def find_similar_templates(self, template_structure: dict, threshold: float = 0.7) -> List[dict]:
        """
        Find templates similar to a given structure (by node/edge count similarity).

        Args:
            template_structure: Dict with "node_count" and "edge_count"
            threshold: Similarity threshold (0.0-1.0)

        Returns:
            List of similar template metadata dicts with similarity scores
        """
        try:
            target_nodes = template_structure.get("node_count", 0)
            target_edges = template_structure.get("edge_count", 0)

            # Find templates and count their nodes
            query = f"""
            MATCH (t:Template)
            MATCH (n:TemplateNode {{template_id: t.template_id}})
            WITH t, COUNT(DISTINCT n) as node_count
            RETURN t.template_id, t.name, t.description, node_count
            """

            result = self.conn.execute(query)
            similar_templates = []

            while result.has_next():
                row = result.get_next()
                template_id, name, desc, node_count = row[0], row[1], row[2], row[3]

                # For now, use node count only (edge count requires additional query)
                similarity = self._calculate_similarity(
                    target_nodes, target_edges,
                    node_count, 0
                )

                if similarity >= threshold:
                    similar_templates.append({
                        "template_id": template_id,
                        "name": name,
                        "description": desc,
                        "node_count": node_count,
                        "edge_count": 0,
                        "similarity_score": similarity
                    })

            logger.info(f"Found {len(similar_templates)} similar templates (threshold={threshold})")
            return sorted(similar_templates, key=lambda x: x["similarity_score"], reverse=True)

        except Exception as e:
            logger.error(f"Failed to find similar templates: {e}")
            return []

    def get_template_statistics(self) -> dict:
        """
        Get overall statistics about templates in the graph.

        Returns:
            Dict with statistics:
            {
                "total_templates": int,
                "categories": dict (category -> count),
                "avg_nodes_per_template": float,
                "avg_edges_per_template": float,
                "top_used_templates": list,
                "total_nodes": int,
                "total_edges": int
            }
        """
        try:
            stats = {
                "total_templates": 0,
                "categories": {},
                "avg_nodes_per_template": 0.0,
                "avg_edges_per_template": 0.0,
                "top_used_templates": [],
                "total_nodes": 0,
                "total_edges": 0
            }

            # Total templates
            result = self.conn.execute("MATCH (t:Template) RETURN COUNT(t)")
            stats["total_templates"] = result.get_next()[0] if result.has_next() else 0

            # Categories
            result = self.conn.execute("""
            MATCH (t:Template)
            RETURN t.category, COUNT(t) as cnt
            """)
            while result.has_next():
                row = result.get_next()
                category = row[0] if row[0] else "uncategorized"
                stats["categories"][category] = row[1]

            # Total nodes
            result = self.conn.execute("MATCH (n:TemplateNode) RETURN COUNT(n)")
            stats["total_nodes"] = result.get_next()[0] if result.has_next() else 0

            # Total edges
            result = self.conn.execute("MATCH ()-[e:TemplateEdge]->() RETURN COUNT(e)")
            stats["total_edges"] = result.get_next()[0] if result.has_next() else 0

            # Average nodes and edges
            if stats["total_templates"] > 0:
                stats["avg_nodes_per_template"] = stats["total_nodes"] / stats["total_templates"]
                stats["avg_edges_per_template"] = stats["total_edges"] / stats["total_templates"]

            # Top 10 used templates
            result = self.conn.execute("""
            MATCH (t:Template)
            RETURN t.template_id, t.name, t.usage_count
            ORDER BY t.usage_count DESC
            LIMIT 10
            """)
            while result.has_next():
                row = result.get_next()
                stats["top_used_templates"].append({
                    "template_id": row[0],
                    "name": row[1],
                    "usage_count": row[2]
                })

            logger.info(f"Retrieved template statistics: {stats['total_templates']} templates, "
                       f"{stats['total_nodes']} nodes, {stats['total_edges']} edges")
            return stats

        except Exception as e:
            logger.error(f"Failed to get template statistics: {e}")
            return {
                "total_templates": 0,
                "categories": {},
                "avg_nodes_per_template": 0.0,
                "avg_edges_per_template": 0.0,
                "top_used_templates": [],
                "total_nodes": 0,
                "total_edges": 0
            }

    def record_template_match(self, template_id: int, workflow_id: int, match_score: float, match_reason: str, matched_fields: List[str] = None) -> bool:
        """
        Record a template matching result.

        Args:
            template_id: Template ID
            workflow_id: Workflow ID (placeholder, structure may vary)
            match_score: Matching score (0.0-1.0)
            match_reason: Reason for match
            matched_fields: List of matched field names

        Returns:
            True if recording successful, False otherwise
        """
        try:
            matched_fields = matched_fields or []
            fields_str = f"[{', '.join(repr(f) for f in matched_fields)}]"

            # Update usage count
            update_query = f"""
            MATCH (t:Template {{template_id: {template_id}}})
            SET t.usage_count = t.usage_count + 1
            RETURN t.template_id
            """
            self.conn.execute(update_query)

            logger.info(f"Recorded template match: template_id={template_id}, score={match_score}")
            return True

        except Exception as e:
            logger.error(f"Failed to record template match: {e}")
            return False

    def get_template_usage_history(self, template_id: int) -> List[dict]:
        """
        Get usage history for a template (simplified - returns usage count).

        Args:
            template_id: Template ID

        Returns:
            List with usage count (simplified implementation)
        """
        try:
            query = f"""
            MATCH (t:Template {{template_id: {template_id}}})
            RETURN t.template_id, t.name, t.usage_count, t.updated_at
            """
            result = self.conn.execute(query)

            if result.has_next():
                row = result.get_next()
                return [{
                    "template_id": row[0],
                    "name": row[1],
                    "usage_count": row[2],
                    "last_updated": str(row[3])
                }]
            else:
                logger.warning(f"Template not found: {template_id}")
                return []

        except Exception as e:
            logger.error(f"Failed to get template usage history: {e}")
            return []

    # ===== HELPER METHODS =====

    @staticmethod
    def _escape_string(s: str) -> str:
        """Escape single quotes in strings for Cypher."""
        if s is None:
            return ""
        return s.replace("'", "\\'")

    @staticmethod
    def _calculate_similarity(target_nodes: int, target_edges: int, actual_nodes: int, actual_edges: int) -> float:
        """
        Calculate similarity score based on node/edge counts.

        Returns value between 0.0 and 1.0
        """
        if target_nodes == 0 and target_edges == 0:
            return 0.0

        node_diff = abs(target_nodes - actual_nodes)
        edge_diff = abs(target_edges - actual_edges)

        # Simple similarity: 1.0 - (average difference as percentage)
        max_nodes = max(target_nodes, actual_nodes) or 1
        max_edges = max(target_edges, actual_edges) or 1

        node_similarity = 1.0 - (node_diff / max_nodes)
        edge_similarity = 1.0 - (edge_diff / max_edges)

        # Average
        return max(0.0, (node_similarity + edge_similarity) / 2.0)
