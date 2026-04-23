import json
import sqlite3
import uuid
from datetime import datetime
from pathlib import Path

import aiosqlite
from fastapi import APIRouter, HTTPException, Header, Depends

from workflow.services.nlp_service import NLPService, validate_dag, _compute_critical_path

DASHBOARD_DIR = Path(__file__).parent
THEBRANCH_DB = DASHBOARD_DIR / "data" / "thebranch.sqlite"

router = APIRouter(prefix="/api/v1/workflows", tags=["autogen"])


def get_current_user(auth_header: str = None):
    """認証トークンからユーザーを取得（簡易実装）"""
    if not auth_header:
        return None
    token = auth_header.replace("Bearer ", "")
    return {"id": token, "email": f"user-{token[:8]}@example.com"}


@router.post("/auto-generate")
async def auto_generate_dag(
    request_data: dict,
    auth_header: str = Header(None)
):
    """自然言語 → DAG変換API"""
    try:
        user = get_current_user(auth_header) if auth_header else None
        if not user:
            raise HTTPException(status_code=401, detail="認証が必要です")

        organization_id = request_data.get("organization_id", "default")
        user_input = request_data.get("natural_language_input", "").strip()
        options = request_data.get("options", {})
        model = options.get("model", "claude-sonnet-4-6")

        if not user_input or len(user_input) < 10:
            return {
                "success": False,
                "error": {
                    "code": "INVALID_INPUT",
                    "message": "入力テキストが短すぎます（最小 10 文字）",
                    "details": {"input_length": len(user_input), "minimum_length": 10}
                }
            }

        nlp_service = NLPService()
        result = nlp_service.extract_workflow_dag(user_input, model=model)

        if not result["success"]:
            return {
                "success": False,
                "error": result.get("error", {"code": "UNKNOWN_ERROR", "message": "未知のエラー"})
            }

        generation_id = f"autogen-{datetime.now().strftime('%Y%m%d')}-{uuid.uuid4().hex[:8]}"
        workflow = result["workflow"]
        validation = result["validation"]

        await _save_autogen_history(
            generation_id=generation_id,
            organization_id=organization_id,
            workflow_instance_id=None,
            user_id=user["id"],
            natural_language_input=user_input,
            generated_dag_json=json.dumps(workflow),
            model_used=result["metadata"]["model_used"],
            prompt_tokens=result["metadata"]["prompt_tokens"],
            completion_tokens=result["metadata"]["completion_tokens"],
            cache_hit=result["metadata"]["cache_hit"],
            is_valid=validation["is_valid"],
            validation_errors=json.dumps(validation["errors"]) if validation["errors"] else None
        )

        return {
            "success": True,
            "data": {
                "generation_id": generation_id,
                "workflow": workflow,
                "metadata": {
                    "generated_at": datetime.utcnow().isoformat() + "Z",
                    "model_used": result["metadata"]["model_used"],
                    "prompt_tokens": result["metadata"]["prompt_tokens"],
                    "completion_tokens": result["metadata"]["completion_tokens"],
                    "cache_hit": result["metadata"]["cache_hit"]
                }
            }
        }

    except json.JSONDecodeError:
        return {
            "success": False,
            "error": {
                "code": "PARSING_ERROR",
                "message": "Claude APIレスポンスが無効なJSONです"
            }
        }

    except HTTPException:
        raise

    except Exception as e:
        return {
            "success": False,
            "error": {
                "code": "INTERNAL_ERROR",
                "message": str(e)
            }
        }


@router.post("/validate-dag")
async def validate_dag_endpoint(
    request_data: dict,
    auth_header: str = Header(None)
):
    """DAGバリデーションAPI"""
    try:
        user = get_current_user(auth_header) if auth_header else None
        if not user:
            raise HTTPException(status_code=401, detail="認証が必要です")

        nodes = request_data.get("nodes", [])
        edges = request_data.get("edges", [])

        if not nodes:
            return {
                "success": False,
                "error": {
                    "code": "INVALID_INPUT",
                    "message": "ノードが定義されていません"
                }
            }

        validation_result = validate_dag(nodes, edges)
        critical_path = _compute_critical_path(nodes, edges)
        critical_path_duration = sum(
            next((n['estimated_duration_minutes'] for n in nodes if n['task_id'] == t), 0)
            for t in critical_path or []
        )

        return {
            "success": True,
            "data": {
                "validation_result": validation_result,
                "statistics": {
                    "total_nodes": len(nodes),
                    "total_edges": len(edges),
                    "critical_path_length": len(critical_path) if critical_path else 0,
                    "critical_path_duration_minutes": critical_path_duration,
                    "critical_path": critical_path or []
                }
            }
        }

    except Exception as e:
        return {
            "success": False,
            "error": {
                "code": "INTERNAL_ERROR",
                "message": str(e)
            }
        }


async def _save_autogen_history(
    generation_id: str,
    organization_id: str,
    workflow_instance_id,
    user_id: str,
    natural_language_input: str,
    generated_dag_json: str,
    model_used: str,
    prompt_tokens: int,
    completion_tokens: int,
    cache_hit: bool,
    is_valid: bool,
    validation_errors: str = None,
    status: str = "pending",
    approved_by: str = None,
    approved_at: str = None,
    notes: str = None
):
    """生成履歴をデータベースに保存"""
    try:
        async with aiosqlite.connect(str(THEBRANCH_DB)) as db:
            db.row_factory = sqlite3.Row
            await db.execute(
                """INSERT INTO autogen_history
                   (generation_id, organization_id, workflow_instance_id, user_id,
                    natural_language_input, generated_dag_json, model_used,
                    prompt_tokens, completion_tokens, cache_hit, is_valid,
                    validation_errors, status, approved_by, approved_at, notes,
                    created_at, updated_at)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                (
                    generation_id,
                    organization_id,
                    workflow_instance_id,
                    user_id,
                    natural_language_input,
                    generated_dag_json,
                    model_used,
                    prompt_tokens,
                    completion_tokens,
                    1 if cache_hit else 0,
                    1 if is_valid else 0,
                    validation_errors,
                    status,
                    approved_by,
                    approved_at,
                    notes,
                    datetime.now().isoformat(),
                    datetime.now().isoformat()
                )
            )
            await db.commit()
    except Exception as e:
        pass


bp = router
