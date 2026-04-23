"""Service layer for processing NLP output and saving workflow DAGs to KuzuDB"""
from pathlib import Path
from workflow.repositories.graph_repository_workflow import WorkflowGraphRepository
from workflow.services.nlp_service import validate_dag


class GraphService:
    """
    NLP出力をKuzuDB DAG構造に変換し保存するサービス層。

    NLPService の出力と WorkflowGraphRepository を橋渡しする役割を担当。
    """

    def __init__(self, db_path: str | Path = None):
        """
        Initialize GraphService with KuzuDB connection.

        Args:
            db_path: Path to KuzuDB database. If None, uses default path.
        """
        self.repository = WorkflowGraphRepository(db_path)
        self.repository.initialize_schema()

    def process_and_save(self, generation_id: str, nlp_result: dict) -> dict:
        """
        NLP サービスの出力を受け取り、バリデーション後に KuzuDB へ保存。

        Args:
            generation_id: autogen-YYYYMMDD-xxxx 形式の ID
            nlp_result: NLPService.extract_workflow_dag() の戻り値
                        {"workflow": {"name": ..., "nodes": [...], "edges": [...], "validation": {...}}}

        Returns:
            {
                "success": bool,
                "generation_id": str,
                "nodes_saved": int,
                "edges_saved": int,
                "validation": {...},
                "error": str | None
            }
        """
        try:
            # {"workflow": {...}} 形式と {"success": True, "data": {"workflow": ...}} 形式の両方を受け付ける
            if "data" in nlp_result:
                workflow = nlp_result["data"].get("workflow")
            else:
                workflow = nlp_result.get("workflow")
            if not workflow:
                return {
                    "success": False,
                    "generation_id": generation_id,
                    "nodes_saved": 0,
                    "edges_saved": 0,
                    "validation": None,
                    "error": "No workflow data in NLP result"
                }

            nodes = workflow.get("nodes", [])
            edges = workflow.get("edges", [])

            # Validate DAG structure
            validation_result = validate_dag(nodes, edges)

            # Return validation error if DAG is invalid
            if not validation_result.get("is_valid"):
                return {
                    "success": False,
                    "generation_id": generation_id,
                    "nodes_saved": 0,
                    "edges_saved": 0,
                    "validation": validation_result,
                    "error": f"DAG validation failed: {validation_result.get('errors', [])}"
                }

            # Save to KuzuDB
            self.repository.save_workflow_dag(generation_id, workflow)

            return {
                "success": True,
                "generation_id": generation_id,
                "nodes_saved": len(nodes),
                "edges_saved": len(edges),
                "validation": validation_result,
                "error": None
            }

        except Exception as e:
            return {
                "success": False,
                "generation_id": generation_id,
                "nodes_saved": 0,
                "edges_saved": 0,
                "validation": None,
                "error": str(e)
            }

    def get_workflow_graph(self, generation_id: str) -> dict:
        """
        generation_id に紐付く DAG を KuzuDB から取得して返す。

        Args:
            generation_id: Workflow generation ID

        Returns:
            {
                "generation_id": str,
                "tasks": list[dict],
                "success": bool,
                "error": str | None
            }
        """
        try:
            tasks = self.repository.get_workflow_tasks(generation_id)
            return {
                "generation_id": generation_id,
                "tasks": tasks,
                "success": True,
                "error": None
            }
        except Exception as e:
            return {
                "generation_id": generation_id,
                "tasks": [],
                "success": False,
                "error": str(e)
            }

    def delete_workflow(self, generation_id: str) -> bool:
        """
        generation_id に紐付く全ノード・エッジを削除。

        Args:
            generation_id: Workflow generation ID

        Returns:
            True on success, False on error
        """
        try:
            # Delete depends_on edges (directed)
            self.repository.kuzu.execute(
                """
                MATCH (from:WorkflowTask {workflow_instance_id: $workflow_instance_id})
                      -[rel:workflow_depends_on]->
                      (to:WorkflowTask {workflow_instance_id: $workflow_instance_id})
                DELETE rel
                """,
                {"workflow_instance_id": generation_id}
            )

            # Delete blocks edges (directed)
            self.repository.kuzu.execute(
                """
                MATCH (from:WorkflowTask {workflow_instance_id: $workflow_instance_id})
                      -[rel:workflow_blocks]->
                      (to:WorkflowTask {workflow_instance_id: $workflow_instance_id})
                DELETE rel
                """,
                {"workflow_instance_id": generation_id}
            )

            # Delete triggers edges (directed)
            self.repository.kuzu.execute(
                """
                MATCH (from:WorkflowTask {workflow_instance_id: $workflow_instance_id})
                      -[rel:workflow_triggers]->
                      (to:WorkflowTask {workflow_instance_id: $workflow_instance_id})
                DELETE rel
                """,
                {"workflow_instance_id": generation_id}
            )

            # Delete all task nodes
            self.repository.kuzu.execute(
                """
                MATCH (t:WorkflowTask {workflow_instance_id: $workflow_instance_id})
                DELETE t
                """,
                {"workflow_instance_id": generation_id}
            )

            return True
        except Exception as e:
            print(f"Error deleting workflow {generation_id}: {e}")
            return False

    def close(self):
        """Close the KuzuDB connection"""
        self.repository.close()

    def __enter__(self):
        """Context manager entry"""
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        """Context manager exit"""
        self.close()
