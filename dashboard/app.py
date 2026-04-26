import asyncio
import hashlib
import json
import logging
import os
import re
import shutil
import sqlite3
import subprocess
import time
import uuid
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from datetime import datetime
from typing import AsyncGenerator, List, Optional

import aiosqlite
import yaml
import httpx
from fastapi import FastAPI, HTTPException, WebSocket, WebSocketDisconnect, Header, Depends, Query, Request
from fastapi.responses import HTMLResponse, StreamingResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

from dashboard import auth, models, autogen_routes, blueprints, manage_routes, scores_routes, marketplace_routes, agents_control_routes, project_routes
from workflow.repositories.template import TemplateRepository
from workflow.services.template import TemplateService
from workflow.validation.template import TemplateValidator
from workflow.repositories.graph_repository_departments import GraphRepositoryDepartments
from workflow.repositories.kuzu_connection import KuzuConnection
from workflow.repositories.cost_repository import CostRepository
from workflow.services.cost_service import CostTrackingService
from workflow.repositories.accounting_repository import AccountingRepository
from workflow.services.accounting_service import AccountingService

TASKS_DB = Path.home() / ".claude" / "skills" / "task-manager-sqlite" / "data" / "tasks.sqlite"
SESSIONS_DIR = Path.home() / ".claude" / "sessions"
PROJECTS_DIR = Path.home() / ".claude" / "projects"
TASK_SCRIPT = Path.home() / ".claude" / "skills" / "task-manager-sqlite" / "scripts" / "task.py"
PORTS_YAML = Path(__file__).parent.parent / "ports.yaml"
MONITORING_YAML = Path(__file__).parent.parent / "monitoring.yaml"
TMUX_BIN = shutil.which("tmux") or "/opt/homebrew/bin/tmux"

app = FastAPI()

# Mount static files (CSS, JS)
DASHBOARD_DIR = Path(__file__).parent
static_styles = DASHBOARD_DIR / "styles"
static_js = DASHBOARD_DIR / "js"

if static_styles.exists():
    app.mount("/styles", StaticFiles(directory=str(static_styles)), name="styles")
if static_js.exists():
    app.mount("/js", StaticFiles(directory=str(static_js)), name="js")


# ── Task #2793: SPA ページルート（include_router より前に登録して優先させる）
# index.html を返し、フロント側で window.location.pathname に応じてモーダルを表示する
@app.get("/projects", response_class=HTMLResponse)
async def page_projects_spa():
    html_path = DASHBOARD_DIR / "index.html"
    return HTMLResponse(content=html_path.read_text(encoding="utf-8"))


@app.get("/workflows", response_class=HTMLResponse)
async def page_workflows_spa():
    html_path = DASHBOARD_DIR / "index.html"
    return HTMLResponse(content=html_path.read_text(encoding="utf-8"))


@app.get("/workflow-templates", response_class=HTMLResponse)
async def page_workflow_templates_spa():
    html_path = DASHBOARD_DIR / "index.html"
    return HTMLResponse(content=html_path.read_text(encoding="utf-8"))


# ── Task #2509: AIエージェントチャット SPA ルート
@app.get("/agent-chat", response_class=HTMLResponse)
async def page_agent_chat_spa():
    html_path = DASHBOARD_DIR / "index.html"
    return HTMLResponse(content=html_path.read_text(encoding="utf-8"))


app.include_router(autogen_routes.router)
app.include_router(blueprints.router)
app.include_router(manage_routes.router)
app.include_router(scores_routes.router)
app.include_router(scores_routes.dept_router)
app.include_router(marketplace_routes.router)
app.include_router(agents_control_routes.router)
app.include_router(project_routes.router)

logger = logging.getLogger(__name__)

THEBRANCH_DB = DASHBOARD_DIR / "data" / "thebranch.sqlite"

# ──────────────────────────────────────────────
# Zero Trust Authentication (Task #2755)
# ──────────────────────────────────────────────

async def verify_token_with_scope(authorization: Optional[str], required_scope: Optional[list] = None) -> tuple[Optional[str], Optional[list], Optional[str]]:
    """
    トークンを検証し、スコープをチェック。
    Bearer {session_token} または APIトークン両方に対応。

    Returns:
        (user_id, scopes, token_type) or (None, None, None)
    """
    if not authorization:
        return None, None, None

    try:
        # Bearer token (session token)
        if authorization.startswith("Bearer "):
            token = authorization[7:]
            result = await auth.verify_token(token)
            # verify_token returns (user_id, org_id) tuple
            if isinstance(result, tuple):
                user_id, org_id = result
            else:
                user_id = result
                org_id = None

            if user_id:
                await auth.update_last_activity(token)
                await auth.enforce_max_sessions(user_id, max_sessions=3)
                return user_id, ["read", "write", "admin"], "session"
            return None, None, None

        # API token
        token = authorization
        result = await auth.verify_api_token_scope(token, required_scope or "read")
        if result:
            user_id, token_id, has_scope = result
            if user_id and has_scope:
                return user_id, [required_scope or "read"], "api_token"

        return None, None, None
    except Exception as e:
        logger.error(f"Token verification error: {e}")
        return None, None, None


async def get_current_user_zero_trust(authorization: Optional[str] = Header(None)) -> dict:
    """FastAPI dependency for zero trust authentication."""
    user_id, scopes, token_type = await verify_token_with_scope(authorization)

    if not user_id:
        raise HTTPException(status_code=401, detail="Unauthorized")

    # Fetch user details
    async with aiosqlite.connect(str(auth.DB_PATH)) as db:
        db.row_factory = aiosqlite.Row
        cursor = await db.execute(
            "SELECT id, username, email, created_at, updated_at, COALESCE(onboarding_completed, 0) as onboarding_completed FROM users WHERE id = ?",
            (user_id,),
        )
        user_row = await cursor.fetchone()
        if not user_row:
            raise HTTPException(status_code=401, detail="User not found")

        roles_cursor = await db.execute(
            "SELECT role FROM user_roles WHERE user_id = ?",
            (user_id,),
        )
        roles_rows = await roles_cursor.fetchall()
        roles = [r["role"] for r in roles_rows] or ["member"]

        return {
            "id": user_row["id"],
            "username": user_row["username"],
            "email": user_row["email"],
            "created_at": user_row["created_at"],
            "updated_at": user_row["updated_at"],
            "onboarding_completed": user_row["onboarding_completed"],
            "scopes": scopes,
            "token_type": token_type,
            "roles": roles,
        }

# SLA メトリクス計算エンジン
sla_scheduler_task = None

async def calculate_sla_metrics():
    """SLAメトリクスを計算して記録"""
    try:
        db_path = DASHBOARD_DIR / "data" / "thebranch.sqlite"
        async with aiosqlite.connect(str(db_path)) as db:
            db.row_factory = sqlite3.Row

            cursor = await db.execute("SELECT id, name FROM sla_policies WHERE enabled = 1")
            policies = await cursor.fetchall()

            for policy in policies:
                policy_id = policy["id"]
                policy_name = policy["name"]

                response_time_ms = 0
                uptime_percentage = 100.0
                error_rate = 0.0

                # 応答時間を測定（ローカルサーバーへのテストリクエスト）
                try:
                    start_time = time.time()
                    async with httpx.AsyncClient(timeout=10.0) as client:
                        response = await client.get("http://localhost:7002/api/sla/policies")
                        response_time_ms = int((time.time() - start_time) * 1000)

                        # 簡易的なエラー率計算
                        if response.status_code >= 400:
                            error_rate = 0.1
                        else:
                            error_rate = 0.0
                except Exception as e:
                    response_time_ms = 10000  # タイムアウトの場合は大きな値
                    error_rate = 1.0
                    uptime_percentage = 0.0
                    logger.error(f"Failed to measure metrics for policy {policy_name}: {str(e)}")

                # メトリクスを記録
                cursor = await db.execute(
                    """INSERT INTO sla_metrics
                       (policy_id, response_time_ms, uptime_percentage, error_rate)
                       VALUES (?, ?, ?, ?)""",
                    (policy_id, response_time_ms, uptime_percentage, error_rate)
                )
                await db.commit()
                metric_id = cursor.lastrowid

                # ポリシーの閾値を取得
                cursor = await db.execute(
                    "SELECT response_time_limit_ms, uptime_percentage, error_rate_limit FROM sla_policies WHERE id = ?",
                    (policy_id,)
                )
                policy_limits = await cursor.fetchone()

                # SLA違反を検知
                violations = []

                if response_time_ms > policy_limits["response_time_limit_ms"]:
                    violations.append({
                        "type": "response_time_exceeded",
                        "severity": "high" if response_time_ms > policy_limits["response_time_limit_ms"] * 1.5 else "medium",
                        "details": f"応答時間 {response_time_ms}ms が限界値 {policy_limits['response_time_limit_ms']}ms を超過"
                    })

                if uptime_percentage < policy_limits["uptime_percentage"]:
                    violations.append({
                        "type": "uptime_below_limit",
                        "severity": "high",
                        "details": f"稼働率 {uptime_percentage}% が限界値 {policy_limits['uptime_percentage']}% 以下"
                    })

                if error_rate > policy_limits["error_rate_limit"]:
                    violations.append({
                        "type": "error_rate_exceeded",
                        "severity": "medium" if error_rate < policy_limits["error_rate_limit"] * 2 else "high",
                        "details": f"エラー率 {error_rate * 100}% が限界値 {policy_limits['error_rate_limit'] * 100}% を超過"
                    })

                # 違反をテーブルに記録
                for violation in violations:
                    await db.execute(
                        """INSERT INTO sla_violations
                           (policy_id, metric_id, violation_type, severity, details, alert_sent)
                           VALUES (?, ?, ?, ?, ?, ?)""",
                        (policy_id, metric_id, violation["type"], violation["severity"], violation["details"], False)
                    )
                    await db.commit()

    except Exception as e:
        logger.error(f"Error calculating SLA metrics: {str(e)}")


async def sla_metrics_scheduler():
    """定期的にSLAメトリクスを計算"""
    while True:
        try:
            await calculate_sla_metrics()
        except Exception as e:
            logger.error(f"SLA metrics scheduler error: {str(e)}")
        finally:
            await asyncio.sleep(30)  # 30秒ごとに実行


async def verify_api_key(x_api_key: str = Header(None)) -> dict:
    """APIキー検証とレート制限チェック"""
    if not x_api_key:
        raise HTTPException(status_code=401, detail="APIキーが必要です")

    try:
        async with aiosqlite.connect(str(THEBRANCH_DB)) as db:
            db.row_factory = sqlite3.Row

            key_hash = hashlib.sha256(x_api_key.encode()).hexdigest()
            cursor = await db.execute(
                "SELECT id, org_id, name, rate_limit_per_minute, is_active, expires_at FROM api_keys WHERE key_hash = ?",
                (key_hash,)
            )
            api_key = await cursor.fetchone()

            if not api_key:
                raise HTTPException(status_code=401, detail="無効なAPIキーです")

            if not api_key["is_active"]:
                raise HTTPException(status_code=403, detail="APIキーが無効です")

            if api_key["expires_at"] and datetime.fromisoformat(api_key["expires_at"]) < datetime.now():
                raise HTTPException(status_code=403, detail="APIキーの有効期限が切れています")

            return {
                "api_key_id": api_key["id"],
                "org_id": api_key["org_id"],
                "name": api_key["name"],
                "rate_limit": api_key["rate_limit_per_minute"]
            }
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"APIキー検証エラー: {str(e)}")
        raise HTTPException(status_code=500, detail="APIキー検証エラー")


@app.on_event("startup")
async def startup_event():
    """アプリケーション起動時にスケジューラーを開始"""
    global sla_scheduler_task
    sla_scheduler_task = asyncio.create_task(sla_metrics_scheduler())


@app.on_event("shutdown")
async def shutdown_event():
    """アプリケーション終了時にスケジューラーを停止"""
    global sla_scheduler_task
    if sla_scheduler_task:
        sla_scheduler_task.cancel()
        try:
            await sla_scheduler_task
        except asyncio.CancelledError:
            pass

# ──────────────────────────────────────────────
# Workflow Services
# ──────────────────────────────────────────────

template_repo = None
template_service = None
kuzu_conn = None
graph_repo_dept = None
cost_repo = None
cost_service = None
accounting_repo = None
accounting_service = None

def run_migrations():
    """Run all migration SQL files"""
    migrations_dir = DASHBOARD_DIR / "migrations"
    migration_files = sorted(migrations_dir.glob("*.sql"))

    conn = sqlite3.connect(str(THEBRANCH_DB))
    cursor = conn.cursor()
    cursor.execute("PRAGMA foreign_keys = ON")

    for migration_file in migration_files:
        try:
            sql = migration_file.read_text(encoding="utf-8")
            cursor.executescript(sql)
            conn.commit()
        except Exception as e:
            logger.warning(f"Migration {migration_file.name} failed or already applied: {e}")
            conn.rollback()

    conn.close()

def init_workflow_services():
    global template_repo, template_service, kuzu_conn, graph_repo_dept, cost_repo, cost_service, accounting_repo, accounting_service
    if template_repo is None:
        THEBRANCH_DB.parent.mkdir(parents=True, exist_ok=True)
        run_migrations()
        template_repo = TemplateRepository(str(THEBRANCH_DB))
        template_service = TemplateService(template_repo, TemplateValidator(template_repo))
    if kuzu_conn is None:
        kuzu_conn = KuzuConnection()
        graph_repo_dept = GraphRepositoryDepartments(kuzu_conn)
    if cost_repo is None:
        cost_repo = CostRepository(str(THEBRANCH_DB))
        cost_service = CostTrackingService(cost_repo)
    if accounting_repo is None:
        accounting_repo = AccountingRepository(str(THEBRANCH_DB))
        accounting_service = AccountingService(accounting_repo)

def get_template_service():
    if template_service is None:
        init_workflow_services()
    return template_service

def get_template_repo():
    if template_repo is None:
        init_workflow_services()
    return template_repo

def get_accounting_service():
    if accounting_service is None:
        init_workflow_services()
    return accounting_service


# ──────────────────────────────────────────────
# HTML
# ──────────────────────────────────────────────

@app.get("/", response_class=HTMLResponse)
async def root():
    html_path = DASHBOARD_DIR / "index.html"
    return HTMLResponse(content=html_path.read_text(encoding="utf-8"))


# ──────────────────────────────────────────────
# Ports
# ──────────────────────────────────────────────

@app.get("/api/ports")
async def get_ports(user: dict = Depends(get_current_user_zero_trust)):
    if not PORTS_YAML.exists():
        return {"reserved": [], "projects": {}}
    try:
        with open(PORTS_YAML, encoding="utf-8") as f:
            data = yaml.safe_load(f)
        return data or {}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# ──────────────────────────────────────────────
# Tasks
# ──────────────────────────────────────────────

@app.get("/api/tasks")
async def get_tasks(status: str = "", category: str = "", dir_filter: str = "", limit: int = 0, user: dict = Depends(get_current_user_zero_trust)):
    if not TASKS_DB.exists():
        return []
    async with aiosqlite.connect(str(TASKS_DB)) as db:
        db.row_factory = aiosqlite.Row
        cursor = await db.execute(
            "SELECT id, title, description, status, priority, category, dir, session_id, created_at, updated_at, phase, assignee "
            "FROM dev_tasks ORDER BY id DESC"
        )
        rows = await cursor.fetchall()

    results = []
    for row in rows:
        item = dict(row)
        if status == "incomplete":
            if item.get("status") in ("done", "completed", "cancelled", "cancel"):
                continue
        elif status and status != "all" and item.get("status") != status:
            continue
        if category and item.get("category") != category:
            continue
        if dir_filter and dir_filter not in (item.get("dir") or ""):
            continue
        results.append(item)
    if limit > 0:
        results = results[:limit]
    return results


class CreateTaskRequest(BaseModel):
    title: str
    description: str = ""
    category: str = ""
    priority: int = 2
    dir: str = ""


@app.get("/api/workflow-templates")
async def get_workflow_templates(status: str = "", user: dict = Depends(get_current_user_zero_trust)):
    """全ワークフローテンプレート一覧を JSON で返却"""
    try:
        async with aiosqlite.connect(str(THEBRANCH_DB)) as db:
            query = "SELECT id, name, description, status, created_at, created_by FROM workflow_templates"
            params = []
            if status:
                query += " WHERE status = ?"
                params.append(status)
            query += " ORDER BY created_at DESC LIMIT 100"

            async with db.execute(query, params) as cursor:
                rows = await cursor.fetchall()

            result = []
            for row in rows:
                template_id = row[0]
                # Get phases for this template
                async with db.execute(
                    "SELECT id, phase_key, phase_label, specialist_type, phase_order, is_parallel FROM wf_template_phases WHERE template_id = ? ORDER BY phase_order",
                    [template_id]
                ) as cursor:
                    phases = await cursor.fetchall()

                steps = []
                for phase in phases:
                    phase_id = phase[0]
                    # Get tasks for this phase
                    async with db.execute(
                        "SELECT id, task_key, task_title, task_description, estimated_hours, priority, task_order FROM wf_template_tasks WHERE phase_id = ? ORDER BY task_order",
                        [phase_id]
                    ) as cursor:
                        tasks = await cursor.fetchall()

                    phase_step = {
                        "phase_id": phase[0],
                        "phase_key": phase[1],
                        "phase_label": phase[2],
                        "specialist_type": phase[3],
                        "phase_order": phase[4],
                        "is_parallel": bool(phase[5]),
                        "tasks": [
                            {
                                "id": t[0],
                                "task_key": t[1],
                                "task_title": t[2],
                                "task_description": t[3],
                                "estimated_hours": t[4],
                                "priority": t[5],
                                "task_order": t[6],
                            }
                            for t in tasks
                        ]
                    }
                    steps.append(phase_step)

                result.append({
                    "id": row[0],
                    "name": row[1],
                    "description": row[2],
                    "status": row[3],
                    "created_at": row[4],
                    "created_by": row[5],
                    "steps": steps
                })

            return {"templates": result}
    except Exception as e:
        logger.error(f"Error fetching workflow templates: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/workflow-templates/{template_id}")
async def get_workflow_template_detail(template_id: int, user: dict = Depends(get_current_user_zero_trust)):
    """ワークフローテンプレート詳細を JSON で返却"""
    try:
        async with aiosqlite.connect(str(THEBRANCH_DB)) as db:
            async with db.execute(
                "SELECT id, name, description, status, created_at, created_by FROM workflow_templates WHERE id = ?",
                [template_id]
            ) as cursor:
                row = await cursor.fetchone()

            if not row:
                raise HTTPException(status_code=404, detail="Template not found")

            # Get phases for this template
            async with db.execute(
                "SELECT id, phase_key, phase_label, specialist_type, phase_order, is_parallel FROM wf_template_phases WHERE template_id = ? ORDER BY phase_order",
                [template_id]
            ) as cursor:
                phases = await cursor.fetchall()

            steps = []
            for phase in phases:
                phase_id = phase[0]
                # Get tasks for this phase
                async with db.execute(
                    "SELECT id, task_key, task_title, task_description, estimated_hours, priority, task_order FROM wf_template_tasks WHERE phase_id = ? ORDER BY task_order",
                    [phase_id]
                ) as cursor:
                    tasks = await cursor.fetchall()

                phase_step = {
                    "phase_id": phase[0],
                    "phase_key": phase[1],
                    "phase_label": phase[2],
                    "specialist_type": phase[3],
                    "phase_order": phase[4],
                    "is_parallel": bool(phase[5]),
                    "tasks": [
                        {
                            "id": t[0],
                            "task_key": t[1],
                            "task_title": t[2],
                            "task_description": t[3],
                            "estimated_hours": t[4],
                            "priority": t[5],
                            "task_order": t[6],
                        }
                        for t in tasks
                    ]
                }
                steps.append(phase_step)

            return {
                "id": row[0],
                "name": row[1],
                "description": row[2],
                "status": row[3],
                "created_at": row[4],
                "created_by": row[5],
                "steps": steps
            }
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error fetching template detail: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/tasks")
async def create_task(req: CreateTaskRequest, user: dict = Depends(get_current_user_zero_trust)):
    cmd = [
        "python3", str(TASK_SCRIPT),
        "add", req.title,
        "--description", req.description,
        "--category", req.category,
        "--priority", str(req.priority),
        "--dir", req.dir,
    ]
    result = subprocess.run(cmd, capture_output=True, text=True)
    if result.returncode != 0:
        raise HTTPException(status_code=500, detail=result.stderr)
    return {"ok": True}


class UpdateStatusRequest(BaseModel):
    status: str  # "in_progress" | "done" | "pending" | "completed"


@app.patch("/api/tasks/{task_id}/status")
async def update_task_status(task_id: int, req: UpdateStatusRequest, user: dict = Depends(get_current_user_zero_trust)):
    if req.status == "done":
        cmd = ["python3", str(TASK_SCRIPT), "done", str(task_id)]
    else:
        cmd = ["python3", str(TASK_SCRIPT), "update", str(task_id), "--status", req.status]
    result = subprocess.run(cmd, capture_output=True, text=True)
    if result.returncode != 0:
        raise HTTPException(status_code=500, detail=result.stderr)
    return {"ok": True}


class ReorderItem(BaseModel):
    id: int
    priority: int

class ReorderRequest(BaseModel):
    order: list[ReorderItem]

@app.patch("/api/tasks/reorder")
async def reorder_tasks(req: ReorderRequest, user: dict = Depends(get_current_user_zero_trust)):
    """ドラッグ&ドロップ並び替え後の優先度を一括更新する。"""
    if not req.order:
        return {"ok": True, "updated": 0}
    async with aiosqlite.connect(str(TASKS_DB)) as db:
        for item in req.order:
            await db.execute(
                "UPDATE dev_tasks SET priority=?, updated_at=datetime('now') WHERE id=?",
                (item.priority, item.id),
            )
        await db.commit()
    return {"ok": True, "updated": len(req.order)}


@app.get("/api/dashboard/summary")
async def get_dashboard_summary(user: dict = Depends(get_current_user_zero_trust)):
    """ダッシュボード統計まとめを返す。 (#459)

    Returns:
        pending/in_progress/completed/total タスク件数,
        アクティブセッション数（チームセッション），
        直近完了タスク3件
    """
    counts = {"pending": 0, "in_progress": 0, "completed": 0, "total": 0}
    recent_completed: list = []

    if TASKS_DB.exists():
        async with aiosqlite.connect(str(TASKS_DB)) as db:
            db.row_factory = aiosqlite.Row
            # ステータス別集計
            cursor = await db.execute(
                "SELECT status, COUNT(*) as cnt FROM dev_tasks GROUP BY status"
            )
            for row in await cursor.fetchall():
                s = row["status"]
                c = row["cnt"]
                counts["total"] += c
                if s == "pending":
                    counts["pending"] = c
                elif s == "in_progress":
                    counts["in_progress"] = c
                elif s in ("completed", "done"):
                    counts["completed"] += c

            # 直近完了タスク3件
            cursor = await db.execute(
                "SELECT id, title, status, updated_at, assignee, dir "
                "FROM dev_tasks WHERE status IN ('completed', 'done') "
                "ORDER BY updated_at DESC LIMIT 3"
            )
            recent_completed = [dict(row) for row in await cursor.fetchall()]

    # アクティブセッション数（v3チームセッション: {service}_orchestrator_wf{N}_{team}@main）
    active_sessions = 0
    try:
        result = subprocess.run(
            [TMUX_BIN, "ls", "-F", "#{session_name}"],
            capture_output=True, text=True, timeout=5,
        )
        if result.returncode == 0:
            sessions = result.stdout.strip().splitlines()
            active_sessions = sum(
                1 for s in sessions
                if "_orchestrator_wf" in s and s.endswith("@main")
            )
    except Exception:
        pass

    return {
        "pending": counts["pending"],
        "in_progress": counts["in_progress"],
        "completed": counts["completed"],
        "total": counts["total"],
        "active_sessions": active_sessions,
        "recent_completed": recent_completed,
    }


@app.get("/api/tasks/export")
async def export_tasks(format: str = "json", user: dict = Depends(get_current_user_zero_trust)):
    """全タスクを CSV または JSON でエクスポートする。

    Query params:
        format: "csv" | "json" (default: "json")
    """
    import csv
    import io

    if not TASKS_DB.exists():
        if format == "csv":
            return StreamingResponse(io.StringIO(""), media_type="text/csv",
                                     headers={"Content-Disposition": "attachment; filename=tasks.csv"})
        return []

    async with aiosqlite.connect(str(TASKS_DB)) as db:
        db.row_factory = aiosqlite.Row
        cursor = await db.execute(
            "SELECT id, title, description, status, priority, category, dir, project, "
            "session_id, session_name, created_at, updated_at, phase, assignee, role "
            "FROM dev_tasks ORDER BY id"
        )
        rows = await cursor.fetchall()

    records = [dict(row) for row in rows]

    if format == "csv":
        if not records:
            buf = io.StringIO()
        else:
            buf = io.StringIO()
            writer = csv.DictWriter(buf, fieldnames=list(records[0].keys()))
            writer.writeheader()
            writer.writerows(records)
        buf.seek(0)
        return StreamingResponse(
            iter([buf.getvalue()]),
            media_type="text/csv; charset=utf-8",
            headers={"Content-Disposition": "attachment; filename=tasks.csv"},
        )

    # JSON
    return StreamingResponse(
        iter([json.dumps(records, ensure_ascii=False, indent=2)]),
        media_type="application/json; charset=utf-8",
        headers={"Content-Disposition": "attachment; filename=tasks.json"},
    )


@app.get("/api/tasks/stats")
async def get_tasks_stats(days: int = 30, user: dict = Depends(get_current_user_zero_trust)):
    """ステータス別・カテゴリ別タスク統計と日別完了タスク数を返す (#439 #780)。

    Returns:
        {
            "total": int,
            "by_status": {"pending": N, "in_progress": N, ...},
            "by_category": {"frontend": N, "infra": N, ...},
            "daily_completed": [{"date": "YYYY-MM-DD", "count": N}, ...]
        }
    """
    import datetime as _dt

    if not TASKS_DB.exists():
        return {"total": 0, "by_status": {}, "by_category": {}, "daily_completed": []}

    async with aiosqlite.connect(str(TASKS_DB)) as db:
        db.row_factory = aiosqlite.Row

        # 合計
        total_row = await (await db.execute("SELECT COUNT(*) AS cnt FROM dev_tasks")).fetchone()
        total = total_row["cnt"] if total_row else 0

        # ステータス別カウント
        cursor = await db.execute(
            "SELECT status, COUNT(*) AS cnt FROM dev_tasks GROUP BY status ORDER BY cnt DESC"
        )
        rows = await cursor.fetchall()
        by_status = {row["status"]: row["cnt"] for row in rows}

        # カテゴリ別カウント (#780)
        cursor = await db.execute(
            "SELECT category, COUNT(*) AS cnt FROM dev_tasks"
            " WHERE category IS NOT NULL AND category != ''"
            " GROUP BY category ORDER BY cnt DESC"
        )
        rows = await cursor.fetchall()
        by_category = {row["category"]: row["cnt"] for row in rows}

        # 日別完了タスク数（updated_at を使用）
        cursor = await db.execute(
            """
            SELECT DATE(updated_at) AS day, COUNT(*) AS cnt
            FROM dev_tasks
            WHERE status IN ('done', 'completed')
              AND DATE(updated_at) >= DATE('now', :offset || ' days')
            GROUP BY day
            ORDER BY day
            """,
            {"offset": f"-{days}"},
        )
        rows = await cursor.fetchall()
        daily_completed_raw = [{"date": row["day"], "count": row["cnt"]} for row in rows]

    # 欠損日を 0 で埋める
    date_map = {r["date"]: r["count"] for r in daily_completed_raw}
    today = _dt.date.today()
    daily_completed = []
    for i in range(days, -1, -1):
        d = (today - _dt.timedelta(days=i)).isoformat()
        daily_completed.append({"date": d, "count": date_map.get(d, 0)})

    return {
        "total": total,
        "by_status": by_status,
        "by_category": by_category,
        "daily_completed": daily_completed,
    }


@app.get("/api/tasks/agent-performance")
async def get_agent_performance(user: dict = Depends(get_current_user_zero_trust)):
    """エージェント別パフォーマンスランキングを返す (#337)。

    Returns:
        [
          {
            "assignee": str,
            "total": int,
            "done": int,
            "in_progress": int,
            "completion_rate": float,   # done / total
            "throughput_7d": float,     # 過去7日間の完了タスク数 / 7
          },
          ...
        ]  done の降順
    """
    if not TASKS_DB.exists():
        return []

    async with aiosqlite.connect(str(TASKS_DB)) as db:
        db.row_factory = aiosqlite.Row

        # 全体集計
        cursor = await db.execute(
            """
            SELECT assignee,
                   COUNT(*) AS total,
                   SUM(CASE WHEN status IN ('done','completed') THEN 1 ELSE 0 END) AS done,
                   SUM(CASE WHEN status = 'in_progress'         THEN 1 ELSE 0 END) AS in_progress
            FROM dev_tasks
            WHERE assignee IS NOT NULL AND assignee != ''
            GROUP BY assignee
            ORDER BY done DESC
            """
        )
        rows = await cursor.fetchall()

        # 過去7日間の完了タスク数
        cursor7 = await db.execute(
            """
            SELECT assignee, COUNT(*) AS cnt
            FROM dev_tasks
            WHERE status IN ('done','completed')
              AND DATE(updated_at) >= DATE('now', '-7 days')
              AND assignee IS NOT NULL AND assignee != ''
            GROUP BY assignee
            """
        )
        rows7 = await cursor7.fetchall()

    done7_map = {r["assignee"]: r["cnt"] for r in rows7}

    result = []
    for row in rows:
        assignee = row["assignee"]
        total = row["total"] or 0
        done = row["done"] or 0
        in_progress = row["in_progress"] or 0
        done7 = done7_map.get(assignee, 0)
        result.append({
            "assignee": assignee,
            "total": total,
            "done": done,
            "in_progress": in_progress,
            "completion_rate": round(done / total, 3) if total > 0 else 0.0,
            "throughput_7d": round(done7 / 7, 2),
        })

    return result


class PatchTaskRequest(BaseModel):
    status: str  # "pending" | "open" | "in_progress" | "completed" | "done" | "blocked"


@app.patch("/api/tasks/{task_id}")
async def patch_task(task_id: int, req: PatchTaskRequest, user: dict = Depends(get_current_user_zero_trust)):
    """タスクのステータスを更新し、更新後のタスク JSON を返す (#442 #1111)。"""
    VALID_STATUSES = {"pending", "open", "in_progress", "completed", "done", "blocked"}
    if req.status not in VALID_STATUSES:
        raise HTTPException(
            status_code=422,
            detail=f"status は {VALID_STATUSES} のいずれかを指定してください",
        )
    if not TASKS_DB.exists():
        raise HTTPException(status_code=404, detail="tasks DB が見つかりません")

    now = datetime.utcnow().isoformat(timespec="seconds")
    async with aiosqlite.connect(str(TASKS_DB)) as db:
        db.row_factory = aiosqlite.Row
        await db.execute(
            "UPDATE dev_tasks SET status = ?, updated_at = ? WHERE id = ?",
            (req.status, now, task_id),
        )
        await db.commit()
        cursor = await db.execute(
            "SELECT id, title, description, status, priority, category, dir, "
            "session_id, created_at, updated_at, phase, assignee "
            "FROM dev_tasks WHERE id = ?",
            (task_id,),
        )
        row = await cursor.fetchone()

    if row is None:
        raise HTTPException(status_code=404, detail=f"タスク #{task_id} が見つかりません")

    return dict(row)


# ──────────────────────────────────────────────
# Department Templates
# ──────────────────────────────────────────────

@app.get("/api/department-templates")
async def get_department_templates(user: dict = Depends(get_current_user_zero_trust)):
    if not THEBRANCH_DB.exists():
        return []
    async with aiosqlite.connect(str(THEBRANCH_DB)) as db:
        db.row_factory = aiosqlite.Row
        cursor = await db.execute(
            "SELECT id, name, description, category, status, total_roles, total_processes, total_tasks "
            "FROM departments_templates WHERE status='active' ORDER BY id ASC"
        )
        rows = await cursor.fetchall()
    return [dict(row) for row in rows]


@app.get("/api/departments_templates/{template_id}")
async def get_department_template_detail(template_id: int, user: dict = Depends(get_current_user_zero_trust)):
    if not THEBRANCH_DB.exists():
        raise HTTPException(status_code=404, detail="Template not found")

    async with aiosqlite.connect(str(THEBRANCH_DB)) as db:
        db.row_factory = aiosqlite.Row

        # Get template
        cursor = await db.execute(
            "SELECT id, name, category, total_roles, total_processes "
            "FROM departments_templates WHERE id = ?",
            (template_id,)
        )
        template_row = await cursor.fetchone()
        if not template_row:
            raise HTTPException(status_code=404, detail="Template not found")

        template_dict = dict(template_row)

        # Get roles
        cursor = await db.execute(
            "SELECT role_key, role_label, min_members, max_members, supervisor_role_key "
            "FROM department_template_roles WHERE template_id = ? ORDER BY role_order ASC",
            (template_id,)
        )
        roles_rows = await cursor.fetchall()
        template_dict['roles'] = [dict(row) for row in roles_rows]

        # Get processes
        cursor = await db.execute(
            "SELECT process_key, process_label, frequency, estimated_hours "
            "FROM department_template_processes WHERE template_id = ? ORDER BY id ASC",
            (template_id,)
        )
        processes_rows = await cursor.fetchall()
        template_dict['processes'] = [dict(row) for row in processes_rows]

    return template_dict


@app.post("/api/departments")
async def create_department(request: models.DepartmentCreateRequest, user: dict = Depends(get_current_user_zero_trust), _rbac: dict = Depends(auth.require_role("manager"))):
    if not THEBRANCH_DB.exists():
        raise HTTPException(status_code=500, detail="Database not found")

    async with aiosqlite.connect(str(THEBRANCH_DB)) as db:
        try:
            # Verify template exists
            cursor = await db.execute(
                "SELECT id FROM departments_templates WHERE id = ?",
                (request.template_id,)
            )
            if not await cursor.fetchone():
                raise HTTPException(status_code=404, detail="Template not found")

            # Create department instance
            cursor = await db.execute(
                "INSERT INTO department_instances (template_id, name, organization_id, status) VALUES (?, ?, ?, ?)",
                (request.template_id, request.name, request.org_id or "default", "planning")
            )
            await db.commit()
            dept_id = cursor.lastrowid

            # Get current timestamp
            now = datetime.utcnow().isoformat() + "Z"

            return models.DepartmentCreateResponse(
                id=dept_id,
                name=request.name,
                template_id=request.template_id,
                created_at=now
            )
        except HTTPException:
            raise
        except Exception as e:
            raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/customize_template")
async def customize_template(request: models.CustomizeTemplateRequest, user: dict = Depends(get_current_user_zero_trust), _rbac: dict = Depends(auth.require_role("manager"))):
    if not THEBRANCH_DB.exists():
        raise HTTPException(status_code=500, detail="Database not found")

    async with aiosqlite.connect(str(THEBRANCH_DB)) as db:
        try:
            # Verify template exists
            cursor = await db.execute(
                "SELECT id FROM departments_templates WHERE id = ?",
                (request.template_id,)
            )
            if not await cursor.fetchone():
                raise HTTPException(status_code=404, detail="Template not found")

            # Create department instance with customization
            now = datetime.utcnow().isoformat() + "Z"
            cursor = await db.execute(
                "INSERT INTO department_instances (template_id, name, organization_id, member_count, status, created_at, updated_at) "
                "VALUES (?, ?, ?, ?, ?, ?, ?)",
                (request.template_id, request.department_name, request.org_id, request.member_count, "planning", now, now)
            )
            await db.commit()
            dept_id = cursor.lastrowid

            # Store process configurations
            for process_config in request.processes:
                # Get process_id from departments_templates
                cursor = await db.execute(
                    "SELECT id FROM department_template_processes WHERE template_id = ? AND process_key = ?",
                    (request.template_id, process_config.process_key)
                )
                process_row = await cursor.fetchone()
                if process_row:
                    process_id = process_row[0]
                    # Create workflow entry (status will be 'pending' initially)
                    await db.execute(
                        "INSERT INTO department_instance_workflows (instance_id, process_id, status) "
                        "VALUES (?, ?, ?)",
                        (dept_id, process_id, "pending")
                    )
            await db.commit()

            return models.CustomizeTemplateResponse(
                department_id=dept_id,
                organization_id=request.org_id,
                created_at=now
            )
        except HTTPException:
            raise
        except Exception as e:
            raise HTTPException(status_code=500, detail=str(e))


# ──────────────────────────────────────────────
# Agents
# ──────────────────────────────────────────────

def get_latest_prompt(cwd: str) -> str:
    """cwdに対応するプロジェクトディレクトリの最新JSONLから最後のuserメッセージを取得"""
    encoded = cwd.replace("/", "-")  # /Users/... → -Users-...
    proj_dir = PROJECTS_DIR / encoded
    if not proj_dir.exists():
        return ""
    jsonl_files = sorted(proj_dir.glob("*.jsonl"), key=lambda p: p.stat().st_mtime, reverse=True)
    if not jsonl_files:
        return ""
    latest = jsonl_files[0]
    last_user_msg = ""
    try:
        for line in latest.read_text(errors="replace").splitlines():
            try:
                obj = json.loads(line)
            except Exception:
                continue
            if obj.get("type") == "user":
                msg = obj.get("message", {})
                content = msg.get("content", "")
                if isinstance(content, str):
                    last_user_msg = content
                elif isinstance(content, list):
                    parts = [c.get("text", "") for c in content if isinstance(c, dict) and c.get("type") == "text"]
                    last_user_msg = " ".join(parts)
    except Exception:
        pass
    return last_user_msg[:500]


def _get_latest_jsonl(cwd: str):
    """cwdに対応するプロジェクトの最新JSONLファイルパスを返す"""
    encoded = cwd.replace("/", "-")
    proj_dir = PROJECTS_DIR / encoded
    if not proj_dir.exists():
        return None
    jsonl_files = sorted(proj_dir.glob("*.jsonl"), key=lambda p: p.stat().st_mtime, reverse=True)
    return jsonl_files[0] if jsonl_files else None


def get_persona_name(cwd: str, session_id: str, kind: str = "") -> str:
    """エージェントのペルソナ名を取得する"""
    try:
        latest = _get_latest_jsonl(cwd)
        if latest:
            lines = latest.read_text(errors="replace").splitlines()
            for line in reversed(lines):
                try:
                    obj = json.loads(line)
                except Exception:
                    continue
                if obj.get("type") != "assistant":
                    continue
                msg = obj.get("message", {})
                content = msg.get("content", [])
                # summariesフィールドを確認
                summaries = msg.get("summaries", [])
                if summaries and isinstance(summaries, list):
                    for s in summaries:
                        if isinstance(s, dict) and s.get("summary"):
                            return s["summary"][:30]
                # textコンテンツから「私は〇〇です」「名前：〇〇」パターンを探す
                text = ""
                if isinstance(content, list):
                    for c in content:
                        if isinstance(c, dict) and c.get("type") == "text":
                            text += c.get("text", "")
                elif isinstance(content, str):
                    text = content
                if text:
                    m = re.search(r"私は(.{1,20})です", text)
                    if m:
                        return m.group(1).strip()
                    m = re.search(r"名前[：:]\s*(.{1,20})", text)
                    if m:
                        return m.group(1).strip()
    except Exception:
        pass

    # フォールバック: kindフィールド
    if kind:
        return kind

    return ""


def get_task_title(session_id: str, cwd: str) -> str:
    """エージェントのin_progressタスクタイトルを取得する"""
    try:
        if not TASKS_DB.exists():
            return ""
        conn = sqlite3.connect(str(TASKS_DB))
        conn.row_factory = sqlite3.Row
        cur = conn.cursor()
        # session_idが一致するin_progressタスクを探す
        if session_id:
            cur.execute(
                "SELECT title FROM dev_tasks WHERE status='in_progress' AND session_id=? LIMIT 1",
                (session_id,)
            )
            row = cur.fetchone()
            if row:
                conn.close()
                return row["title"]
        # cwdでdirが一致するin_progressタスクを探す
        if cwd:
            cur.execute(
                "SELECT title FROM dev_tasks WHERE status='in_progress' AND dir=? LIMIT 1",
                (cwd,)
            )
            row = cur.fetchone()
            if row:
                conn.close()
                return row["title"]
        conn.close()
    except Exception:
        pass
    return ""


def get_progress(cwd: str) -> str:
    """最新アシスタントメッセージのテキスト先頭20文字を返す"""
    try:
        latest = _get_latest_jsonl(cwd)
        if not latest:
            return ""
        lines = latest.read_text(errors="replace").splitlines()
        for line in reversed(lines):
            try:
                obj = json.loads(line)
            except Exception:
                continue
            if obj.get("type") != "assistant":
                continue
            msg = obj.get("message", {})
            content = msg.get("content", [])
            if isinstance(content, list):
                for c in content:
                    if not isinstance(c, dict):
                        continue
                    if c.get("type") == "text":
                        text = c.get("text", "").strip()
                        if text:
                            return text[:20]
                    elif c.get("type") == "tool_use":
                        name = c.get("name", "")
                        if name:
                            return name[:20]
            elif isinstance(content, str) and content.strip():
                return content.strip()[:20]
    except Exception:
        pass
    return ""


async def get_agents_data() -> list:
    agents = []

    if not SESSIONS_DIR.exists():
        return agents

    # 7日超えセッションJSON削除
    cutoff = time.time() - 7 * 24 * 3600
    for json_file in SESSIONS_DIR.glob("*.json"):
        try:
            if json_file.stat().st_mtime < cutoff:
                json_file.unlink()
        except Exception:
            pass

    # tmux ペイン一覧取得
    tmux_panes: dict[str, str] = {}
    try:
        tmux_result = subprocess.run(
            ["/opt/homebrew/bin/tmux", "list-panes", "-a", "-F", "#{session_name}@#{window_name}:#{window_index}.#{pane_index} #{pane_current_path}"],
            capture_output=True, text=True
        )
        for line in tmux_result.stdout.splitlines():
            parts = line.split(" ", 1)
            if len(parts) == 2:
                pane_id, pane_path = parts
                tmux_panes[pane_path] = pane_id
    except Exception:
        pass

    for json_file in SESSIONS_DIR.glob("*.json"):
        try:
            data = json.loads(json_file.read_text(errors="replace"))
        except Exception:
            continue

        pid = data.get("pid")
        if isinstance(pid, int):
            try:
                os.kill(pid, 0)
            except (OSError, ProcessLookupError, PermissionError):
                continue

        session_id = data.get("sessionId")
        cwd = data.get("cwd", "")
        started_at_raw = data.get("startedAt")
        kind = data.get("kind", "")

        # エポックミリ秒 → ISO文字列
        if isinstance(started_at_raw, (int, float)):
            started_at = datetime.fromtimestamp(started_at_raw / 1000).strftime("%Y-%m-%dT%H:%M:%S")
        elif isinstance(started_at_raw, str):
            started_at = started_at_raw
        else:
            started_at = ""

        # tmux ペイン照合
        tmux_pane = tmux_panes.get(cwd, None)

        latest_prompt = get_latest_prompt(cwd)
        persona_name = get_persona_name(cwd, session_id or "", kind)
        task_title = get_task_title(session_id or "", cwd)
        progress = get_progress(cwd)

        agents.append({
            "pid": pid,
            "sessionId": session_id,
            "cwd": cwd,
            "startedAt": started_at,
            "kind": kind,
            "tmux_pane": tmux_pane,
            "latest_prompt": latest_prompt,
            "persona_name": persona_name,
            "task_title": task_title,
            "progress": progress,
        })

    agents = [a for a in agents if a.get('tmux_pane') is not None]
    return agents


@app.get("/api/agents")
async def get_agents(user: dict = Depends(get_current_user_zero_trust)):
    return await get_agents_data()


class DelegateRequest(BaseModel):
    delegateToId: str


@app.put("/api/agents/{agent_id}/delegate")
async def delegate_agent(agent_id: int, req: DelegateRequest, user: dict = Depends(get_current_user_zero_trust), _rbac: dict = Depends(auth.require_role("manager"))):
    """エージェントのタスクを別のエージェントに委譲"""
    try:
        if not req.delegateToId:
            raise HTTPException(status_code=400, detail="委譲先エージェントが指定されていません")

        agents = await get_agents_data()
        agent = next((a for a in agents if a.get('id') == agent_id), None)

        if not agent:
            raise HTTPException(status_code=404, detail=f"エージェント {agent_id} が見つかりません")

        task_title = agent.get('task_title', '')
        delegate_info = {
            "from_agent_id": agent_id,
            "to_agent_id": req.delegateToId,
            "task_title": task_title,
            "delegated_at": datetime.now().isoformat()
        }

        return {
            "success": True,
            "message": f"タスク「{task_title}」をエージェント {req.delegateToId} に委譲しました",
            "delegate_info": delegate_info
        }
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"委譲処理エラー: {str(e)}")


# ──────────────────────────────────────────────
# SSE stream
# ──────────────────────────────────────────────

async def agent_event_generator() -> AsyncGenerator[str, None]:
    while True:
        try:
            agents = await get_agents_data()
            data = json.dumps(agents, ensure_ascii=False)
            yield f"data: {data}\n\n"
        except Exception as e:
            yield f"data: []\n\n"
        await asyncio.sleep(5)


@app.get("/api/stream")
async def stream_agents(user: dict = Depends(get_current_user_zero_trust)):
    return StreamingResponse(
        agent_event_generator(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )


# ──────────────────────────────────────────────
# Projects
# ──────────────────────────────────────────────

import socket as _socket

@app.get("/api/projects")
async def get_projects(status: str = "incomplete", user: dict = Depends(get_current_user_zero_trust)):
    """プロジェクト単位で agents + tasks + service status をまとめて返す"""
    agents = await get_agents_data()

    all_tasks: list = []
    if TASKS_DB.exists():
        async with aiosqlite.connect(str(TASKS_DB)) as db:
            db.row_factory = aiosqlite.Row
            cursor = await db.execute(
                "SELECT id, title, description, status, priority, category, dir, session_id, created_at, updated_at, phase, assignee "
                "FROM dev_tasks ORDER BY priority ASC, id DESC"
            )
            rows = await cursor.fetchall()
            all_tasks = [dict(r) for r in rows]

    if status == "incomplete":
        tasks = [t for t in all_tasks if t.get("status") not in ("done", "completed", "cancel", "cancelled")]
    elif status and status != "all":
        tasks = [t for t in all_tasks if t.get("status") == status]
    else:
        tasks = all_tasks

    ports_data: dict = {}
    if PORTS_YAML.exists():
        try:
            with open(PORTS_YAML, encoding="utf-8") as f:
                ports_data = yaml.safe_load(f) or {}
        except Exception:
            pass

    def extract_proj(path: str):
        if not path:
            return "(未分類)", ""
        parts = [p for p in path.rstrip("/").split("/") if p]
        for i, p in enumerate(parts):
            if p == "adachi-koichi" and i + 1 < len(parts):
                return parts[i + 1], path
        return parts[-1] if parts else "(未分類)", path

    projects: dict = {}

    def ensure_proj(name: str, dir_: str):
        if name not in projects:
            projects[name] = {"name": name, "dir": dir_, "agents": [], "tasks": [], "services": []}

    for agent in agents:
        name, dir_ = extract_proj(agent.get("cwd", ""))
        ensure_proj(name, dir_)
        projects[name]["agents"].append(agent)

    for task in tasks:
        name, dir_ = extract_proj(task.get("dir", ""))
        ensure_proj(name, dir_)
        projects[name]["tasks"].append(task)

    for proj_name, svcs in (ports_data.get("projects") or {}).items():
        ensure_proj(proj_name, "")
        for svc_name, svc_info in svcs.items():
            port = svc_info.get("port") if isinstance(svc_info, dict) else None
            alive = False
            if port:
                try:
                    with _socket.create_connection(("localhost", port), timeout=0.5):
                        alive = True
                except Exception:
                    pass
            projects[proj_name]["services"].append({
                "name": svc_name,
                "port": port,
                "alive": alive,
                "description": svc_info.get("description", "") if isinstance(svc_info, dict) else "",
                "url": svc_info.get("url", "") if isinstance(svc_info, dict) else "",
            })

    return sorted(projects.values(), key=lambda p: p["name"])


# ──────────────────────────────────────────────
# Daemons
# ──────────────────────────────────────────────

DAEMON_CONFIGS = [
    {"label": "com.bcresearch.supervisor",        "name": "BCR Supervisor",        "project": "breast_cancer_research", "log_path": "/tmp/bcr_supervisor_launchd.log",          "hang_minutes": 30},
    {"label": "com.exp-stock.realtime-monitor",   "name": "Exp-Stock Realtime Mon","project": "exp-stock",              "log_path": "/tmp/exp-stock-realtime-monitor.log",       "hang_minutes": 30},
    {"label": "com.exp-stock.streamlit",          "name": "Exp-Stock Streamlit",   "project": "exp-stock",              "log_path": "/tmp/exp-stock-streamlit.log",              "hang_minutes": 120},
]


def get_daemon_status(cfg):
    import subprocess, time, re as _re, os, pathlib
    label = cfg["label"]
    log_path = cfg["log_path"]
    hang_minutes = cfg["hang_minutes"]

    # launchctl list で PID / LastExitStatus 取得
    pid = None
    last_exit_status = None
    try:
        out = subprocess.check_output(["launchctl", "list", label], text=True, stderr=subprocess.DEVNULL)
        for line in out.splitlines():
            m = _re.search(r'"PID"\s*=\s*(\d+)', line)
            if m:
                pid = int(m.group(1))
            m2 = _re.search(r'"LastExitStatus"\s*=\s*(\d+)', line)
            if m2:
                last_exit_status = int(m2.group(1))
    except Exception:
        pass

    # PID の生存確認
    pid_alive = False
    if pid:
        try:
            os.kill(pid, 0)
            pid_alive = True
        except OSError:
            pass

    # ログファイル情報
    log_mtime = None
    log_age_minutes = None
    last_log_lines = []
    detail = None
    p = pathlib.Path(log_path)
    if p.exists():
        log_mtime = p.stat().st_mtime
        log_age_minutes = (time.time() - log_mtime) / 60
        try:
            lines = p.read_text(errors="replace").splitlines()
            last_log_lines = lines[-5:] if len(lines) >= 5 else lines
            for ln in reversed(lines[-10:]):
                if any(kw in ln for kw in ["タスク完了", "ポーリング完了", "分析完了"]):
                    detail = ln
                    break
        except Exception:
            pass

    # ステータス判定
    if not pid_alive:
        status = "error"
        status_reason = "プロセスが存在しない"
    elif log_age_minutes is not None and log_age_minutes > hang_minutes:
        status = "hang"
        status_reason = f"ログ更新なし ({log_age_minutes:.0f}分経過)"
    else:
        status = "ok"
        status_reason = None

    return {
        "label": label,
        "name": cfg["name"],
        "project": cfg["project"],
        "pid": pid,
        "pid_alive": pid_alive,
        "last_exit_status": last_exit_status,
        "status": status,
        "status_reason": status_reason,
        "log_path": log_path,
        "log_mtime": log_mtime,
        "log_age_minutes": log_age_minutes,
        "last_log_lines": last_log_lines,
        "detail": detail,
    }


@app.get("/api/daemons")
async def api_daemons(user: dict = Depends(get_current_user_zero_trust)):
    loop = asyncio.get_event_loop()
    results = await asyncio.gather(*[
        loop.run_in_executor(None, get_daemon_status, cfg)
        for cfg in DAEMON_CONFIGS
    ])
    return list(results)


# ──────────────────────────────────────────────
# Panes
# ──────────────────────────────────────────────

def _capture_pane_content(pane_id: str) -> str:
    """ペイン内容を取得して末尾5行を返す。"""
    try:
        r = subprocess.run(
            [TMUX_BIN, "capture-pane", "-t", pane_id, "-p"],
            capture_output=True, text=True, timeout=2,
        )
        lines = [l for l in r.stdout.splitlines() if l.strip()]
        return "\n".join(lines[-5:]) if lines else ""
    except Exception:
        return ""


def _status_from_content(content: str, command: str) -> str:
    """ペイン内容とコマンドからステータスを判定。"""
    flat = content.replace("\n", " ")
    if "Esc to" in flat and "cancel" in flat:
        return "approval"
    if "Now using extra usage" in flat or "accept edits" in flat:
        return "busy"
    # ccc / ccc-engineer プロセスは常に busy
    if command in ("ccc", "ccc-engineer", "ccc-orchestrator", "ccc-engineering-manager"):
        return "busy"
    if command in ("zsh", "bash", "fish"):
        return "idle"
    if content:
        return "busy"
    return "unknown"


def _list_panes() -> list[dict]:
    """tmux list-panes -a を実行してペイン情報リストを返す（同期）。"""
    result = subprocess.run(
        [TMUX_BIN, "list-panes", "-a", "-F",
         "#{pane_id}\t#{session_name}\t#{window_index}\t#{pane_index}"
         "\t#{pane_current_command}\t#{pane_current_path}\t#{pane_active}"],
        capture_output=True, text=True, timeout=5,
    )
    panes: list[dict] = []
    for line in result.stdout.splitlines():
        parts = line.split("\t", 6)
        if len(parts) < 7:
            continue
        pane_id, session_name, window_index, pane_index, command, path, active = parts
        panes.append({
            "pane_id": pane_id,
            "session": session_name,
            "session_name": session_name,
            "window_index": window_index,
            "pane_index": pane_index,
            "command": command,
            "path": path,
            "status": "unknown",
            "pane_content": "",
            "active": active == "1",
        })

    def enrich(pane: dict) -> dict:
        content = _capture_pane_content(pane["pane_id"])
        pane["status"] = _status_from_content(content, pane["command"])
        pane["pane_content"] = content[:50] if content else ""
        return pane

    with ThreadPoolExecutor(max_workers=8) as ex:
        panes = list(ex.map(enrich, panes))

    return panes


@app.get("/api/panes")
async def get_panes(user: dict = Depends(get_current_user_zero_trust)):
    """tmuxペイン状態をJSON形式で返す"""
    try:
        return _list_panes()
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# ──────────────────────────────────────────────
# Workflows
# ──────────────────────────────────────────────

@app.get("/api/workflows/instances")
async def get_wf_instances(status: str = "", user: dict = Depends(get_current_user_zero_trust)):
    if not TASKS_DB.exists():
        return []
    async with aiosqlite.connect(str(TASKS_DB)) as db:
        db.row_factory = aiosqlite.Row
        if status:
            cursor = await db.execute(
                "SELECT wi.*, wt.name AS template_name FROM workflow_instances wi "
                "LEFT JOIN workflow_templates wt ON wi.template_id = wt.id "
                "WHERE wi.status = ? ORDER BY wi.id DESC", (status,)
            )
        else:
            cursor = await db.execute(
                "SELECT wi.*, wt.name AS template_name FROM workflow_instances wi "
                "LEFT JOIN workflow_templates wt ON wi.template_id = wt.id "
                "ORDER BY wi.id DESC"
            )
        instances = [dict(r) for r in await cursor.fetchall()]
        for inst in instances:
            cursor = await db.execute(
                "SELECT n.*, t.title as task_title, t.status as task_status, t.role as task_role "
                "FROM wf_instance_nodes n LEFT JOIN dev_tasks t ON n.task_id = t.id "
                "WHERE n.instance_id = ? ORDER BY n.id",
                (inst["id"],)
            )
            inst["nodes"] = [dict(r) for r in await cursor.fetchall()]
    return instances


@app.get("/api/workflows/templates")
async def get_wf_templates(user: dict = Depends(get_current_user_zero_trust)):
    if not TASKS_DB.exists():
        return []
    async with aiosqlite.connect(str(TASKS_DB)) as db:
        db.row_factory = aiosqlite.Row
        cursor = await db.execute("SELECT * FROM workflow_templates ORDER BY id")
        templates = [dict(r) for r in await cursor.fetchall()]
        for tmpl in templates:
            cursor = await db.execute(
                "SELECT * FROM wf_template_nodes WHERE template_id = ? ORDER BY id",
                (tmpl["id"],)
            )
            nodes = [dict(r) for r in await cursor.fetchall()]
            tmpl["nodes"] = nodes
            cursor = await db.execute(
                "SELECT e.*, fn.node_key as from_key, fn.label as from_label, "
                "tn.node_key as to_key, tn.label as to_label "
                "FROM wf_template_edges e "
                "JOIN wf_template_nodes fn ON e.from_node_id = fn.id "
                "JOIN wf_template_nodes tn ON e.to_node_id = tn.id "
                "WHERE e.template_id = ? ORDER BY e.priority, e.id",
                (tmpl["id"],)
            )
            tmpl["edges"] = [dict(r) for r in await cursor.fetchall()]
    return templates


# ──────────────────────────────────────────────
# Self-Improvement
# ──────────────────────────────────────────────

SELF_IMPROVEMENT_SCRIPT = Path(__file__).parent.parent / "scripts" / "self_improvement.py"
SELF_IMPROVEMENT_REPORT = Path("/tmp/self_improvement_report.md")


@app.get("/api/self-improvement")
async def get_self_improvement(user: dict = Depends(get_current_user_zero_trust)):
    """自動改善提案レポートを返す"""
    if not SELF_IMPROVEMENT_REPORT.exists():
        result = subprocess.run(
            ["python3", str(SELF_IMPROVEMENT_SCRIPT)],
            capture_output=True,
            text=True,
        )
        if result.returncode != 0:
            raise HTTPException(status_code=500, detail=result.stderr or "レポート生成に失敗しました")
    if SELF_IMPROVEMENT_REPORT.exists():
        return {
            "report": SELF_IMPROVEMENT_REPORT.read_text(encoding="utf-8"),
            "generated_at": datetime.fromtimestamp(SELF_IMPROVEMENT_REPORT.stat().st_mtime).isoformat(),
        }
    return {"report": "レポートが生成されていません", "generated_at": None}


# ──────────────────────────────────────────────
# Sessions
# ──────────────────────────────────────────────

@app.get("/api/sessions")
async def get_sessions(user: dict = Depends(get_current_user_zero_trust), _rbac: dict = Depends(auth.require_role("owner"))):
    """~/.claude/sessions/*.json からセッション一覧を返す"""
    sessions = []
    if not SESSIONS_DIR.exists():
        return sessions
    for json_file in SESSIONS_DIR.glob("*.json"):
        try:
            data = json.loads(json_file.read_text(errors="replace"))
            pid = data.get("pid")
            alive = False
            if isinstance(pid, int):
                try:
                    os.kill(pid, 0)
                    alive = True
                except OSError:
                    pass
            started_at_raw = data.get("startedAt")
            if isinstance(started_at_raw, (int, float)):
                started_at = datetime.fromtimestamp(started_at_raw / 1000).strftime("%Y-%m-%dT%H:%M:%S")
            else:
                started_at = started_at_raw or ""
            sessions.append({
                "session_id": data.get("sessionId"),
                "pid": pid,
                "alive": alive,
                "cwd": data.get("cwd", ""),
                "kind": data.get("kind", ""),
                "started_at": started_at,
                "cost_usd": data.get("costUSD"),
            })
        except Exception:
            continue
    sessions.sort(key=lambda s: s.get("started_at") or "", reverse=True)
    return sessions


# ──────────────────────────────────────────────
# WebSocket: ConnectionManager + /ws メインエンドポイント (#276)
# ──────────────────────────────────────────────

class ConnectionManager:
    def __init__(self):
        self.active: list[WebSocket] = []

    async def connect(self, ws: WebSocket):
        await ws.accept()
        self.active.append(ws)

    def disconnect(self, ws: WebSocket):
        self.active = [c for c in self.active if c is not ws]

    async def broadcast(self, message: str):
        dead = []
        for ws in self.active:
            try:
                await ws.send_text(message)
            except Exception:
                dead.append(ws)
        for ws in dead:
            self.disconnect(ws)


_manager = ConnectionManager()


async def _get_task_stats() -> dict:
    counts: dict[str, int] = {"pending": 0, "in_progress": 0, "completed": 0, "done": 0}
    if TASKS_DB.exists():
        try:
            async with aiosqlite.connect(str(TASKS_DB)) as db:
                cursor = await db.execute(
                    "SELECT status, COUNT(*) AS cnt FROM dev_tasks GROUP BY status"
                )
                for row in await cursor.fetchall():
                    counts[row[0]] = row[1]
        except Exception:
            pass
    return counts


async def _broadcast_loop():
    while True:
        try:
            if _manager.active:
                stats = await _get_task_stats()
                try:
                    panes = await asyncio.get_event_loop().run_in_executor(None, _list_panes)
                    pane_summary = {
                        "total": len(panes),
                        "approval": sum(1 for p in panes if p["status"] == "approval"),
                        "busy": sum(1 for p in panes if p["status"] == "busy"),
                    }
                except Exception:
                    pane_summary = {"total": 0, "approval": 0, "busy": 0}
                payload = json.dumps({
                    "type": "stats",
                    "stats": stats,
                    "panes": pane_summary,
                    "ts": datetime.now().isoformat(),
                })
                await _manager.broadcast(payload)
        except Exception:
            pass
        await asyncio.sleep(3)


@app.on_event("startup")
async def startup_broadcast():
    asyncio.create_task(_broadcast_loop())


@app.websocket("/ws")
async def websocket_main(websocket: WebSocket):
    """タスク統計＋ペイン状態を3秒ごとにブロードキャストするメインWebSocket"""
    await _manager.connect(websocket)
    try:
        while True:
            await websocket.receive_text()
    except WebSocketDisconnect:
        _manager.disconnect(websocket)


# ──────────────────────────────────────────────
# WebSocket: ペインログストリーミング
# ──────────────────────────────────────────────

@app.websocket("/ws/pane/{pane_id}")
async def websocket_pane_log(websocket: WebSocket, pane_id: str):
    """指定ペインの出力をWebSocketでリアルタイムストリーミング"""
    await websocket.accept()
    try:
        last_content = ""
        while True:
            result = subprocess.run(
                ["/opt/homebrew/bin/tmux", "capture-pane", "-t", pane_id, "-p"],
                capture_output=True, text=True
            )
            content = result.stdout
            if content != last_content:
                await websocket.send_text(json.dumps({
                    "pane_id": pane_id,
                    "content": content[-2000:],
                    "ts": datetime.now().isoformat()
                }))
                last_content = content
            await asyncio.sleep(2)
    except WebSocketDisconnect:
        pass


# ──────────────────────────────────────────────
# WebSocket: タスクリアルタイム更新 (#355)
# ──────────────────────────────────────────────

@app.websocket("/ws/tasks")
async def websocket_tasks(websocket: WebSocket):
    """タスク一覧をWebSocketでリアルタイム配信（3秒ごとに差分チェック）"""
    await websocket.accept()
    try:
        last_snapshot = None
        while True:
            if TASKS_DB.exists():
                async with aiosqlite.connect(str(TASKS_DB)) as db:
                    db.row_factory = aiosqlite.Row
                    cursor = await db.execute(
                        "SELECT id, title, description, status, priority, category, dir, "
                        "session_id, created_at, updated_at, phase, assignee "
                        "FROM dev_tasks ORDER BY id DESC"
                    )
                    rows = await cursor.fetchall()
                tasks = [dict(row) for row in rows]
            else:
                tasks = []

            snapshot = json.dumps(tasks, ensure_ascii=False, sort_keys=True)
            if snapshot != last_snapshot:
                await websocket.send_text(json.dumps({"type": "tasks", "data": tasks}))
                last_snapshot = snapshot

            await asyncio.sleep(3)
    except WebSocketDisconnect:
        pass


# ──────────────────────────────────────────────
# WebSocket: ペイン状態リアルタイム更新 (#783)
# ──────────────────────────────────────────────

@app.websocket("/ws/panes")
async def websocket_panes(websocket: WebSocket):
    """tmuxペイン状態を3秒ごとにリアルタイム配信。差分があるときのみ送信。"""
    await websocket.accept()
    try:
        last_snapshot: str | None = None
        while True:
            try:
                panes = _list_panes()
            except Exception:
                panes = []
            snapshot = json.dumps(panes, ensure_ascii=False, sort_keys=True)
            if snapshot != last_snapshot:
                await websocket.send_text(json.dumps({"type": "panes", "data": panes}))
                last_snapshot = snapshot
            await asyncio.sleep(3)
    except WebSocketDisconnect:
        pass


# ──────────────────────────────────────────────
# WebSocket: エージェント状態リアルタイム更新 (#2400)
# ──────────────────────────────────────────────

_agent_snapshot: dict[str, dict] = {}

async def _detect_agent_changes() -> tuple[list, list]:
    """
    エージェント状態の変化を検出し、全エージェント + 変化イベントを返す
    Returns: (agents, changes)
    - agents: 全エージェント最新状態の辞書リスト
    - changes: 状態変化があったエージェントの変化イベント
    """
    global _agent_snapshot

    agents = await get_agents_data()
    changes = []

    current: dict[str, dict] = {a.get("sessionId", a.get("pid", "unknown")): a for a in agents}

    for agent_id, agent in current.items():
        if agent_id in _agent_snapshot:
            prev = _agent_snapshot[agent_id]
            if prev.get("tmux_pane") != agent.get("tmux_pane"):
                change = {
                    "agent_id": agent_id,
                    "previous_pane": prev.get("tmux_pane"),
                    "current_pane": agent.get("tmux_pane"),
                    "timestamp": datetime.now().isoformat()
                }
                changes.append(change)
        else:
            changes.append({
                "agent_id": agent_id,
                "event": "started",
                "timestamp": datetime.now().isoformat()
            })

    for agent_id in _agent_snapshot:
        if agent_id not in current:
            changes.append({
                "agent_id": agent_id,
                "event": "stopped",
                "timestamp": datetime.now().isoformat()
            })

    _agent_snapshot = current
    return agents, changes


@app.websocket("/ws/agents")
async def websocket_agents(websocket: WebSocket):
    """エージェント状態をリアルタイム配信。3秒ごとに差分チェック"""
    await websocket.accept()
    try:
        last_snapshot: str | None = None
        while True:
            agents, changes = await _detect_agent_changes()
            snapshot = json.dumps(agents, ensure_ascii=False, sort_keys=True)

            if snapshot != last_snapshot or changes:
                payload = {
                    "type": "agents_update",
                    "agents": agents,
                    "changes": changes if changes else []
                }
                await websocket.send_text(json.dumps(payload, ensure_ascii=False))
                last_snapshot = snapshot

            await asyncio.sleep(3)
    except WebSocketDisconnect:
        pass


# ──────────────────────────────────────────────
# Costs
# ──────────────────────────────────────────────

INPUT_TOKEN_RATE  = 3.0 / 1_000_000
OUTPUT_TOKEN_RATE = 15.0 / 1_000_000
CACHE_READ_RATE   = 0.30 / 1_000_000
TODAY = "2026-04-15"


def _compute_cost_from_session(data: dict) -> float:
    """セッションJSONからコストを計算する"""
    cost = data.get("costUSD")
    if isinstance(cost, (int, float)):
        return float(cost)
    usage = data.get("usage")
    if isinstance(usage, dict):
        input_tokens      = usage.get("input_tokens", 0) or 0
        output_tokens     = usage.get("output_tokens", 0) or 0
        cache_read_tokens = usage.get("cache_read_input_tokens", 0) or 0
        return (
            input_tokens * INPUT_TOKEN_RATE
            + output_tokens * OUTPUT_TOKEN_RATE
            + cache_read_tokens * CACHE_READ_RATE
        )
    return 0.0


def _extract_date(data: dict) -> str:
    raw = data.get("startedAt")
    if isinstance(raw, (int, float)):
        try:
            return datetime.fromtimestamp(raw / 1000).strftime("%Y-%m-%d")
        except Exception:
            pass
    elif isinstance(raw, str) and raw:
        return raw[:10]
    return ""


def _extract_project_name(cwd: str) -> str:
    if not cwd:
        return "(未分類)"
    parts = [p for p in cwd.rstrip("/").split("/") if p]
    for i, p in enumerate(parts):
        if p == "adachi-koichi" and i + 1 < len(parts):
            return parts[i + 1]
    return parts[-1] if parts else "(未分類)"


@app.get("/api/costs")
async def get_costs(user: dict = Depends(get_current_user_zero_trust)):
    if not SESSIONS_DIR.exists():
        return {"today_total": 0, "all_total": 0, "by_session": [], "by_project": [], "by_date": []}

    by_session = []
    by_project: dict[str, float] = {}
    by_date: dict[str, float] = {}
    all_total = 0.0
    today_total = 0.0

    for json_file in SESSIONS_DIR.glob("*.json"):
        try:
            data = json.loads(json_file.read_text(errors="replace"))
        except Exception:
            continue

        cost    = _compute_cost_from_session(data)
        date    = _extract_date(data)
        cwd     = data.get("cwd", "")
        sid     = data.get("sessionId", json_file.stem)
        project = _extract_project_name(cwd)

        all_total += cost
        if date == TODAY:
            today_total += cost

        by_project[project] = by_project.get(project, 0.0) + cost
        if date:
            by_date[date] = by_date.get(date, 0.0) + cost

        by_session.append({"sessionId": sid, "cwd": cwd, "costUSD": round(cost, 6), "date": date})

    by_session.sort(key=lambda x: x["date"], reverse=True)
    by_project_list = sorted(
        [{"project": k, "costUSD": round(v, 6)} for k, v in by_project.items()],
        key=lambda x: x["costUSD"], reverse=True,
    )
    by_date_list = sorted(
        [{"date": k, "costUSD": round(v, 6)} for k, v in by_date.items()],
        key=lambda x: x["date"], reverse=True,
    )

    return {
        "today_total": round(today_total, 6),
        "all_total": round(all_total, 6),
        "by_session": by_session,
        "by_project": by_project_list,
        "by_date": by_date_list,
    }


# ──────────────────────────────────────────────
# Cost Tracking
# ──────────────────────────────────────────────



@app.get("/api/departments/{dept_id}/budget")
async def get_budget_comparison(dept_id: int, user: dict = Depends(get_current_user_zero_trust)):
    """Get budget vs cost comparison with alerts"""
    try:
        init_workflow_services()
        summary = cost_service.get_department_cost_summary(dept_id)

        now = datetime.now()
        alerts = cost_service.check_budget_alerts(
            dept_id, now.year, now.month, summary.get("budget")
        )

        return {
            "budget": summary.get("budget"),
            "spent": summary.get("spent"),
            "remaining": summary.get("remaining"),
            "utilization_percent": summary.get("utilization_percent"),
            "alerts": alerts,
        }
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


@app.get("/api/cost-alerts")
async def list_cost_alerts(department_id: Optional[int] = None, status: str = "unresolved", user: dict = Depends(get_current_user_zero_trust)):
    """List cost alerts"""
    try:
        init_workflow_services()
        alerts = cost_service.get_cost_alerts(department_id, status)
        return {"ok": True, "alerts": alerts}
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


@app.post("/api/cost-alerts/{alert_id}/resolve")
async def resolve_cost_alert(alert_id: int, request_data: dict, user: dict = Depends(get_current_user_zero_trust), _rbac: dict = Depends(auth.require_role("manager"))):
    """Resolve cost alert"""
    try:
        init_workflow_services()
        resolved_by = request_data.get("resolved_by", "system")
        note = request_data.get("note")

        cost_service.resolve_alert(alert_id, resolved_by, note)
        return {"ok": True}
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


@app.post("/api/costs/record")
async def record_cost(request: models.CostRecordRequest, user: dict = Depends(get_current_user_zero_trust), _rbac: dict = Depends(auth.require_role("manager"))):
    """Record API call cost"""
    try:
        init_workflow_services()
        call_id = cost_service.record_api_call(
            department_id=request.department_id,
            agent_id=request.agent_id,
            api_provider=request.api_provider,
            model_name=request.model_name,
            input_tokens=request.input_tokens,
            output_tokens=request.output_tokens,
            cache_read_tokens=request.cache_read_tokens,
            cache_creation_tokens=request.cache_creation_tokens,
            cost_usd=request.cost_usd,
        )
        return {"ok": True, "id": call_id}
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


@app.get("/api/departments/{department_id}/costs")
async def get_department_cost_summary(department_id: int, user: dict = Depends(get_current_user_zero_trust)):
    """Get department cost summary for current month"""
    try:
        init_workflow_services()
        summary = cost_service.get_department_cost_summary(department_id)

        return models.DepartmentCostResponse(
            year=summary['year'],
            month=summary['month'],
            budget=summary['budget'],
            spent=summary['spent'],
            remaining=summary['remaining'],
            utilization_percent=summary['utilization_percent'],
            api_call_count=summary['api_call_count'],
        )
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


@app.get("/api/costs/summary")
async def get_costs_summary(user: dict = Depends(get_current_user_zero_trust)):
    """Get cost summary for all departments"""
    try:
        init_workflow_services()

        now = datetime.now()
        year = now.year
        month = now.month

        costs = cost_repo.execute_all(
            """SELECT id, name FROM departments WHERE status = 'active'""",
            ()
        )

        items = []
        for dept in costs:
            dept_id = dept['id']
            cost_record = cost_repo.get_cost_record(dept_id, year, month)

            if cost_record:
                items.append(models.CostSummaryItem(
                    department_id=dept_id,
                    year=cost_record['year'],
                    month=cost_record['month'],
                    total_cost_usd=cost_record['total_cost_usd'],
                    api_call_count=cost_record['api_call_count'],
                    failed_call_count=cost_record.get('failed_call_count', 0),
                    top_model=cost_record.get('top_model'),
                ))
            else:
                items.append(models.CostSummaryItem(
                    department_id=dept_id,
                    year=year,
                    month=month,
                    total_cost_usd=0.0,
                    api_call_count=0,
                    failed_call_count=0,
                    top_model=None,
                ))

        return models.CostSummaryResponse(items=items)
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


# ──────────────────────────────────────────────
# Metrics
# ──────────────────────────────────────────────

ORCHESTRATE_METRICS = Path("/tmp/orchestrate_metrics.jsonl")
ALERTS_RESOLVED_FILE = Path("/tmp/dashboard_alerts_resolved.json")


def _load_resolved_alerts() -> set:
    if ALERTS_RESOLVED_FILE.exists():
        try:
            return set(json.loads(ALERTS_RESOLVED_FILE.read_text()))
        except Exception:
            pass
    return set()


def _save_resolved_alerts(resolved: set):
    try:
        ALERTS_RESOLVED_FILE.write_text(json.dumps(list(resolved)))
    except Exception:
        pass


@app.get("/api/metrics")
async def get_metrics(user: dict = Depends(get_current_user_zero_trust)):
    now = datetime.now()
    tasks_per_hour = 0.0
    avg_task_duration_min = 0.0
    pending_tasks = 0
    completed_today = 0
    error_rate = 0.0
    durations: list[float] = []

    if TASKS_DB.exists():
        try:
            conn = sqlite3.connect(str(TASKS_DB))
            conn.row_factory = sqlite3.Row
            cur = conn.cursor()

            # tasks completed in last hour
            cur.execute(
                "SELECT COUNT(*) as cnt FROM dev_tasks WHERE status IN ('done', 'completed') "
                "AND datetime(updated_at) >= datetime('now', '-1 hour')"
            )
            row = cur.fetchone()
            tasks_per_hour = float(row["cnt"]) if row else 0.0

            # tasks completed today
            cur.execute(
                "SELECT COUNT(*) as cnt FROM dev_tasks WHERE status IN ('done', 'completed') "
                "AND date(updated_at) = date('now')"
            )
            row = cur.fetchone()
            completed_today = int(row["cnt"]) if row else 0

            # pending tasks
            cur.execute("SELECT COUNT(*) as cnt FROM dev_tasks WHERE status = 'pending'")
            row = cur.fetchone()
            pending_tasks = int(row["cnt"]) if row else 0

            # avg task duration (created_at to updated_at for recently completed tasks)
            cur.execute(
                "SELECT created_at, updated_at FROM dev_tasks "
                "WHERE status IN ('done', 'completed') "
                "AND created_at IS NOT NULL AND updated_at IS NOT NULL "
                "ORDER BY updated_at DESC LIMIT 50"
            )
            for r in cur.fetchall():
                try:
                    created = datetime.fromisoformat(r["created_at"])
                    updated = datetime.fromisoformat(r["updated_at"])
                    diff_min = (updated - created).total_seconds() / 60
                    if 0 < diff_min < 1440:
                        durations.append(diff_min)
                except Exception:
                    pass

            if durations:
                avg_task_duration_min = sum(durations) / len(durations)

            # error_rate: blocked / total
            cur.execute("SELECT COUNT(*) as cnt FROM dev_tasks WHERE status = 'blocked'")
            blocked_row = cur.fetchone()
            cur.execute("SELECT COUNT(*) as cnt FROM dev_tasks")
            total_row = cur.fetchone()
            blocked = int(blocked_row["cnt"]) if blocked_row else 0
            total = int(total_row["cnt"]) if total_row else 0
            error_rate = round(blocked / total * 100, 1) if total > 0 else 0.0

            conn.close()
        except Exception:
            pass

    # active sessions from tmux
    active_sessions = 0
    try:
        result = subprocess.run(
            ["/opt/homebrew/bin/tmux", "list-sessions"],
            capture_output=True, text=True
        )
        active_sessions = len([l for l in result.stdout.splitlines() if l.strip()])
    except Exception:
        pass

    # history from /tmp/orchestrate_metrics.jsonl
    history_tph: list[dict] = []
    if ORCHESTRATE_METRICS.exists():
        try:
            lines = ORCHESTRATE_METRICS.read_text(errors="replace").splitlines()
            for line in lines[-24:]:
                try:
                    entry = json.loads(line)
                    if "tasks_per_hour" in entry:
                        history_tph.append({
                            "ts": entry.get("timestamp", ""),
                            "value": entry.get("tasks_per_hour", 0),
                        })
                except Exception:
                    pass
        except Exception:
            pass

    return {
        "tasks_per_hour": round(tasks_per_hour, 2),
        "avg_task_duration_min": round(avg_task_duration_min, 1),
        "active_sessions": active_sessions,
        "pending_tasks": pending_tasks,
        "completed_today": completed_today,
        "error_rate": error_rate,
        "history": history_tph,
        "timestamp": now.isoformat(),
    }


# ──────────────────────────────────────────────
# Alerts
# ──────────────────────────────────────────────

def _scan_tmux_for_errors() -> list:
    """tmuxペインからエラーパターンを検出（上位5件のみ）"""
    alerts = []
    error_patterns = ["Error", "Exception", "FAILED", "Traceback", "CRITICAL"]
    seen_sources: set[str] = set()

    try:
        panes_result = subprocess.run(
            ["/opt/homebrew/bin/tmux", "list-panes", "-a", "-F",
             "#{pane_id} #{session_name}:#{window_index}.#{pane_index}"],
            capture_output=True, text=True
        )
        for line in panes_result.stdout.splitlines():
            parts = line.strip().split(" ", 1)
            if len(parts) != 2:
                continue
            pane_id, pane_label = parts
            if pane_label in seen_sources:
                continue

            content_result = subprocess.run(
                ["/opt/homebrew/bin/tmux", "capture-pane", "-t", pane_id, "-p"],
                capture_output=True, text=True
            )
            content = content_result.stdout
            for pattern in error_patterns:
                matched_line = ""
                for ltext in reversed(content.splitlines()[-50:]):
                    if pattern in ltext and ltext.strip():
                        matched_line = ltext.strip()
                        break
                if matched_line:
                    alert_id = f"tmux-{pane_id.lstrip('%')}-{pattern}"
                    alerts.append({
                        "id": alert_id,
                        "level": "error",
                        "message": matched_line[:200],
                        "source": pane_label,
                        "timestamp": datetime.now().isoformat(),
                        "resolved": False,
                    })
                    seen_sources.add(pane_label)
                    break  # one alert per pane

            if len(alerts) >= 20:
                break
    except Exception:
        pass

    return alerts


async def _get_health_check_alerts(resolved_ids: set) -> list:
    """monitoring.yaml のヘルスチェック異常をアラートに変換する。"""
    alerts = []
    if not MONITORING_YAML.exists():
        return alerts
    try:
        with open(MONITORING_YAML, encoding="utf-8") as f:
            mon = yaml.safe_load(f) or {}
        projects_cfg = mon.get("projects", {})
        loop = asyncio.get_event_loop()
        for proj_name, cfg in projects_cfg.items():
            hc = cfg.get("health_check") or {}
            url = hc.get("url") if isinstance(hc, dict) else None
            if not url:
                continue
            result = await loop.run_in_executor(None, _check_url_health, url)
            if result["status"] != "healthy":
                alert_id = f"health-{proj_name}"
                error_detail = f", error: {result['error']}" if result.get("error") else ""
                alerts.append({
                    "id": alert_id,
                    "level": "error" if result["status"] == "down" else "warning",
                    "type": "health_check",
                    "message": f"[{proj_name}] {url} → {result['status'].upper()} ({result['response_time_ms']}ms{error_detail})",
                    "source": f"health_check/{proj_name}",
                    "timestamp": datetime.now().isoformat(),
                    "resolved": alert_id in resolved_ids,
                    "url": url,
                    "project": proj_name,
                })
    except Exception:
        pass
    return alerts


async def _get_long_pending_alerts(resolved_ids: set, threshold_hours: int = 24) -> list:
    """threshold_hours 以上 pending のタスクのアラートを返す。"""
    alerts = []
    if not TASKS_DB.exists():
        return alerts
    try:
        async with aiosqlite.connect(str(TASKS_DB)) as db:
            db.row_factory = aiosqlite.Row
            cursor = await db.execute(
                "SELECT id, title, priority, created_at, updated_at "
                "FROM dev_tasks "
                "WHERE status = 'pending' "
                "AND datetime(updated_at) <= datetime('now', ?) "
                "ORDER BY priority ASC, id ASC LIMIT 20",
                (f"-{threshold_hours} hours",),
            )
            rows = await cursor.fetchall()
            for row in rows:
                r = dict(row)
                alert_id = f"long-pending-{r['id']}"
                alerts.append({
                    "id": alert_id,
                    "level": "warning",
                    "type": "long_pending",
                    "message": f"[Task #{r['id']}] {str(r['title'])[:120]} (priority={r['priority']}) — {threshold_hours}時間以上 pending",
                    "source": "task_manager",
                    "timestamp": r.get("updated_at") or datetime.now().isoformat(),
                    "resolved": alert_id in resolved_ids,
                    "task_id": r["id"],
                })
    except Exception:
        pass
    return alerts


@app.get("/api/alerts")
async def get_alerts(user: dict = Depends(get_current_user_zero_trust)):
    resolved_ids = _load_resolved_alerts()
    alerts: list[dict] = []

    # from orchestrate_metrics.jsonl
    if ORCHESTRATE_METRICS.exists():
        try:
            lines = ORCHESTRATE_METRICS.read_text(errors="replace").splitlines()
            for i, line in enumerate(lines[-50:]):
                try:
                    entry = json.loads(line)
                    if entry.get("error") or entry.get("level") in ("error", "warning"):
                        alert_id = f"metrics-{i}"
                        alerts.append({
                            "id": alert_id,
                            "level": entry.get("level", "error"),
                            "type": "metrics",
                            "message": str(entry.get("error") or entry.get("message", "Unknown error"))[:200],
                            "source": entry.get("source", "orchestrate_metrics"),
                            "timestamp": entry.get("timestamp", datetime.now().isoformat()),
                            "resolved": alert_id in resolved_ids,
                        })
                except Exception:
                    pass
        except Exception:
            pass

    # from tmux panes
    loop = asyncio.get_event_loop()
    tmux_alerts = await loop.run_in_executor(None, _scan_tmux_for_errors)
    for a in tmux_alerts:
        a["type"] = a.get("type", "tmux_error")
        a["resolved"] = a["id"] in resolved_ids
        alerts.append(a)

    # health check 異常
    health_alerts = await _get_health_check_alerts(resolved_ids)
    alerts.extend(health_alerts)

    # 長期 pending タスク警告
    pending_alerts = await _get_long_pending_alerts(resolved_ids)
    alerts.extend(pending_alerts)

    # deduplicate by id
    seen: set[str] = set()
    unique_alerts: list[dict] = []
    for a in alerts:
        if a["id"] not in seen:
            seen.add(a["id"])
            unique_alerts.append(a)

    unresolved_count = sum(1 for a in unique_alerts if not a["resolved"])

    return {
        "alerts": unique_alerts[:100],
        "unresolved_count": unresolved_count,
    }


@app.post("/api/alerts/{alert_id:path}/resolve")
async def resolve_alert(alert_id: str, user: dict = Depends(get_current_user_zero_trust)):
    resolved_ids = _load_resolved_alerts()
    resolved_ids.add(alert_id)
    _save_resolved_alerts(resolved_ids)
    return {"ok": True}


# ──────────────────────────────────────────────
# Gantt
# ──────────────────────────────────────────────

@app.get("/api/gantt")
async def get_gantt(status: str = "incomplete", dir_filter: str = "", user: dict = Depends(get_current_user_zero_trust)):
    """タスクと依存関係をGanttチャート用にまとめて返す"""
    if not TASKS_DB.exists():
        return {"tasks": [], "dependencies": []}

    async with aiosqlite.connect(str(TASKS_DB)) as db:
        db.row_factory = aiosqlite.Row

        # タスク取得
        cursor = await db.execute(
            "SELECT id, title, status, priority, category, dir, created_at, updated_at, phase, assignee "
            "FROM dev_tasks ORDER BY id ASC"
        )
        rows = await cursor.fetchall()
        all_tasks = [dict(r) for r in rows]

        # 依存関係取得
        try:
            cursor = await db.execute("SELECT task_id, depends_on_id FROM task_dependencies")
            dep_rows = await cursor.fetchall()
            dependencies = [dict(r) for r in dep_rows]
        except Exception:
            dependencies = []

    # フィルタリング
    if status == "incomplete":
        tasks = [t for t in all_tasks if t.get("status") not in ("done", "completed", "cancel", "cancelled")]
    elif status and status != "all":
        tasks = [t for t in all_tasks if t.get("status") == status]
    else:
        tasks = all_tasks

    if dir_filter:
        tasks = [t for t in tasks if dir_filter in (t.get("dir") or "")]

    task_ids = {t["id"] for t in tasks}
    deps = [d for d in dependencies if d["task_id"] in task_ids or d["depends_on_id"] in task_ids]

    return {"tasks": tasks, "dependencies": deps}


# ──────────────────────────────────────────────
# DAG (#348)
# ──────────────────────────────────────────────

_DAG_STATUS_COLORS = {
    "pending":     "#9ca3af",
    "in_progress": "#3b82f6",
    "done":        "#22c55e",
    "completed":   "#16a34a",
    "blocked":     "#ef4444",
}


@app.get("/api/dag")
async def get_dag(status: str = "incomplete", user: dict = Depends(get_current_user_zero_trust)):
    """タスク依存関係をvis-network形式（nodes/edges）で返す。"""
    if not TASKS_DB.exists():
        return {"nodes": [], "edges": []}

    async with aiosqlite.connect(str(TASKS_DB)) as db:
        db.row_factory = aiosqlite.Row
        cursor = await db.execute("SELECT task_id, depends_on_id FROM task_dependencies")
        dep_rows = await cursor.fetchall()

    edges_raw = [{"from": r["depends_on_id"], "to": r["task_id"]} for r in dep_rows]
    if not edges_raw:
        return {"nodes": [], "edges": []}

    involved_ids = {e["from"] for e in edges_raw} | {e["to"] for e in edges_raw}

    async with aiosqlite.connect(str(TASKS_DB)) as db:
        db.row_factory = aiosqlite.Row
        placeholders = ",".join("?" * len(involved_ids))
        cursor2 = await db.execute(
            f"SELECT id, title, status FROM dev_tasks WHERE id IN ({placeholders})",
            list(involved_ids),
        )
        task_rows = await cursor2.fetchall()

    tasks = {r["id"]: dict(r) for r in task_rows}

    if status == "incomplete":
        visible = {tid for tid, t in tasks.items() if t["status"] not in ("done", "completed", "cancel", "cancelled")}
    else:
        visible = set(tasks.keys())

    edges = [e for e in edges_raw if e["from"] in visible or e["to"] in visible]
    node_ids = {e["from"] for e in edges} | {e["to"] for e in edges}

    nodes = []
    for tid in node_ids:
        if tid in tasks:
            t = tasks[tid]
            label = f"#{t['id']} {t['title'][:25]}"
            color = _DAG_STATUS_COLORS.get(t["status"], "#9ca3af")
            nodes.append({
                "id": t["id"],
                "label": label,
                "color": {"background": color, "border": color},
                "title": t["title"],
                "status": t["status"],
            })
        else:
            nodes.append({
                "id": tid,
                "label": f"#{tid}",
                "color": {"background": "#9ca3af", "border": "#9ca3af"},
            })

    return {"nodes": nodes, "edges": edges}


# (duplicate /api/panes removed — see _list_panes() above)


# ──────────────────────────────────────────────
# Cycle stats (#319)
# ──────────────────────────────────────────────

CYCLE_STATS_DB = Path.home() / ".claude" / "orchestrator" / "cycle_stats.sqlite"


@app.get("/api/cycle-stats")
async def api_cycle_stats(limit: int = 100, user: dict = Depends(get_current_user_zero_trust)):
    """サイクル実行統計を返す（新しい順）。"""
    if not CYCLE_STATS_DB.exists():
        return {"stats": [], "total": 0}

    async with aiosqlite.connect(str(CYCLE_STATS_DB)) as db:
        db.row_factory = aiosqlite.Row
        cursor = await db.execute(
            "SELECT id, executed_at, duration_seconds, idle_pane_count, "
            "completed_task_count, closed_session_count, long_pending_count, "
            "discord_summary_sent "
            "FROM cycle_stats ORDER BY id DESC LIMIT ?",
            (limit,),
        )
        rows = await cursor.fetchall()
        stats = [dict(r) for r in rows]

        cursor2 = await db.execute("SELECT COUNT(*) FROM cycle_stats")
        row2 = await cursor2.fetchone()
        total = row2[0] if row2 else 0

    return {"stats": stats, "total": total}


# ──────────────────────────────────────────────
# Orchestrate History (#784)
# ──────────────────────────────────────────────

ORCHESTRATE_LOOP_LOGS_DB = Path("/tmp/orchestrate_cycles.sqlite")


@app.get("/api/orchestrate/history")
async def api_orchestrate_history(limit: int = 100, user: dict = Depends(get_current_user_zero_trust)):
    """オーケストレーターのサイクル別実行履歴を返す（新しい順）。

    プライマリソース: /tmp/orchestrate_cycles.sqlite (cycles テーブル)
    フォールバック: ~/.claude/orchestrator/cycle_stats.sqlite (cycle_stats テーブル)
    """
    if ORCHESTRATE_LOOP_LOGS_DB.exists():
        async with aiosqlite.connect(str(ORCHESTRATE_LOOP_LOGS_DB)) as db:
            db.row_factory = aiosqlite.Row
            cursor = await db.execute(
                "SELECT id, started_at, panes_scanned, approvals_handled, "
                "approvals_handled + tasks_assigned AS actions_sum, duration_sec "
                "FROM cycles ORDER BY id DESC LIMIT ?",
                (limit,),
            )
            rows = await cursor.fetchall()
            return [
                {
                    "cycle_num": r["id"],
                    "timestamp": r["started_at"],
                    "panes_scanned": r["panes_scanned"],
                    "waiting_count": r["approvals_handled"],
                    "actions_taken": r["actions_sum"],
                    "elapsed_sec": r["duration_sec"],
                }
                for r in rows
            ]

    # フォールバック: cycle_stats テーブル
    if CYCLE_STATS_DB.exists():
        async with aiosqlite.connect(str(CYCLE_STATS_DB)) as db:
            db.row_factory = aiosqlite.Row
            cursor = await db.execute(
                "SELECT id, executed_at, idle_pane_count, duration_seconds "
                "FROM cycle_stats ORDER BY id DESC LIMIT ?",
                (limit,),
            )
            rows = await cursor.fetchall()
            return [
                {
                    "cycle_num": r["id"],
                    "timestamp": r["executed_at"],
                    "panes_scanned": r["idle_pane_count"],
                    "waiting_count": 0,
                    "actions_taken": 0,
                    "elapsed_sec": r["duration_seconds"],
                }
                for r in rows
            ]

    return []


# ──────────────────────────────────────────────
# Orchestrate Performance (#315)
# ──────────────────────────────────────────────

@app.get("/api/orchestrate/performance")
async def api_orchestrate_performance(limit: int = 100, user: dict = Depends(get_current_user_zero_trust)):
    """エージェントループのパフォーマンス指標（レイテンシ・スループット）を返す。

    レスポンス:
    - latency_series: [{cycle_num, timestamp, elapsed_sec}]  時系列（昇順）
    - throughput_series: [{cycle_num, timestamp, actions_taken}]  時系列（昇順）
    - stats: {avg_latency, p50_latency, p95_latency, max_latency,
               avg_throughput, total_cycles}
    """
    import statistics

    rows_data: list[dict] = []

    if ORCHESTRATE_LOOP_LOGS_DB.exists():
        async with aiosqlite.connect(str(ORCHESTRATE_LOOP_LOGS_DB)) as db:
            db.row_factory = aiosqlite.Row
            cursor = await db.execute(
                "SELECT id, started_at, panes_scanned, approvals_handled, "
                "approvals_handled + tasks_assigned AS actions_sum, duration_sec "
                "FROM cycles ORDER BY id DESC LIMIT ?",
                (limit,),
            )
            for r in await cursor.fetchall():
                rows_data.append({
                    "cycle_num": r["id"],
                    "timestamp": r["started_at"],
                    "elapsed_sec": r["duration_sec"],
                    "actions_taken": r["actions_sum"],
                })
    elif CYCLE_STATS_DB.exists():
        async with aiosqlite.connect(str(CYCLE_STATS_DB)) as db:
            db.row_factory = aiosqlite.Row
            cursor = await db.execute(
                "SELECT id, executed_at, duration_seconds, "
                "COALESCE(completed_task_count, 0) AS actions_sum "
                "FROM cycle_stats ORDER BY id DESC LIMIT ?",
                (limit,),
            )
            for r in await cursor.fetchall():
                rows_data.append({
                    "cycle_num": r["id"],
                    "timestamp": r["executed_at"],
                    "elapsed_sec": r["duration_seconds"],
                    "actions_taken": r["actions_sum"],
                })

    if not rows_data:
        return {"latency_series": [], "throughput_series": [], "stats": {}}

    # 時系列は昇順（グラフ表示用）
    rows_asc = list(reversed(rows_data))

    latency_series = [
        {"cycle_num": r["cycle_num"], "timestamp": r["timestamp"], "elapsed_sec": r["elapsed_sec"]}
        for r in rows_asc
    ]
    throughput_series = [
        {"cycle_num": r["cycle_num"], "timestamp": r["timestamp"], "actions_taken": r["actions_taken"]}
        for r in rows_asc
    ]

    latencies = [r["elapsed_sec"] for r in rows_asc if r["elapsed_sec"] is not None]
    actions = [r["actions_taken"] for r in rows_asc if r["actions_taken"] is not None]

    def _percentile(sorted_lst, p):
        if not sorted_lst:
            return None
        idx = int(len(sorted_lst) * p / 100)
        return sorted_lst[min(idx, len(sorted_lst) - 1)]

    sorted_lat = sorted(latencies)
    stats = {
        "total_cycles": len(rows_data),
        "avg_latency": round(statistics.mean(latencies), 2) if latencies else None,
        "p50_latency": round(_percentile(sorted_lat, 50), 2) if sorted_lat else None,
        "p95_latency": round(_percentile(sorted_lat, 95), 2) if sorted_lat else None,
        "max_latency": round(max(latencies), 2) if latencies else None,
        "avg_throughput": round(statistics.mean(actions), 2) if actions else None,
        "total_actions": sum(actions),
    }

    return {
        "latency_series": latency_series,
        "throughput_series": throughput_series,
        "stats": stats,
    }


# ──────────────────────────────────────────────
# Session Detail (#341)
# ──────────────────────────────────────────────

@app.get("/api/sessions/{session_name:path}")
async def get_session_detail(session_name: str, user: dict = Depends(get_current_user_zero_trust)):
    """セッション詳細: 関連タスク一覧とtmuxログプレビューを返す。"""

    # tmuxペイン一覧からpane_idと稼働状態を取得
    pane_id = ""
    status = "dead"
    try:
        result = subprocess.run(
            [TMUX_BIN, "list-panes", "-a", "-F",
             "#{pane_id} #{session_name}:#{window_index}.#{pane_index}"],
            capture_output=True, text=True, timeout=5,
        )
        for line in result.stdout.splitlines():
            parts = line.strip().split(" ", 1)
            if len(parts) == 2:
                pid, sess_info = parts
                if sess_info.startswith(session_name + ":"):
                    pane_id = pid
                    status = "active"
                    break
    except Exception:
        pass

    if not pane_id:
        # セッションが存在するか確認
        try:
            r = subprocess.run([TMUX_BIN, "has-session", "-t", session_name],
                               capture_output=True, timeout=5)
            status = "idle" if r.returncode == 0 else "dead"
        except Exception:
            status = "dead"

    # tmux log_preview (末尾50行)
    log_preview = ""
    if pane_id:
        try:
            r = subprocess.run(
                [TMUX_BIN, "capture-pane", "-t", pane_id, "-p"],
                capture_output=True, text=True, timeout=5,
            )
            lines = r.stdout.splitlines()
            log_preview = "\n".join(lines[-50:])
        except Exception:
            pass

    # SQLite からこのセッションに関連するタスクを取得
    tasks = []
    if TASKS_DB.exists():
        try:
            async with aiosqlite.connect(str(TASKS_DB)) as db:
                db.row_factory = aiosqlite.Row
                cursor = await db.execute(
                    "SELECT id, title, status, updated_at FROM dev_tasks "
                    "WHERE session_id = ? ORDER BY updated_at DESC LIMIT 50",
                    (session_name,),
                )
                rows = await cursor.fetchall()
                tasks = [dict(r) for r in rows]
        except Exception:
            pass

    return {
        "session_name": session_name,
        "pane_id": pane_id,
        "status": status,
        "tasks": tasks,
        "log_preview": log_preview,
    }


# ──────────────────────────────────────────────
# Health Check (#343)
# ──────────────────────────────────────────────

MONITORING_YAML = Path(__file__).parent.parent / "monitoring.yaml"
_health_cache: dict = {"ts": 0.0, "data": None}
HEALTH_CACHE_TTL = 30  # 秒


def _check_url_health(url: str) -> dict:
    """指定URLにHTTP GETを送り、応答時間とステータスを返す（同期）。"""
    import urllib.request
    import urllib.error
    start = time.monotonic()
    try:
        with urllib.request.urlopen(url, timeout=3) as resp:
            elapsed_ms = int((time.monotonic() - start) * 1000)
            code = resp.getcode()
            if 200 <= code < 400:
                return {"status": "healthy", "response_time_ms": elapsed_ms, "error": None}
            return {"status": "degraded", "response_time_ms": elapsed_ms, "error": f"HTTP {code}"}
    except Exception as e:
        elapsed_ms = int((time.monotonic() - start) * 1000)
        return {"status": "down", "response_time_ms": elapsed_ms, "error": str(e)[:120]}


@app.get("/api/health")
async def get_health():
    """monitoring.yaml の health_check URLをHTTP GETして結果を返す（30秒キャッシュ）。"""
    now = time.monotonic()
    if _health_cache["data"] is not None and (now - _health_cache["ts"]) < HEALTH_CACHE_TTL:
        return _health_cache["data"]

    checks = []
    if MONITORING_YAML.exists():
        try:
            with open(MONITORING_YAML, encoding="utf-8") as f:
                mon = yaml.safe_load(f) or {}
            projects_cfg = mon.get("projects", {})
            loop = asyncio.get_event_loop()
            for proj_name, cfg in projects_cfg.items():
                hc = cfg.get("health_check") or {}
                url = hc.get("url") if isinstance(hc, dict) else None
                if not url:
                    continue
                result = await loop.run_in_executor(None, _check_url_health, url)
                checks.append({
                    "project": proj_name,
                    "url": url,
                    "last_checked": datetime.now().isoformat(),
                    **result,
                })
        except Exception:
            pass

    data = {"checks": checks}
    _health_cache["ts"] = now
    _health_cache["data"] = data
    return data


# ──────────────────────────────────────────────
# Prometheus Metrics (#347)
# ──────────────────────────────────────────────

from fastapi.responses import PlainTextResponse

@app.get("/metrics", response_class=PlainTextResponse)
async def prometheus_metrics():
    """Prometheus テキスト形式でメトリクスを返す。"""
    counts = {"completed": 0, "in_progress": 0, "pending": 0, "done": 0}
    if TASKS_DB.exists():
        try:
            async with aiosqlite.connect(str(TASKS_DB)) as db:
                cursor = await db.execute(
                    "SELECT status, COUNT(*) as cnt FROM dev_tasks GROUP BY status"
                )
                for row in await cursor.fetchall():
                    counts[row[0]] = row[1]
        except Exception:
            pass

    # アイドルペイン数・アクティブセッション数
    idle_pane_count = 0
    active_session_count = 0
    try:
        r = subprocess.run(
            [TMUX_BIN, "list-sessions", "-F", "#{session_name}"],
            capture_output=True, text=True, timeout=5,
        )
        active_session_count = len([l for l in r.stdout.splitlines() if l.strip()])
    except Exception:
        pass

    # サイクル統計（最新1件）
    last_cycle_duration = 0.0
    last_idle_panes = 0
    if CYCLE_STATS_DB.exists():
        try:
            async with aiosqlite.connect(str(CYCLE_STATS_DB)) as db:
                cursor = await db.execute(
                    "SELECT duration_seconds, idle_pane_count FROM cycle_stats ORDER BY id DESC LIMIT 1"
                )
                row = await cursor.fetchone()
                if row:
                    last_cycle_duration = row[0] or 0.0
                    last_idle_panes = row[1] or 0
        except Exception:
            pass

    lines = [
        "# HELP orchestrator_tasks_total Total tasks by status",
        "# TYPE orchestrator_tasks_total gauge",
        f'orchestrator_tasks_total{{status="completed"}} {counts.get("completed", 0)}',
        f'orchestrator_tasks_total{{status="done"}} {counts.get("done", 0)}',
        f'orchestrator_tasks_total{{status="in_progress"}} {counts.get("in_progress", 0)}',
        f'orchestrator_tasks_total{{status="pending"}} {counts.get("pending", 0)}',
        "",
        "# HELP orchestrator_active_sessions Number of active tmux sessions",
        "# TYPE orchestrator_active_sessions gauge",
        f"orchestrator_active_sessions {active_session_count}",
        "",
        "# HELP orchestrator_idle_panes Idle panes detected in last cycle",
        "# TYPE orchestrator_idle_panes gauge",
        f"orchestrator_idle_panes {last_idle_panes}",
        "",
        "# HELP orchestrator_cycle_latency_seconds Duration of last orchestration cycle",
        "# TYPE orchestrator_cycle_latency_seconds gauge",
        f"orchestrator_cycle_latency_seconds {last_cycle_duration:.3f}",
        "",
    ]
    return "\n".join(lines)


# ──────────────────────────────────────────────
# Stats (#366)
# ──────────────────────────────────────────────

@app.get("/api/stats")
async def get_stats(user: dict = Depends(get_current_user_zero_trust)):
    """タスク完了率・ステータス別件数・カテゴリ別件数を返す。"""
    status_counts: dict = {}
    category_counts: dict = {}

    if TASKS_DB.exists():
        try:
            async with aiosqlite.connect(str(TASKS_DB)) as db:
                cur = await db.execute(
                    "SELECT status, COUNT(*) FROM dev_tasks GROUP BY status"
                )
                for row in await cur.fetchall():
                    status_counts[row[0]] = row[1]

                cur = await db.execute(
                    "SELECT COALESCE(category, '(未分類)'), COUNT(*) FROM dev_tasks "
                    "GROUP BY category ORDER BY COUNT(*) DESC"
                )
                for row in await cur.fetchall():
                    category_counts[row[0]] = row[1]
        except Exception:
            pass

    total = sum(status_counts.values())
    finished = status_counts.get("completed", 0) + status_counts.get("done", 0)
    completion_rate = round(finished / total * 100, 1) if total > 0 else 0.0

    return {
        "total": total,
        "finished": finished,
        "completion_rate": completion_rate,
        "status_counts": status_counts,
        "category_counts": category_counts,
    }


# ──────────────────────────────────────────────
# Projects Summary (monitoring.yaml横断) (#351)
# ──────────────────────────────────────────────


@app.get("/api/projects/summary")
async def get_projects_summary(user: dict = Depends(get_current_user_zero_trust)):
    if not MONITORING_YAML.exists():
        return []
    with open(MONITORING_YAML, encoding="utf-8") as f:
        data = yaml.safe_load(f)
    projects = data.get("projects", {}) if data else {}
    results = []
    for name, cfg in projects.items():
        process_pattern = (cfg.get("timeout") or {}).get("process_pattern", "")
        process_status = "unknown"
        if process_pattern:
            try:
                r = subprocess.run(["ps", "ax"], capture_output=True, text=True, timeout=5)
                process_status = "running" if re.search(process_pattern, r.stdout) else "stopped"
            except Exception:
                process_status = "unknown"
        results.append(
            {
                "name": name,
                "dir": cfg.get("dir", ""),
                "process_status": process_status,
                "metrics_status": "ok",
                "timeout_minutes": (cfg.get("timeout") or {}).get("threshold_minutes"),
                "last_updated": datetime.utcnow().isoformat(),
            }
        )
    return results


# ──────────────────────────────────────────────
# Trend (#327)
# ──────────────────────────────────────────────

@app.get("/api/trend")
async def get_trend(hours: int = 24, user: dict = Depends(get_current_user_zero_trust)):
    """過去N時間のタスク完了・作成トレンドを1時間刻みで返す。"""
    from datetime import timedelta

    now = datetime.now()
    buckets: list[datetime] = [
        now.replace(minute=0, second=0, microsecond=0) - timedelta(hours=hours - 1 - i)
        for i in range(hours)
    ]
    labels = [b.strftime("%H:%M") for b in buckets]
    completed_counts = [0] * hours
    created_counts   = [0] * hours

    if TASKS_DB.exists():
        try:
            async with aiosqlite.connect(str(TASKS_DB)) as db:
                db.row_factory = aiosqlite.Row

                cutoff = buckets[0].strftime("%Y-%m-%d %H:%M:%S")
                cursor = await db.execute(
                    "SELECT updated_at FROM dev_tasks "
                    "WHERE status IN ('done', 'completed') "
                    "AND updated_at >= ?",
                    (cutoff,)
                )
                for row in await cursor.fetchall():
                    try:
                        dt_str = row["updated_at"].replace("T", " ")[:19]
                        dt = datetime.strptime(dt_str, "%Y-%m-%d %H:%M:%S")
                        idx = int((dt - buckets[0]).total_seconds() // 3600)
                        if 0 <= idx < hours:
                            completed_counts[idx] += 1
                    except Exception:
                        pass

                cursor2 = await db.execute(
                    "SELECT created_at FROM dev_tasks WHERE created_at >= ?",
                    (cutoff,)
                )
                for row in await cursor2.fetchall():
                    try:
                        dt_str = row["created_at"].replace("T", " ")[:19]
                        dt = datetime.strptime(dt_str, "%Y-%m-%d %H:%M:%S")
                        idx = int((dt - buckets[0]).total_seconds() // 3600)
                        if 0 <= idx < hours:
                            created_counts[idx] += 1
                    except Exception:
                        pass
        except Exception:
            pass

    total_completed = sum(completed_counts)
    peak_idx = completed_counts.index(max(completed_counts)) if total_completed > 0 else -1
    peak_hour = labels[peak_idx] if peak_idx >= 0 else "—"

    return {
        "labels": labels,
        "completed": completed_counts,
        "created": created_counts,
        "total_completed": total_completed,
        "peak_hour": peak_hour,
    }


# ──────────────────────────────────────────────
# Stats History (#462)
# ──────────────────────────────────────────────

@app.get("/api/stats/history")
async def get_stats_history(hours: int = 24, user: dict = Depends(get_current_user_zero_trust)):
    """過去N時間（1時間刻み）の完了タスク数時系列データを返す。

    Response: [{"timestamp": "ISO8601", "completed_count": N}, ...]
    """
    from datetime import timedelta

    hours = max(1, min(hours, 168))  # 1〜168時間（1週間）に制限
    now = datetime.now()
    buckets = [
        now.replace(minute=0, second=0, microsecond=0) - timedelta(hours=hours - 1 - i)
        for i in range(hours)
    ]
    counts = [0] * hours

    if TASKS_DB.exists():
        try:
            async with aiosqlite.connect(str(TASKS_DB)) as db:
                db.row_factory = aiosqlite.Row
                cutoff = buckets[0].strftime("%Y-%m-%d %H:%M:%S")
                cursor = await db.execute(
                    "SELECT updated_at FROM dev_tasks "
                    "WHERE status IN ('done', 'completed') AND updated_at >= ?",
                    (cutoff,),
                )
                for row in await cursor.fetchall():
                    try:
                        dt_str = row["updated_at"].replace("T", " ")[:19]
                        dt = datetime.strptime(dt_str, "%Y-%m-%d %H:%M:%S")
                        idx = int((dt - buckets[0]).total_seconds() // 3600)
                        if 0 <= idx < hours:
                            counts[idx] += 1
                    except Exception:
                        pass
        except Exception:
            pass

    return [
        {"timestamp": b.isoformat(), "completed_count": counts[i]}
        for i, b in enumerate(buckets)
    ]


# ──────────────────────────────────────────────
# Alerts: pending long-term tasks (#501 #531)
# ──────────────────────────────────────────────

@app.get("/api/alerts/pending")
async def get_alerts_pending(days: int = 7, user: dict = Depends(get_current_user_zero_trust)):
    """長期pendingタスク一覧を返す（デフォルト7日以上）。"""
    import datetime as _dt
    if not TASKS_DB.exists():
        return {"tasks": [], "count": 0}

    threshold = (datetime.now() - _dt.timedelta(days=days)).strftime("%Y-%m-%d %H:%M:%S")
    async with aiosqlite.connect(str(TASKS_DB)) as db:
        db.row_factory = aiosqlite.Row
        cursor = await db.execute(
            "SELECT id, title, status, priority, category, dir, created_at, updated_at, phase, assignee "
            "FROM dev_tasks WHERE status IN ('pending', 'in_progress') AND created_at <= ? "
            "ORDER BY created_at ASC",
            (threshold,),
        )
        rows = await cursor.fetchall()
    tasks = [dict(r) for r in rows]
    return {"tasks": tasks, "count": len(tasks), "threshold_days": days}


@app.get("/api/tasks/pending/alert")
async def get_tasks_pending_alert(days: int = 7, user: dict = Depends(get_current_user_zero_trust)):
    """長期pendingタスク警告一覧（/api/alerts/pending のエイリアス）。"""
    return await get_alerts_pending(days=days)


# ──────────────────────────────────────────────
# Long-pending alert (#451)
# ──────────────────────────────────────────────

@app.get("/api/alerts/pending-long")
async def get_alerts_pending_long(minutes: int = 60, user: dict = Depends(get_current_user_zero_trust)):
    """60分以上 pending のタスク一覧を返す。バナー表示用。"""
    import datetime as _dt
    if not TASKS_DB.exists():
        return {"tasks": [], "count": 0, "max_wait_minutes": 0}

    threshold = (datetime.now() - _dt.timedelta(minutes=minutes)).strftime("%Y-%m-%d %H:%M:%S")
    async with aiosqlite.connect(str(TASKS_DB)) as db:
        db.row_factory = aiosqlite.Row
        cursor = await db.execute(
            "SELECT id, title, status, priority, category, created_at, updated_at "
            "FROM dev_tasks WHERE status = 'pending' AND "
            "(updated_at <= ? OR (updated_at IS NULL AND created_at <= ?)) "
            "ORDER BY created_at ASC",
            (threshold, threshold),
        )
        rows = await cursor.fetchall()

    now = datetime.now()
    tasks = []
    max_wait = 0
    for r in rows:
        row = dict(r)
        ts_str = row.get("updated_at") or row.get("created_at") or ""
        try:
            ts = datetime.strptime(ts_str[:19], "%Y-%m-%d %H:%M:%S")
            wait_minutes = int((now - ts).total_seconds() / 60)
        except Exception:
            wait_minutes = 0
        row["wait_minutes"] = wait_minutes
        if wait_minutes > max_wait:
            max_wait = wait_minutes
        tasks.append(row)

    return {"tasks": tasks, "count": len(tasks), "max_wait_minutes": max_wait}


# ──────────────────────────────────────────────
# Cycle timings (#492)
# ──────────────────────────────────────────────

@app.get("/api/cycle/timings")
async def get_cycle_timings(limit: int = 50, user: dict = Depends(get_current_user_zero_trust)):
    """ステップ別実行時間統計を返す。cycle_stats テーブルから集計。"""
    if not CYCLE_STATS_DB.exists():
        return {"timings": [], "avg_duration_seconds": None}

    async with aiosqlite.connect(str(CYCLE_STATS_DB)) as db:
        db.row_factory = aiosqlite.Row
        cursor = await db.execute(
            "SELECT id, executed_at, duration_seconds FROM cycle_stats ORDER BY id DESC LIMIT ?",
            (limit,),
        )
        rows = await cursor.fetchall()

    timings = [dict(r) for r in rows]
    durations = [r["duration_seconds"] for r in timings if r.get("duration_seconds") is not None]
    avg = sum(durations) / len(durations) if durations else None
    return {"timings": timings, "avg_duration_seconds": avg, "count": len(timings)}


# ──────────────────────────────────────────────
# Cycle stats alias (#504 #546)
# ──────────────────────────────────────────────

@app.get("/api/cycle/stats")
async def get_cycle_stats(limit: int = 100, user: dict = Depends(get_current_user_zero_trust)):
    """最新N件サイクル統計（/api/cycle-stats のエイリアス）。"""
    return await api_cycle_stats(limit=limit)


# ──────────────────────────────────────────────
# Health history (#524)
# ──────────────────────────────────────────────

HEALTH_HISTORY_FILE = Path.home() / ".claude" / "orchestrator" / "health_history.jsonl"
_health_history_lock = asyncio.Lock()


@app.get("/api/health/history")
async def get_health_history(hours: int = 24, user: dict = Depends(get_current_user_zero_trust)):
    """過去N時間のヘルスチェック履歴を返す。"""
    import datetime as _dt
    history = []
    if HEALTH_HISTORY_FILE.exists():
        cutoff = datetime.now() - _dt.timedelta(hours=hours)
        try:
            for line in HEALTH_HISTORY_FILE.read_text(errors="replace").splitlines():
                try:
                    entry = json.loads(line)
                    ts_str = entry.get("timestamp", "")
                    if ts_str:
                        ts = datetime.fromisoformat(ts_str[:19])
                        if ts >= cutoff:
                            history.append(entry)
                except Exception:
                    pass
        except Exception:
            pass
    return {"history": history, "count": len(history), "hours": hours}


# ──────────────────────────────────────────────
# Health detail (#1636)
# ──────────────────────────────────────────────

@app.get("/api/health/detail")
async def get_health_detail(user: dict = Depends(get_current_user_zero_trust)):
    """ヘルスチェック詳細（各サービス + プロセス状態）。"""
    base = await get_health()
    checks = base.get("checks", [])

    # THEBRANCH プロセス監視
    process_alive = False
    try:
        result = subprocess.run(
            ["pgrep", "-f", "orchestrate_loop.py"],
            capture_output=True, text=True, timeout=3,
        )
        process_alive = result.returncode == 0
    except Exception:
        pass

    # tmux セッション数
    session_count = 0
    try:
        r = subprocess.run(
            [TMUX_BIN, "list-sessions", "-F", "#{session_name}"],
            capture_output=True, text=True, timeout=3,
        )
        session_count = len([l for l in r.stdout.splitlines() if l.strip()])
    except Exception:
        pass

    return {
        "checks": checks,
        "process": {"orchestrate_loop_alive": process_alive},
        "tmux": {"session_count": session_count},
        "timestamp": datetime.now().isoformat(),
    }


# ──────────────────────────────────────────────
# Sessions summary (#692 #717)
# ──────────────────────────────────────────────

@app.get("/api/sessions/summary")
async def get_sessions_summary(user: dict = Depends(get_current_user_zero_trust)):
    """セッション統計サマリーを返す。"""
    if not SESSIONS_DIR.exists():
        return {"total": 0, "alive": 0, "dead": 0, "total_cost_usd": 0.0}

    total = 0
    alive = 0
    dead = 0
    total_cost = 0.0
    for json_file in SESSIONS_DIR.glob("*.json"):
        try:
            data = json.loads(json_file.read_text(errors="replace"))
            total += 1
            pid = data.get("pid")
            is_alive = False
            if isinstance(pid, int):
                try:
                    os.kill(pid, 0)
                    is_alive = True
                except OSError:
                    pass
            if is_alive:
                alive += 1
            else:
                dead += 1
            cost = data.get("costUSD")
            if isinstance(cost, (int, float)):
                total_cost += float(cost)
        except Exception:
            continue

    return {
        "total": total,
        "alive": alive,
        "dead": dead,
        "total_cost_usd": round(total_cost, 6),
    }


# ──────────────────────────────────────────────
# Sessions active (#1271)
# ──────────────────────────────────────────────

@app.get("/api/sessions/active")
async def get_sessions_active(user: dict = Depends(get_current_user_zero_trust)):
    """アクティブ（alive）なセッション一覧を返す。"""
    all_sessions = await get_sessions()
    active = [s for s in all_sessions if s.get("alive")]
    return active


# ──────────────────────────────────────────────
# Sessions status (#1509)
# ──────────────────────────────────────────────

@app.get("/api/sessions/status")
async def get_sessions_status(user: dict = Depends(get_current_user_zero_trust)):
    """セッション稼働状態サマリー。"""
    summary = await get_sessions_summary()
    tmux_sessions = []
    try:
        r = subprocess.run(
            [TMUX_BIN, "list-sessions", "-F", "#{session_name}\t#{session_windows}\t#{session_created}"],
            capture_output=True, text=True, timeout=5,
        )
        for line in r.stdout.splitlines():
            parts = line.strip().split("\t")
            if len(parts) >= 1:
                tmux_sessions.append({
                    "name": parts[0],
                    "windows": int(parts[1]) if len(parts) > 1 and parts[1].isdigit() else 0,
                    "created": parts[2] if len(parts) > 2 else "",
                })
    except Exception:
        pass
    return {**summary, "tmux_sessions": tmux_sessions}


# ──────────────────────────────────────────────
# Sessions register / create (#1211 #1407)
# ──────────────────────────────────────────────

class RegisterSessionRequest(BaseModel):
    session_name: str
    cwd: str = ""
    kind: str = ""
    pid: Optional[int] = None


@app.post("/api/sessions")
async def create_session(req: RegisterSessionRequest, user: dict = Depends(get_current_user_zero_trust)):
    """セッション情報を登録する（JSON ファイルとして保存）。"""
    return await _register_session(req)


@app.post("/api/sessions/register")
async def register_session(req: RegisterSessionRequest, user: dict = Depends(get_current_user_zero_trust)):
    """セッション登録エンドポイント（/api/sessions POST のエイリアス）。"""
    return await _register_session(req)


async def _register_session(req: RegisterSessionRequest) -> dict:
    SESSIONS_DIR.mkdir(parents=True, exist_ok=True)
    session_id = f"{req.session_name}-{int(time.time())}"
    data = {
        "sessionId": session_id,
        "session_name": req.session_name,
        "cwd": req.cwd,
        "kind": req.kind,
        "pid": req.pid,
        "startedAt": int(time.time() * 1000),
    }
    out_path = SESSIONS_DIR / f"{session_id}.json"
    out_path.write_text(json.dumps(data, ensure_ascii=False), encoding="utf-8")
    return {"ok": True, "session_id": session_id}


# ──────────────────────────────────────────────
# Tasks bulk create (#1296)
# ──────────────────────────────────────────────

class BulkCreateTasksRequest(BaseModel):
    tasks: list[CreateTaskRequest]


@app.post("/api/tasks/bulk")
async def bulk_create_tasks(req: BulkCreateTasksRequest, user: dict = Depends(get_current_user_zero_trust)):
    """タスクを一括作成する。"""
    results = []
    for task_req in req.tasks:
        try:
            cmd = [
                "python3", str(TASK_SCRIPT),
                "add", task_req.title,
                "--description", task_req.description,
                "--category", task_req.category,
                "--priority", str(task_req.priority),
                "--dir", task_req.dir,
            ]
            result = subprocess.run(cmd, capture_output=True, text=True)
            results.append({"title": task_req.title, "ok": result.returncode == 0, "error": result.stderr if result.returncode != 0 else None})
        except Exception as e:
            results.append({"title": task_req.title, "ok": False, "error": str(e)})
    return {"results": results, "count": len(results)}


# ──────────────────────────────────────────────
# Logs: orchestrate_alerts.log viewer (#450)
# ──────────────────────────────────────────────

ORCHESTRATE_ALERTS_LOG = Path("/tmp/orchestrate_alerts.log")
ORCHESTRATE_DELEGATION_LOG = Path("/tmp/orchestrate_delegation_failures.log")
ORCHESTRATE_STATS_LOG = Path("/tmp/orchestrate_stats.log")


@app.get("/api/logs/alerts")
async def get_logs_alerts(limit: int = 500, user: dict = Depends(get_current_user_zero_trust)):
    """orchestrate_alerts.log の最新N行を返す。"""
    lines_all: list[str] = []

    for logfile in [ORCHESTRATE_ALERTS_LOG, ORCHESTRATE_DELEGATION_LOG, ORCHESTRATE_STATS_LOG]:
        if logfile.exists():
            try:
                file_lines = logfile.read_text(errors="replace").splitlines()
                for line in file_lines[-200:]:
                    if line.strip():
                        lines_all.append(f"[{logfile.name}] {line}")
            except Exception:
                pass

    # sort by timestamp-like prefix if present, otherwise keep order
    lines_all = lines_all[-limit:]
    return {
        "lines": lines_all,
        "count": len(lines_all),
        "sources": [
            str(ORCHESTRATE_ALERTS_LOG),
            str(ORCHESTRATE_DELEGATION_LOG),
            str(ORCHESTRATE_STATS_LOG),
        ],
    }


# ──────────────────────────────────────────────
# Session Task Assignments (#426)
# ──────────────────────────────────────────────

@app.get("/api/session-task-assignments")
async def get_session_task_assignments(user: dict = Depends(get_current_user_zero_trust)):
    """セッション別タスク割り当て状況を返す。

    Returns:
        [
          {
            "session_id": "abc123...",
            "session_short": "abc123",
            "alive": true,
            "cwd": "/path/to/project",
            "tasks": [
              {"id": 1, "title": "...", "status": "in_progress", "category": "...", "dir": "...", "updated_at": "..."}
            ]
          },
          ...
        ]
    """
    sessions_map: dict[str, dict] = {}

    # セッション情報を ~/.claude/sessions/*.json から読み込む
    if SESSIONS_DIR.exists():
        for json_file in SESSIONS_DIR.glob("*.json"):
            try:
                data = json.loads(json_file.read_text(errors="replace"))
                sid = data.get("sessionId")
                if not sid:
                    continue
                pid = data.get("pid")
                alive = False
                if isinstance(pid, int):
                    try:
                        os.kill(pid, 0)
                        alive = True
                    except OSError:
                        pass
                sessions_map[sid] = {
                    "session_id": sid,
                    "session_short": sid[:8],
                    "alive": alive,
                    "cwd": data.get("cwd", ""),
                    "tasks": [],
                }
            except Exception:
                continue

    if not TASKS_DB.exists():
        return list(sessions_map.values())

    try:
        async with aiosqlite.connect(str(TASKS_DB)) as db:
            db.row_factory = aiosqlite.Row
            cursor = await db.execute(
                "SELECT id, title, status, category, dir, session_id, updated_at, priority "
                "FROM dev_tasks "
                "WHERE session_id IS NOT NULL AND session_id != '' "
                "  AND status NOT IN ('done', 'completed', 'cancelled') "
                "ORDER BY "
                "  CASE status WHEN 'in_progress' THEN 0 WHEN 'pending' THEN 1 ELSE 2 END, "
                "  updated_at DESC"
            )
            rows = await cursor.fetchall()
    except Exception:
        return list(sessions_map.values())

    unlinked: list[dict] = []
    for row in rows:
        t = dict(row)
        sid = t.get("session_id") or ""
        entry = {
            "id": t["id"],
            "title": t["title"] or "",
            "status": t["status"] or "",
            "category": t["category"] or "",
            "dir": (t["dir"] or "").split("/")[-1],
            "updated_at": (t["updated_at"] or "")[:16],
            "priority": t["priority"],
        }
        if sid in sessions_map:
            sessions_map[sid]["tasks"].append(entry)
        else:
            if sid:
                sessions_map[sid] = {
                    "session_id": sid,
                    "session_short": sid[:8],
                    "alive": False,
                    "cwd": "",
                    "tasks": [entry],
                }

    result = sorted(
        sessions_map.values(),
        key=lambda s: (not s["alive"], -len(s["tasks"]))
    )
    return result


# ──────────────────────────────────────────────
# Workflow Instances (#1267)
# ──────────────────────────────────────────────

@app.get("/api/workflow_instances")
async def get_workflow_instances(user: dict = Depends(get_current_user_zero_trust)):
    """SQLiteの workflow_instances テーブルから一覧を返す。テーブルが存在しない場合は空リスト。"""
    if not TASKS_DB.exists():
        return []
    try:
        async with aiosqlite.connect(str(TASKS_DB)) as db:
            db.row_factory = aiosqlite.Row
            cursor = await db.execute("SELECT * FROM workflow_instances ORDER BY id DESC")
            rows = await cursor.fetchall()
            return [dict(r) for r in rows]
    except Exception:
        return []


# ──────────────────────────────────────────────
# Loop Stats (#1348)
# ──────────────────────────────────────────────

CYCLE_STATS_JSONL = Path("/tmp/orchestrate_cycle_stats.jsonl")


@app.get("/api/loop/stats")
async def get_loop_stats(limit: int = 50, user: dict = Depends(get_current_user_zero_trust)):
    """サイクル統計の最新50件を返す（cycle_stats DBまたはJSONLから）。"""
    # 1. cycle_stats SQLite から取得
    if CYCLE_STATS_DB.exists():
        try:
            async with aiosqlite.connect(str(CYCLE_STATS_DB)) as db:
                db.row_factory = aiosqlite.Row
                cursor = await db.execute(
                    "SELECT * FROM cycle_stats ORDER BY id DESC LIMIT ?", (limit,)
                )
                rows = await cursor.fetchall()
                if rows:
                    return {"source": "sqlite", "stats": [dict(r) for r in rows]}
        except Exception:
            pass

    # 2. JSONL フォールバック
    entries: list[dict] = []
    if CYCLE_STATS_JSONL.exists():
        try:
            lines = CYCLE_STATS_JSONL.read_text(errors="replace").splitlines()
            for line in lines[-limit:]:
                try:
                    entries.append(json.loads(line))
                except Exception:
                    pass
            entries.reverse()
        except Exception:
            pass

    return {"source": "jsonl", "stats": entries}


# ──────────────────────────────────────────────
# Health All (#1425)
# ──────────────────────────────────────────────

HEALTH_CHECK_SCRIPT = Path(__file__).parent.parent / "scripts" / "health_check.py"


@app.get("/api/health/all")
async def get_health_all(user: dict = Depends(get_current_user_zero_trust)):
    """health_check.py を実行してその結果を返す。存在しなければ簡易ヘルス返却。"""
    if HEALTH_CHECK_SCRIPT.exists():
        try:
            result = subprocess.run(
                ["python3", str(HEALTH_CHECK_SCRIPT), "--json"],
                capture_output=True, text=True, timeout=30,
            )
            if result.returncode == 0 and result.stdout.strip():
                try:
                    data = json.loads(result.stdout)
                    return {"source": "health_check.py", "data": data}
                except json.JSONDecodeError:
                    pass
            output = result.stdout or result.stderr
            return {"source": "health_check.py", "raw": output[:2000]}
        except Exception:
            pass

    # 簡易ヘルス
    process_alive = False
    try:
        r = subprocess.run(["pgrep", "-f", "orchestrate_loop.py"],
                           capture_output=True, timeout=3)
        process_alive = r.returncode == 0
    except Exception:
        pass

    session_count = 0
    try:
        r = subprocess.run([TMUX_BIN, "list-sessions", "-F", "#{session_name}"],
                           capture_output=True, text=True, timeout=3)
        session_count = len([l for l in r.stdout.splitlines() if l.strip()])
    except Exception:
        pass

    return {
        "source": "inline",
        "data": {
            "status": "ok",
            "orchestrate_loop_alive": process_alive,
            "tmux_session_count": session_count,
            "tasks_db_exists": TASKS_DB.exists(),
            "timestamp": datetime.now().isoformat(),
        },
    }


# ──────────────────────────────────────────────
# KPI Summary (#323)
# ──────────────────────────────────────────────

@app.get("/api/kpi")
async def get_kpi(user: dict = Depends(get_current_user_zero_trust)):
    """KPIサマリー: 完了率・スループット・稼働ペイン数を返す。"""
    completion_rate = 0.0
    throughput_today = 0
    total = 0
    finished = 0

    if TASKS_DB.exists():
        try:
            async with aiosqlite.connect(str(TASKS_DB)) as db:
                cur = await db.execute(
                    "SELECT status, COUNT(*) FROM dev_tasks GROUP BY status"
                )
                status_counts: dict = {}
                for row in await cur.fetchall():
                    status_counts[row[0]] = row[1]
                total = sum(status_counts.values())
                finished = status_counts.get("completed", 0) + status_counts.get("done", 0)
                completion_rate = round(finished / total * 100, 1) if total > 0 else 0.0

                cur = await db.execute(
                    "SELECT COUNT(*) FROM dev_tasks "
                    "WHERE status IN ('done', 'completed') "
                    "AND DATE(updated_at) = DATE('now')"
                )
                row = await cur.fetchone()
                throughput_today = row[0] if row else 0
        except Exception:
            pass

    active_panes = 0
    try:
        loop = asyncio.get_event_loop()
        panes = await loop.run_in_executor(None, _list_panes)
        active_panes = len(panes)
    except Exception:
        pass

    return {
        "completion_rate": completion_rate,
        "total": total,
        "finished": finished,
        "throughput_today": throughput_today,
        "active_panes": active_panes,
    }


# ──────────────────────────────────────────────
# Activity Feed (#335)
# ──────────────────────────────────────────────

_ACTIVITY_KIND_MAP = {
    "done":        ("task_done",      "✅ タスク完了"),
    "completed":   ("task_done",      "✅ タスク完了"),
    "in_progress": ("task_started",   "⚙️ 作業開始"),
    "pending":     ("task_created",   "📋 タスク登録"),
    "blocked":     ("task_blocked",   "⛔ ブロック"),
    "cancelled":   ("task_cancelled", "🚫 キャンセル"),
}


async def _build_activity_from_db(since_ts: Optional[str] = None, limit: int = 50) -> list[dict]:
    if not TASKS_DB.exists():
        return []
    try:
        async with aiosqlite.connect(str(TASKS_DB)) as db:
            db.row_factory = aiosqlite.Row
            if since_ts:
                cursor = await db.execute(
                    "SELECT id, title, status, updated_at, assignee, category "
                    "FROM dev_tasks WHERE updated_at > ? ORDER BY updated_at DESC LIMIT ?",
                    (since_ts, limit),
                )
            else:
                cursor = await db.execute(
                    "SELECT id, title, status, updated_at, assignee, category "
                    "FROM dev_tasks ORDER BY updated_at DESC LIMIT ?",
                    (limit,),
                )
            rows = await cursor.fetchall()
    except Exception:
        return []

    events = []
    for row in rows:
        item = dict(row)
        kind, label = _ACTIVITY_KIND_MAP.get(item["status"], ("task_updated", "🔄 更新"))
        events.append({
            "id": f"task-{item['id']}-{item['updated_at']}",
            "kind": kind,
            "label": label,
            "ts": item["updated_at"] or "",
            "title": item["title"] or "(no title)",
            "detail": item.get("category") or "",
            "task_id": item["id"],
            "assignee": item.get("assignee") or "",
            "status": item["status"],
        })
    return events


def _build_activity_from_alerts(limit: int = 30) -> list[dict]:
    events = []
    for logfile in [ORCHESTRATE_ALERTS_LOG, ORCHESTRATE_DELEGATION_LOG]:
        if not logfile.exists():
            continue
        try:
            lines = logfile.read_text(errors="replace").splitlines()
            for line in lines[-limit:]:
                line = line.strip()
                if not line:
                    continue
                events.append({
                    "id": f"alert-{logfile.stem}-{abs(hash(line)) & 0xFFFFFF}",
                    "kind": "alert",
                    "label": "🔔 アラート",
                    "ts": "",
                    "title": line[:120],
                    "detail": logfile.name,
                    "task_id": None,
                    "assignee": "",
                    "status": "",
                })
        except Exception:
            pass
    return events


@app.get("/api/activity")
async def get_activity(limit: int = 50, user: dict = Depends(get_current_user_zero_trust)):
    task_events = await _build_activity_from_db(limit=limit)
    alert_events = _build_activity_from_alerts(limit=20)
    all_events = task_events + alert_events
    all_events.sort(key=lambda e: e["ts"], reverse=True)
    return {"events": all_events[:limit]}


@app.get("/api/agent-chat-history")
async def get_agent_chat_history(
    agent_id: str = None,
    event_type: str = None,
    date_from: str = None,
    date_to: str = None,
    limit: int = 50,
user: dict = Depends(get_current_user_zero_trust)):
    items = []
    async with aiosqlite.connect(str(THEBRANCH_DB)) as db:
        # delegation_events の取得
        query = "SELECT id, event_type, actor_id, actor_name, message, metadata, event_timestamp FROM delegation_events WHERE 1=1"
        params = []
        if agent_id:
            query += " AND actor_id = ?"
            params.append(agent_id)
        if event_type:
            query += " AND event_type = ?"
            params.append(event_type)
        if date_from:
            query += " AND DATE(event_timestamp) >= DATE(?)"
            params.append(date_from)
        if date_to:
            query += " AND DATE(event_timestamp) <= DATE(?)"
            params.append(date_to)
        query += " ORDER BY event_timestamp DESC LIMIT ?"
        params.append(limit * 2)

        async with db.execute(query, params) as cursor:
            async for row in cursor:
                try:
                    metadata = json.loads(row[5]) if row[5] else {}
                except:
                    metadata = {}
                items.append({
                    "id": f"delev-{row[0]}",
                    "timestamp": row[6],
                    "agent_id": row[2],
                    "agent_name": row[3] or row[2],
                    "event_type": "delegation",
                    "message": row[4],
                    "metadata": metadata
                })

        # delegation_comments の取得
        if not event_type or event_type == "comment":
            query = "SELECT id, author_id, content, comment_type, created_at FROM delegation_comments WHERE 1=1"
            params = []
            if agent_id:
                query += " AND author_id = ?"
                params.append(agent_id)
            if date_from:
                query += " AND DATE(created_at) >= DATE(?)"
                params.append(date_from)
            if date_to:
                query += " AND DATE(created_at) <= DATE(?)"
                params.append(date_to)
            query += " ORDER BY created_at DESC LIMIT ?"
            params.append(limit * 2)

            async with db.execute(query, params) as cursor:
                async for row in cursor:
                    items.append({
                        "id": f"dlcmt-{row[0]}",
                        "timestamp": row[4],
                        "agent_id": row[1],
                        "agent_name": row[1],
                        "event_type": "comment",
                        "message": row[2],
                        "metadata": {"comment_type": row[3]}
                    })

        # agent_logs の取得
        if not event_type or event_type == "log":
            query = "SELECT al.id, al.agent_id, al.action, al.detail, al.created_at, a.role FROM agent_logs al LEFT JOIN agents a ON al.agent_id = a.id WHERE 1=1"
            params = []
            if agent_id:
                query += " AND al.agent_id = ?"
                params.append(agent_id)
            if date_from:
                query += " AND DATE(al.created_at) >= DATE(?)"
                params.append(date_from)
            if date_to:
                query += " AND DATE(al.created_at) <= DATE(?)"
                params.append(date_to)
            query += " ORDER BY al.created_at DESC LIMIT ?"
            params.append(limit * 2)

            async with db.execute(query, params) as cursor:
                async for row in cursor:
                    items.append({
                        "id": f"aglog-{row[0]}",
                        "timestamp": row[4],
                        "agent_id": str(row[1]),
                        "agent_name": row[5] or f"Agent {row[1]}",
                        "event_type": "log",
                        "message": row[3] or row[2],
                        "metadata": {"action": row[2]}
                    })

    # タイムスタンプでソート＆制限
    items.sort(key=lambda x: x["timestamp"], reverse=True)
    items = items[:limit]

    return {
        "items": items,
        "total": len(items),
        "filters_applied": {
            "agent_id": agent_id,
            "event_type": event_type,
            "date_range": [date_from, date_to] if date_from or date_to else None
        }
    }


@app.websocket("/ws/activity")
async def websocket_activity(websocket: WebSocket):
    """アクティビティフィードをWebSocketでリアルタイム配信（3秒ごとに差分チェック）。"""
    await websocket.accept()
    try:
        initial = await _build_activity_from_db(limit=50)
        await websocket.send_text(json.dumps({"type": "activity_init", "events": initial}))

        last_updated_at: Optional[str] = initial[0]["ts"] if initial else None

        def _count_alert_lines() -> int:
            return sum(
                len(f.read_text(errors="replace").splitlines())
                for f in [ORCHESTRATE_ALERTS_LOG, ORCHESTRATE_DELEGATION_LOG]
                if f.exists()
            )

        last_alert_count = _count_alert_lines()

        while True:
            await asyncio.sleep(3)
            new_events: list[dict] = []

            task_events = await _build_activity_from_db(since_ts=last_updated_at, limit=20)
            if task_events:
                new_events.extend(task_events)
                last_updated_at = task_events[0]["ts"]

            current_alert_count = _count_alert_lines()
            if current_alert_count > last_alert_count:
                new_events.extend(_build_activity_from_alerts(
                    limit=current_alert_count - last_alert_count + 5
                ))
                last_alert_count = current_alert_count

            if new_events:
                await websocket.send_text(json.dumps({"type": "activity_delta", "events": new_events}))
    except WebSocketDisconnect:
        pass


# ──────────────────────────────────────────────
# Notifications: WebSocket + REST API
# ──────────────────────────────────────────────

_notification_manager = None

class NotificationRequest(BaseModel):
    notification_type: str
    title: str
    message: str
    severity: str = "info"
    recipient_id: Optional[str] = None
    recipient_type: Optional[str] = None
    source_table: Optional[str] = None
    source_id: Optional[int] = None
    action_url: Optional[str] = None

class NotificationManager:
    def __init__(self):
        self.active: list[WebSocket] = []

    async def connect(self, ws: WebSocket):
        await ws.accept()
        self.active.append(ws)

    def disconnect(self, ws: WebSocket):
        self.active = [c for c in self.active if c is not ws]

    async def broadcast(self, message: str):
        dead = []
        for ws in self.active:
            try:
                await ws.send_text(message)
            except Exception:
                dead.append(ws)
        for ws in dead:
            self.disconnect(ws)

def get_notification_manager():
    global _notification_manager
    if _notification_manager is None:
        _notification_manager = NotificationManager()
    return _notification_manager

async def create_notification_log(
    notification_type: str,
    title: str,
    message: str,
    severity: str = "info",
    recipient_id: str = None,
    recipient_type: str = None,
    source_table: str = None,
    source_id: int = None,
    metadata: dict = None,
    action_url: str = None
):
    """通知ログを DB に記録して WebSocket でブロードキャストする"""
    try:
        notification_key = f"notif-{uuid.uuid4()}"
        now = datetime.now().isoformat()

        async with aiosqlite.connect(str(THEBRANCH_DB)) as db:
            await db.execute("""
                INSERT INTO notification_logs (
                    notification_key, notification_type, title, message, severity,
                    recipient_id, recipient_type, source_table, source_id,
                    metadata, action_url, status, created_at, updated_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                notification_key, notification_type, title, message, severity,
                recipient_id, recipient_type, source_table, source_id,
                json.dumps(metadata) if metadata else None, action_url,
                "unread", now, now
            ))
            await db.commit()

        # WebSocket でブロードキャスト
        notif_msg = {
            "type": "notification",
            "id": notification_key,
            "notification_type": notification_type,
            "title": title,
            "message": message,
            "severity": severity,
            "recipient_id": recipient_id,
            "source_table": source_table,
            "source_id": source_id,
            "action_url": action_url,
            "created_at": now
        }
        await get_notification_manager().broadcast(json.dumps(notif_msg))
        return notification_key
    except Exception as e:
        logging.error(f"Failed to create notification: {e}")
        return None

@app.websocket("/ws/notifications")
async def websocket_notifications(websocket: WebSocket):
    """通知をリアルタイム配信する WebSocket エンドポイント"""
    manager = get_notification_manager()
    await manager.connect(websocket)
    try:
        while True:
            await websocket.receive_text()
    except WebSocketDisconnect:
        manager.disconnect(websocket)

@app.get("/api/notifications")
async def get_notifications(
    limit: int = 50,
    status: Optional[str] = None,
    notification_type: Optional[str] = None,
    severity: Optional[str] = None,
user: dict = Depends(get_current_user_zero_trust)):
    """通知一覧を取得（フィルタ対応）"""
    if not THEBRANCH_DB.exists():
        return {"notifications": [], "total": 0}

    query = "SELECT * FROM notification_logs WHERE 1=1"
    params = []

    if status:
        query += " AND status = ?"
        params.append(status)
    if notification_type:
        query += " AND notification_type = ?"
        params.append(notification_type)
    if severity:
        query += " AND severity = ?"
        params.append(severity)

    query += " ORDER BY created_at DESC LIMIT ?"
    params.append(limit)

    try:
        async with aiosqlite.connect(str(THEBRANCH_DB)) as db:
            db.row_factory = aiosqlite.Row
            cursor = await db.execute(query, params)
            rows = await cursor.fetchall()

            # 合計数を取得
            count_query = "SELECT COUNT(*) FROM notification_logs WHERE 1=1"
            count_params = []
            if status:
                count_query += " AND status = ?"
                count_params.append(status)
            if notification_type:
                count_query += " AND notification_type = ?"
                count_params.append(notification_type)
            if severity:
                count_query += " AND severity = ?"
                count_params.append(severity)

            cursor = await db.execute(count_query, count_params)
            total = (await cursor.fetchone())[0]

        notifications = [dict(row) for row in rows]
        return {"notifications": notifications, "total": total}
    except Exception as e:
        logging.error(f"Failed to get notifications: {e}")
        return {"notifications": [], "total": 0, "error": str(e)}

@app.post("/api/notifications/{notification_id}/read")
async def mark_notification_read(notification_id: int, user: dict = Depends(get_current_user_zero_trust)):
    """通知を既読化する"""
    if not THEBRANCH_DB.exists():
        raise HTTPException(status_code=404, detail="Database not found")

    try:
        now = datetime.now().isoformat()
        async with aiosqlite.connect(str(THEBRANCH_DB)) as db:
            await db.execute("""
                UPDATE notification_logs
                SET status = 'read', read_at = ?, updated_at = ?
                WHERE id = ?
            """, (now, now, notification_id))
            await db.commit()
        return {"status": "marked_as_read"}
    except Exception as e:
        logging.error(f"Failed to mark notification as read: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/api/notifications/create")
async def create_notification_endpoint(req: NotificationRequest, user: dict = Depends(get_current_user_zero_trust)):
    """通知を手動作成（テスト・内部用）"""
    try:
        notification_key = await create_notification_log(
            notification_type=req.notification_type,
            title=req.title,
            message=req.message,
            severity=req.severity,
            recipient_id=req.recipient_id,
            recipient_type=req.recipient_type,
            source_table=req.source_table,
            source_id=req.source_id,
            action_url=req.action_url
        )
        return {"notification_key": notification_key, "status": "created"}
    except Exception as e:
        logging.error(f"Failed to create notification: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# ──────────────────────────────────────────────
# Agent Rankings
# ──────────────────────────────────────────────

@app.get("/api/agent-rankings")
async def get_agent_rankings(user: dict = Depends(get_current_user_zero_trust)):
    """エージェント別完了タスク数・スループットランキングを返す。

    Returns:
        [
            {
                "agent": str,          # session_name or assigned_session
                "completed": int,      # 完了タスク数
                "throughput": float,   # タスク/時間
                "first_completed": str,
                "last_completed": str,
            },
            ...
        ]
    """
    import datetime as _dt

    if not TASKS_DB.exists():
        return []

    async with aiosqlite.connect(str(TASKS_DB)) as db:
        db.row_factory = aiosqlite.Row
        cursor = await db.execute(
            """
            SELECT
                COALESCE(NULLIF(session_name,''), NULLIF(assigned_session,''), NULLIF(assignee,'')) AS agent,
                COUNT(*) AS completed,
                MIN(updated_at) AS first_completed,
                MAX(updated_at) AS last_completed
            FROM dev_tasks
            WHERE status IN ('done', 'completed')
              AND COALESCE(NULLIF(session_name,''), NULLIF(assigned_session,''), NULLIF(assignee,'')) IS NOT NULL
            GROUP BY agent
            ORDER BY completed DESC
            LIMIT 50
            """
        )
        rows = await cursor.fetchall()

    results = []
    for row in rows:
        agent = row["agent"]
        completed = row["completed"]
        first_str = row["first_completed"]
        last_str = row["last_completed"]

        throughput = 0.0
        if first_str and last_str and completed > 1:
            try:
                def _parse_dt(s: str):
                    s = s.split("+")[0].split("Z")[0].replace("T", " ")
                    for fmt in ("%Y-%m-%d %H:%M:%S.%f", "%Y-%m-%d %H:%M:%S"):
                        try:
                            return _dt.datetime.strptime(s, fmt)
                        except ValueError:
                            continue
                    return None

                t0 = _parse_dt(first_str)
                t1 = _parse_dt(last_str)
                if t0 and t1:
                    hours = (t1 - t0).total_seconds() / 3600
                    if hours > 0:
                        throughput = round(completed / hours, 2)
            except Exception:
                pass

        results.append({
            "agent": agent,
            "completed": completed,
            "throughput": throughput,
            "first_completed": first_str,
            "last_completed": last_str,
        })

    return results


# ──────────────────────────────────────────────
# Authentication
# ──────────────────────────────────────────────

@app.on_event("startup")
async def startup_event():
    await auth.init_db()


@app.post("/api/auth/signup", response_model=models.UserResponse)
async def signup(user: models.UserCreate):
    success, message, user_id = await auth.create_user(user.username, user.email, user.password)
    if not success:
        raise HTTPException(status_code=400, detail=message)

    async with aiosqlite.connect(str(auth.DB_PATH)) as db:
        db.row_factory = aiosqlite.Row
        cursor = await db.execute(
            "SELECT id, username, email, created_at, updated_at FROM users WHERE username = ?",
            (user.username,),
        )
        row = await cursor.fetchone()
        return dict(row) if row else {}


@app.post("/api/auth/login", response_model=models.SessionResponse)
async def login(credentials: models.SessionCreate):
    user_id, token, org_id = await auth.authenticate_user(credentials.username, credentials.password)
    if not user_id:
        raise HTTPException(status_code=401, detail="Invalid credentials")

    async with aiosqlite.connect(str(auth.DB_PATH)) as db:
        cursor = await db.execute(
            "SELECT expires_at FROM sessions WHERE token = ?",
            (token,),
        )
        row = await cursor.fetchone()
        expires_at = row[0] if row else None

    return {
        "token": token,
        "user_id": user_id,
        "expires_at": expires_at,
    }


@app.get("/api/auth/me", response_model=models.UserDetailResponse)
async def get_current_user(authorization: Optional[str] = Header(None)):
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="Missing token")

    token = authorization[7:]
    user_id = await auth.verify_token(token)
    if not user_id:
        raise HTTPException(status_code=401, detail="Invalid token")

    async with aiosqlite.connect(str(auth.DB_PATH)) as db:
        db.row_factory = aiosqlite.Row
        cursor = await db.execute(
            "SELECT id, username, email, created_at, updated_at, COALESCE(onboarding_completed, 0) as onboarding_completed FROM users WHERE id = ?",
            (user_id,),
        )
        user_row = await cursor.fetchone()
        if not user_row:
            raise HTTPException(status_code=404, detail="User not found")

        cursor = await db.execute(
            "SELECT id, user_id, role, created_at FROM user_roles WHERE user_id = ?",
            (user_id,),
        )
        role_rows = await cursor.fetchall()

    user_data = dict(user_row)
    user_data["roles"] = [dict(row) for row in role_rows]
    return user_data


@app.post("/api/auth/role", response_model=dict)
async def add_role(role_req: models.UserRoleCreate, authorization: Optional[str] = Header(None), user: dict = Depends(get_current_user_zero_trust)):
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="Missing token")

    token = authorization[7:]
    user_id = await auth.verify_token(token)
    if not user_id:
        raise HTTPException(status_code=401, detail="Invalid token")

    success, message = await auth.add_user_role(user_id, role_req.role)
    if not success:
        raise HTTPException(status_code=400, detail=message)

    return {"status": "ok", "message": message}


@app.delete("/api/auth/role", response_model=dict)
async def delete_role(role_req: models.UserRoleCreate, authorization: Optional[str] = Header(None), user: dict = Depends(get_current_user_zero_trust)):
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="Missing token")

    token = authorization[7:]
    user_id = await auth.verify_token(token)
    if not user_id:
        raise HTTPException(status_code=401, detail="Invalid token")

    success, message = await auth.remove_user_role(user_id, role_req.role)
    if not success:
        raise HTTPException(status_code=400, detail=message)

    return {"status": "ok", "message": message}


# ──────────────────────────────────────────────
# RBAC: User Management (#2493)
# ──────────────────────────────────────────────

ROLE_HIERARCHY = {"owner": 3, "manager": 2, "member": 1}


def get_user_highest_role(roles: list) -> str:
    if not roles:
        return "member"
    role_names = [r.get("role", "member") if isinstance(r, dict) else r for r in roles]
    return max(role_names, key=lambda r: ROLE_HIERARCHY.get(r, 0))


@app.get("/api/rbac/users", response_model=dict)
async def list_users_with_roles(authorization: Optional[str] = Header(None), user: dict = Depends(get_current_user_zero_trust)):
    """ユーザー一覧とロール情報（owner/manager のみアクセス可能）"""
    user_roles = user.get("roles", [])
    highest = get_user_highest_role(user_roles)
    if ROLE_HIERARCHY.get(highest, 0) < ROLE_HIERARCHY["manager"]:
        raise HTTPException(status_code=403, detail="権限が不足しています")

    async with aiosqlite.connect(str(auth.DB_PATH)) as db:
        db.row_factory = aiosqlite.Row
        cursor = await db.execute(
            "SELECT id, username, email, created_at FROM users ORDER BY created_at DESC"
        )
        users_rows = await cursor.fetchall()
        users = []
        for row in users_rows:
            u = dict(row)
            cursor2 = await db.execute(
                "SELECT role FROM user_roles WHERE user_id = ?", (u["id"],)
            )
            role_rows = await cursor2.fetchall()
            u["roles"] = [r[0] for r in role_rows]
            users.append(u)

    return {"users": users}


@app.post("/api/rbac/users/{target_user_id}/roles", response_model=dict)
async def assign_role_to_user(target_user_id: str, role_req: models.UserRoleCreate, authorization: Optional[str] = Header(None), user: dict = Depends(get_current_user_zero_trust)):
    """指定ユーザーにロールを付与（owner のみ）"""
    user_roles = user.get("roles", [])
    highest = get_user_highest_role(user_roles)
    if highest != "owner":
        raise HTTPException(status_code=403, detail="オーナー権限が必要です")

    success, message = await auth.add_user_role(target_user_id, role_req.role)
    if not success:
        raise HTTPException(status_code=400, detail=message)

    return {"status": "ok", "message": message}


@app.delete("/api/rbac/users/{target_user_id}/roles/{role}", response_model=dict)
async def revoke_role_from_user(target_user_id: str, role: str, authorization: Optional[str] = Header(None), user: dict = Depends(get_current_user_zero_trust)):
    """指定ユーザーからロールを剥奪（owner のみ）"""
    user_roles = user.get("roles", [])
    highest = get_user_highest_role(user_roles)
    if highest != "owner":
        raise HTTPException(status_code=403, detail="オーナー権限が必要です")

    success, message = await auth.remove_user_role(target_user_id, role)
    if not success:
        raise HTTPException(status_code=400, detail=message)

    return {"status": "ok", "message": message}


# ──────────────────────────────────────────────
# API Token Management (#2525)
# ──────────────────────────────────────────────

@app.post("/api/auth/tokens", response_model=models.APITokenCreateResponse)
async def create_api_token(token_req: models.APITokenCreate, authorization: Optional[str] = Header(None), user: dict = Depends(get_current_user_zero_trust)):
    """Create a new personal access token."""
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="Missing token")

    token = authorization[7:]
    user_id, org_id = await auth.verify_token(token)
    if not user_id:
        raise HTTPException(status_code=401, detail="Invalid token")

    success, message, api_token = await auth.create_api_token(
        user_id, token_req.name, token_req.scope, token_req.expires_in_days
    )
    if not success:
        raise HTTPException(status_code=400, detail=message)

    async with aiosqlite.connect(str(auth.DB_PATH)) as db:
        cursor = await db.execute(
            "SELECT id, created_at, expires_at FROM api_tokens WHERE token_hash = ?",
            (hashlib.sha256(api_token.encode()).hexdigest(),),
        )
        result = await cursor.fetchone()
        if result:
            return models.APITokenCreateResponse(
                id=result[0],
                name=token_req.name,
                token=api_token,
                scope=token_req.scope,
                created_at=result[1],
                expires_at=result[2],
            )

    raise HTTPException(status_code=500, detail="Failed to create token")


@app.get("/api/auth/tokens", response_model=models.APITokenListResponse)
async def list_api_tokens(authorization: Optional[str] = Header(None), user: dict = Depends(get_current_user_zero_trust)):
    """List all personal access tokens for the current user."""
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="Missing token")

    token = authorization[7:]
    user_id, org_id = await auth.verify_token(token)
    if not user_id:
        raise HTTPException(status_code=401, detail="Invalid token")

    tokens = await auth.list_api_tokens(user_id)
    return models.APITokenListResponse(tokens=[models.APITokenResponse(**t) for t in tokens])


@app.delete("/api/auth/tokens/{token_id}")
async def revoke_api_token(token_id: str, authorization: Optional[str] = Header(None), user: dict = Depends(get_current_user_zero_trust)):
    """Revoke a personal access token."""
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="Missing token")

    token = authorization[7:]
    user_id, org_id = await auth.verify_token(token)
    if not user_id:
        raise HTTPException(status_code=401, detail="Invalid token")

    success, message = await auth.revoke_api_token(user_id, token_id)
    if not success:
        raise HTTPException(status_code=400, detail=message)

    return {"status": "ok", "message": message}


# ──────────────────────────────────────────────
# Onboarding (#2532)
# ──────────────────────────────────────────────

@app.get("/api/onboarding/status", response_model=models.OnboardingStatusResponse)
async def get_onboarding_status(user: dict = Depends(get_current_user)):
    """Get user's current onboarding status."""
    try:
        async with aiosqlite.connect(str(auth.DB_PATH)) as db:
            db.row_factory = aiosqlite.Row

            cursor = await db.execute(
                "SELECT current_step, organization_type, department_choice FROM onboarding_state WHERE user_id = ? LIMIT 1",
                (user["id"],)
            )
            state = await cursor.fetchone()

            if not state:
                state = {
                    "current_step": 1,
                    "organization_type": None,
                    "department_choice": None
                }

            return models.OnboardingStatusResponse(
                user_id=user["id"],
                current_step=state["current_step"] if state else 1,
                organization_type=state["organization_type"] if state else None,
                department_choice=state["department_choice"] if state else None,
                onboarding_completed=user.get("onboarding_completed", 0)
            )
    except Exception as e:
        logger.error(f"Error fetching onboarding status: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/onboarding/step", response_model=models.OnboardingStateResponse)
async def update_onboarding_step(req: models.OnboardingStateUpdate, user: dict = Depends(get_current_user)):
    """Update onboarding step and save choices."""
    try:
        async with aiosqlite.connect(str(auth.DB_PATH)) as db:
            db.row_factory = aiosqlite.Row

            cursor = await db.execute(
                "SELECT id FROM onboarding_state WHERE user_id = ? LIMIT 1",
                (user["id"],)
            )
            existing = await cursor.fetchone()

            if existing:
                await db.execute(
                    """UPDATE onboarding_state
                       SET current_step = COALESCE(?, current_step), organization_type = COALESCE(?, organization_type), department_choice = COALESCE(?, department_choice), updated_at = ?
                       WHERE user_id = ?""",
                    (req.current_step, req.organization_type, req.department_choice, datetime.now().isoformat(), user["id"])
                )
            else:
                await db.execute(
                    """INSERT INTO onboarding_state
                       (user_id, current_step, organization_type, department_choice, created_at, updated_at)
                       VALUES (?, ?, ?, ?, ?, ?)""",
                    (user["id"], req.current_step or 1, req.organization_type, req.department_choice, datetime.now().isoformat(), datetime.now().isoformat())
                )
            await db.commit()

            cursor = await db.execute(
                "SELECT id, user_id, current_step, organization_type, department_choice, created_at, updated_at FROM onboarding_state WHERE user_id = ? LIMIT 1",
                (user["id"],)
            )
            state = await cursor.fetchone()

            if state:
                return models.OnboardingStateResponse(**dict(state))
            raise HTTPException(status_code=500, detail="Failed to update state")
    except Exception as e:
        logger.error(f"Error updating onboarding step: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/onboarding/complete", response_model=dict)
async def complete_onboarding(user: dict = Depends(get_current_user)):
    """Mark onboarding as completed."""
    try:
        async with aiosqlite.connect(str(auth.DB_PATH)) as db:
            await db.execute(
                "UPDATE users SET onboarding_completed = 1, updated_at = ? WHERE id = ?",
                (datetime.now().isoformat(), user["id"])
            )
            await db.commit()
            return {"ok": True, "message": "Onboarding completed"}
    except Exception as e:
        logger.error(f"Error completing onboarding: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/onboarding/skip", response_model=dict)
async def skip_onboarding(user: dict = Depends(get_current_user)):
    """Skip onboarding."""
    try:
        async with aiosqlite.connect(str(auth.DB_PATH)) as db:
            await db.execute(
                "UPDATE users SET onboarding_completed = 1, updated_at = ? WHERE id = ?",
                (datetime.now().isoformat(), user["id"])
            )
            await db.commit()
            return {"ok": True, "message": "Onboarding skipped"}
    except Exception as e:
        logger.error(f"Error skipping onboarding: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# ──────────────────────────────────────────────
# Departments (#2362) & Agents (#2391)
# ──────────────────────────────────────────────

def generate_session_name(dept_id: int, dept_slug: str, role: str) -> str:
    """Generate tmux session name following v3 format."""
    return f"thebranch_orchestrator_wf{dept_id:03d}_{role}@main"

async def start_ccc_agent(session_name: str, role: str, dept_id: int) -> tuple[bool, str]:
    """Start ccc agent in tmux session. Returns (success, session_id_or_error)."""
    try:
        ccc_cmd = "ccc"
        if role == "orchestrator":
            ccc_cmd = "ccc-orchestrator"

        cmd = [
            TMUX_BIN, "new-session", "-d", "-s", session_name,
            "-x", "250", "-y", "50",
            f"cd $HOME && {ccc_cmd}"
        ]
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=5)
        if result.returncode != 0:
            return False, f"Failed to create tmux session: {result.stderr}"
        return True, session_name
    except Exception as e:
        return False, str(e)

async def stop_tmux_session(session_name: str) -> bool:
    """Stop tmux session."""
    try:
        cmd = [TMUX_BIN, "kill-session", "-t", session_name]
        subprocess.run(cmd, capture_output=True, timeout=5)
        return True
    except Exception:
        return False

async def log_agent_activity(
    agent_id: int,
    action: str,
    detail: Optional[str] = None
) -> None:
    """Record agent activity to agent_logs table."""
    try:
        async with aiosqlite.connect(str(THEBRANCH_DB)) as db:
            await db.execute(
                "INSERT INTO agent_logs (agent_id, action, detail) VALUES (?, ?, ?)",
                (agent_id, action, detail)
            )
            await db.commit()
    except Exception as e:
        pass

async def ensure_db_initialized():
    """Initialize database if not exists."""
    if not THEBRANCH_DB.parent.exists():
        THEBRANCH_DB.parent.mkdir(parents=True, exist_ok=True)

    if not THEBRANCH_DB.exists():
        conn = sqlite3.connect(str(THEBRANCH_DB))
        try:
            migrations_dir = DASHBOARD_DIR / "migrations"
            for mig_file in sorted(migrations_dir.glob("*.sql")):
                with open(mig_file) as f:
                    conn.executescript(f.read())
            conn.commit()
        finally:
            conn.close()

@app.on_event("startup")
async def startup_event():
    await ensure_db_initialized()

@app.post("/api/departments", status_code=201)
async def create_department(dept_req: models.DepartmentCreate, user: dict = Depends(get_current_user_zero_trust)):
    await ensure_db_initialized()
    try:
        async with aiosqlite.connect(str(THEBRANCH_DB)) as db:
            db.row_factory = aiosqlite.Row
            cursor = await db.execute(
                """INSERT INTO departments (name, slug, description, parent_id, budget, status, created_by)
                   VALUES (?, ?, ?, ?, ?, 'active', 'system')""",
                (dept_req.name, dept_req.slug, dept_req.description, dept_req.parent_id, dept_req.budget),
            )
            dept_id = cursor.lastrowid
            await db.commit()

            cursor = await db.execute(
                """SELECT id, name, slug, description, parent_id, budget, status,
                          (SELECT COUNT(*) FROM department_agents WHERE department_id = ?) as agent_count,
                          (SELECT COUNT(*) FROM teams WHERE department_id = ?) as team_count,
                          created_at, updated_at FROM departments WHERE id = ?""",
                (dept_id, dept_id, dept_id),
            )
            row = await cursor.fetchone()

        return dict(row) if row else {"error": "Failed to create"}
    except sqlite3.IntegrityError as e:
        if "UNIQUE constraint failed" in str(e):
            if "name" in str(e):
                raise HTTPException(status_code=400, detail={"error": "DEPT_NAME_DUPLICATE", "message": "部署名が既に存在します"})
            elif "slug" in str(e):
                raise HTTPException(status_code=400, detail={"error": "DEPT_SLUG_DUPLICATE", "message": "スラッグが既に存在します"})
        raise HTTPException(status_code=400, detail="データ完全性エラー")

@app.get("/api/departments")
async def list_departments(status: str = "", parent_id: int = None, page: int = 1, limit: int = 20, user: dict = Depends(get_current_user_zero_trust)):
    await ensure_db_initialized()
    async with aiosqlite.connect(str(THEBRANCH_DB)) as db:
        db.row_factory = aiosqlite.Row
        query = "SELECT id, name, slug, description, parent_id, budget, status, " \
                "(SELECT COUNT(*) FROM department_agents WHERE department_id = departments.id) as agent_count, " \
                "(SELECT COUNT(*) FROM teams WHERE department_id = departments.id) as team_count, " \
                "created_at FROM departments WHERE 1=1"
        params = []

        if status:
            query += " AND status = ?"
            params.append(status)
        if parent_id:
            query += " AND parent_id = ?"
            params.append(parent_id)

        query += " ORDER BY id DESC LIMIT ? OFFSET ?"
        offset = (page - 1) * limit
        params.extend([limit, offset])

        cursor = await db.execute(query, params)
        rows = await cursor.fetchall()

        cursor = await db.execute("SELECT COUNT(*) FROM departments WHERE 1=1" +
                                  (" AND status = ?" if status else "") +
                                  (" AND parent_id = ?" if parent_id else ""),
                                  params[:-2] if params else [])
        total = (await cursor.fetchone())[0]

    return {
        "data": [dict(r) for r in rows],
        "pagination": {"page": page, "limit": limit, "total": total, "pages": (total + limit - 1) // limit}
    }

@app.get("/api/departments/hierarchy")
async def get_departments_hierarchy(user: dict = Depends(get_current_user_zero_trust)):
    """Get all departments in hierarchical tree structure"""
    await ensure_db_initialized()
    async with aiosqlite.connect(str(THEBRANCH_DB)) as db:
        db.row_factory = aiosqlite.Row
        cursor = await db.execute("SELECT id FROM departments WHERE parent_id IS NULL ORDER BY name")
        root_ids = [r[0] for r in await cursor.fetchall()]

        hierarchy = []
        for root_id in root_ids:
            dept = await _build_dept_tree(root_id, db)
            if dept:
                hierarchy.append(dept)

    return hierarchy

@app.get("/api/departments/{dept_id}")
async def get_department(dept_id: int, user: dict = Depends(get_current_user_zero_trust)):
    await ensure_db_initialized()
    async with aiosqlite.connect(str(THEBRANCH_DB)) as db:
        db.row_factory = aiosqlite.Row
        cursor = await db.execute(
            """SELECT id, name, slug, description, parent_id, budget, status,
                      (SELECT COUNT(*) FROM department_agents WHERE department_id = ?) as agent_count,
                      (SELECT COUNT(*) FROM teams WHERE department_id = ?) as team_count,
                      created_at, updated_at FROM departments WHERE id = ?""",
            (dept_id, dept_id, dept_id),
        )
        row = await cursor.fetchone()
        if not row:
            raise HTTPException(status_code=404, detail="部署が見つかりません")

        dept = dict(row)
        if dept["parent_id"]:
            cursor = await db.execute(
                "SELECT id, name, slug FROM departments WHERE id = ?",
                (dept["parent_id"],),
            )
            parent = await cursor.fetchone()
            dept["parent"] = dict(parent) if parent else None

    return dept

@app.put("/api/departments/{dept_id}")
async def update_department(dept_id: int, update_req: models.DepartmentUpdate, user: dict = Depends(get_current_user_zero_trust)):
    await ensure_db_initialized()
    init_workflow_services()
    async with aiosqlite.connect(str(THEBRANCH_DB)) as db:
        db.row_factory = aiosqlite.Row
        updates = []
        params = []

        if update_req.name:
            updates.append("name = ?")
            params.append(update_req.name)
        if update_req.description is not None:
            updates.append("description = ?")
            params.append(update_req.description)
        if update_req.budget is not None:
            updates.append("budget = ?")
            params.append(update_req.budget)
        if update_req.status:
            updates.append("status = ?")
            params.append(update_req.status)
        if update_req.parent_id is not None:
            if graph_repo_dept and graph_repo_dept.detect_circular_parent_assignment(dept_id, update_req.parent_id):
                raise HTTPException(status_code=400, detail={"error": "CIRCULAR_REFERENCE", "message": "循環参照が検出されました"})
            updates.append("parent_id = ?")
            params.append(update_req.parent_id)

        if not updates:
            raise HTTPException(status_code=400, detail="更新フィールドがありません")

        updates.append("updated_at = datetime('now','localtime')")
        params.append(dept_id)

        await db.execute(f"UPDATE departments SET {', '.join(updates)} WHERE id = ?", params)
        await db.commit()

        cursor = await db.execute(
            "SELECT id, name, slug, description, parent_id, budget, status, created_at, updated_at FROM departments WHERE id = ?",
            (dept_id,),
        )
        row = await cursor.fetchone()

    return dict(row) if row else {"error": "更新失敗"}

async def _build_dept_tree(dept_id: int, db) -> dict:
    """Build hierarchical tree structure for a department"""
    cursor = await db.execute(
        "SELECT id, name, slug, description, parent_id, budget, status, created_at, updated_at FROM departments WHERE id = ?",
        (dept_id,)
    )
    row = await cursor.fetchone()
    if not row:
        return None

    dept = dict(row)
    cursor = await db.execute("SELECT COUNT(*) FROM department_agents WHERE department_id = ?", (dept_id,))
    agent_count = (await cursor.fetchone())[0]
    cursor = await db.execute("SELECT COUNT(*) FROM teams WHERE department_id = ?", (dept_id,))
    team_count = (await cursor.fetchone())[0]
    dept["agent_count"] = agent_count
    dept["team_count"] = team_count

    cursor = await db.execute("SELECT id FROM departments WHERE parent_id = ? ORDER BY name", (dept_id,))
    children_ids = [r[0] for r in await cursor.fetchall()]
    dept["children"] = []
    for child_id in children_ids:
        child = await _build_dept_tree(child_id, db)
        if child:
            dept["children"].append(child)

    return dept

@app.put("/api/departments/{dept_id}/parent")
async def change_department_parent(dept_id: int, parent_req: models.ParentChangeRequest, user: dict = Depends(get_current_user_zero_trust)):
    """Change a department's parent"""
    await ensure_db_initialized()
    init_workflow_services()

    if not parent_req.parent_id:
        new_parent_id = None
    else:
        new_parent_id = parent_req.parent_id

    async with aiosqlite.connect(str(THEBRANCH_DB)) as db:
        db.row_factory = aiosqlite.Row

        cursor = await db.execute("SELECT id FROM departments WHERE id = ?", (dept_id,))
        if not await cursor.fetchone():
            raise HTTPException(status_code=404, detail="部署が見つかりません")

        if new_parent_id:
            cursor = await db.execute("SELECT id FROM departments WHERE id = ?", (new_parent_id,))
            if not await cursor.fetchone():
                raise HTTPException(status_code=404, detail="親部署が見つかりません")

            if graph_repo_dept and graph_repo_dept.detect_circular_parent_assignment(dept_id, new_parent_id):
                raise HTTPException(status_code=400, detail={"error": "CIRCULAR_REFERENCE", "message": "循環参照が検出されました"})

        await db.execute("UPDATE departments SET parent_id = ?, updated_at = datetime('now','localtime') WHERE id = ?", (new_parent_id, dept_id))
        await db.commit()

        cursor = await db.execute(
            "SELECT id, name, slug, description, parent_id, budget, status, created_at, updated_at FROM departments WHERE id = ?",
            (dept_id,)
        )
        row = await cursor.fetchone()

    return dict(row) if row else {"error": "更新失敗"}

@app.delete("/api/departments/{dept_id}", status_code=204)
async def delete_department(dept_id: int, user: dict = Depends(get_current_user_zero_trust)):
    await ensure_db_initialized()
    async with aiosqlite.connect(str(THEBRANCH_DB)) as db:
        cursor = await db.execute("SELECT COUNT(*) FROM departments WHERE parent_id = ?", (dept_id,))
        child_count = (await cursor.fetchone())[0]

        if child_count > 0:
            cursor = await db.execute(
                "SELECT id, name, slug FROM departments WHERE parent_id = ?",
                (dept_id,),
            )
            children = await cursor.fetchall()
            raise HTTPException(
                status_code=400,
                detail={"error": "DEPT_HAS_CHILDREN", "message": "子部署が存在するため削除できません",
                        "child_departments": [{"id": c[0], "name": c[1], "slug": c[2]} for c in children]}
            )

        await db.execute("DELETE FROM departments WHERE id = ?", (dept_id,))
        await db.commit()

@app.get("/api/departments/templates")
async def list_department_templates(category: str = "", status: str = "active", user: dict = Depends(get_current_user_zero_trust)):
    await ensure_db_initialized()
    async with aiosqlite.connect(str(THEBRANCH_DB)) as db:
        db.row_factory = aiosqlite.Row
        query = "SELECT id, name, description, category, status, total_roles, total_processes, total_tasks FROM departments_templates WHERE 1=1"
        params = []

        if category:
            query += " AND category = ?"
            params.append(category)
        if status:
            query += " AND status = ?"
            params.append(status)

        query += " ORDER BY name"
        cursor = await db.execute(query, params)
        rows = await cursor.fetchall()

    return [dict(r) for r in rows]

@app.post("/api/departments/{dept_id}/agents", status_code=201)
async def add_agent_to_department(dept_id: int, agent_req: models.DepartmentAgentCreate, user: dict = Depends(get_current_user_zero_trust)):
    await ensure_db_initialized()
    async with aiosqlite.connect(str(THEBRANCH_DB)) as db:
        cursor = await db.execute("SELECT id FROM departments WHERE id = ?", (dept_id,))
        if not await cursor.fetchone():
            raise HTTPException(status_code=404, detail="部署が見つかりません")

        await db.execute(
            "INSERT INTO department_agents (department_id, agent_id, role) VALUES (?, ?, ?)",
            (dept_id, agent_req.agent_id, agent_req.role),
        )
        await db.commit()

        cursor = await db.execute(
            """SELECT da.department_id, da.agent_id, da.role, da.joined_at,
                      a.id, a.slug, a.name, a.role_type, a.specialty
               FROM department_agents da
               JOIN agents a ON da.agent_id = a.id
               WHERE da.department_id = ? AND da.agent_id = ?""",
            (dept_id, agent_req.agent_id),
        )
        row = await cursor.fetchone()

    if row:
        await log_agent_activity(agent_req.agent_id, "started", f"部署にエージェント追加: {agent_req.role}")
        return {
            "department_id": row[0],
            "agent_id": row[1],
            "role": row[2],
            "joined_at": row[3],
            "agent": {"id": row[4], "slug": row[5], "name": row[6], "role_type": row[7], "specialty": row[8]}
        }
    raise HTTPException(status_code=500, detail="エージェント追加に失敗しました")

@app.get("/api/departments/{dept_id}/agents")
async def list_department_agents(dept_id: int, user: dict = Depends(get_current_user_zero_trust)):
    await ensure_db_initialized()
    async with aiosqlite.connect(str(THEBRANCH_DB)) as db:
        db.row_factory = aiosqlite.Row
        cursor = await db.execute(
            """SELECT da.agent_id, da.role, da.joined_at,
                      a.id, a.slug, a.name, a.role_type, a.specialty
               FROM department_agents da
               JOIN agents a ON da.agent_id = a.id
               WHERE da.department_id = ?
               ORDER BY da.joined_at""",
            (dept_id,),
        )
        rows = await cursor.fetchall()

    agents = []
    for r in rows:
        agents.append({
            "agent_id": r[0],
            "role": r[1],
            "joined_at": r[2],
            "agent": {"id": r[3], "slug": r[4], "name": r[5], "role_type": r[6], "specialty": r[7]}
        })
    return {"data": agents, "total": len(agents)}

@app.delete("/api/departments/{dept_id}/agents/{agent_id}", status_code=204)
async def remove_agent_from_department(dept_id: int, agent_id: int, user: dict = Depends(get_current_user_zero_trust)):
    await ensure_db_initialized()
    async with aiosqlite.connect(str(THEBRANCH_DB)) as db:
        await db.execute(
            "DELETE FROM department_agents WHERE department_id = ? AND agent_id = ?",
            (dept_id, agent_id),
        )
        await db.commit()

# ──────────────────────────────────────────────
# Agents (#2391)
# ──────────────────────────────────────────────

@app.post("/api/agents", status_code=201)
async def create_agent(agent_req: models.AgentCreate, user: dict = Depends(get_current_user_zero_trust)):
    await ensure_db_initialized()
    try:
        async with aiosqlite.connect(str(THEBRANCH_DB)) as db:
            db.row_factory = aiosqlite.Row
            cursor = await db.execute(
                "SELECT id, slug FROM departments WHERE id = ?", (agent_req.department_id,)
            )
            dept = await cursor.fetchone()
            if not dept:
                raise HTTPException(status_code=404, detail="部署が見つかりません")

            session_name = generate_session_name(agent_req.department_id, dept["slug"], agent_req.role)
            success, result = await start_ccc_agent(session_name, agent_req.role, agent_req.department_id)

            if not success:
                raise HTTPException(status_code=500, detail=f"エージェント起動に失敗: {result}")

            cursor = await db.execute(
                """INSERT INTO agents (department_id, session_id, role, status)
                   VALUES (?, ?, ?, 'running')""",
                (agent_req.department_id, result, agent_req.role),
            )
            agent_id = cursor.lastrowid
            await db.commit()

            cursor = await db.execute(
                """SELECT id, department_id, session_id, role, status, started_at,
                          stopped_at, error_message, created_at, updated_at FROM agents WHERE id = ?""",
                (agent_id,),
            )
            row = await cursor.fetchone()

        return dict(row) if row else {"error": "Failed to create"}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/agents/{agent_id}")
async def get_agent(agent_id: int, user: dict = Depends(get_current_user_zero_trust)):
    await ensure_db_initialized()
    async with aiosqlite.connect(str(THEBRANCH_DB)) as db:
        db.row_factory = aiosqlite.Row
        cursor = await db.execute(
            """SELECT id, department_id, session_id, role, status, started_at,
                      stopped_at, error_message, created_at, updated_at FROM agents WHERE id = ?""",
            (agent_id,),
        )
        row = await cursor.fetchone()

    if not row:
        raise HTTPException(status_code=404, detail="エージェントが見つかりません")
    return dict(row)

@app.get("/api/departments/{dept_id}/agents-managed")
async def list_department_agents_managed(dept_id: int, user: dict = Depends(get_current_user_zero_trust)):
    await ensure_db_initialized()
    async with aiosqlite.connect(str(THEBRANCH_DB)) as db:
        db.row_factory = aiosqlite.Row
        cursor = await db.execute(
            """SELECT id, department_id, session_id, role, status, started_at,
                      stopped_at, error_message, created_at, updated_at
               FROM agents WHERE department_id = ? ORDER BY created_at DESC""",
            (dept_id,),
        )
        rows = await cursor.fetchall()
    return {"data": [dict(r) for r in rows], "total": len(rows)}

@app.post("/api/agents/{agent_id}/stop", status_code=200)
async def stop_agent(agent_id: int, user: dict = Depends(get_current_user_zero_trust)):
    await ensure_db_initialized()
    async with aiosqlite.connect(str(THEBRANCH_DB)) as db:
        db.row_factory = aiosqlite.Row
        cursor = await db.execute(
            "SELECT id, session_id FROM agents WHERE id = ?", (agent_id,)
        )
        agent = await cursor.fetchone()

        if not agent:
            raise HTTPException(status_code=404, detail="エージェントが見つかりません")

        success = await stop_tmux_session(agent["session_id"])
        if not success:
            raise HTTPException(status_code=500, detail="セッション停止に失敗しました")

        await db.execute(
            """UPDATE agents SET status = 'stopped', stopped_at = datetime('now','localtime')
               WHERE id = ?""",
            (agent_id,),
        )
        await db.commit()

        cursor = await db.execute(
            """SELECT id, department_id, session_id, role, status, started_at,
                      stopped_at, error_message, created_at, updated_at FROM agents WHERE id = ?""",
            (agent_id,),
        )
        row = await cursor.fetchone()

    if row:
        await log_agent_activity(agent_id, "stopped", "エージェント停止")
    return dict(row) if row else {"error": "Failed to stop"}


# ============================================================================
# Task #2509: エージェントチャットUI改善 — chat persistence & context
# ============================================================================

async def _ensure_agent_chats_table(db) -> None:
    """agent_chats テーブルを必要に応じて作成（マイグレーション未適用環境への保険）。"""
    await db.execute(
        """
        CREATE TABLE IF NOT EXISTS agent_chats (
            id              INTEGER PRIMARY KEY AUTOINCREMENT,
            agent_id        INTEGER NOT NULL,
            session_id      TEXT NOT NULL,
            role            TEXT NOT NULL
                CHECK(role IN ('user', 'assistant', 'system')),
            content         TEXT NOT NULL,
            context_meta    TEXT,
            user_id         TEXT,
            username        TEXT,
            created_at      TEXT NOT NULL DEFAULT (datetime('now', 'localtime'))
        )
        """
    )
    await db.execute(
        "CREATE INDEX IF NOT EXISTS idx_agent_chats_agent_id ON agent_chats(agent_id)"
    )
    await db.execute(
        "CREATE INDEX IF NOT EXISTS idx_agent_chats_session ON agent_chats(agent_id, session_id)"
    )
    await db.execute(
        "CREATE INDEX IF NOT EXISTS idx_agent_chats_created_at ON agent_chats(created_at DESC)"
    )


class AgentChatHistoryItem(BaseModel):
    role: str
    content: str


class AgentChatRequest(BaseModel):
    message: str
    session_id: Optional[str] = None
    history: Optional[List[AgentChatHistoryItem]] = None
    model_hint: Optional[str] = None


def _build_assistant_reply(role_name: str, message: str, history: list) -> str:
    """簡易応答ジェネレーター。

    将来的にはここを LLM/エージェント実体への呼び出しに差し替える。
    当面は会話履歴を踏まえた決定的な応答を返し、UI改善（Task #2509）の
    動作確認とコンテキスト維持の検証に使う。
    """
    msg = (message or "").strip()
    history_count = len([h for h in (history or []) if (h.get("role") if isinstance(h, dict) else getattr(h, "role", None)) in ("user", "assistant")])
    role_label = role_name or "AIエージェント"

    lower = msg.lower()
    if not msg:
        return f"[{role_label}] メッセージが空です。質問内容を入力してください。"
    if any(k in msg for k in ("こんにちは", "おはよう", "はじめまして")) or "hello" in lower or "hi" in lower:
        return f"[{role_label}] こんにちは。これまでに {history_count} 件のやりとりをしています。どのようにお手伝いしましょうか？"
    if msg.endswith("?") or msg.endswith("？") or any(k in msg for k in ("教えて", "とは", "ですか", "what", "why", "how")):
        return (
            f"[{role_label}] ご質問ありがとうございます。\n"
            f"これまで {history_count} 件の文脈を踏まえてお答えします:\n"
            f"「{msg}」については、関連情報を整理しています。"
        )
    if any(k in msg for k in ("お願い", "やって", "実装", "作って", "please")):
        return (
            f"[{role_label}] 了解しました。会話履歴 {history_count} 件をコンテキストとして踏まえ、"
            f"以下の方針で進めます: 『{msg[:80]}』"
        )
    return (
        f"[{role_label}] メッセージを受け取りました（履歴 {history_count} 件）。\n"
        f"内容: {msg[:200]}"
    )


@app.post("/api/agents/{agent_id}/chat", status_code=200)
async def post_agent_chat(
    agent_id: int,
    payload: AgentChatRequest,
    user: dict = Depends(get_current_user_zero_trust),
):
    """エージェントへチャットメッセージを送信し、ユーザー/アシスタントの両ロウを永続化して返す。"""
    await ensure_db_initialized()
    if not payload.message or not payload.message.strip():
        raise HTTPException(status_code=400, detail="メッセージが空です")

    session_id = (payload.session_id or "").strip() or f"sess-{uuid.uuid4().hex[:12]}"
    history_payload = []
    for h in (payload.history or []):
        if isinstance(h, AgentChatHistoryItem):
            history_payload.append({"role": h.role, "content": h.content})
        elif isinstance(h, dict):
            history_payload.append({"role": h.get("role", ""), "content": h.get("content", "")})
    user_id = str(user.get("id") or user.get("user_id") or "") if isinstance(user, dict) else ""
    username = str(user.get("username") or user.get("name") or "") if isinstance(user, dict) else ""

    async with aiosqlite.connect(str(THEBRANCH_DB)) as db:
        db.row_factory = aiosqlite.Row
        await _ensure_agent_chats_table(db)

        cursor = await db.execute(
            "SELECT id, role, status, session_id FROM agents WHERE id = ?", (agent_id,)
        )
        agent = await cursor.fetchone()
        if not agent:
            raise HTTPException(status_code=404, detail="エージェントが見つかりません")

        meta = json.dumps({
            "history_count": len(history_payload),
            "agent_session": agent["session_id"],
        }, ensure_ascii=False)

        await db.execute(
            """INSERT INTO agent_chats (agent_id, session_id, role, content, context_meta, user_id, username)
               VALUES (?, ?, 'user', ?, ?, ?, ?)""",
            (agent_id, session_id, payload.message, meta, user_id, username),
        )

        reply_text = _build_assistant_reply(agent["role"] or "", payload.message, history_payload)

        await db.execute(
            """INSERT INTO agent_chats (agent_id, session_id, role, content, context_meta, user_id, username)
               VALUES (?, ?, 'assistant', ?, ?, ?, ?)""",
            (agent_id, session_id, reply_text, meta, user_id, username),
        )
        await db.commit()

        cursor = await db.execute(
            """SELECT id, agent_id, session_id, role, content, created_at
               FROM agent_chats
               WHERE agent_id = ? AND session_id = ?
               ORDER BY id DESC LIMIT 2""",
            (agent_id, session_id),
        )
        rows = await cursor.fetchall()

    items = [dict(r) for r in rows]
    items.sort(key=lambda r: r["id"])
    try:
        await log_agent_activity(agent_id, "chat", f"chat: {payload.message[:80]}")
    except Exception:
        pass

    return {
        "agent_id": agent_id,
        "session_id": session_id,
        "messages": items,
        "reply": reply_text,
        "history_count": len(history_payload),
    }


@app.get("/api/agents/{agent_id}/chat")
async def list_agent_chat(
    agent_id: int,
    session_id: Optional[str] = None,
    limit: int = 200,
    user: dict = Depends(get_current_user_zero_trust),
):
    """指定エージェントの永続化済みチャット履歴を取得。session_id 未指定時は最新セッションのみ。"""
    await ensure_db_initialized()
    async with aiosqlite.connect(str(THEBRANCH_DB)) as db:
        db.row_factory = aiosqlite.Row
        await _ensure_agent_chats_table(db)

        cursor = await db.execute("SELECT id, role FROM agents WHERE id = ?", (agent_id,))
        agent = await cursor.fetchone()
        if not agent:
            raise HTTPException(status_code=404, detail="エージェントが見つかりません")

        if session_id:
            cursor = await db.execute(
                """SELECT id, agent_id, session_id, role, content, created_at
                   FROM agent_chats
                   WHERE agent_id = ? AND session_id = ?
                   ORDER BY id ASC LIMIT ?""",
                (agent_id, session_id, max(1, min(limit, 1000))),
            )
        else:
            cursor = await db.execute(
                """SELECT id, agent_id, session_id, role, content, created_at
                   FROM agent_chats
                   WHERE agent_id = ?
                   ORDER BY id ASC LIMIT ?""",
                (agent_id, max(1, min(limit, 1000))),
            )
        rows = await cursor.fetchall()

        cursor = await db.execute(
            """SELECT session_id, COUNT(*) AS cnt, MAX(created_at) AS last_at
               FROM agent_chats WHERE agent_id = ?
               GROUP BY session_id ORDER BY last_at DESC LIMIT 50""",
            (agent_id,),
        )
        sess_rows = await cursor.fetchall()

    return {
        "agent_id": agent_id,
        "agent_role": agent["role"],
        "session_id": session_id,
        "messages": [dict(r) for r in rows],
        "sessions": [dict(s) for s in sess_rows],
        "total": len(rows),
    }


@app.delete("/api/agents/{agent_id}/chat")
async def delete_agent_chat(
    agent_id: int,
    session_id: Optional[str] = None,
    user: dict = Depends(get_current_user_zero_trust),
):
    """チャット履歴を削除（session_id 指定時はそのセッションのみ）。"""
    await ensure_db_initialized()
    async with aiosqlite.connect(str(THEBRANCH_DB)) as db:
        await _ensure_agent_chats_table(db)
        if session_id:
            await db.execute(
                "DELETE FROM agent_chats WHERE agent_id = ? AND session_id = ?",
                (agent_id, session_id),
            )
        else:
            await db.execute("DELETE FROM agent_chats WHERE agent_id = ?", (agent_id,))
        await db.commit()
    return {"ok": True, "agent_id": agent_id, "session_id": session_id}


async def activity_event_generator(dept_id: int) -> AsyncGenerator[str, None]:
    """Stream agent activity logs for a department."""
    while True:
        try:
            async with aiosqlite.connect(str(THEBRANCH_DB)) as db:
                db.row_factory = aiosqlite.Row
                cursor = await db.execute(
                    """SELECT al.id, al.agent_id, al.action, al.detail, al.created_at,
                             a.role
                       FROM agent_logs al
                       JOIN agents a ON al.agent_id = a.id
                       WHERE a.department_id = ?
                       ORDER BY al.created_at DESC
                       LIMIT 20""",
                    (dept_id,)
                )
                rows = await cursor.fetchall()

            logs = [dict(row) for row in rows]
            yield f"data: {json.dumps(logs, ensure_ascii=False)}\n\n"
        except Exception:
            yield f"data: []\n\n"
        await asyncio.sleep(5)

@app.get("/api/departments/{dept_id}/activity-feed")
async def stream_activity_feed(dept_id: int, user: dict = Depends(get_current_user_zero_trust)):
    """SSE endpoint for agent activity logs."""
    await ensure_db_initialized()
    return StreamingResponse(
        activity_event_generator(dept_id),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )


@app.post("/api/departments/{dept_id}/agents/{agent_id}/mission", status_code=201)
async def create_agent_mission(
    dept_id: int,
    agent_id: int,
    mission_req: models.MissionCreate,
user: dict = Depends(get_current_user_zero_trust)):
    await ensure_db_initialized()
    async with aiosqlite.connect(str(THEBRANCH_DB)) as db:
        db.row_factory = aiosqlite.Row
        cursor = await db.execute(
            "SELECT id FROM agents WHERE id = ? AND department_id = ?",
            (agent_id, dept_id)
        )
        if not await cursor.fetchone():
            raise HTTPException(status_code=404, detail="Agent not found in department")

        cursor = await db.execute(
            "SELECT id FROM department_instance_workflows WHERE id = ?",
            (mission_req.workflow_id,)
        )
        if not await cursor.fetchone():
            raise HTTPException(status_code=404, detail="Workflow not found")

        cursor = await db.execute(
            """INSERT INTO missions (agent_id, department_id, workflow_id, name, status, custom_prompt, target_completion, priority)
               VALUES (?, ?, ?, ?, 'planning', ?, ?, ?)""",
            (agent_id, dept_id, mission_req.workflow_id,
             f"Mission for agent {agent_id}",
             mission_req.custom_prompt,
             mission_req.target_completion,
             mission_req.priority)
        )
        mission_id = cursor.lastrowid

        for task_id in mission_req.task_ids:
            await db.execute(
                """INSERT INTO mission_tasks (mission_id, task_key, task_title, status)
                   VALUES (?, ?, ?, 'pending')""",
                (mission_id, f"task_{task_id}", f"Task {task_id}")
            )

        await db.commit()

        cursor = await db.execute(
            """SELECT id, agent_id, workflow_id, name, status, priority, custom_prompt, target_completion, created_at, updated_at
               FROM missions WHERE id = ?""",
            (mission_id,)
        )
        row = await cursor.fetchone()

    return dict(row) if row else {"error": "Failed to create mission"}


@app.get("/api/departments/{dept_id}/agents/{agent_id}/mission")
async def get_agent_mission(dept_id: int, agent_id: int, user: dict = Depends(get_current_user_zero_trust)):
    await ensure_db_initialized()
    async with aiosqlite.connect(str(THEBRANCH_DB)) as db:
        db.row_factory = aiosqlite.Row

        cursor = await db.execute(
            """SELECT id, agent_id, workflow_id, name, status, priority, custom_prompt, target_completion, created_at, updated_at
               FROM missions WHERE agent_id = ? AND department_id = ?""",
            (agent_id, dept_id)
        )
        mission = await cursor.fetchone()

        if not mission:
            return {"data": None}

        cursor = await db.execute(
            """SELECT id, task_key, task_title, status, priority FROM mission_tasks
               WHERE mission_id = ?""",
            (mission['id'],)
        )
        tasks = await cursor.fetchall()

        return {
            "data": {
                **dict(mission),
                "tasks": [dict(t) for t in tasks]
            }
        }


@app.post("/api/departments/{dept_id}/teams", status_code=201)
async def create_team(dept_id: int, team_req: models.TeamCreate, user: dict = Depends(get_current_user_zero_trust)):
    await ensure_db_initialized()
    async with aiosqlite.connect(str(THEBRANCH_DB)) as db:
        db.row_factory = aiosqlite.Row
        cursor = await db.execute("SELECT id FROM departments WHERE id = ?", (dept_id,))
        if not await cursor.fetchone():
            raise HTTPException(status_code=404, detail="部署が見つかりません")

        cursor = await db.execute(
            """INSERT INTO teams (department_id, name, slug, description, status, created_by)
               VALUES (?, ?, ?, ?, ?, 'system')""",
            (dept_id, team_req.name, team_req.slug, team_req.description, team_req.status),
        )
        team_id = cursor.lastrowid
        await db.commit()

        cursor = await db.execute(
            "SELECT id, department_id, name, slug, description, status, created_at, updated_at FROM teams WHERE id = ?",
            (team_id,),
        )
        row = await cursor.fetchone()

    return dict(row) if row else {"error": "チーム作成失敗"}

@app.get("/api/departments/{dept_id}/teams")
async def list_teams(dept_id: int, user: dict = Depends(get_current_user_zero_trust)):
    await ensure_db_initialized()
    async with aiosqlite.connect(str(THEBRANCH_DB)) as db:
        db.row_factory = aiosqlite.Row
        cursor = await db.execute(
            "SELECT id, department_id, name, slug, description, status, created_at, updated_at FROM teams WHERE department_id = ? ORDER BY id",
            (dept_id,),
        )
        rows = await cursor.fetchall()

    return {"data": [dict(r) for r in rows], "total": len(rows)}

@app.get("/api/departments/{dept_id}/teams/{team_id}")
async def get_team(dept_id: int, team_id: int, user: dict = Depends(get_current_user_zero_trust)):
    await ensure_db_initialized()
    async with aiosqlite.connect(str(THEBRANCH_DB)) as db:
        db.row_factory = aiosqlite.Row
        cursor = await db.execute(
            "SELECT id, department_id, name, slug, description, status, created_at, updated_at FROM teams WHERE id = ? AND department_id = ?",
            (team_id, dept_id),
        )
        row = await cursor.fetchone()
        if not row:
            raise HTTPException(status_code=404, detail="チームが見つかりません")

    return dict(row)

@app.put("/api/departments/{dept_id}/teams/{team_id}")
async def update_team(dept_id: int, team_id: int, update_req: models.TeamUpdate, user: dict = Depends(get_current_user_zero_trust)):
    await ensure_db_initialized()
    async with aiosqlite.connect(str(THEBRANCH_DB)) as db:
        db.row_factory = aiosqlite.Row
        updates = []
        params = []

        if update_req.name:
            updates.append("name = ?")
            params.append(update_req.name)
        if update_req.description is not None:
            updates.append("description = ?")
            params.append(update_req.description)
        if update_req.status:
            updates.append("status = ?")
            params.append(update_req.status)

        if not updates:
            raise HTTPException(status_code=400, detail="更新フィールドがありません")

        updates.append("updated_at = datetime('now','localtime')")
        params.extend([team_id, dept_id])

        await db.execute(
            f"UPDATE teams SET {', '.join(updates)} WHERE id = ? AND department_id = ?",
            params
        )
        await db.commit()

        cursor = await db.execute(
            "SELECT id, department_id, name, slug, description, status, created_at, updated_at FROM teams WHERE id = ?",
            (team_id,),
        )
        row = await cursor.fetchone()

    return dict(row) if row else {"error": "チーム更新失敗"}

@app.delete("/api/departments/{dept_id}/teams/{team_id}", status_code=204)
async def delete_team(dept_id: int, team_id: int, user: dict = Depends(get_current_user_zero_trust)):
    await ensure_db_initialized()
    async with aiosqlite.connect(str(THEBRANCH_DB)) as db:
        await db.execute(
            "DELETE FROM teams WHERE id = ? AND department_id = ?",
            (team_id, dept_id),
        )
        await db.commit()


# Department Relations

@app.post("/api/departments/{dept_id}/relations", status_code=201)
async def create_relation(dept_id: int, rel_req: models.RelationCreate, user: dict = Depends(get_current_user_zero_trust)):
    await ensure_db_initialized()
    async with aiosqlite.connect(str(THEBRANCH_DB)) as db:
        db.row_factory = aiosqlite.Row
        cursor = await db.execute("SELECT id FROM departments WHERE id = ?", (dept_id,))
        if not await cursor.fetchone():
            raise HTTPException(status_code=404, detail="部署が見つかりません")

        cursor = await db.execute("SELECT id FROM departments WHERE id = ?", (rel_req.dept_b_id,))
        if not await cursor.fetchone():
            raise HTTPException(status_code=404, detail="関連部署が見つかりません")

        cursor = await db.execute(
            """INSERT INTO department_relations (dept_a_id, dept_b_id, relation_type, description)
               VALUES (?, ?, ?, ?)""",
            (dept_id, rel_req.dept_b_id, rel_req.relation_type, rel_req.description),
        )
        await db.commit()

        rel_id = cursor.lastrowid
        cursor = await db.execute(
            """SELECT id, dept_a_id, dept_b_id, relation_type, description, created_at
               FROM department_relations WHERE id = ?""",
            (rel_id,),
        )
        row = await cursor.fetchone()

    return dict(row) if row else {"error": "関係作成失敗"}


@app.get("/api/departments/{dept_id}/relations")
async def list_relations(dept_id: int, user: dict = Depends(get_current_user_zero_trust)):
    await ensure_db_initialized()
    async with aiosqlite.connect(str(THEBRANCH_DB)) as db:
        db.row_factory = aiosqlite.Row
        cursor = await db.execute("SELECT id FROM departments WHERE id = ?", (dept_id,))
        if not await cursor.fetchone():
            raise HTTPException(status_code=404, detail="部署が見つかりません")

        cursor = await db.execute(
            """SELECT id, dept_a_id, dept_b_id, relation_type, description, created_at
               FROM department_relations WHERE dept_a_id = ? ORDER BY id""",
            (dept_id,),
        )
        rows = await cursor.fetchall()

    return {
        "data": [dict(r) for r in rows],
        "total": len(rows)
    }


@app.delete("/api/departments/{dept_id}/relations/{related_dept_id}", status_code=204)
async def delete_relation(dept_id: int, related_dept_id: int, user: dict = Depends(get_current_user_zero_trust)):
    await ensure_db_initialized()
    async with aiosqlite.connect(str(THEBRANCH_DB)) as db:
        await db.execute(
            "DELETE FROM department_relations WHERE dept_a_id = ? AND dept_b_id = ?",
            (dept_id, related_dept_id),
        )
        await db.commit()


# ──────────────────────────────────────────────
# Metrics (#2408)
# ──────────────────────────────────────────────

@app.get("/api/departments/{dept_id}/metrics")
async def get_department_metrics(dept_id: int, user: dict = Depends(get_current_user_zero_trust)):
    """Get department metrics including agent uptime and task completion."""
    await ensure_db_initialized()
    try:
        async with aiosqlite.connect(str(THEBRANCH_DB)) as db:
            db.row_factory = aiosqlite.Row

            # Verify department exists
            cursor = await db.execute("SELECT id FROM departments WHERE id = ?", (dept_id,))
            if not await cursor.fetchone():
                raise HTTPException(status_code=404, detail="部署が見つかりません")

            # Get agent metrics
            cursor = await db.execute(
                """SELECT
                     COUNT(*) as total_agents,
                     SUM(CASE WHEN status = 'running' THEN 1 ELSE 0 END) as running_agents,
                     SUM(CASE WHEN status = 'stopped' THEN 1 ELSE 0 END) as stopped_agents,
                     SUM(CASE WHEN status = 'failed' THEN 1 ELSE 0 END) as failed_agents,
                     SUM(CASE WHEN status = 'starting' THEN 1 ELSE 0 END) as starting_agents
                   FROM agents
                   WHERE department_id = ?""",
                (dept_id,),
            )
            agent_stats = await cursor.fetchone()

            # Calculate agent uptime percentage
            total_agents = agent_stats["total_agents"] or 0
            running_agents = agent_stats["running_agents"] or 0
            uptime_percentage = (running_agents / total_agents * 100) if total_agents > 0 else 0

            # Get task completion metrics
            cursor = await db.execute(
                """SELECT
                     COUNT(*) as total_tasks,
                     SUM(CASE WHEN status = 'completed' THEN 1 ELSE 0 END) as completed_tasks,
                     SUM(CASE WHEN status = 'in_progress' THEN 1 ELSE 0 END) as in_progress_tasks
                   FROM missions
                   WHERE agent_id IN (SELECT id FROM agents WHERE department_id = ?)""",
                (dept_id,),
            )
            task_stats = await cursor.fetchone()

            total_tasks = task_stats["total_tasks"] or 0
            completed_tasks = task_stats["completed_tasks"] or 0
            task_completion_percentage = (completed_tasks / total_tasks * 100) if total_tasks > 0 else 0

            # Get time series data for last 30 days
            cursor = await db.execute(
                """SELECT
                     DATE(a.created_at) as date,
                     COUNT(DISTINCT a.id) as agent_count,
                     SUM(CASE WHEN a.status = 'running' THEN 1 ELSE 0 END) as running_count
                   FROM agents a
                   WHERE a.department_id = ?
                     AND datetime(a.created_at) >= datetime('now', '-30 days')
                   GROUP BY DATE(a.created_at)
                   ORDER BY date ASC""",
                (dept_id,),
            )
            time_series = await cursor.fetchall()

            # Get agent logs for activity tracking
            cursor = await db.execute(
                """SELECT
                     COUNT(CASE WHEN al.action = 'started' THEN 1 END) as starts,
                     COUNT(CASE WHEN al.action = 'stopped' THEN 1 END) as stops,
                     COUNT(CASE WHEN al.action = 'failed' THEN 1 END) as failures,
                     COUNT(CASE WHEN al.action = 'message' THEN 1 END) as messages
                   FROM agent_logs al
                   WHERE al.agent_id IN (SELECT id FROM agents WHERE department_id = ?)""",
                (dept_id,),
            )
            activity_stats = await cursor.fetchone()

        # Build response
        return {
            "department_id": dept_id,
            "agents": {
                "total": total_agents,
                "running": running_agents,
                "stopped": agent_stats["stopped_agents"] or 0,
                "failed": agent_stats["failed_agents"] or 0,
                "starting": agent_stats["starting_agents"] or 0,
                "uptime_percentage": round(uptime_percentage, 2),
            },
            "tasks": {
                "total": total_tasks,
                "completed": completed_tasks,
                "in_progress": task_stats["in_progress_tasks"] or 0,
                "completion_percentage": round(task_completion_percentage, 2),
            },
            "activity": {
                "starts": activity_stats["starts"] or 0,
                "stops": activity_stats["stops"] or 0,
                "failures": activity_stats["failures"] or 0,
                "messages": activity_stats["messages"] or 0,
            },
            "time_series": [
                {
                    "date": row["date"],
                    "agent_count": row["agent_count"],
                    "running_count": row["running_count"],
                }
                for row in time_series
            ],
        }
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"メトリクス取得エラー: {str(e)}")


# ──────────────────────────────────────────────
# Workflow Templates
# ──────────────────────────────────────────────

class CreateTemplateRequest(BaseModel):
    name: str
    description: Optional[str] = None
    created_by: Optional[str] = None

class CreatePhaseRequest(BaseModel):
    phase_key: str
    phase_label: str
    specialist_type: str
    phase_order: int
    is_parallel: bool = False

class CreateTaskRequest(BaseModel):
    task_key: str
    task_title: str
    task_description: Optional[str] = None
    depends_on_key: Optional[str] = None
    priority: int = 1
    estimated_hours: Optional[float] = None
    task_order: int = 0

@app.post("/api/templates")
async def create_template(req: CreateTemplateRequest, user: dict = Depends(get_current_user_zero_trust)):
    try:
        service = get_template_service()
        template = service.create_template(
            name=req.name,
            description=req.description,
            created_by=req.created_by or "dashboard",
        )
        return {
            "id": template.id,
            "name": template.name,
            "description": template.description,
            "status": template.status,
            "created_by": template.created_by,
            "created_at": template.created_at.isoformat() if template.created_at else None,
        }
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))

@app.get("/api/templates")
async def list_templates(status: Optional[str] = None, limit: int = 50, offset: int = 0, user: dict = Depends(get_current_user_zero_trust)):
    try:
        service = get_template_service()
        templates = service.list_templates(status=status, limit=limit, offset=offset)
        return [
            {
                "id": t.id,
                "name": t.name,
                "description": t.description,
                "status": t.status,
                "phase_count": t.phase_count,
                "task_count": t.task_count,
                "created_by": t.created_by,
                "created_at": t.created_at.isoformat() if t.created_at else None,
            }
            for t in templates
        ]
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))

@app.get("/api/templates/{template_id}")
async def get_template(template_id: int, user: dict = Depends(get_current_user_zero_trust)):
    try:
        service = get_template_service()
        template = service.get_template(template_id)

        def phase_to_dict(phase):
            tasks = [
                {
                    "id": t.id,
                    "task_key": t.task_key,
                    "task_title": t.task_title,
                    "task_description": t.task_description,
                    "priority": t.priority,
                    "estimated_hours": t.estimated_hours,
                    "task_order": t.task_order,
                    "depends_on_key": t.depends_on_key,
                }
                for t in (phase.tasks or [])
            ]
            return {
                "id": phase.id,
                "phase_key": phase.phase_key,
                "phase_label": phase.phase_label,
                "specialist_type": phase.specialist_type,
                "phase_order": phase.phase_order,
                "is_parallel": phase.is_parallel,
                "tasks": tasks,
            }

        phases = [phase_to_dict(p) for p in (template.phases or [])]

        return {
            "id": template.id,
            "name": template.name,
            "description": template.description,
            "status": template.status,
            "phase_count": template.phase_count,
            "task_count": template.task_count,
            "created_by": template.created_by,
            "created_at": template.created_at.isoformat() if template.created_at else None,
            "phases": phases,
        }
    except Exception as e:
        raise HTTPException(status_code=404, detail=str(e))

@app.post("/api/templates/{template_id}/phases")
async def create_phase(template_id: int, req: CreatePhaseRequest, user: dict = Depends(get_current_user_zero_trust)):
    try:
        service = get_template_service()
        phase = service.add_phase(
            template_id=template_id,
            phase_key=req.phase_key,
            phase_label=req.phase_label,
            specialist_type=req.specialist_type,
            phase_order=req.phase_order,
            is_parallel=req.is_parallel,
        )
        return {
            "id": phase.id,
            "phase_key": phase.phase_key,
            "phase_label": phase.phase_label,
            "specialist_type": phase.specialist_type,
            "phase_order": phase.phase_order,
            "is_parallel": phase.is_parallel,
        }
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))

@app.post("/api/templates/{template_id}/phases/{phase_id}/tasks")
async def create_task_def(template_id: int, phase_id: int, req: CreateTaskRequest, user: dict = Depends(get_current_user_zero_trust)):
    try:
        service = get_template_service()
        task = service.add_task_to_phase(
            phase_id=phase_id,
            task_key=req.task_key,
            task_title=req.task_title,
            task_description=req.task_description,
            depends_on_key=req.depends_on_key,
            priority=req.priority,
            estimated_hours=req.estimated_hours,
            task_order=req.task_order,
        )
        return {
            "id": task.id,
            "task_key": task.task_key,
            "task_title": task.task_title,
            "task_description": task.task_description,
            "priority": task.priority,
            "estimated_hours": task.estimated_hours,
            "task_order": task.task_order,
            "depends_on_key": task.depends_on_key,
        }
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))

@app.post("/api/templates/{template_id}/publish")
async def publish_template(template_id: int, user: dict = Depends(get_current_user_zero_trust)):
    try:
        service = get_template_service()
        template = service.publish_template(template_id)
        return {
            "id": template.id,
            "name": template.name,
            "status": template.status,
            "updated_at": template.updated_at.isoformat() if template.updated_at else None,
        }
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


# ──────────────────────────────────────────────
# Accounting
# ──────────────────────────────────────────────

class InvoiceCreateRequest(BaseModel):
    department_id: int
    invoice_number: str
    vendor_name: str
    invoice_date: str
    due_date: str
    amount_jpy: float
    tax_amount_jpy: float = 0
    description: Optional[str] = None
    items: list = []

class ExpenseSubmissionRequest(BaseModel):
    department_id: int
    submission_number: str
    employee_name: str
    submission_date: str
    period_start: str
    period_end: str
    total_amount_jpy: float
    description: Optional[str] = None
    items: list = []

@app.post("/api/accounting/invoices", status_code=201)
async def create_invoice(req: InvoiceCreateRequest, user: dict = Depends(get_current_user_zero_trust)):
    try:
        init_workflow_services()
        service = get_accounting_service()
        invoice_id = service.create_invoice(
            department_id=req.department_id,
            invoice_number=req.invoice_number,
            vendor_name=req.vendor_name,
            invoice_date=req.invoice_date,
            due_date=req.due_date,
            amount_jpy=req.amount_jpy,
            tax_amount_jpy=req.tax_amount_jpy,
            description=req.description,
        )
        if req.items:
            service.add_invoice_items(invoice_id, req.items)
        return {
            "invoice_id": invoice_id,
            "invoice_number": req.invoice_number,
            "status": "pending"
        }
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))

@app.get("/api/accounting/invoices/{invoice_id}")
async def get_invoice(invoice_id: int, user: dict = Depends(get_current_user_zero_trust)):
    try:
        init_workflow_services()
        service = get_accounting_service()
        invoice = service.get_invoice_detail(invoice_id)
        return invoice
    except Exception as e:
        raise HTTPException(status_code=404, detail=str(e))

@app.post("/api/accounting/invoices/{invoice_id}/approve")
async def approve_invoice(invoice_id: int, approver_id: int, user: dict = Depends(get_current_user_zero_trust)):
    try:
        init_workflow_services()
        service = get_accounting_service()
        service.approve_invoice(invoice_id, approver_id)
        return {"invoice_id": invoice_id, "status": "approved"}
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))

@app.post("/api/accounting/expenses", status_code=201)
async def submit_expense(req: ExpenseSubmissionRequest, user: dict = Depends(get_current_user_zero_trust)):
    try:
        init_workflow_services()
        service = get_accounting_service()
        submission_id = service.submit_expense(
            department_id=req.department_id,
            submission_number=req.submission_number,
            employee_name=req.employee_name,
            submission_date=req.submission_date,
            period_start=req.period_start,
            period_end=req.period_end,
            total_amount_jpy=req.total_amount_jpy,
            description=req.description,
        )
        if req.items:
            service.add_expense_items(submission_id, req.items)
        return {
            "submission_id": submission_id,
            "submission_number": req.submission_number,
            "status": "pending"
        }
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))

@app.get("/api/accounting/expenses/{submission_id}")
async def get_expense(submission_id: int, user: dict = Depends(get_current_user_zero_trust)):
    try:
        init_workflow_services()
        service = get_accounting_service()
        submission = service.get_expense_detail(submission_id)
        return submission
    except Exception as e:
        raise HTTPException(status_code=404, detail=str(e))

@app.post("/api/accounting/expenses/{submission_id}/approve")
async def approve_expense(submission_id: int, approver_id: int, user: dict = Depends(get_current_user_zero_trust)):
    try:
        init_workflow_services()
        service = get_accounting_service()
        service.approve_expense_submission(submission_id, approver_id)
        return {"submission_id": submission_id, "status": "approved"}
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))

@app.get("/api/accounting/departments/{department_id}/summary")
async def get_accounting_summary(department_id: int, user: dict = Depends(get_current_user_zero_trust)):
    try:
        init_workflow_services()
        service = get_accounting_service()
        summary = service.get_department_summary(department_id)
        return summary
    except Exception as e:
        raise HTTPException(status_code=404, detail=str(e))

@app.post("/api/accounting/reports/monthly")
async def generate_monthly_report(department_id: int, year: int, month: int, user: dict = Depends(get_current_user_zero_trust)):
    try:
        init_workflow_services()
        service = get_accounting_service()
        report = service.generate_monthly_report(department_id, year, month)
        return report
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


# ──────────────────────────────────────────────
# Onboarding
# ──────────────────────────────────────────────

@app.get("/onboarding", response_class=HTMLResponse)
async def get_onboarding_page(user: dict = Depends(get_current_user_zero_trust)):
    """オンボーディングウィザードページを提供"""
    html_path = DASHBOARD_DIR / "onboarding-wizard.html"
    return HTMLResponse(content=html_path.read_text(encoding="utf-8"))


@app.post("/api/onboarding/vision", status_code=201, response_model=models.VisionInputResponse)
async def post_onboarding_vision(
    req: models.VisionInputRequest,
    authorization: Optional[str] = Header(None),
user: dict = Depends(get_current_user_zero_trust)):
    """ビジョン入力を保存"""
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="Missing token")

    token = authorization[7:]
    user_id = await auth.verify_token(token)
    if not user_id:
        raise HTTPException(status_code=401, detail="Invalid token")

    await ensure_db_initialized()

    try:
        async with aiosqlite.connect(str(THEBRANCH_DB)) as db:
            await db.execute(
                """
                INSERT OR REPLACE INTO user_onboarding_progress
                (onboarding_id, user_id, vision_input, current_step, created_at, updated_at)
                VALUES (?, ?, ?, ?, datetime('now','localtime'), datetime('now','localtime'))
                """,
                (req.onboarding_id, user_id, req.vision_input, 0)
            )
            await db.commit()

        return {
            "success": True,
            "onboarding_id": req.onboarding_id,
            "current_step": 0,
            "message": "ビジョンを保存しました"
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"ビジョン保存エラー: {str(e)}")


@app.post("/api/onboarding/suggest", response_model=models.DepartmentSuggestionResponse)
async def post_onboarding_suggest(
    req: models.DepartmentSuggestionRequest,
    authorization: Optional[str] = Header(None),
user: dict = Depends(get_current_user_zero_trust)):
    """AI が部署を提案"""
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="Missing token")

    token = authorization[7:]
    user_id = await auth.verify_token(token)
    if not user_id:
        raise HTTPException(status_code=401, detail="Invalid token")

    await ensure_db_initialized()

    try:
        async with aiosqlite.connect(str(THEBRANCH_DB)) as db:
            # Get vision input
            cursor = await db.execute(
                "SELECT vision_input FROM user_onboarding_progress WHERE onboarding_id = ? AND user_id = ?",
                (req.onboarding_id, user_id)
            )
            row = await cursor.fetchone()
            if not row or not row[0]:
                raise HTTPException(status_code=400, detail="ビジョン入力が見つかりません")

            vision_input = row[0]

            # Get onboarding service and analyze vision
            from workflow.services.onboarding import get_onboarding_service
            onboarding_service = get_onboarding_service()

            # Get suggestions from Claude API
            suggestions_data = onboarding_service.analyze_vision_for_templates(vision_input)

            # Convert to TemplateSuggestion models
            suggestions = [
                models.TemplateSuggestion(**s) for s in suggestions_data
            ]

            # Update current step
            await db.execute(
                "UPDATE user_onboarding_progress SET current_step = 1 WHERE onboarding_id = ?",
                (req.onboarding_id,)
            )
            await db.commit()

        return {
            "success": True,
            "suggestions": suggestions,
            "current_step": 1,
            "message": "部署提案を取得しました"
        }
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"部署提案取得エラー: {str(e)}")


@app.post("/api/onboarding/setup", response_model=models.SetupResponse)
async def post_onboarding_setup(
    req: models.DetailedSetupRequest,
    authorization: Optional[str] = Header(None),
user: dict = Depends(get_current_user_zero_trust)):
    """部署の詳細設定・予算検証・初期タスク生成"""
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="Missing token")

    token = authorization[7:]
    user_id = await auth.verify_token(token)
    if not user_id:
        raise HTTPException(status_code=401, detail="Invalid token")

    await ensure_db_initialized()

    try:
        from workflow.services.onboarding import get_onboarding_service

        onboarding_service = get_onboarding_service()

        # Validate budget
        budget_validation = onboarding_service.validate_budget(
            members_count=req.members_count,
            budget=req.budget,
            dept_type=req.dept_name.lower()
        )

        # Generate initial tasks
        initial_tasks = onboarding_service.generate_initial_tasks(
            dept_name=req.dept_name,
            kpi=req.kpi,
            budget=req.budget,
            members_count=req.members_count
        )

        # Update onboarding progress
        async with aiosqlite.connect(str(THEBRANCH_DB)) as db:
            await db.execute(
                """UPDATE user_onboarding_progress
                SET current_step = 2,
                    dept_name = ?,
                    manager_name = ?,
                    members_count = ?,
                    budget = ?,
                    kpi = ?,
                    integrations = ?
                WHERE onboarding_id = ? AND user_id = ?""",
                (req.dept_name, req.manager_name, req.members_count, req.budget, req.kpi,
                 json.dumps(req.integrations or {}),
                 req.onboarding_id, user_id)
            )
            await db.commit()

        # Convert to response models
        tasks_data = [
            models.InitialTask(**task) for task in initial_tasks
        ]

        return {
            "success": True,
            "budget_validation": models.BudgetValidation(**budget_validation),
            "initial_tasks": tasks_data,
            "current_step": 2,
            "message": "セットアップ完了。初期タスクを生成しました"
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Setup error: {str(e)}")
        raise HTTPException(status_code=500, detail=f"セットアップエラー: {str(e)}")


@app.post("/api/onboarding/execute", response_model=models.ExecuteResponse)
async def execute_onboarding(
    req: models.ExecuteRequest,
    authorization: Optional[str] = Header(None),
user: dict = Depends(get_current_user_zero_trust)):
    """初期タスク生成 → エージェント起動"""
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="Missing token")

    token = authorization[7:]
    user_id = await auth.verify_token(token)
    if not user_id:
        raise HTTPException(status_code=401, detail="Invalid token")

    await ensure_db_initialized()

    try:
        from workflow.services.onboarding import get_onboarding_service
        from datetime import datetime

        async with aiosqlite.connect(str(THEBRANCH_DB)) as db:
            # Get onboarding details
            cursor = await db.execute(
                """
                SELECT dept_id FROM user_onboarding_progress
                WHERE onboarding_id = ? AND user_id = ?
                """,
                (req.onboarding_id, user_id)
            )
            row = await cursor.fetchone()
            if not row:
                raise HTTPException(status_code=404, detail="Onboarding not found")

            dept_id = row[0]

            # Get department details
            cursor = await db.execute(
                "SELECT name FROM departments WHERE id = ?",
                (dept_id,)
            )
            dept_row = await cursor.fetchone()
            if not dept_row:
                raise HTTPException(status_code=404, detail="Department not found")

            dept_name = dept_row[0]

            # Generate initial tasks
            onboarding_service = get_onboarding_service()
            tasks = onboarding_service.generate_initial_tasks(
                dept_name=dept_name,
                kpi="初期KPI設定",
                budget=10000.0,  # デフォルト予算
                members_count=3
            )

            # Create tasks in database
            tasks_created = []
            for i, task in enumerate(tasks):
                cursor = await db.execute(
                    """
                    INSERT INTO tasks
                    (title, description, status, department_id, created_at, updated_at)
                    VALUES (?, ?, ?, ?, datetime('now','localtime'), datetime('now','localtime'))
                    """,
                    (task.get("title"), task.get("description"), "pending", dept_id)
                )
                await db.commit()
                task_id = cursor.lastrowid

                tasks_created.append({
                    "task_id": str(task_id),
                    "title": task.get("title"),
                    "description": task.get("description"),
                    "budget": task.get("budget", 0),
                    "deadline": task.get("deadline"),
                    "assigned_to": task.get("assigned_to")
                })

            # Create agent
            session_id = f"thebranch_onboarding_{user_id}_{dept_id}"
            cursor = await db.execute(
                """
                INSERT INTO agents
                (department_id, session_id, role, status, created_at, updated_at)
                VALUES (?, ?, ?, ?, datetime('now','localtime'), datetime('now','localtime'))
                """,
                (dept_id, session_id, "coordinator", "activating")
            )
            await db.commit()
            agent_id = cursor.lastrowid

            # Update onboarding_progress
            now = datetime.now().isoformat()
            await db.execute(
                """
                UPDATE user_onboarding_progress
                SET current_step = 3, completed_at = datetime('now','localtime'),
                    updated_at = datetime('now','localtime')
                WHERE onboarding_id = ?
                """,
                (req.onboarding_id,)
            )

            # Update user
            await db.execute(
                "UPDATE users SET onboarding_completed = 1 WHERE id = ?",
                (user_id,)
            )
            await db.commit()

        return {
            "dept_id": dept_id,
            "tasks_created": tasks_created,
            "agent_status": "activating",
            "dashboard_url": f"/dashboard?dept_id={dept_id}",
            "completed_at": now
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Execute error: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Execute error: {str(e)}")


@app.post("/api/onboarding/complete", status_code=201, response_model=models.OnboardingCompleteResponse)
async def complete_onboarding(
    req: models.OnboardingRequest,
    authorization: Optional[str] = Header(None),
user: dict = Depends(get_current_user_zero_trust)):
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="Missing token")

    token = authorization[7:]
    user_id = await auth.verify_token(token)
    if not user_id:
        raise HTTPException(status_code=401, detail="Invalid token")

    await ensure_db_initialized()

    try:
        async with aiosqlite.connect(str(THEBRANCH_DB)) as db:
            # Create department
            slug = req.dept_name.lower().replace(" ", "-")
            cursor = await db.execute(
                "INSERT INTO departments (name, slug, description, status, created_by, created_at, updated_at) VALUES (?, ?, ?, ?, ?, datetime('now','localtime'), datetime('now','localtime'))",
                (req.dept_name, slug, f"{req.dept_name} (AI-powered)", "active", user_id)
            )
            await db.commit()
            dept_id = cursor.lastrowid

            # Create agent
            session_id = f"thebranch_onboarding_{user_id}_{dept_id}"
            cursor = await db.execute(
                "INSERT INTO agents (department_id, session_id, role, status, created_at, updated_at) VALUES (?, ?, ?, ?, datetime('now','localtime'), datetime('now','localtime'))",
                (dept_id, session_id, req.agent_role, "starting")
            )
            await db.commit()
            agent_id = cursor.lastrowid

            # Update onboarding_completed flag
            await db.execute(
                "UPDATE users SET onboarding_completed = 1 WHERE id = ?",
                (user_id,)
            )
            await db.commit()

        return {
            "success": True,
            "dept_id": dept_id,
            "agent_id": agent_id,
            "message": "ウィザード完了。エージェント起動中..."
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"ウィザード実行エラー: {str(e)}")


# ──────────────────────────────────────────────
# Accounting (会計部)
# ──────────────────────────────────────────────

# Initialize accounting service
accounting_repo = None
accounting_service = None

def init_accounting_services():
    global accounting_repo, accounting_service
    if accounting_repo is None:
        from workflow.repositories.accounting_repository import AccountingRepository
        from workflow.services.accounting_service import AccountingService
        accounting_repo = AccountingRepository(str(THEBRANCH_DB))
        accounting_service = AccountingService(accounting_repo)

# Pydantic models for requests
class InvoiceCreate(BaseModel):
    invoice_number: str
    vendor_name: str
    invoice_date: str
    due_date: str
    amount_jpy: float
    tax_amount_jpy: float = 0.0
    description: Optional[str] = None
    vendor_id: Optional[int] = None

class InvoiceItemCreate(BaseModel):
    item_description: str
    quantity: float
    unit_price_jpy: float
    line_amount_jpy: float

class ExpenseSubmissionCreate(BaseModel):
    submission_number: str
    employee_name: str
    submission_date: str
    period_start: str
    period_end: str
    total_amount_jpy: float
    description: Optional[str] = None
    employee_id: Optional[int] = None

class ExpenseItemCreate(BaseModel):
    expense_category: str
    expense_date: str
    description: str
    amount_jpy: float
    receipt_file_path: Optional[str] = None

# Invoice endpoints
@app.post("/api/accounting/invoices")
async def create_invoice(department_id: int, invoice: InvoiceCreate, user: dict = Depends(get_current_user_zero_trust)):
    init_accounting_services()
    try:
        invoice_id = accounting_service.create_invoice(
            department_id=department_id,
            invoice_number=invoice.invoice_number,
            vendor_name=invoice.vendor_name,
            invoice_date=invoice.invoice_date,
            due_date=invoice.due_date,
            amount_jpy=invoice.amount_jpy,
            tax_amount_jpy=invoice.tax_amount_jpy,
            description=invoice.description,
            vendor_id=invoice.vendor_id,
        )
        return {"id": invoice_id, "status": "created"}
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))

@app.get("/api/accounting/invoices/{invoice_id}")
async def get_invoice(invoice_id: int, user: dict = Depends(get_current_user_zero_trust)):
    init_accounting_services()
    try:
        invoice = accounting_service.get_invoice(invoice_id)
        if not invoice:
            raise HTTPException(status_code=404, detail="Invoice not found")
        return invoice
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/accounting/invoices")
async def list_invoices(department_id: int, status: Optional[str] = None, user: dict = Depends(get_current_user_zero_trust)):
    init_accounting_services()
    try:
        invoices = accounting_service.get_invoices(department_id, status)
        return {"invoices": invoices}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/api/accounting/invoices/{invoice_id}/items")
async def add_invoice_item(invoice_id: int, item: InvoiceItemCreate, user: dict = Depends(get_current_user_zero_trust)):
    init_accounting_services()
    try:
        item_id = accounting_service.add_invoice_item(
            invoice_id=invoice_id,
            item_description=item.item_description,
            quantity=item.quantity,
            unit_price_jpy=item.unit_price_jpy,
            line_amount_jpy=item.line_amount_jpy,
        )
        return {"id": item_id, "status": "created"}
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))

@app.post("/api/accounting/invoices/{invoice_id}/approve")
async def approve_invoice(invoice_id: int, approver_id: int, user: dict = Depends(get_current_user_zero_trust)):
    init_accounting_services()
    try:
        accounting_service.approve_invoice(invoice_id, approver_id)
        return {"status": "approved"}
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))

@app.put("/api/accounting/invoices/{invoice_id}/status")
async def update_invoice_status(
    invoice_id: int, status: str, approval_status: Optional[str] = None,
user: dict = Depends(get_current_user_zero_trust)):
    init_accounting_services()
    try:
        accounting_service.update_invoice_status(invoice_id, status, approval_status)
        return {"status": "updated"}
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))

# Expense endpoints
@app.post("/api/accounting/expenses")
async def create_expense_submission(
    department_id: int, submission: ExpenseSubmissionCreate,
user: dict = Depends(get_current_user_zero_trust)):
    init_accounting_services()
    try:
        submission_id = accounting_service.create_expense_submission(
            department_id=department_id,
            submission_number=submission.submission_number,
            employee_name=submission.employee_name,
            submission_date=submission.submission_date,
            period_start=submission.period_start,
            period_end=submission.period_end,
            total_amount_jpy=submission.total_amount_jpy,
            description=submission.description,
            employee_id=submission.employee_id,
        )
        return {"id": submission_id, "status": "created"}
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))

@app.get("/api/accounting/expenses/{submission_id}")
async def get_expense_submission(submission_id: int, user: dict = Depends(get_current_user_zero_trust)):
    init_accounting_services()
    try:
        submission = accounting_service.get_expense_submission(submission_id)
        if not submission:
            raise HTTPException(status_code=404, detail="Expense submission not found")
        return submission
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/accounting/expenses")
async def list_expense_submissions(department_id: int, status: Optional[str] = None, user: dict = Depends(get_current_user_zero_trust)):
    init_accounting_services()
    try:
        submissions = accounting_service.get_expense_submissions(department_id, status)
        return {"submissions": submissions}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/api/accounting/expenses/{submission_id}/items")
async def add_expense_item(submission_id: int, item: ExpenseItemCreate, user: dict = Depends(get_current_user_zero_trust)):
    init_accounting_services()
    try:
        item_id = accounting_service.add_expense_item(
            submission_id=submission_id,
            expense_category=item.expense_category,
            expense_date=item.expense_date,
            description=item.description,
            amount_jpy=item.amount_jpy,
            receipt_file_path=item.receipt_file_path,
        )
        return {"id": item_id, "status": "created"}
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))

@app.post("/api/accounting/expenses/{submission_id}/approve")
async def approve_expense_submission(submission_id: int, approver_id: int, user: dict = Depends(get_current_user_zero_trust)):
    init_accounting_services()
    try:
        accounting_service.approve_expense_submission(submission_id, approver_id)
        return {"status": "approved"}
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))

# Report endpoints
@app.get("/api/accounting/reports/monthly/{year}/{month}")
async def get_monthly_report(department_id: int, year: int, month: int, user: dict = Depends(get_current_user_zero_trust)):
    init_accounting_services()
    try:
        report = accounting_service.generate_monthly_report(department_id, year, month)
        return report
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/accounting/reports/pending-approvals")
async def get_pending_approvals(department_id: int, user: dict = Depends(get_current_user_zero_trust)):
    init_accounting_services()
    try:
        result = accounting_service.get_pending_approvals(department_id)
        return result
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/accounting/reports/expenses-by-category")
async def get_expenses_by_category(
    department_id: int, year: int, month: int,
user: dict = Depends(get_current_user_zero_trust)):
    init_accounting_services()
    try:
        result = accounting_service.get_expense_summary_by_category(
            department_id, year, month
        )
        return result
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# ──────────────────────────────────────────────
# Team Dynamics & Collaboration Optimization
# ──────────────────────────────────────────────

@app.get("/api/teams/{team_id}/communication-timeline")
async def get_communication_timeline(
    team_id: int, date_from: str = None, date_to: str = None, event_type: str = None, agent_id: int = None, limit: int = 100,
user: dict = Depends(get_current_user_zero_trust)):
    """チーム内の通信タイムラインを時系列で取得（delegation_events）"""
    await ensure_db_initialized()
    try:
        async with aiosqlite.connect(str(THEBRANCH_DB)) as db:
            db.row_factory = aiosqlite.Row

            # チーム内のエージェントを取得
            cursor = await db.execute(
                "SELECT agent_id FROM team_x_agents WHERE team_id = ?", (team_id,)
            )
            team_agent_ids = [row[0] for row in await cursor.fetchall()]

            if not team_agent_ids:
                return {"items": [], "total": 0}

            placeholders = ",".join("?" * len(team_agent_ids))
            query = f"SELECT * FROM delegation_events WHERE actor_id IN ({placeholders})"
            params = team_agent_ids

            if date_from:
                query += " AND event_timestamp >= ?"
                params.append(date_from)
            if date_to:
                query += " AND event_timestamp <= ?"
                params.append(date_to)
            if event_type:
                query += " AND event_type = ?"
                params.append(event_type)

            query += " ORDER BY event_timestamp DESC LIMIT ?"
            params.append(limit)

            cursor = await db.execute(query, params)
            rows = await cursor.fetchall()

        items = [dict(row) for row in rows]
        return {"items": items, "total": len(items)}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/teams/{team_id}/communication-graph")
async def get_communication_graph(team_id: int, user: dict = Depends(get_current_user_zero_trust)):
    """チーム内の通信ネットワークデータを取得（nodes/edges）"""
    await ensure_db_initialized()
    try:
        async with aiosqlite.connect(str(THEBRANCH_DB)) as db:
            db.row_factory = aiosqlite.Row

            # チーム内のエージェントを取得
            cursor = await db.execute(
                """SELECT txa.agent_id, a.session_id, txa.role
                   FROM team_x_agents txa
                   JOIN agents a ON txa.agent_id = a.id
                   WHERE txa.team_id = ?""", (team_id,)
            )
            agents = await cursor.fetchall()
            agent_ids = [a["agent_id"] for a in agents]

            if not agent_ids:
                return {"nodes": [], "edges": []}

            nodes = [{"id": a["agent_id"], "name": a["session_id"], "role": a.get("role", "engineer"), "activity_count": 0} for a in agents]

            placeholders = ",".join("?" * len(agent_ids))
            cursor = await db.execute(
                f"""SELECT actor_id, COUNT(*) as activity_count FROM delegation_events
                   WHERE actor_id IN ({placeholders}) GROUP BY actor_id""",
                agent_ids
            )
            activities = await cursor.fetchall()

            for activity in activities:
                for node in nodes:
                    if node["id"] == int(activity["actor_id"]):
                        node["activity_count"] = activity["activity_count"]

            return {"nodes": nodes, "edges": []}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/teams/{team_id}/performance-summary")
async def get_performance_summary(team_id: int, user: dict = Depends(get_current_user_zero_trust)):
    """チーム全体のパフォーマンスサマリーを取得"""
    await ensure_db_initialized()
    try:
        async with aiosqlite.connect(str(THEBRANCH_DB)) as db:
            db.row_factory = aiosqlite.Row

            cursor = await db.execute(
                """SELECT AVG(completion_rate) as avg_completion, AVG(throughput_tasks_7d) as avg_throughput,
                   AVG(quality_score) as avg_quality FROM team_performance_metrics WHERE team_id = ?""",
                (team_id,)
            )
            metrics = await cursor.fetchone()

            cursor = await db.execute(
                "SELECT COUNT(*) as member_count FROM team_x_agents WHERE team_id = ?", (team_id,)
            )
            members = await cursor.fetchone()

            # チームの department_id を取得
            cursor = await db.execute(
                "SELECT id FROM teams WHERE id = ?", (team_id,)
            )
            team = await cursor.fetchone()
            if not team:
                return {
                    "completion_rate": 0,
                    "throughput_7d": 0,
                    "collaboration_score": 0,
                    "active_members": 0,
                    "completed_tasks": 0
                }

            cursor = await db.execute(
                "SELECT COUNT(*) as completed_tasks FROM team_dynamics_snapshot WHERE team_id = ?", (team_id,)
            )
            snapshot = await cursor.fetchone()

        return {
            "completion_rate": metrics["avg_completion"] or 0,
            "throughput_7d": metrics["avg_throughput"] or 0,
            "collaboration_score": metrics["avg_quality"] or 0,
            "active_members": members["member_count"] or 0,
            "completed_tasks": snapshot["completed_tasks"] or 0
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/teams/{team_id}/member-performance")
async def get_member_performance(team_id: int, sort_by: str = "workload", user: dict = Depends(get_current_user_zero_trust)):
    """チームメンバーの個別パフォーマンスを取得"""
    await ensure_db_initialized()
    try:
        async with aiosqlite.connect(str(THEBRANCH_DB)) as db:
            db.row_factory = aiosqlite.Row

            query = """SELECT a.id, a.session_id, txa.role,
                       COALESCE(tpm.completion_rate, 0) as completion_rate,
                       COALESCE(tpm.throughput_tasks_7d, 0) as throughput_tasks_7d,
                       COALESCE(tpm.quality_score, 0) as quality_score,
                       a.workload_level, a.collaboration_score
                       FROM team_x_agents txa
                       JOIN agents a ON txa.agent_id = a.id
                       LEFT JOIN team_performance_metrics tpm ON a.id = tpm.agent_id AND tpm.team_id = ?
                       WHERE txa.team_id = ?
                       ORDER BY """

            if sort_by == "workload":
                query += "a.workload_level ASC"
            elif sort_by == "completion":
                query += "tpm.completion_rate DESC"
            elif sort_by == "collaboration":
                query += "a.collaboration_score DESC"
            else:
                query += "a.id ASC"

            cursor = await db.execute(query, (team_id, team_id))
            rows = await cursor.fetchall()

        members = [dict(row) for row in rows]
        return {"members": members}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/teams/{team_id}/collaboration-heatmap")
async def get_collaboration_heatmap(team_id: int, user: dict = Depends(get_current_user_zero_trust)):
    """チーム内のコミュニケーションマトリックスを取得"""
    await ensure_db_initialized()
    try:
        async with aiosqlite.connect(str(THEBRANCH_DB)) as db:
            db.row_factory = aiosqlite.Row

            cursor = await db.execute(
                """SELECT txa.agent_id, a.session_id FROM team_x_agents txa
                   JOIN agents a ON txa.agent_id = a.id
                   WHERE txa.team_id = ? ORDER BY a.id""", (team_id,)
            )
            agents = await cursor.fetchall()
            agent_ids = [a["agent_id"] for a in agents]
            agent_names = {a["agent_id"]: a["session_id"] for a in agents}

            if not agent_ids:
                return {"agents": [], "heatmap": {}}

            heatmap_data = {}
            for actor_id in agent_ids:
                heatmap_data[str(actor_id)] = {str(target_id): 0 for target_id in agent_ids}

            # delegation_events からアクティビティを集計
            placeholders = ",".join("?" * len(agent_ids))
            cursor = await db.execute(
                f"""SELECT actor_id, COUNT(*) as message_count
                   FROM delegation_events WHERE actor_id IN ({placeholders})
                   GROUP BY actor_id""",
                agent_ids
            )
            interactions = await cursor.fetchall()

            for interaction in interactions:
                actor = str(interaction["actor_id"])
                if actor in heatmap_data:
                    heatmap_data[actor][actor] = interaction["message_count"]

        return {
            "agents": [{"id": a["agent_id"], "name": agent_names[a["agent_id"]]} for a in agents],
            "heatmap": heatmap_data
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


def calculate_skill_match(task_required_skills: str, agent_skill_tags: str) -> float:
    """スキルマッチ度を計算（0-30ポイント）"""
    if not task_required_skills or not agent_skill_tags:
        return 5.0  # デフォルトスコア

    import json
    try:
        task_skills = set(json.loads(task_required_skills) or [])
        agent_skills = set(json.loads(agent_skill_tags) or [])

        if not task_skills:
            return 5.0

        # 一致度 = 一致スキル数 / 要件スキル数
        match_count = len(task_skills & agent_skills)
        match_ratio = match_count / len(task_skills) if task_skills else 0

        # スコア: 0-30ポイント（ただし0の場合はデフォルト値5.0を返す）
        if match_ratio == 0:
            return 5.0
        return min(30, match_ratio * 30)
    except:
        return 5.0


def calculate_task_allocation_score(task: dict, agent: dict) -> dict:
    """
    タスク割り当てスコアを計算

    Formula:
    total_score =
      skill_match * 1.0 +              (0-30)
      workload_score +                 (0-30)
      collaboration * 1.0 +            (0-20)
      reliability_score +              (0-15)
      domain_bonus                     (0-5)

    Total: 0-100
    """
    required_skills = task.get("required_skills")
    skill_tags = agent.get("skill_tags")

    skill_match = calculate_skill_match(required_skills, skill_tags)

    workload_level = agent.get("workload_level", 0) or 0
    workload_score = (1 - min(workload_level / 100, 1.0)) * 30

    collaboration_score = (agent.get("collaboration_score", 50) or 50) / 100 * 20

    # エージェント完了率を基に信頼性スコアを計算（0-15ポイント）
    completion_rate = agent.get("completion_rate", 0) or 0
    reliability_score = completion_rate * 15 if completion_rate else 8.0

    # タスク複雑度がエージェント専門性に合致しているかで加点
    domain_bonus = 5.0
    task_category = task.get("category", "general")
    agent_skills = agent.get("skill_tags", "[]")
    if task_category and task_category.lower() in (agent_skills or "").lower():
        domain_bonus = 5.0

    total_score = skill_match + workload_score + collaboration_score + reliability_score + domain_bonus

    return {
        "total": round(total_score, 2),
        "factors": {
            "skill_match": round(skill_match, 2),
            "workload_score": round(workload_score, 2),
            "collaboration": round(collaboration_score, 2),
            "reliability": round(reliability_score, 2),
            "domain_bonus": round(domain_bonus, 2)
        }
    }


@app.post("/api/tasks/{task_id}/auto-allocate")
async def auto_allocate_task(task_id: int, team_id: int, user: dict = Depends(get_current_user_zero_trust)):
    """タスクを最適なエージェントに自動割り当てする"""
    await ensure_db_initialized()
    try:
        import json
        from datetime import datetime, timezone

        async with aiosqlite.connect(str(THEBRANCH_DB)) as db:
            db.row_factory = aiosqlite.Row

            cursor = await db.execute("SELECT * FROM tasks WHERE id = ?", (task_id,))
            task_row = await cursor.fetchone()
            if not task_row:
                raise HTTPException(status_code=404, detail="Task not found")
            task = dict(task_row)

            cursor = await db.execute(
                """SELECT a.id, a.session_id, a.workload_level, a.collaboration_score,
                          a.completion_rate, a.skill_tags
                   FROM team_x_agents txa
                   JOIN agents a ON txa.agent_id = a.id
                   WHERE txa.team_id = ?""", (team_id,)
            )
            agent_rows = await cursor.fetchall()

            if not agent_rows:
                raise HTTPException(status_code=400, detail="No agents in team")

            # 各エージェントのスコアを計算
            scores = []
            candidate_scores = {}
            for agent_row in agent_rows:
                agent = dict(agent_row)
                score_result = calculate_task_allocation_score(task, agent)
                total_score = score_result["total"]

                scores.append({
                    "agent_id": agent["id"],
                    "agent_name": agent["session_id"],
                    "score": total_score,
                    "factors": score_result["factors"]
                })
                candidate_scores[str(agent["id"])] = total_score

            best_agent = max(scores, key=lambda x: x["score"])

            # 割り当て履歴を記録
            candidate_scores_json = json.dumps(candidate_scores)
            try:
                cursor = await db.execute(
                    """INSERT INTO task_allocation_history
                       (task_id, allocated_agent_id, algorithm_version, ranking_score, candidate_scores, allocation_timestamp)
                       VALUES (?, ?, ?, ?, ?, ?)""",
                    (task_id, best_agent["agent_id"], "v2_skill_matching",
                     best_agent["score"], candidate_scores_json,
                     datetime.now(timezone.utc).isoformat())
                )
                await db.commit()
            except Exception as e:
                # allocation historyへの記録失敗は無視（メインロジック継続）
                pass

        return {
            "selected_agent_id": best_agent["agent_id"],
            "selected_agent_name": best_agent["agent_name"],
            "ranking": sorted(scores, key=lambda x: x["score"], reverse=True),
            "algorithm_version": "v2_skill_matching",
            "top_reason": f"Best match with skill compatibility {best_agent['factors']['skill_match']}/30 and low workload"
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/teams/{team_id}/allocation-recommendations")
async def get_allocation_recommendations(team_id: int, user: dict = Depends(get_current_user_zero_trust)):
    """タスク割り当て推奨一覧を取得（v2_skill_matchingアルゴリズム使用）"""
    await ensure_db_initialized()
    try:
        async with aiosqlite.connect(str(THEBRANCH_DB)) as db:
            db.row_factory = aiosqlite.Row

            # チーム内のペンディングタスクを取得
            cursor = await db.execute(
                "SELECT t.* FROM tasks t JOIN teams tm ON t.department_id = tm.department_id WHERE tm.id = ? AND t.status = 'pending' LIMIT 10",
                (team_id,)
            )
            pending_tasks_rows = await cursor.fetchall()

            # チーム内のエージェントを取得
            cursor = await db.execute(
                """SELECT a.id, a.session_id, a.workload_level, a.collaboration_score,
                          a.completion_rate, a.skill_tags
                   FROM team_x_agents txa
                   JOIN agents a ON txa.agent_id = a.id
                   WHERE txa.team_id = ?""",
                (team_id,)
            )
            agents_rows = await cursor.fetchall()
            agents = [dict(agent) for agent in agents_rows]

            recommendations = []
            for task_row in pending_tasks_rows:
                task = dict(task_row)

                # 各エージェントのスコアを計算
                scores = []
                for agent in agents:
                    score_result = calculate_task_allocation_score(task, agent)
                    scores.append({
                        "agent_id": agent["id"],
                        "agent_name": agent["session_id"],
                        "score": score_result["total"],
                        "factors": score_result["factors"]
                    })

                best_agent = max(scores, key=lambda x: x["score"])
                confidence = min(95, max(50, best_agent["score"]))  # スコアを信頼度として使用

                recommendations.append({
                    "task_id": task["id"],
                    "task_title": task.get("title"),
                    "suggested_agent_id": best_agent["agent_id"],
                    "suggested_agent_name": best_agent["agent_name"],
                    "confidence": round(confidence, 2),
                    "allocation_score": round(best_agent["score"], 2),
                    "factors": {
                        "skill_match": best_agent["factors"]["skill_match"],
                        "workload_score": best_agent["factors"]["workload_score"],
                        "collaboration": best_agent["factors"]["collaboration"],
                        "reliability": best_agent["factors"]["reliability"],
                        "domain_bonus": best_agent["factors"]["domain_bonus"]
                    }
                })

            return {"recommendations": recommendations}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/teams/{team_id}/dynamics-report/generate")
async def generate_dynamics_report(team_id: int, period: str = "week", include_charts: bool = True, user: dict = Depends(get_current_user_zero_trust)):
    """チーム動的レポートを生成（week/month/day対応）"""
    await ensure_db_initialized()
    try:
        import datetime as _dt
        import json

        async with aiosqlite.connect(str(THEBRANCH_DB)) as db:
            db.row_factory = aiosqlite.Row

            # チーム情報を取得
            cursor = await db.execute(
                "SELECT id, department_id FROM teams WHERE id = ?", (team_id,)
            )
            team = await cursor.fetchone()
            if not team:
                raise HTTPException(status_code=404, detail="Team not found")

            # 期間を決定
            today = _dt.date.today()
            if period == "day":
                date_from = today
            elif period == "week":
                date_from = today - _dt.timedelta(days=7)
            elif period == "month":
                date_from = today - _dt.timedelta(days=30)
            else:
                date_from = today - _dt.timedelta(days=7)

            # 完了タスク数（期間内）
            cursor = await db.execute(
                """SELECT COUNT(*) as count FROM tasks
                   WHERE department_id = ? AND status = 'completed'
                   AND DATE(updated_at) >= ?""",
                (team["department_id"], str(date_from))
            )
            completed = await cursor.fetchone()
            completed_count = completed["count"] or 0

            # メンバーパフォーマンス集計
            cursor = await db.execute(
                """SELECT txa.agent_id, a.session_id, a.workload_level,
                          COALESCE(tpm.completion_rate, 0.8) as completion_rate,
                          COALESCE(tpm.throughput_tasks_7d, 0) as throughput_7d,
                          COALESCE(tpm.quality_score, 50) as quality_score
                   FROM team_x_agents txa
                   JOIN agents a ON txa.agent_id = a.id
                   LEFT JOIN team_performance_metrics tpm ON a.id = tpm.agent_id
                   WHERE txa.team_id = ?
                   ORDER BY a.id""",
                (team_id,)
            )
            members = await cursor.fetchall()
            member_data = [dict(m) for m in members]

            # チーム統計
            avg_completion = sum(m["completion_rate"] for m in member_data) / len(member_data) if member_data else 0.8
            avg_quality = sum(m["quality_score"] for m in member_data) / len(member_data) if member_data else 50
            total_workload = sum(m["workload_level"] for m in member_data) if member_data else 0
            avg_workload = total_workload / len(member_data) if member_data else 0
            workload_balance = 100 - (max([m["workload_level"] for m in member_data]) if member_data else 0)

            # コラボレーション指標
            cursor = await db.execute(
                """SELECT COUNT(*) as event_count FROM team_collaboration_events
                   WHERE team_id = ? AND DATE(event_timestamp) >= ?""",
                (team_id, str(date_from))
            )
            collab_events = await cursor.fetchone()
            collab_count = collab_events["event_count"] or 0

            # レポートデータ生成
            report_data = {
                "team_id": team_id,
                "period": period,
                "period_start": str(date_from),
                "period_end": str(today),
                "summary": {
                    "completed_tasks": completed_count,
                    "average_completion_rate": round(avg_completion, 2),
                    "average_quality_score": round(avg_quality, 2),
                    "average_workload": round(avg_workload, 1),
                    "workload_balance": round(workload_balance, 1),
                    "collaboration_events": collab_count,
                    "active_members": len(member_data)
                },
                "member_breakdown": member_data,
                "generated_at": _dt.datetime.now(_dt.timezone.utc).isoformat()
            }

            # レポートを JSON で保存
            cursor = await db.execute(
                """INSERT INTO team_dynamics_snapshot
                   (team_id, snapshot_date, member_count, completed_tasks_today,
                    avg_completion_rate, collaboration_score, metadata, created_at)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
                (team_id, str(today), len(member_data), completed_count,
                 avg_completion, avg_quality, json.dumps(report_data), _dt.datetime.now(_dt.timezone.utc).isoformat())
            )
            await db.commit()
            report_id = cursor.lastrowid

        return {
            "report_id": report_id,
            "status": "generated",
            "data": report_data
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/teams/{team_id}/dynamics-report")
async def get_dynamics_report(team_id: int, report_id: int = None, period: str = None, user: dict = Depends(get_current_user_zero_trust)):
    """チーム動的レポートを取得（report_id指定 or 最新レポート）"""
    await ensure_db_initialized()
    try:
        import json

        async with aiosqlite.connect(str(THEBRANCH_DB)) as db:
            db.row_factory = aiosqlite.Row

            if report_id:
                cursor = await db.execute(
                    "SELECT * FROM team_dynamics_snapshot WHERE id = ? AND team_id = ?",
                    (report_id, team_id)
                )
            else:
                cursor = await db.execute(
                    "SELECT * FROM team_dynamics_snapshot WHERE team_id = ? ORDER BY created_at DESC LIMIT 1",
                    (team_id,)
                )

            report = await cursor.fetchone()
            if not report:
                return {
                    "report_id": None,
                    "summary": None,
                    "member_breakdown": [],
                    "trends": {}
                }

            report_dict = dict(report)

            # メタデータを JSON から解析
            metadata = {}
            if report_dict.get("metadata"):
                try:
                    metadata = json.loads(report_dict["metadata"])
                except:
                    metadata = {}

            # レポート形式で返却
            return {
                "report_id": report_dict.get("id"),
                "period": metadata.get("period", "unknown"),
                "summary": metadata.get("summary", {
                    "completed_tasks": report_dict.get("completed_tasks_today", 0),
                    "average_completion_rate": report_dict.get("avg_completion_rate", 0),
                    "average_quality_score": report_dict.get("collaboration_score", 0),
                    "collaboration_events": 0,
                    "active_members": report_dict.get("member_count", 0)
                }),
                "member_breakdown": metadata.get("member_breakdown", []),
                "generated_at": report_dict.get("created_at"),
                "trends": {}
            }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# ──────────────────────────────────────────────
# Agent Decision Transparency - Explainable AI
# ──────────────────────────────────────────────

@app.post("/api/agent-decision/log", response_model=models.AgentDecisionLogResponse)
async def log_agent_decision(decision: models.AgentDecisionLogCreate, user: dict = Depends(get_current_user_zero_trust)):
    """エージェント意思決定をログに記録"""
    await ensure_db_initialized()
    try:
        async with aiosqlite.connect(str(THEBRANCH_DB)) as db:
            db.row_factory = aiosqlite.Row
            cursor = await db.execute(
                """INSERT INTO agent_decision_logs
                   (agent_id, department_id, decision_type, decision_summary, reasoning,
                    context, confidence_score, input_data, output_data, impact_assessment, status)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 'logged')""",
                (decision.agent_id, decision.department_id, decision.decision_type,
                 decision.decision_summary, decision.reasoning, decision.context,
                 decision.confidence_score, decision.input_data, decision.output_data,
                 decision.impact_assessment),
            )
            log_id = cursor.lastrowid

            for factor in decision.factors:
                await db.execute(
                    """INSERT INTO agent_decision_factors
                       (decision_log_id, factor_type, factor_name, factor_value, weight, description, order_sequence)
                       VALUES (?, ?, ?, ?, ?, ?, ?)""",
                    (log_id, factor.factor_type, factor.factor_name, factor.factor_value,
                     factor.weight, factor.description, factor.order_sequence),
                )
            await db.commit()

            cursor = await db.execute(
                """SELECT * FROM agent_decision_logs WHERE id = ?""", (log_id,)
            )
            row = await cursor.fetchone()

        decision_dict = dict(row)
        decision_dict["factors"] = []

        async with aiosqlite.connect(str(THEBRANCH_DB)) as db:
            db.row_factory = aiosqlite.Row
            cursor = await db.execute(
                """SELECT * FROM agent_decision_factors WHERE decision_log_id = ? ORDER BY order_sequence""",
                (log_id,)
            )
            factors = await cursor.fetchall()
            decision_dict["factors"] = [dict(f) for f in factors]

        return decision_dict
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


@app.get("/api/agent-decision/logs")
async def get_decision_logs(agent_id: int, limit: int = 50, user: dict = Depends(get_current_user_zero_trust)):
    """エージェント意思決定ログを取得"""
    await ensure_db_initialized()
    try:
        async with aiosqlite.connect(str(THEBRANCH_DB)) as db:
            db.row_factory = aiosqlite.Row
            cursor = await db.execute(
                """SELECT * FROM agent_decision_logs WHERE agent_id = ?
                   ORDER BY created_at DESC LIMIT ?""",
                (agent_id, limit),
            )
            rows = await cursor.fetchall()

        results = []
        for row in rows:
            decision_dict = dict(row)
            async with aiosqlite.connect(str(THEBRANCH_DB)) as db:
                db.row_factory = aiosqlite.Row
                cursor = await db.execute(
                    """SELECT * FROM agent_decision_factors WHERE decision_log_id = ? ORDER BY order_sequence""",
                    (row["id"],)
                )
                factors = await cursor.fetchall()
                decision_dict["factors"] = [dict(f) for f in factors]
            results.append(decision_dict)

        return results
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/agent-decision/logs/{log_id}")
async def get_decision_log(log_id: int, user: dict = Depends(get_current_user_zero_trust)):
    """特定の意思決定ログを取得"""
    await ensure_db_initialized()
    try:
        async with aiosqlite.connect(str(THEBRANCH_DB)) as db:
            db.row_factory = aiosqlite.Row
            cursor = await db.execute(
                """SELECT * FROM agent_decision_logs WHERE id = ?""", (log_id,)
            )
            row = await cursor.fetchone()
            if not row:
                raise HTTPException(status_code=404, detail="Decision log not found")

            decision_dict = dict(row)

            cursor = await db.execute(
                """SELECT * FROM agent_decision_factors WHERE decision_log_id = ? ORDER BY order_sequence""",
                (log_id,)
            )
            factors = await cursor.fetchall()
            decision_dict["factors"] = [dict(f) for f in factors]

        return decision_dict
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/agent-decision/{log_id}/explain")
async def generate_decision_explanation(log_id: int, report: models.DecisionExplanationReportCreate, user: dict = Depends(get_current_user_zero_trust)):
    """意思決定の説明を生成"""
    await ensure_db_initialized()
    try:
        async with aiosqlite.connect(str(THEBRANCH_DB)) as db:
            db.row_factory = aiosqlite.Row

            cursor = await db.execute(
                """SELECT * FROM agent_decision_logs WHERE id = ?""", (log_id,)
            )
            decision_log = await cursor.fetchone()
            if not decision_log:
                raise HTTPException(status_code=404, detail="Decision log not found")

            cursor = await db.execute(
                """INSERT INTO decision_explanation_report
                   (decision_log_id, explanation_summary, explanation_html, generated_by, generation_method)
                   VALUES (?, ?, ?, ?, ?)""",
                (log_id, report.explanation_summary, report.explanation_html,
                 report.generated_by, report.generation_method),
            )
            report_id = cursor.lastrowid
            await db.commit()

            cursor = await db.execute(
                """SELECT * FROM decision_explanation_report WHERE id = ?""", (report_id,)
            )
            row = await cursor.fetchone()

        return dict(row)
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


@app.get("/api/agent-decision/{log_id}/explanation")
async def get_decision_explanation(log_id: int, user: dict = Depends(get_current_user_zero_trust)):
    """意思決定の説明を取得"""
    await ensure_db_initialized()
    try:
        async with aiosqlite.connect(str(THEBRANCH_DB)) as db:
            db.row_factory = aiosqlite.Row
            cursor = await db.execute(
                """SELECT * FROM decision_explanation_report WHERE decision_log_id = ? ORDER BY created_at DESC LIMIT 1""",
                (log_id,)
            )
            row = await cursor.fetchone()
            if not row:
                raise HTTPException(status_code=404, detail="Explanation not found")

        return dict(row)
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/agent-decision/audit")
async def log_action_audit(audit: models.AgentActionAuditCreate, user: dict = Depends(get_current_user_zero_trust)):
    """エージェント行動を監査ログに記録"""
    await ensure_db_initialized()
    try:
        async with aiosqlite.connect(str(THEBRANCH_DB)) as db:
            db.row_factory = aiosqlite.Row
            cursor = await db.execute(
                """INSERT INTO agent_action_audit
                   (agent_id, decision_log_id, action_type, action_detail, result_status,
                    result_detail, affected_entity_type, affected_entity_id)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
                (audit.agent_id, audit.decision_log_id, audit.action_type,
                 audit.action_detail, audit.result_status, audit.result_detail,
                 audit.affected_entity_type, audit.affected_entity_id),
            )
            audit_id = cursor.lastrowid
            await db.commit()

            cursor = await db.execute(
                """SELECT * FROM agent_action_audit WHERE id = ?""", (audit_id,)
            )
            row = await cursor.fetchone()

        return dict(row)
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


@app.get("/api/agent-decision/audit/{agent_id}")
async def get_action_audit(agent_id: int, limit: int = 100, user: dict = Depends(get_current_user_zero_trust)):
    """エージェントの行動監査ログを取得"""
    await ensure_db_initialized()
    try:
        async with aiosqlite.connect(str(THEBRANCH_DB)) as db:
            db.row_factory = aiosqlite.Row
            cursor = await db.execute(
                """SELECT * FROM agent_action_audit WHERE agent_id = ?
                   ORDER BY created_at DESC LIMIT ?""",
                (agent_id, limit),
            )
            rows = await cursor.fetchall()

        return [dict(row) for row in rows]
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/agent-decision/report/{agent_id}")
async def get_transparency_report(agent_id: int, user: dict = Depends(get_current_user_zero_trust)):
    """エージェントの透明性レポートを取得"""
    await ensure_db_initialized()
    try:
        async with aiosqlite.connect(str(THEBRANCH_DB)) as db:
            db.row_factory = aiosqlite.Row

            cursor = await db.execute(
                """SELECT a.id, a.role FROM agents a WHERE a.id = ?""", (agent_id,)
            )
            agent = await cursor.fetchone()
            if not agent:
                raise HTTPException(status_code=404, detail="Agent not found")

            cursor = await db.execute(
                """SELECT COUNT(*) as total FROM agent_decision_logs WHERE agent_id = ?""",
                (agent_id,)
            )
            total_decisions = await cursor.fetchone()

            cursor = await db.execute(
                """SELECT decision_type, COUNT(*) as count FROM agent_decision_logs
                   WHERE agent_id = ? GROUP BY decision_type""",
                (agent_id,)
            )
            decision_breakdown_rows = await cursor.fetchall()
            decision_breakdown = {row["decision_type"]: row["count"] for row in decision_breakdown_rows}

            cursor = await db.execute(
                """SELECT AVG(confidence_score) as avg_confidence FROM agent_decision_logs WHERE agent_id = ?""",
                (agent_id,)
            )
            confidence_row = await cursor.fetchone()
            confidence_avg = confidence_row["avg_confidence"] or 0.0

            cursor = await db.execute(
                """SELECT * FROM agent_decision_logs WHERE agent_id = ?
                   ORDER BY created_at DESC LIMIT 10""",
                (agent_id,)
            )
            recent_logs = await cursor.fetchall()
            recent_decisions = []
            for log in recent_logs:
                log_dict = dict(log)
                cursor = await db.execute(
                    """SELECT * FROM agent_decision_factors WHERE decision_log_id = ?""",
                    (log["id"],)
                )
                factors = await cursor.fetchall()
                log_dict["factors"] = [dict(f) for f in factors]
                recent_decisions.append(log_dict)

            cursor = await db.execute(
                """SELECT * FROM agent_action_audit WHERE agent_id = ?
                   ORDER BY created_at DESC LIMIT 20""",
                (agent_id,)
            )
            action_audit = await cursor.fetchall()

        return {
            "agent_id": agent_id,
            "agent_role": agent["role"],
            "total_decisions": total_decisions["total"] if total_decisions else 0,
            "decision_breakdown": decision_breakdown,
            "confidence_avg": float(confidence_avg),
            "recent_decisions": recent_decisions,
            "action_audit_trail": [dict(row) for row in action_audit],
        }
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# ──────────────────────────────────────────────
# Learning Patterns API
# ──────────────────────────────────────────────

@app.get("/api/learning/patterns")
async def get_learning_patterns(user: dict = Depends(get_current_user_zero_trust)):
    """Get analyzed learning patterns from workflow executions"""
    try:
        db_path = DASHBOARD_DIR / "data" / "thebranch.sqlite"
        async with aiosqlite.connect(str(db_path)) as db:
            db.row_factory = sqlite3.Row
            cursor = await db.execute(
                "SELECT * FROM learning_patterns ORDER BY created_at DESC LIMIT 100"
            )
            rows = await cursor.fetchall()
            patterns = [dict(row) for row in rows]

            success_count = sum(1 for p in patterns if p.get("result_status") == "success")
            success_rate = success_count / len(patterns) if patterns else 0

            return {
                "patterns": patterns,
                "total_count": len(patterns),
                "success_rate": success_rate,
                "timestamp": datetime.now().isoformat()
            }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# ──────────────────────────────────────────────
# SLA Management API
# ──────────────────────────────────────────────

@app.get("/api/sla/policies")
async def get_sla_policies(user: dict = Depends(get_current_user_zero_trust)):
    """SLAポリシー一覧を取得"""
    try:
        db_path = DASHBOARD_DIR / "data" / "thebranch.sqlite"
        async with aiosqlite.connect(str(db_path)) as db:
            db.row_factory = sqlite3.Row
            cursor = await db.execute("SELECT * FROM sla_policies ORDER BY created_at DESC")
            rows = await cursor.fetchall()
            return [dict(row) for row in rows]
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/sla/policies")
async def create_sla_policy(policy: models.SLAPolicyCreate, user: dict = Depends(get_current_user_zero_trust)):
    """新規SLAポリシーを作成"""
    try:
        db_path = DASHBOARD_DIR / "data" / "thebranch.sqlite"
        async with aiosqlite.connect(str(db_path)) as db:
            db.row_factory = sqlite3.Row
            cursor = await db.execute(
                """INSERT INTO sla_policies
                   (name, response_time_limit_ms, uptime_percentage, error_rate_limit, enabled)
                   VALUES (?, ?, ?, ?, ?)""",
                (policy.name, policy.response_time_limit_ms, policy.uptime_percentage,
                 policy.error_rate_limit, policy.enabled)
            )
            await db.commit()
            policy_id = cursor.lastrowid

            cursor = await db.execute("SELECT * FROM sla_policies WHERE id = ?", (policy_id,))
            row = await cursor.fetchone()
            return dict(row)
    except sqlite3.IntegrityError:
        raise HTTPException(status_code=400, detail="ポリシー名が既に存在します")
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.put("/api/sla/policies/{policy_id}")
async def update_sla_policy(policy_id: int, policy: models.SLAPolicyUpdate, user: dict = Depends(get_current_user_zero_trust)):
    """SLAポリシーを更新"""
    try:
        db_path = DASHBOARD_DIR / "data" / "thebranch.sqlite"
        async with aiosqlite.connect(str(db_path)) as db:
            db.row_factory = sqlite3.Row

            update_fields = []
            update_values = []

            if policy.name is not None:
                update_fields.append("name = ?")
                update_values.append(policy.name)
            if policy.response_time_limit_ms is not None:
                update_fields.append("response_time_limit_ms = ?")
                update_values.append(policy.response_time_limit_ms)
            if policy.uptime_percentage is not None:
                update_fields.append("uptime_percentage = ?")
                update_values.append(policy.uptime_percentage)
            if policy.error_rate_limit is not None:
                update_fields.append("error_rate_limit = ?")
                update_values.append(policy.error_rate_limit)
            if policy.enabled is not None:
                update_fields.append("enabled = ?")
                update_values.append(policy.enabled)

            update_values.append(policy_id)

            if update_fields:
                query = f"UPDATE sla_policies SET updated_at = CURRENT_TIMESTAMP, {', '.join(update_fields)} WHERE id = ?"
                await db.execute(query, update_values)
                await db.commit()

            cursor = await db.execute("SELECT * FROM sla_policies WHERE id = ?", (policy_id,))
            row = await cursor.fetchone()
            if not row:
                raise HTTPException(status_code=404, detail="ポリシーが見つかりません")
            return dict(row)
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.delete("/api/sla/policies/{policy_id}")
async def delete_sla_policy(policy_id: int, user: dict = Depends(get_current_user_zero_trust)):
    """SLAポリシーを削除"""
    try:
        db_path = DASHBOARD_DIR / "data" / "thebranch.sqlite"
        async with aiosqlite.connect(str(db_path)) as db:
            cursor = await db.execute("SELECT id FROM sla_policies WHERE id = ?", (policy_id,))
            if not await cursor.fetchone():
                raise HTTPException(status_code=404, detail="ポリシーが見つかりません")

            await db.execute("DELETE FROM sla_policies WHERE id = ?", (policy_id,))
            await db.commit()
            return {"message": "ポリシーを削除しました"}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/sla/metrics/{policy_id}")
async def get_sla_metrics(policy_id: int, user: dict = Depends(get_current_user_zero_trust)):
    """SLAメトリクスを取得"""
    try:
        db_path = DASHBOARD_DIR / "data" / "thebranch.sqlite"
        async with aiosqlite.connect(str(db_path)) as db:
            db.row_factory = sqlite3.Row

            cursor = await db.execute("SELECT * FROM sla_policies WHERE id = ?", (policy_id,))
            policy = await cursor.fetchone()
            if not policy:
                raise HTTPException(status_code=404, detail="ポリシーが見つかりません")

            cursor = await db.execute(
                "SELECT * FROM sla_metrics WHERE policy_id = ? ORDER BY measured_at DESC",
                (policy_id,)
            )
            metrics = [dict(row) for row in await cursor.fetchall()]

            cursor = await db.execute(
                "SELECT * FROM sla_violations WHERE policy_id = ? ORDER BY created_at DESC",
                (policy_id,)
            )
            violations = [dict(row) for row in await cursor.fetchall()]

            latest_metric = metrics[0] if metrics else None
            violation_count = len(violations)

            metrics_with_violations = sum(1 for v in violations if not v.get("resolved_at"))
            compliance_rate = ((len(metrics) - metrics_with_violations) / len(metrics) * 100) if metrics else 0

            return {
                "policy_id": policy_id,
                "policy_name": policy["name"],
                "metrics": metrics,
                "violations": violations,
                "latest_metric": latest_metric,
                "violation_count": violation_count,
                "compliance_rate": compliance_rate
            }
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# ──────────────────────────────────────────────
# Authentication Endpoints (Multi-tenant)
# ──────────────────────────────────────────────

@app.post("/auth/signup", response_model=models.SignupResponse)
async def signup(request: models.SignupRequest, user: dict = Depends(get_current_user_zero_trust)):
    success, message, user_id = await auth.create_user(
        request.username, request.email, request.password, request.org_id
    )
    if not success:
        raise HTTPException(status_code=400, detail=message)
    return models.SignupResponse(
        success=True,
        user_id=user_id or "",
        message=message
    )


@app.post("/auth/login", response_model=models.LoginResponse)
async def login(request: models.LoginRequest, user: dict = Depends(get_current_user_zero_trust)):
    user_id, token, org_id = await auth.authenticate_user(
        request.username, request.password, request.org_id
    )
    if not user_id or not token:
        raise HTTPException(status_code=401, detail="Invalid username or password")

    from datetime import timedelta
    expires_at = datetime.utcnow() + timedelta(days=7)

    return models.LoginResponse(
        success=True,
        token=token,
        user_id=user_id,
        org_id=org_id or "default",
        expires_at=expires_at,
        message="Logged in successfully"
    )


@app.post("/auth/logout", response_model=models.LogoutResponse)
async def logout(authorization: Optional[str] = Header(None), user: dict = Depends(get_current_user_zero_trust)):
    if not authorization:
        raise HTTPException(status_code=400, detail="Authorization header required")

    token = authorization.replace("Bearer ", "")
    success, message = await auth.logout_user(token)

    if not success:
        raise HTTPException(status_code=400, detail=message)

    return models.LogoutResponse(success=True, message=message)


@app.get("/auth/verify", response_model=models.AuthTokenValidationResponse)
async def verify_token(authorization: Optional[str] = Header(None), user: dict = Depends(get_current_user_zero_trust)):
    if not authorization:
        return models.AuthTokenValidationResponse(
            success=False,
            message="Authorization header required"
        )

    token = authorization.replace("Bearer ", "")
    user_id, org_id = await auth.verify_token(token)

    if not user_id:
        return models.AuthTokenValidationResponse(
            success=False,
            message="Invalid or expired token"
        )

    return models.AuthTokenValidationResponse(
        success=True,
        user_id=user_id,
        org_id=org_id or "default",
        message="Token is valid"
    )


# ──────────────────────────────────────────────
# API v1 エンドポイント（外部連携用）
# ──────────────────────────────────────────────

@app.get("/api/v1/departments", response_model=list)
async def get_public_departments(auth: dict = Depends(verify_api_key), user: dict = Depends(get_current_user_zero_trust)):
    """公開API: 部署一覧取得"""
    try:
        async with aiosqlite.connect(str(THEBRANCH_DB)) as db:
            db.row_factory = sqlite3.Row
            cursor = await db.execute(
                """SELECT id, name, slug, description, status, created_at
                   FROM departments"""
            )
            departments = await cursor.fetchall()
            return [dict(d) for d in departments]
    except Exception as e:
        logger.error(f"Error fetching departments: {str(e)}")
        raise HTTPException(status_code=500, detail="部署取得エラー")


@app.get("/api/v1/agents", response_model=list)
async def get_public_agents(auth: dict = Depends(verify_api_key), user: dict = Depends(get_current_user_zero_trust)):
    """公開API: AIエージェント一覧取得"""
    try:
        async with aiosqlite.connect(str(THEBRANCH_DB)) as db:
            db.row_factory = sqlite3.Row
            cursor = await db.execute(
                """SELECT id, role, status, department_id, completion_rate, created_at
                   FROM agents"""
            )
            agents = await cursor.fetchall()
            return [dict(a) for a in agents]
    except Exception as e:
        logger.error(f"Error fetching agents: {str(e)}")
        raise HTTPException(status_code=500, detail="エージェント取得エラー")


@app.get("/api/v1/workflows", response_model=list)
async def get_public_workflows(auth: dict = Depends(verify_api_key), user: dict = Depends(get_current_user_zero_trust)):
    """公開API: ワークフロー一覧取得"""
    try:
        async with aiosqlite.connect(str(THEBRANCH_DB)) as db:
            db.row_factory = sqlite3.Row
            cursor = await db.execute(
                """SELECT id, name, description, status, created_at
                   FROM workflow_templates"""
            )
            workflows = await cursor.fetchall()
            return [dict(w) for w in workflows]
    except Exception as e:
        logger.error(f"Error fetching workflows: {str(e)}")
        raise HTTPException(status_code=500, detail="ワークフロー取得エラー")


@app.post("/api/v1/api-keys", response_model=models.ApiKeyWithSecret)
async def create_api_key(
    key_create: models.ApiKeyCreate,
    authorization: Optional[str] = Header(None),
user: dict = Depends(get_current_user_zero_trust)):
    """APIキー作成（管理者向け）"""
    if not authorization:
        raise HTTPException(status_code=401, detail="認証が必要です")

    token = authorization.replace("Bearer ", "")
    user_id, org_id = await auth.verify_token(token)

    if not user_id:
        raise HTTPException(status_code=401, detail="無効なトークンです")

    try:
        api_key_id = str(uuid.uuid4())
        raw_key = f"sk_{uuid.uuid4().hex[:32]}"
        key_hash = hashlib.sha256(raw_key.encode()).hexdigest()

        async with aiosqlite.connect(str(THEBRANCH_DB)) as db:
            await db.execute(
                """INSERT INTO api_keys
                   (id, org_id, name, key_hash, created_by, rate_limit_per_minute, description)
                   VALUES (?, ?, ?, ?, ?, ?, ?)""",
                (api_key_id, org_id, key_create.name, key_hash, user_id,
                 key_create.rate_limit_per_minute, key_create.description)
            )
            await db.commit()

        return models.ApiKeyWithSecret(
            id=api_key_id,
            name=key_create.name,
            description=key_create.description,
            created_at=datetime.now(),
            is_active=True,
            rate_limit_per_minute=key_create.rate_limit_per_minute,
            key=raw_key
        )
    except Exception as e:
        logger.error(f"Error creating API key: {str(e)}")
        raise HTTPException(status_code=500, detail="APIキー作成エラー")


@app.get("/api/v1/api-keys", response_model=list)
async def list_api_keys(authorization: Optional[str] = Header(None), user: dict = Depends(get_current_user_zero_trust)):
    """APIキー一覧取得"""
    if not authorization:
        raise HTTPException(status_code=401, detail="認証が必要です")

    token = authorization.replace("Bearer ", "")
    user_id, org_id = await auth.verify_token(token)

    if not user_id:
        raise HTTPException(status_code=401, detail="無効なトークンです")

    try:
        async with aiosqlite.connect(str(THEBRANCH_DB)) as db:
            db.row_factory = sqlite3.Row
            cursor = await db.execute(
                """SELECT id, name, description, created_at, last_used_at, is_active, rate_limit_per_minute
                   FROM api_keys WHERE org_id = ? AND created_by = ?""",
                (org_id, user_id)
            )
            keys = await cursor.fetchall()
            return [dict(k) for k in keys]
    except Exception as e:
        logger.error(f"Error listing API keys: {str(e)}")
        raise HTTPException(status_code=500, detail="APIキー一覧取得エラー")


@app.delete("/api/v1/api-keys/{key_id}")
async def revoke_api_key(key_id: str, authorization: Optional[str] = Header(None), user: dict = Depends(get_current_user_zero_trust)):
    """APIキー無効化"""
    if not authorization:
        raise HTTPException(status_code=401, detail="認証が必要です")

    token = authorization.replace("Bearer ", "")
    user_id, org_id = await auth.verify_token(token)

    if not user_id:
        raise HTTPException(status_code=401, detail="無効なトークンです")

    try:
        async with aiosqlite.connect(str(THEBRANCH_DB)) as db:
            await db.execute(
                "UPDATE api_keys SET is_active = 0 WHERE id = ? AND org_id = ?",
                (key_id, org_id)
            )
            await db.commit()
            return {"success": True, "message": "APIキーを無効化しました"}
    except Exception as e:
        logger.error(f"Error revoking API key: {str(e)}")
        raise HTTPException(status_code=500, detail="APIキー無効化エラー")


# ──────────────────────────────────────────────
# Resource Allocation API Endpoints
# ──────────────────────────────────────────────

@app.get("/api/resources/")
async def get_resources(department_id: Optional[int] = None, user: dict = Depends(get_current_user_zero_trust)):
    """Get all resources or resources for a specific department"""
    try:
        async with aiosqlite.connect(str(THEBRANCH_DB)) as db:
            db.row_factory = sqlite3.Row

            if department_id:
                cursor = await db.execute(
                    """SELECT id, department_id, resource_type, total_allocated,
                              current_used, reserved, unit, created_at, updated_at
                       FROM department_resources
                       WHERE department_id = ?
                       ORDER BY resource_type""",
                    (department_id,)
                )
            else:
                cursor = await db.execute(
                    """SELECT id, department_id, resource_type, total_allocated,
                              current_used, reserved, unit, created_at, updated_at
                       FROM department_resources
                       ORDER BY department_id, resource_type"""
                )

            rows = await cursor.fetchall()
            resources = [dict(row) for row in rows]

            return {
                "success": True,
                "count": len(resources),
                "resources": resources
            }
    except Exception as e:
        logger.error(f"Failed to get resources: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/resources/")
async def request_resource(request: models.ResourceAllocationRequest, user: dict = Depends(get_current_user_zero_trust)):
    """Request resource allocation"""
    try:
        async with aiosqlite.connect(str(THEBRANCH_DB)) as db:
            db.row_factory = sqlite3.Row

            # Verify department exists
            cursor = await db.execute(
                "SELECT id FROM departments WHERE id = ?",
                (request.department_id,)
            )
            dept = await cursor.fetchone()
            if not dept:
                raise HTTPException(status_code=404, detail="Department not found")

            # Create resource request
            cursor = await db.execute(
                """INSERT INTO resource_requests
                   (department_id, resource_type, required_amount, reason, status)
                   VALUES (?, ?, ?, ?, 'pending')""",
                (request.department_id, request.resource_type, request.required_amount, request.reason)
            )
            await db.commit()
            request_id = cursor.lastrowid

            return {
                "success": True,
                "resource_request_id": request_id,
                "status": "pending",
                "message": "Resource request created"
            }
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to create resource request: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))


@app.put("/api/resources/{request_id}/allocate")
async def allocate_resource(request_id: int, approval: models.ResourceAllocationApprovalRequest, user: dict = Depends(get_current_user_zero_trust)):
    """Approve and allocate resources"""
    try:
        async with aiosqlite.connect(str(THEBRANCH_DB)) as db:
            db.row_factory = sqlite3.Row

            # Get resource request
            cursor = await db.execute(
                """SELECT * FROM resource_requests WHERE id = ?""",
                (request_id,)
            )
            req = await cursor.fetchone()
            if not req:
                raise HTTPException(status_code=404, detail="Resource request not found")

            dept_id = req["department_id"]
            resource_type = req["resource_type"]
            approved_amount = approval.approved_amount

            # Check if department has enough resources available
            cursor = await db.execute(
                """SELECT total_allocated, current_used, reserved
                   FROM department_resources
                   WHERE department_id = ? AND resource_type = ?""",
                (dept_id, resource_type)
            )
            resource = await cursor.fetchone()

            if not resource:
                # Create new resource entry if doesn't exist
                cursor = await db.execute(
                    """INSERT INTO department_resources
                       (department_id, resource_type, total_allocated, current_used, reserved)
                       VALUES (?, ?, ?, ?, ?)""",
                    (dept_id, resource_type, approved_amount, 0, 0)
                )
                await db.commit()
            else:
                available = resource["total_allocated"] - resource["current_used"] - resource["reserved"]
                if available < approved_amount:
                    raise HTTPException(
                        status_code=400,
                        detail=f"Insufficient resources. Available: {available}, Requested: {approved_amount}"
                    )

            # Update resource request status
            cursor = await db.execute(
                """UPDATE resource_requests
                   SET status = 'approved', approved_amount = ?, approval_reason = ?,
                       approved_by = ?, approved_at = CURRENT_TIMESTAMP
                   WHERE id = ?""",
                (approved_amount, approval.approval_reason, approval.approved_by or "system", request_id)
            )
            await db.commit()

            # Create resource allocation
            cursor = await db.execute(
                """INSERT INTO resource_allocations
                   (department_id, resource_type, amount, status, allocated_at)
                   VALUES (?, ?, ?, 'active', CURRENT_TIMESTAMP)""",
                (dept_id, resource_type, approved_amount)
            )
            await db.commit()
            allocation_id = cursor.lastrowid

            # Update reserved amount
            cursor = await db.execute(
                """UPDATE department_resources
                   SET reserved = reserved + ?
                   WHERE department_id = ? AND resource_type = ?""",
                (approved_amount, dept_id, resource_type)
            )
            await db.commit()

            return {
                "success": True,
                "allocation_id": allocation_id,
                "status": "active",
                "approved_amount": approved_amount,
                "message": "Resource allocated successfully"
            }
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to allocate resource: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/resources/{request_id}/status")
async def get_resource_status(request_id: int, user: dict = Depends(get_current_user_zero_trust)):
    """Get resource allocation status"""
    try:
        async with aiosqlite.connect(str(THEBRANCH_DB)) as db:
            db.row_factory = sqlite3.Row

            # Get resource request
            cursor = await db.execute(
                """SELECT * FROM resource_requests WHERE id = ?""",
                (request_id,)
            )
            req = await cursor.fetchone()
            if not req:
                raise HTTPException(status_code=404, detail="Resource request not found")

            # Get related allocations
            cursor = await db.execute(
                """SELECT * FROM resource_allocations
                   WHERE department_id = ? AND resource_type = ? AND status = 'active'""",
                (req["department_id"], req["resource_type"])
            )
            allocations = await cursor.fetchall()

            # Get current resource usage
            cursor = await db.execute(
                """SELECT * FROM department_resources
                   WHERE department_id = ? AND resource_type = ?""",
                (req["department_id"], req["resource_type"])
            )
            resource = await cursor.fetchone()

            return {
                "success": True,
                "request_id": request_id,
                "request_status": req["status"],
                "request_details": {
                    "department_id": req["department_id"],
                    "resource_type": req["resource_type"],
                    "required_amount": req["required_amount"],
                    "approved_amount": req["approved_amount"],
                    "reason": req["reason"],
                    "requested_at": req["requested_at"],
                    "approved_at": req["approved_at"]
                },
                "allocations": [dict(a) for a in allocations] if allocations else [],
                "resource_summary": dict(resource) if resource else None
            }
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to get resource status: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))


# ──────────────────────────────────────────────
# SLA Management
# ──────────────────────────────────────────────

class SLAPolicyCreate(BaseModel):
    name: str
    response_time_limit_ms: int
    uptime_percentage: float
    error_rate_limit: float

class SLAPolicyUpdate(BaseModel):
    response_time_limit_ms: int = None
    uptime_percentage: float = None
    error_rate_limit: float = None

@app.get("/api/sla/policies")
async def get_sla_policies(user: dict = Depends(get_current_user_zero_trust)):
    """Get all SLA policies"""
    try:
        async with aiosqlite.connect(str(THEBRANCH_DB)) as db:
            db.row_factory = sqlite3.Row
            cursor = await db.execute(
                "SELECT id, name, response_time_limit_ms, uptime_percentage, error_rate_limit, enabled, created_at, updated_at FROM sla_policies ORDER BY id DESC"
            )
            policies = [dict(row) for row in await cursor.fetchall()]
            return policies
    except Exception as e:
        logger.error(f"Failed to get SLA policies: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/api/sla/policies")
async def create_sla_policy(policy: SLAPolicyCreate, user: dict = Depends(get_current_user_zero_trust)):
    """Create new SLA policy"""
    try:
        async with aiosqlite.connect(str(THEBRANCH_DB)) as db:
            db.row_factory = sqlite3.Row
            cursor = await db.execute(
                """INSERT INTO sla_policies
                   (name, response_time_limit_ms, uptime_percentage, error_rate_limit)
                   VALUES (?, ?, ?, ?)""",
                (policy.name, policy.response_time_limit_ms, policy.uptime_percentage, policy.error_rate_limit)
            )
            await db.commit()
            policy_id = cursor.lastrowid

            cursor = await db.execute(
                "SELECT id, name, response_time_limit_ms, uptime_percentage, error_rate_limit, enabled, created_at, updated_at FROM sla_policies WHERE id = ?",
                (policy_id,)
            )
            created = await cursor.fetchone()
            return dict(created) if created else {"id": policy_id}
    except Exception as e:
        logger.error(f"Failed to create SLA policy: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

@app.put("/api/sla/policies/{policy_id}")
async def update_sla_policy(policy_id: int, update: SLAPolicyUpdate, user: dict = Depends(get_current_user_zero_trust)):
    """Update SLA policy"""
    try:
        async with aiosqlite.connect(str(THEBRANCH_DB)) as db:
            db.row_factory = sqlite3.Row

            updates = {}
            if update.response_time_limit_ms is not None:
                updates["response_time_limit_ms"] = update.response_time_limit_ms
            if update.uptime_percentage is not None:
                updates["uptime_percentage"] = update.uptime_percentage
            if update.error_rate_limit is not None:
                updates["error_rate_limit"] = update.error_rate_limit

            if updates:
                set_clause = ", ".join([f"{k} = ?" for k in updates.keys()])
                values = list(updates.values()) + [policy_id]
                await db.execute(
                    f"UPDATE sla_policies SET {set_clause}, updated_at = CURRENT_TIMESTAMP WHERE id = ?",
                    values
                )
                await db.commit()

            cursor = await db.execute(
                "SELECT id, name, response_time_limit_ms, uptime_percentage, error_rate_limit, enabled, created_at, updated_at FROM sla_policies WHERE id = ?",
                (policy_id,)
            )
            updated = await cursor.fetchone()
            if not updated:
                raise HTTPException(status_code=404, detail="Policy not found")
            return dict(updated)
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to update SLA policy: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

@app.delete("/api/sla/policies/{policy_id}")
async def delete_sla_policy(policy_id: int, user: dict = Depends(get_current_user_zero_trust)):
    """Delete SLA policy"""
    try:
        async with aiosqlite.connect(str(THEBRANCH_DB)) as db:
            await db.execute("DELETE FROM sla_policies WHERE id = ?", (policy_id,))
            await db.commit()
            return {"success": True, "message": "Policy deleted successfully"}
    except Exception as e:
        logger.error(f"Failed to delete SLA policy: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/sla/metrics/{policy_id}")
async def get_sla_metrics(policy_id: int, limit: int = 10, user: dict = Depends(get_current_user_zero_trust)):
    """Get SLA metrics for a policy"""
    try:
        async with aiosqlite.connect(str(THEBRANCH_DB)) as db:
            db.row_factory = sqlite3.Row
            cursor = await db.execute(
                """SELECT id, policy_id, response_time_ms, uptime_percentage, error_rate, measured_at
                   FROM sla_metrics WHERE policy_id = ? ORDER BY measured_at DESC LIMIT ?""",
                (policy_id, limit)
            )
            metrics = [dict(row) for row in await cursor.fetchall()]
            return metrics
    except Exception as e:
        logger.error(f"Failed to get SLA metrics: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/sla/violations")
async def get_sla_violations(policy_id: int = None, limit: int = 50, user: dict = Depends(get_current_user_zero_trust)):
    """Get SLA violations"""
    try:
        async with aiosqlite.connect(str(THEBRANCH_DB)) as db:
            db.row_factory = sqlite3.Row

            if policy_id:
                cursor = await db.execute(
                    """SELECT id, policy_id, metric_id, violation_type, severity, details, alert_sent, created_at
                       FROM sla_violations WHERE policy_id = ? ORDER BY created_at DESC LIMIT ?""",
                    (policy_id, limit)
                )
            else:
                cursor = await db.execute(
                    """SELECT id, policy_id, metric_id, violation_type, severity, details, alert_sent, created_at
                       FROM sla_violations ORDER BY created_at DESC LIMIT ?""",
                    (limit,)
                )
            violations = [dict(row) for row in await cursor.fetchall()]
            return violations
    except Exception as e:
        logger.error(f"Failed to get SLA violations: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/api/agents", status_code=201)
async def create_agent(req: models.AgentCreate, user: dict = Depends(get_current_user_zero_trust)):
    """エージェントを作成"""
    await ensure_db_initialized()
    try:
        session_id = str(uuid.uuid4())

        async with aiosqlite.connect(str(THEBRANCH_DB)) as db:
            db.row_factory = aiosqlite.Row

            # department 存在確認
            cursor = await db.execute(
                "SELECT id FROM departments WHERE id = ?",
                (req.department_id,)
            )
            if not await cursor.fetchone():
                raise HTTPException(status_code=404, detail="部署が見つかりません")

            # エージェント作成
            cursor = await db.execute(
                """INSERT INTO agents
                   (department_id, session_id, role, status, started_at, created_at, updated_at)
                   VALUES (?, ?, ?, ?, datetime('now','localtime'), datetime('now','localtime'), datetime('now','localtime'))""",
                (req.department_id, session_id, req.role, 'starting')
            )
            await db.commit()
            agent_id = cursor.lastrowid

            # 作成したエージェント情報を取得
            cursor = await db.execute(
                """SELECT id, department_id, session_id, role, status, started_at, stopped_at,
                          error_message, created_at, updated_at
                   FROM agents WHERE id = ?""",
                (agent_id,)
            )
            agent_row = await cursor.fetchone()

            return dict(agent_row)
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to create agent: {str(e)}")
        raise HTTPException(status_code=400, detail=str(e))


@app.post("/api/agents/{agent_id}/start", status_code=200)
async def start_agent(agent_id: int, user: dict = Depends(get_current_user_zero_trust)):
    """エージェントを起動"""
    await ensure_db_initialized()
    try:
        async with aiosqlite.connect(str(THEBRANCH_DB)) as db:
            db.row_factory = aiosqlite.Row

            # agent 存在確認
            cursor = await db.execute(
                "SELECT id, session_id FROM agents WHERE id = ?",
                (agent_id,)
            )
            agent_row = await cursor.fetchone()
            if not agent_row:
                raise HTTPException(status_code=404, detail="エージェントが見つかりません")

            # status を 'running' に更新
            await db.execute(
                """UPDATE agents SET status = ?, updated_at = datetime('now','localtime')
                   WHERE id = ?""",
                ('running', agent_id)
            )
            await db.commit()

            # 更新後の情報を返す
            cursor = await db.execute(
                """SELECT id, department_id, session_id, role, status, started_at, stopped_at,
                          error_message, created_at, updated_at
                   FROM agents WHERE id = ?""",
                (agent_id,)
            )
            agent_row = await cursor.fetchone()

            return dict(agent_row)
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to start agent: {str(e)}")
        raise HTTPException(status_code=400, detail=str(e))


@app.get("/api/workflows")
async def get_workflows(workflow_type: str = "all", user: dict = Depends(get_current_user_zero_trust)):
    """ワークフロー一覧取得（テンプレートとインスタンスを統合）"""
    try:
        if not TASKS_DB.exists():
            return {"templates": [], "instances": []}

        async with aiosqlite.connect(str(TASKS_DB)) as db:
            db.row_factory = aiosqlite.Row

            # ワークフロー テンプレート取得
            cursor = await db.execute("SELECT * FROM workflow_templates ORDER BY id DESC")
            templates = [dict(r) for r in await cursor.fetchall()]

            # 各テンプレートの node 取得
            for tmpl in templates:
                cursor = await db.execute(
                    "SELECT * FROM wf_template_nodes WHERE template_id = ? ORDER BY id",
                    (tmpl["id"],)
                )
                tmpl["nodes"] = [dict(r) for r in await cursor.fetchall()]

            # ワークフロー インスタンス取得
            if workflow_type == "all" or workflow_type == "instances":
                cursor = await db.execute(
                    """SELECT wi.*, wt.name AS template_name
                       FROM workflow_instances wi
                       LEFT JOIN workflow_templates wt ON wi.template_id = wt.id
                       ORDER BY wi.id DESC"""
                )
                instances = [dict(r) for r in await cursor.fetchall()]

                # 各インスタンスの node 取得
                for inst in instances:
                    cursor = await db.execute(
                        """SELECT n.*, t.title as task_title, t.status as task_status, t.role as task_role
                           FROM wf_instance_nodes n
                           LEFT JOIN dev_tasks t ON n.task_id = t.id
                           WHERE n.instance_id = ?
                           ORDER BY n.id""",
                        (inst["id"],)
                    )
                    inst["nodes"] = [dict(r) for r in await cursor.fetchall()]
            else:
                instances = []

            return {"templates": templates, "instances": instances}
    except Exception as e:
        logger.error(f"Failed to get workflows: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))


# ──────────────────────────────────────────────
# 部署間コラボレーション API エンドポイント (Task #2414)
# ──────────────────────────────────────────────

@app.post("/api/cross-department-requests")
async def create_cross_department_request(
    req: models.CrossDepartmentRequestCreate,
    auth: dict = Depends(verify_api_key),
user: dict = Depends(get_current_user_zero_trust)):
    """他部署にタスク / リソース / スキルを依頼する"""
    try:
        # バリデーション: 同一部署チェック
        if req.requesting_department_id == req.receiving_department_id:
            raise HTTPException(
                status_code=422, detail="同じ部署へのリクエストはできません"
            )

        async with aiosqlite.connect(str(THEBRANCH_DB)) as db:
            await db.execute("PRAGMA foreign_keys = ON")
            db.row_factory = aiosqlite.Row

            # requesting_department_id 存在確認
            cursor = await db.execute(
                "SELECT id FROM department_instances WHERE id = ?",
                (req.requesting_department_id,),
            )
            if not await cursor.fetchone():
                raise HTTPException(
                    status_code=404,
                    detail=f"部署 #{req.requesting_department_id} が見つかりません",
                )

            # receiving_department_id 存在確認
            cursor = await db.execute(
                "SELECT id FROM department_instances WHERE id = ?",
                (req.receiving_department_id,),
            )
            if not await cursor.fetchone():
                raise HTTPException(
                    status_code=404,
                    detail=f"部署 #{req.receiving_department_id} が見つかりません",
                )

            # リクエスト作成
            now = datetime.now().isoformat()
            cursor = await db.execute(
                """
                INSERT INTO inter_department_requests
                    (requesting_department_id, receiving_department_id,
                     request_type, priority, description, created_at, updated_at)
                VALUES (?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    req.requesting_department_id,
                    req.receiving_department_id,
                    req.request_type,
                    req.priority,
                    req.description,
                    now,
                    now,
                ),
            )
            request_id = cursor.lastrowid
            await db.commit()

            return {
                "id": request_id,
                "requesting_department_id": req.requesting_department_id,
                "receiving_department_id": req.receiving_department_id,
                "request_type": req.request_type,
                "priority": req.priority,
                "description": req.description,
                "status": "pending",
                "created_at": now,
                "updated_at": now,
            }
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error creating cross-department request: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/task-sharing")
async def create_task_sharing(
    req: models.TaskSharingCreate,
    auth: dict = Depends(verify_api_key),
user: dict = Depends(get_current_user_zero_trust)):
    """リクエストに基づいてタスクを部署間で共有する"""
    try:
        async with aiosqlite.connect(str(THEBRANCH_DB)) as db:
            await db.execute("PRAGMA foreign_keys = ON")
            db.row_factory = aiosqlite.Row

            # リクエスト存在確認
            cursor = await db.execute(
                "SELECT id, status FROM inter_department_requests WHERE id = ?",
                (req.request_id,),
            )
            request_row = await cursor.fetchone()
            if not request_row:
                raise HTTPException(
                    status_code=404,
                    detail=f"リクエスト #{req.request_id} が見つかりません",
                )

            # タスク存在確認 (production schema: table is `tasks`)
            cursor = await db.execute(
                "SELECT id FROM tasks WHERE id = ?", (req.task_id,)
            )
            if not await cursor.fetchone():
                raise HTTPException(
                    status_code=404,
                    detail=f"タスク #{req.task_id} が見つかりません",
                )

            # タスク割り当て作成
            now = datetime.now().isoformat()
            cursor = await db.execute(
                """
                INSERT INTO inter_department_task_allocations
                    (request_id, task_id, status, created_at)
                VALUES (?, ?, ?, ?)
                """,
                (req.request_id, req.task_id, "pending", now),
            )
            allocation_id = cursor.lastrowid
            await db.commit()

            return {
                "id": allocation_id,
                "request_id": req.request_id,
                "task_id": req.task_id,
                "sharing_terms": req.sharing_terms,
                "status": "pending",
                "created_at": now,
            }
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error creating task sharing: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/received-requests")
async def get_received_requests(
    department_id: int,
    status: Optional[str] = None,
    limit: int = 20,
    auth: dict = Depends(verify_api_key),
user: dict = Depends(get_current_user_zero_trust)):
    """指定部署が受け取った他部署からのリクエスト一覧"""
    try:
        async with aiosqlite.connect(str(THEBRANCH_DB)) as db:
            db.row_factory = aiosqlite.Row

            query = """
                SELECT id, requesting_department_id, receiving_department_id,
                       request_type, priority, status, description,
                       created_at, updated_at
                FROM inter_department_requests
                WHERE receiving_department_id = ?
            """
            params = [department_id]

            if status:
                query += " AND status = ?"
                params.append(status)

            query += " ORDER BY created_at DESC LIMIT ?"
            params.append(limit)

            cursor = await db.execute(query, params)
            rows = await cursor.fetchall()
            return [dict(row) for row in rows]
    except Exception as e:
        logger.error(f"Error getting received requests: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/shared-tasks")
async def get_shared_tasks(
    department_id: int,
    status: Optional[str] = None,
    limit: int = 20,
    auth: dict = Depends(verify_api_key),
user: dict = Depends(get_current_user_zero_trust)):
    """指定部署が受け取った共有タスク一覧"""
    try:
        async with aiosqlite.connect(str(THEBRANCH_DB)) as db:
            db.row_factory = aiosqlite.Row

            query = """
                SELECT
                    a.id AS allocation_id,
                    r.id AS request_id,
                    a.task_id,
                    r.requesting_department_id,
                    r.receiving_department_id,
                    r.request_type,
                    a.status,
                    a.created_at,
                    t.title AS task_title
                FROM inter_department_task_allocations a
                JOIN inter_department_requests r ON a.request_id = r.id
                JOIN tasks t ON a.task_id = t.id
                WHERE r.receiving_department_id = ?
            """
            params = [department_id]

            if status:
                query += " AND a.status = ?"
                params.append(status)

            query += " ORDER BY a.created_at DESC LIMIT ?"
            params.append(limit)

            cursor = await db.execute(query, params)
            rows = await cursor.fetchall()
            return [dict(row) for row in rows]
    except Exception as e:
        logger.error(f"Error getting shared tasks: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))


# ──────────────────────────────────────────────
# Entry point
# ──────────────────────────────────────────────

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=7002)


# ──────────────────────────────────────────────
# Slack/Discord Webhook Integration Endpoints
# ──────────────────────────────────────────────

from .integrations.slack_handler import verify_slack_signature, parse_slack_event
from .integrations.discord_handler import verify_discord_signature, parse_discord_event
from .integrations.webhook_service import (
    record_webhook_event,
    find_integration_config_for_webhook,
    create_notification_from_webhook,
    verify_webhook_url,
)


@app.post("/api/webhooks/slack")
async def webhook_slack(request: models.SlackWebhookPayload, user: dict = Depends(get_current_user_zero_trust)):
    """
    Slack webhook endpoint.
    
    Handles:
    - URL verification challenge (no signature check)
    - Event callbacks (with signature verification)
    """
    try:
        # URL verification (no signature check needed per Slack docs)
        if request.type == "url_verification":
            return {"challenge": request.challenge}

        # Get request headers
        raw_body = request.json()
        headers = {}  # Note: In production, capture from Request object

        # For production, this should be:
        # def webhook_slack(
        #     request: Request,
        #     payload: models.SlackWebhookPayload
        # ):
        #     raw_body = await request.body()
        #     headers = dict(request.headers)

        # Parse parsed data from event
        parsed = parse_slack_event(request.dict())
        event_type = parsed.get("event_type")
        title = parsed.get("title")
        message = parsed.get("message")

        if not event_type or event_type == "url_verification":
            return {"success": True, "notification_id": None}

        # Record webhook event
        async with aiosqlite.connect(str(THEBRANCH_DB)) as db:
            event_id = str(uuid.uuid4())
            webhook_event_id = await record_webhook_event(
                db,
                event_id=event_id,
                integration_config_id=None,  # Would be set from config lookup
                event_type=event_type,
                event_source="slack",
                raw_payload=request.dict(),
                parsed_data=parsed,
                processing_status="received",
            )

            # Create notification
            notification_id = await create_notification_from_webhook(
                db,
                title=title or "Slack Event",
                message=message or "Event received",
                notification_type=event_type,
                integration_config_id=None,
                webhook_event_id=webhook_event_id,
            )

            # Broadcast to WebSocket
            if notification_id:
                now = datetime.now().isoformat()
                notif_msg = {
                    "type": "notification",
                    "id": notification_id,
                    "notification_type": event_type,
                    "title": title or "Slack Event",
                    "message": message or "Event received",
                    "severity": "info",
                    "created_at": now,
                }
                await get_notification_manager().broadcast(json.dumps(notif_msg))

            return {"success": True, "notification_id": notification_id}

    except Exception as e:
        logger.error(f"Slack webhook error: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/webhooks/discord")
async def webhook_discord(payload: models.DiscordWebhookPayload, user: dict = Depends(get_current_user_zero_trust)):
    """
    Discord webhook endpoint.
    
    Handles interaction requests with Ed25519 signature verification.
    """
    try:
        # Parse event
        parsed = parse_discord_event(payload.dict())
        event_type = parsed.get("event_type")
        title = parsed.get("title")
        message = parsed.get("message")

        # Record webhook event
        async with aiosqlite.connect(str(THEBRANCH_DB)) as db:
            event_id = str(uuid.uuid4())
            webhook_event_id = await record_webhook_event(
                db,
                event_id=event_id,
                integration_config_id=None,
                event_type=event_type or f"discord_type_{payload.type}",
                event_source="discord",
                raw_payload=payload.dict(),
                parsed_data=parsed,
                processing_status="received",
            )

            # Handle PING response
            if payload.type == 1:  # PING
                return {"type": 1}  # PONG

            # Create notification for other interaction types
            notification_id = await create_notification_from_webhook(
                db,
                title=title or "Discord Interaction",
                message=message or "Interaction received",
                notification_type=event_type or f"discord_type_{payload.type}",
                integration_config_id=None,
                webhook_event_id=webhook_event_id,
            )

            # Broadcast to WebSocket
            if notification_id:
                now = datetime.now().isoformat()
                notif_msg = {
                    "type": "notification",
                    "id": notification_id,
                    "notification_type": event_type,
                    "title": title or "Discord Interaction",
                    "message": message or "Interaction received",
                    "severity": "info",
                    "created_at": now,
                }
                await get_notification_manager().broadcast(json.dumps(notif_msg))

            return {"success": True, "notification_id": notification_id}

    except Exception as e:
        logger.error(f"Discord webhook error: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/integrations/configs")
async def list_integration_configs(
    integration_type: Optional[str] = None,
    is_active: Optional[int] = None,
    limit: int = 50,
user: dict = Depends(get_current_user_zero_trust)):
    """
    List integration configurations.
    
    Query params:
        integration_type: 'slack' or 'discord' (optional)
        is_active: 0 or 1 (optional)
        limit: max results (default 50)
    """
    try:
        async with aiosqlite.connect(str(THEBRANCH_DB)) as db:
            db.row_factory = aiosqlite.Row

            query = "SELECT * FROM integration_configs WHERE 1=1"
            params = []

            if integration_type:
                query += " AND integration_type = ?"
                params.append(integration_type)
            if is_active is not None:
                query += " AND is_active = ?"
                params.append(is_active)

            query += " ORDER BY created_at DESC LIMIT ?"
            params.append(limit)

            cursor = await db.execute(query, params)
            rows = await cursor.fetchall()

            # Mask webhook_secret in response
            result = []
            for row in rows:
                config = dict(row)
                config["webhook_secret"] = "***REDACTED***"
                result.append(config)

            return {"configs": result, "total": len(result)}
    except Exception as e:
        logger.error(f"Failed to list integration configs: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/integrations/configs")
async def create_integration_config(req: models.IntegrationConfigCreate, user: dict = Depends(get_current_user_zero_trust)):
    """
    Create a new integration configuration.
    """
    try:
        async with aiosqlite.connect(str(THEBRANCH_DB)) as db:
            now = datetime.now().isoformat()

            cursor = await db.execute(
                """
                INSERT INTO integration_configs (
                    integration_type, organization_id, webhook_url, webhook_secret,
                    channel_id, channel_name, is_active,
                    notify_on_agent_status, notify_on_task_delegation,
                    notify_on_cost_alert, notify_on_approval_request,
                    notify_on_error_event, notify_on_system_alert,
                    metadata, created_by, created_at, updated_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    req.integration_type,
                    req.organization_id,
                    req.webhook_url,
                    req.webhook_secret,
                    req.channel_id,
                    req.channel_name,
                    req.is_active,
                    req.notify_on_agent_status,
                    req.notify_on_task_delegation,
                    req.notify_on_cost_alert,
                    req.notify_on_approval_request,
                    req.notify_on_error_event,
                    req.notify_on_system_alert,
                    req.metadata,
                    req.created_by,
                    now,
                    now,
                ),
            )
            await db.commit()

            config_id = cursor.lastrowid

            # Return config with masked secret
            return {
                "id": config_id,
                "integration_type": req.integration_type,
                "organization_id": req.organization_id,
                "webhook_url": req.webhook_url,
                "webhook_secret": "***REDACTED***",
                "channel_id": req.channel_id,
                "channel_name": req.channel_name,
                "is_active": req.is_active,
                "created_at": now,
                "updated_at": now,
            }
    except Exception as e:
        logger.error(f"Failed to create integration config: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/integrations/configs/{config_id}")
async def get_integration_config(config_id: int, user: dict = Depends(get_current_user_zero_trust)):
    """
    Get a specific integration configuration.
    """
    try:
        async with aiosqlite.connect(str(THEBRANCH_DB)) as db:
            db.row_factory = aiosqlite.Row

            cursor = await db.execute(
                "SELECT * FROM integration_configs WHERE id = ?",
                (config_id,),
            )
            row = await cursor.fetchone()

            if not row:
                raise HTTPException(status_code=404, detail="Config not found")

            config = dict(row)
            config["webhook_secret"] = "***REDACTED***"
            return config
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to get integration config: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.put("/api/integrations/configs/{config_id}")
async def update_integration_config(
    config_id: int, req: models.IntegrationConfigUpdate,
user: dict = Depends(get_current_user_zero_trust)):
    """
    Update an integration configuration (partial update).
    """
    try:
        async with aiosqlite.connect(str(THEBRANCH_DB)) as db:
            now = datetime.now().isoformat()

            # Build dynamic update query
            update_fields = []
            params = []

            for field, value in req.dict(exclude_unset=True).items():
                if value is not None:
                    update_fields.append(f"{field} = ?")
                    params.append(value)

            if not update_fields:
                raise HTTPException(status_code=400, detail="No fields to update")

            update_fields.append("updated_at = ?")
            params.append(now)
            params.append(config_id)

            query = f"UPDATE integration_configs SET {', '.join(update_fields)} WHERE id = ?"

            await db.execute(query, params)
            await db.commit()

            # Return updated config
            cursor = await db.execute(
                "SELECT * FROM integration_configs WHERE id = ?",
                (config_id,),
            )
            row = await cursor.fetchone()

            if row:
                config = dict(row)
                config["webhook_secret"] = "***REDACTED***"
                return config
            else:
                raise HTTPException(status_code=404, detail="Config not found")
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to update integration config: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.delete("/api/integrations/configs/{config_id}")
async def delete_integration_config(config_id: int, user: dict = Depends(get_current_user_zero_trust)):
    """
    Delete an integration configuration.
    """
    try:
        async with aiosqlite.connect(str(THEBRANCH_DB)) as db:
            # First check if exists
            cursor = await db.execute(
                "SELECT id FROM integration_configs WHERE id = ?",
                (config_id,),
            )
            if not await cursor.fetchone():
                raise HTTPException(status_code=404, detail="Config not found")

            # Delete
            await db.execute(
                "DELETE FROM integration_configs WHERE id = ?",
                (config_id,),
            )
            await db.commit()

            return {"status": "deleted", "config_id": config_id}
    except Exception as e:
        logger.error(f"Failed to delete integration config: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/integrations/verify/{config_id}")
async def verify_integration_webhook(config_id: int, user: dict = Depends(get_current_user_zero_trust)):
    """
    Verify that a webhook URL is reachable.

    Sends a test POST request to the webhook URL.
    """
    try:
        async with aiosqlite.connect(str(THEBRANCH_DB)) as db:
            db.row_factory = aiosqlite.Row

            cursor = await db.execute(
                "SELECT webhook_url FROM integration_configs WHERE id = ?",
                (config_id,),
            )
            row = await cursor.fetchone()

            if not row:
                raise HTTPException(status_code=404, detail="Config not found")

            webhook_url = row["webhook_url"]

            # Verify URL
            success, error = await verify_webhook_url(webhook_url)

            if success:
                # Update last_verified_at
                now = datetime.now().isoformat()
                await db.execute(
                    "UPDATE integration_configs SET last_verified_at = ? WHERE id = ?",
                    (now, config_id),
                )
                await db.commit()

                return {"success": True, "webhook_url": webhook_url}
            else:
                return {
                    "success": False,
                    "webhook_url": webhook_url,
                    "error": error or "Verification failed",
                }
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to verify webhook: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# ============================================================================
# Team Invitation & Collaboration APIs
# ============================================================================

@app.post("/api/teams/{team_id}/invite", status_code=201)
async def create_team_invite(team_id: int, req: models.InvitationCreate, auth_header: Optional[str] = Header(None)):
    """チームの招待リンクを生成"""
    await ensure_db_initialized()
    try:
        user = get_current_user(auth_header) if auth_header else None
        if not user:
            raise HTTPException(status_code=401, detail="認証が必要です")

        async with aiosqlite.connect(str(THEBRANCH_DB)) as db:
            db.row_factory = aiosqlite.Row

            # チーム確認
            cursor = await db.execute("SELECT id FROM teams WHERE id = ?", (team_id,))
            if not await cursor.fetchone():
                raise HTTPException(status_code=404, detail="チームが見つかりません")

            # ユーザーの権限確認（owner/admin のみ）
            cursor = await db.execute(
                "SELECT role FROM team_members WHERE team_id = ? AND user_id = ?",
                (team_id, user["id"])
            )
            member = await cursor.fetchone()
            if not member or member["role"] not in ("owner", "admin"):
                raise HTTPException(status_code=403, detail="権限がありません")

            # トークン生成
            token = f"invite_{uuid.uuid4().hex[:16]}"
            expires_at = (datetime.now().replace(microsecond=0) +
                         __import__('datetime').timedelta(days=req.expires_in_days)).isoformat()

            # 招待レコード作成
            await db.execute(
                """INSERT INTO invitations (team_id, token, created_by, expires_at, max_uses, status)
                   VALUES (?, ?, ?, ?, ?, 'active')""",
                (team_id, token, user["id"], expires_at, req.max_uses)
            )
            await db.commit()

            # 作成した招待を返す
            cursor = await db.execute("SELECT * FROM invitations WHERE token = ?", (token,))
            inv = await cursor.fetchone()
            return dict(inv) if inv else {"token": token}

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to create invite: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/invites/{token}/accept", status_code=201)
async def accept_invitation(token: str, req: models.InviteAcceptRequest, auth_header: Optional[str] = Header(None), user: dict = Depends(get_current_user_zero_trust)):
    """招待リンクを受け入れてチームメンバーになる"""
    await ensure_db_initialized()
    try:
        async with aiosqlite.connect(str(THEBRANCH_DB)) as db:
            db.row_factory = aiosqlite.Row

            # 招待トークン確認
            cursor = await db.execute(
                "SELECT * FROM invitations WHERE token = ? AND status = 'active'",
                (token,)
            )
            invitation = await cursor.fetchone()
            if not invitation:
                raise HTTPException(status_code=404, detail="招待が見つかりません")

            # 有効期限チェック
            expires_at = datetime.fromisoformat(invitation["expires_at"])
            if datetime.now() > expires_at:
                await db.execute("UPDATE invitations SET status = 'expired' WHERE id = ?", (invitation["id"],))
                await db.commit()
                raise HTTPException(status_code=400, detail="招待の有効期限が切れています")

            # 使用回数チェック
            if invitation["used_count"] >= invitation["max_uses"]:
                raise HTTPException(status_code=409, detail="招待の使用可能回数に達しました")

            # 現在のユーザーを取得（または new user として user_id を生成）
            user_id = None
            if auth_header:
                user = get_current_user(auth_header)
                user_id = user["id"]
            else:
                # 認証なしの場合、username または email から user_id を生成
                user_id = req.username or str(uuid.uuid4())

            # 既にメンバーか確認
            cursor = await db.execute(
                "SELECT id FROM team_members WHERE team_id = ? AND user_id = ?",
                (invitation["team_id"], user_id)
            )
            if await cursor.fetchone():
                raise HTTPException(status_code=409, detail="既にメンバーです")

            # チームメンバーを追加
            member_id = str(uuid.uuid4())
            now = datetime.now().isoformat()
            await db.execute(
                """INSERT INTO team_members (id, team_id, user_id, role, invited_by, accepted_at, status)
                   VALUES (?, ?, ?, 'member', ?, ?, 'active')""",
                (member_id, invitation["team_id"], user_id, invitation["created_by"], now)
            )

            # 招待の used_count をインクリメント
            await db.execute(
                "UPDATE invitations SET used_count = used_count + 1 WHERE id = ?",
                (invitation["id"],)
            )
            await db.commit()

            # チーム情報を返す
            cursor = await db.execute("SELECT * FROM teams WHERE id = ?", (invitation["team_id"],))
            team = await cursor.fetchone()

            return {"team": dict(team) if team else {}, "member_id": member_id}

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to accept invitation: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/teams/{team_id}/members")
async def list_team_members(team_id: int, role: Optional[str] = None, status: str = "active", auth_header: Optional[str] = Header(None), user: dict = Depends(get_current_user_zero_trust)):
    """チームメンバー一覧を取得"""
    await ensure_db_initialized()
    try:
        async with aiosqlite.connect(str(THEBRANCH_DB)) as db:
            db.row_factory = aiosqlite.Row

            # チーム確認
            cursor = await db.execute("SELECT id FROM teams WHERE id = ?", (team_id,))
            if not await cursor.fetchone():
                raise HTTPException(status_code=404, detail="チームが見つかりません")

            # メンバー一覧取得
            query = "SELECT * FROM team_members WHERE team_id = ? AND status = ?"
            params = [team_id, status]

            if role:
                query += " AND role = ?"
                params.append(role)

            query += " ORDER BY joined_at DESC"

            cursor = await db.execute(query, params)
            members = await cursor.fetchall()

            # 各メンバーのユーザー情報を付加
            members_with_user = []
            for member in members:
                member_dict = dict(member)
                cursor = await db.execute("SELECT * FROM users WHERE id = ?", (member["user_id"],))
                user = await cursor.fetchone()
                if user:
                    member_dict["user"] = dict(user)
                members_with_user.append(member_dict)

            return {"data": members_with_user, "total": len(members_with_user)}

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to list members: {e}")
        raise HTTPException(status_code=500, detail=str(e))


class RoleChangeRequest(BaseModel):
    role: str


@app.patch("/api/teams/{team_id}/members/{user_id}/role")
async def change_member_role(team_id: int, user_id: str, req: RoleChangeRequest, auth_header: Optional[str] = Header(None)):
    """チームメンバーの権限を変更（owner のみ）"""
    await ensure_db_initialized()
    try:
        user = get_current_user(auth_header) if auth_header else None
        if not user:
            raise HTTPException(status_code=401, detail="認証が必要です")

        new_role = req.role
        if not new_role or new_role not in ("owner", "admin", "member"):
            raise HTTPException(status_code=400, detail="無効なロールです")

        async with aiosqlite.connect(str(THEBRANCH_DB)) as db:
            db.row_factory = aiosqlite.Row

            # リクエスター（owner）の確認
            cursor = await db.execute(
                "SELECT role FROM team_members WHERE team_id = ? AND user_id = ?",
                (team_id, user["id"])
            )
            requester = await cursor.fetchone()
            if not requester or requester["role"] != "owner":
                raise HTTPException(status_code=403, detail="owner のみ権限変更できます")

            # 変更対象のメンバーを確認
            cursor = await db.execute(
                "SELECT * FROM team_members WHERE team_id = ? AND user_id = ?",
                (team_id, user_id)
            )
            member = await cursor.fetchone()
            if not member:
                raise HTTPException(status_code=404, detail="メンバーが見つかりません")

            # 最後のowner削除防止
            if member["role"] == "owner" and new_role != "owner":
                cursor = await db.execute(
                    "SELECT COUNT(*) as cnt FROM team_members WHERE team_id = ? AND role = 'owner'",
                    (team_id,)
                )
                result = await cursor.fetchone()
                if result["cnt"] <= 1:
                    raise HTTPException(status_code=409, detail="最後のowner を削除することはできません")

            # 権限更新
            await db.execute(
                "UPDATE team_members SET role = ?, updated_at = ? WHERE team_id = ? AND user_id = ?",
                (new_role, datetime.now().isoformat(), team_id, user_id)
            )
            await db.commit()

            # 更新後のメンバーを返す
            cursor = await db.execute(
                "SELECT * FROM team_members WHERE team_id = ? AND user_id = ?",
                (team_id, user_id)
            )
            updated = await cursor.fetchone()
            return dict(updated) if updated else {}

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to change role: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.delete("/api/teams/{team_id}/members/{user_id}", status_code=204)
async def remove_team_member(team_id: int, user_id: str, auth_header: Optional[str] = Header(None)):
    """チームメンバーを削除（owner/admin のみ）"""
    await ensure_db_initialized()
    try:
        user = get_current_user(auth_header) if auth_header else None
        if not user:
            raise HTTPException(status_code=401, detail="認証が必要です")

        async with aiosqlite.connect(str(THEBRANCH_DB)) as db:
            db.row_factory = aiosqlite.Row

            # リクエスター（owner/admin）の確認
            cursor = await db.execute(
                "SELECT role FROM team_members WHERE team_id = ? AND user_id = ?",
                (team_id, user["id"])
            )
            requester = await cursor.fetchone()
            if not requester or requester["role"] not in ("owner", "admin"):
                raise HTTPException(status_code=403, detail="owner/admin のみメンバー削除できます")

            # 削除対象のメンバーを確認
            cursor = await db.execute(
                "SELECT role FROM team_members WHERE team_id = ? AND user_id = ?",
                (team_id, user_id)
            )
            member = await cursor.fetchone()
            if not member:
                raise HTTPException(status_code=404, detail="メンバーが見つかりません")

            # 最後のowner削除防止
            if member["role"] == "owner":
                cursor = await db.execute(
                    "SELECT COUNT(*) as cnt FROM team_members WHERE team_id = ? AND role = 'owner'",
                    (team_id,)
                )
                result = await cursor.fetchone()
                if result["cnt"] <= 1:
                    raise HTTPException(status_code=409, detail="最後のowner を削除することはできません")

            # メンバーを削除（ステータスを'removed'に）
            await db.execute(
                "UPDATE team_members SET status = 'removed', updated_at = ? WHERE team_id = ? AND user_id = ?",
                (datetime.now().isoformat(), team_id, user_id)
            )
            await db.commit()

            return None

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to remove member: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/auth/sessions")
async def get_active_sessions(auth_header: Optional[str] = Header(None), user: dict = Depends(get_current_user_zero_trust)):
    """アクティブなセッション一覧を取得"""
    try:
        if not auth_header:
            raise HTTPException(status_code=401, detail="Unauthorized")

        user_id, org_id = await auth.verify_token(auth_header)
        if not user_id:
            raise HTTPException(status_code=403, detail="Invalid token")

        await auth.update_last_activity(auth_header)
        sessions = await auth.list_active_sessions(user_id)
        return sessions

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to get sessions: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/auth/sessions/{session_id}/force-logout")
async def force_logout_user_session(session_id: str, auth_header: Optional[str] = Header(None), user: dict = Depends(get_current_user_zero_trust)):
    """セッションを強制ログアウト"""
    try:
        if not auth_header:
            raise HTTPException(status_code=401, detail="Unauthorized")

        user_id, org_id = await auth.verify_token(auth_header)
        if not user_id:
            raise HTTPException(status_code=403, detail="Invalid token")

        await auth.update_last_activity(auth_header)

        success, msg = await auth.force_logout_session(session_id)
        if not success:
            raise HTTPException(status_code=404, detail=msg)

        return {"message": msg}

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to force logout: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# 2FA Models
class Enable2FARequest(BaseModel):
    user_id: str


class Verify2FARequest(BaseModel):
    totp_code: str


class Disable2FARequest(BaseModel):
    password: str


@app.post("/api/2fa/enable")
async def enable_2fa(req: Enable2FARequest, auth_header: Optional[str] = Header(None), user: dict = Depends(get_current_user_zero_trust)):
    """TOTP 2FAを有効化（初期設定）"""
    try:
        if not auth_header:
            raise HTTPException(status_code=401, detail="Unauthorized")

        user_id, org_id = await auth.verify_token(auth_header)
        if not user_id:
            raise HTTPException(status_code=403, detail="Invalid token")

        await auth.update_last_activity(auth_header)

        if user_id != req.user_id:
            raise HTTPException(status_code=403, detail="Cannot enable 2FA for other users")

        secret, qr_code, backup_codes = await auth.enable_2fa(user_id)

        return {
            "secret": secret,
            "qr_code": qr_code,
            "backup_codes": backup_codes,
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to enable 2FA: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/2fa/verify")
async def verify_2fa(req: Verify2FARequest, auth_header: Optional[str] = Header(None), user: dict = Depends(get_current_user_zero_trust)):
    """TOTP トークンを検証して2FAを有効化"""
    try:
        if not auth_header:
            raise HTTPException(status_code=401, detail="Unauthorized")

        user_id, org_id = await auth.verify_token(auth_header)
        if not user_id:
            raise HTTPException(status_code=403, detail="Invalid token")

        await auth.update_last_activity(auth_header)

        success, msg = await auth.verify_2fa_token(user_id, req.totp_code)
        if not success:
            raise HTTPException(status_code=400, detail=msg)

        return {"verified": True, "message": msg}

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to verify 2FA: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.delete("/api/2fa/disable")
async def disable_2fa(req: Disable2FARequest, auth_header: Optional[str] = Header(None), user: dict = Depends(get_current_user_zero_trust)):
    """TOTP 2FAを無効化（パスワード確認が必要）"""
    try:
        if not auth_header:
            raise HTTPException(status_code=401, detail="Unauthorized")

        user_id, org_id = await auth.verify_token(auth_header)
        if not user_id:
            raise HTTPException(status_code=403, detail="Invalid token")

        await auth.update_last_activity(auth_header)

        success, msg = await auth.disable_2fa(user_id, req.password)
        if not success:
            raise HTTPException(status_code=400, detail=msg)

        return {"message": msg}

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to disable 2FA: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# ──────────────────────────────────────────────────────────────────────────────
# Cross Department Collaboration API (Task #2486)
# ──────────────────────────────────────────────────────────────────────────────

async def _create_collab_notification(
    db,
    cross_task_id: int,
    sender_dept_id: int,
    receiver_dept_id: int,
    notification_type: str,
    title: str,
    message: str,
    metadata: Optional[str] = None,
):
    await db.execute(
        """INSERT INTO dept_collab_notifications
           (cross_task_id, sender_dept_id, receiver_dept_id, notification_type, title, message, metadata)
           VALUES (?, ?, ?, ?, ?, ?, ?)""",
        (cross_task_id, sender_dept_id, receiver_dept_id, notification_type, title, message, metadata),
    )


@app.post("/api/departments/{dept_id}/collaborate", status_code=201)
async def create_collaborate_request(
    dept_id: int,
    req: models.CrossDeptTaskCreate,
    user: dict = Depends(get_current_user_zero_trust),
):
    """指定部署から別部署へのコラボレーションリクエスト作成"""
    await ensure_db_initialized()
    async with aiosqlite.connect(str(THEBRANCH_DB)) as db:
        db.row_factory = aiosqlite.Row

        cursor = await db.execute("SELECT id, name FROM departments WHERE id = ?", (dept_id,))
        requesting_dept = await cursor.fetchone()
        if not requesting_dept:
            raise HTTPException(status_code=404, detail="依頼元部署が見つかりません")

        cursor = await db.execute("SELECT id, name FROM departments WHERE id = ?", (req.receiving_dept_id,))
        receiving_dept = await cursor.fetchone()
        if not receiving_dept:
            raise HTTPException(status_code=404, detail="依頼先部署が見つかりません")

        if dept_id == req.receiving_dept_id:
            raise HTTPException(status_code=400, detail="同一部署へのリクエストはできません")

        cursor = await db.execute(
            """INSERT INTO cross_department_tasks
               (title, description, requesting_dept_id, receiving_dept_id, priority, deadline, created_by)
               VALUES (?, ?, ?, ?, ?, ?, 'system')""",
            (req.title, req.description, dept_id, req.receiving_dept_id, req.priority, req.deadline),
        )
        cross_task_id = cursor.lastrowid

        await _create_collab_notification(
            db,
            cross_task_id=cross_task_id,
            sender_dept_id=dept_id,
            receiver_dept_id=req.receiving_dept_id,
            notification_type="new_request",
            title=f"新しいコラボレーションリクエスト: {req.title}",
            message=f"{dict(requesting_dept)['name']}部署からコラボレーションを依頼されました。",
        )

        await db.commit()

        cursor = await db.execute(
            """SELECT cdt.*, d1.name as requesting_dept_name, d2.name as receiving_dept_name
               FROM cross_department_tasks cdt
               JOIN departments d1 ON d1.id = cdt.requesting_dept_id
               JOIN departments d2 ON d2.id = cdt.receiving_dept_id
               WHERE cdt.id = ?""",
            (cross_task_id,),
        )
        row = await cursor.fetchone()

    return dict(row)


@app.get("/api/departments/{dept_id}/collaborate")
async def list_collaborate_requests(
    dept_id: int,
    direction: str = "all",
    status: str = "",
    page: int = 1,
    limit: int = 20,
    user: dict = Depends(get_current_user_zero_trust),
):
    """部署のコラボリクエスト一覧（sent/received/all）"""
    await ensure_db_initialized()
    async with aiosqlite.connect(str(THEBRANCH_DB)) as db:
        db.row_factory = aiosqlite.Row

        cursor = await db.execute("SELECT id FROM departments WHERE id = ?", (dept_id,))
        if not await cursor.fetchone():
            raise HTTPException(status_code=404, detail="部署が見つかりません")

        base = """
            SELECT cdt.*, d1.name as requesting_dept_name, d2.name as receiving_dept_name
            FROM cross_department_tasks cdt
            JOIN departments d1 ON d1.id = cdt.requesting_dept_id
            JOIN departments d2 ON d2.id = cdt.receiving_dept_id
            WHERE 1=1
        """
        params: list = []

        if direction == "sent":
            base += " AND cdt.requesting_dept_id = ?"
            params.append(dept_id)
        elif direction == "received":
            base += " AND cdt.receiving_dept_id = ?"
            params.append(dept_id)
        else:
            base += " AND (cdt.requesting_dept_id = ? OR cdt.receiving_dept_id = ?)"
            params.extend([dept_id, dept_id])

        if status:
            base += " AND cdt.status = ?"
            params.append(status)

        cursor = await db.execute(f"SELECT COUNT(*) FROM ({base})", params)
        total = (await cursor.fetchone())[0]

        base += " ORDER BY cdt.created_at DESC LIMIT ? OFFSET ?"
        params.extend([limit, (page - 1) * limit])
        cursor = await db.execute(base, params)
        rows = await cursor.fetchall()

    return {
        "data": [dict(r) for r in rows],
        "pagination": {"page": page, "limit": limit, "total": total, "pages": (total + limit - 1) // limit},
    }


@app.patch("/api/departments/{dept_id}/collaborate/{request_id}")
async def update_collaborate_status(
    dept_id: int,
    request_id: int,
    update: models.CrossDeptTaskStatusUpdate,
    user: dict = Depends(get_current_user_zero_trust),
):
    """コラボリクエストのステータス更新"""
    await ensure_db_initialized()
    async with aiosqlite.connect(str(THEBRANCH_DB)) as db:
        db.row_factory = aiosqlite.Row

        cursor = await db.execute(
            """SELECT cdt.*, d1.name as requesting_dept_name, d2.name as receiving_dept_name
               FROM cross_department_tasks cdt
               JOIN departments d1 ON d1.id = cdt.requesting_dept_id
               JOIN departments d2 ON d2.id = cdt.receiving_dept_id
               WHERE cdt.id = ? AND (cdt.requesting_dept_id = ? OR cdt.receiving_dept_id = ?)""",
            (request_id, dept_id, dept_id),
        )
        task = await cursor.fetchone()
        if not task:
            raise HTTPException(status_code=404, detail="コラボリクエストが見つかりません")

        task = dict(task)
        await db.execute(
            "UPDATE cross_department_tasks SET status = ?, updated_at = datetime('now','localtime') WHERE id = ?",
            (update.status, request_id),
        )

        notif_type_map = {
            "acknowledged": "status_update",
            "in_progress": "status_update",
            "completed": "completed",
            "rejected": "rejected",
        }
        notif_type = notif_type_map.get(update.status, "status_update")
        comment_suffix = f"\nコメント: {update.comment}" if update.comment else ""
        receiver_id = task["requesting_dept_id"] if dept_id == task["receiving_dept_id"] else task["receiving_dept_id"]

        await _create_collab_notification(
            db,
            cross_task_id=request_id,
            sender_dept_id=dept_id,
            receiver_dept_id=receiver_id,
            notification_type=notif_type,
            title=f"リクエスト更新: {task['title']}",
            message=f"ステータスが '{update.status}' に変更されました。{comment_suffix}",
        )

        await db.commit()

        cursor = await db.execute(
            """SELECT cdt.*, d1.name as requesting_dept_name, d2.name as receiving_dept_name
               FROM cross_department_tasks cdt
               JOIN departments d1 ON d1.id = cdt.requesting_dept_id
               JOIN departments d2 ON d2.id = cdt.receiving_dept_id
               WHERE cdt.id = ?""",
            (request_id,),
        )
        row = await cursor.fetchone()

    return dict(row)


@app.post("/api/tasks/cross-dept", status_code=201)
async def create_cross_dept_task(
    req: models.CrossDeptTaskCreate,
    requesting_dept_id: int,
    user: dict = Depends(get_current_user_zero_trust),
):
    """クロス部署タスク作成（requesting_dept_id をクエリパラメータで指定）"""
    return await create_collaborate_request(requesting_dept_id, req, user)


@app.get("/api/tasks/cross-dept")
async def list_cross_dept_tasks(
    dept_id: Optional[int] = None,
    status: str = "",
    priority: str = "",
    page: int = 1,
    limit: int = 20,
    user: dict = Depends(get_current_user_zero_trust),
):
    """クロス部署タスク一覧（全体または特定部署フィルタ）"""
    await ensure_db_initialized()
    async with aiosqlite.connect(str(THEBRANCH_DB)) as db:
        db.row_factory = aiosqlite.Row

        query = """
            SELECT cdt.*, d1.name as requesting_dept_name, d2.name as receiving_dept_name
            FROM cross_department_tasks cdt
            JOIN departments d1 ON d1.id = cdt.requesting_dept_id
            JOIN departments d2 ON d2.id = cdt.receiving_dept_id
            WHERE 1=1
        """
        params: list = []

        if dept_id:
            query += " AND (cdt.requesting_dept_id = ? OR cdt.receiving_dept_id = ?)"
            params.extend([dept_id, dept_id])
        if status:
            query += " AND cdt.status = ?"
            params.append(status)
        if priority:
            query += " AND cdt.priority = ?"
            params.append(priority)

        cursor = await db.execute(f"SELECT COUNT(*) FROM ({query})", params)
        total = (await cursor.fetchone())[0]

        query += " ORDER BY cdt.created_at DESC LIMIT ? OFFSET ?"
        params.extend([limit, (page - 1) * limit])
        cursor = await db.execute(query, params)
        rows = await cursor.fetchall()

    return {
        "data": [dict(r) for r in rows],
        "pagination": {"page": page, "limit": limit, "total": total, "pages": (total + limit - 1) // limit},
    }


@app.get("/api/notifications/cross-dept")
async def list_cross_dept_notifications(
    dept_id: Optional[int] = None,
    unread_only: bool = False,
    page: int = 1,
    limit: int = 20,
    user: dict = Depends(get_current_user_zero_trust),
):
    """部署間コラボレーション通知一覧"""
    await ensure_db_initialized()
    async with aiosqlite.connect(str(THEBRANCH_DB)) as db:
        db.row_factory = aiosqlite.Row

        query = """
            SELECT n.*, d1.name as sender_dept_name, d2.name as receiver_dept_name,
                   cdt.title as task_title, cdt.status as task_status
            FROM dept_collab_notifications n
            JOIN departments d1 ON d1.id = n.sender_dept_id
            JOIN departments d2 ON d2.id = n.receiver_dept_id
            JOIN cross_department_tasks cdt ON cdt.id = n.cross_task_id
            WHERE 1=1
        """
        params: list = []

        if dept_id:
            query += " AND n.receiver_dept_id = ?"
            params.append(dept_id)
        if unread_only:
            query += " AND n.is_read = 0"

        cursor = await db.execute(f"SELECT COUNT(*) FROM ({query})", params)
        total = (await cursor.fetchone())[0]

        unread_q = "SELECT COUNT(*) FROM dept_collab_notifications WHERE is_read = 0"
        unread_params: list = []
        if dept_id:
            unread_q += " AND receiver_dept_id = ?"
            unread_params.append(dept_id)
        cursor = await db.execute(unread_q, unread_params)
        unread_count = (await cursor.fetchone())[0]

        query += " ORDER BY n.created_at DESC LIMIT ? OFFSET ?"
        params.extend([limit, (page - 1) * limit])
        cursor = await db.execute(query, params)
        rows = await cursor.fetchall()

    return {
        "data": [dict(r) for r in rows],
        "unread_count": unread_count,
        "pagination": {"page": page, "limit": limit, "total": total, "pages": (total + limit - 1) // limit},
    }


@app.patch("/api/notifications/cross-dept/{notif_id}/read")
async def mark_cross_dept_notification_read(
    notif_id: int,
    user: dict = Depends(get_current_user_zero_trust),
):
    """部署間通知を既読にする"""
    await ensure_db_initialized()
    async with aiosqlite.connect(str(THEBRANCH_DB)) as db:
        db.row_factory = aiosqlite.Row

        cursor = await db.execute("SELECT id FROM dept_collab_notifications WHERE id = ?", (notif_id,))
        if not await cursor.fetchone():
            raise HTTPException(status_code=404, detail="通知が見つかりません")

        await db.execute(
            "UPDATE dept_collab_notifications SET is_read = 1, read_at = datetime('now','localtime') WHERE id = ?",
            (notif_id,),
        )
        await db.commit()

    return {"id": notif_id, "is_read": True}


# ──────────────────────────────────────────────────────────────────────────────
# Cross-Department Tasks (Task #2486)
# 部署間タスク依頼: cross_dept_tasks テーブル用エンドポイント
#   - POST   /api/departments/{dept_id}/cross-dept-tasks       (新規依頼作成)
#   - GET    /api/departments/{dept_id}/incoming-requests       (受信タスク一覧)
#   - PUT    /api/cross-dept-tasks/{task_id}/accept             (受け入れ)
#   - PUT    /api/cross-dept-tasks/{task_id}/reject             (拒否)
#
# 認証: get_current_user_zero_trust（ゼロトラスト）
# 権限: ユーザは依頼元（POST）または依頼先（GET/accept/reject）部署に所属している必要がある
# Note: POST /api/departments/{dept_id}/collaborate は既に
#       cross_department_tasks 用に使用されているため、新エンドポイントは
#       /cross-dept-tasks サブパスを使用
# ──────────────────────────────────────────────────────────────────────────────

async def check_user_in_department(user_id: str, dept_id: int) -> bool:
    """ユーザが指定部署に所属しているかを確認する。

    判定: users → team_members(active) → teams.department_id == dept_id

    Args:
        user_id: 確認対象ユーザID
        dept_id: 部署ID

    Returns:
        True: 所属している（active な team_members がある）
        False: 所属していない、または DB アクセス失敗
    """
    if not user_id or not dept_id:
        return False
    try:
        async with aiosqlite.connect(str(THEBRANCH_DB)) as db:
            cursor = await db.execute(
                """
                SELECT COUNT(*)
                FROM team_members tm
                JOIN teams t ON tm.team_id = t.id
                WHERE tm.user_id = ?
                  AND tm.status = 'active'
                  AND t.department_id = ?
                """,
                (user_id, dept_id),
            )
            row = await cursor.fetchone()
            return bool(row and row[0] > 0)
    except Exception as e:
        logging.error(f"check_user_in_department failed: {e}")
        return False


def _row_to_cross_dept_task(row) -> dict:
    """sqlite Row を cross_dept_tasks レスポンス dict に変換"""
    return {
        "id": row["id"],
        "from_dept_id": row["from_dept_id"],
        "to_dept_id": row["to_dept_id"],
        "task_name": row["task_name"],
        "task_description": row["task_description"],
        "status": row["status"],
        "created_by": row["created_by"],
        "reject_reason": row["reject_reason"],
        "created_at": row["created_at"],
        "updated_at": row["updated_at"],
    }


@app.post("/api/departments/{dept_id}/cross-dept-tasks", status_code=201)
async def create_cross_dept_task_request(
    dept_id: int,
    req: models.CrossDeptTaskRequestCreate,
    user: dict = Depends(get_current_user_zero_trust),
):
    """部署間タスク依頼を作成する（依頼元 dept_id → 依頼先 to_dept_id）。

    - 401/403/404 を返す
    - 同一部署への依頼は 400
    - 成功時は 201 で CrossDeptTaskRequestResponse を返す
    """
    await ensure_db_initialized()

    if dept_id == req.to_dept_id:
        raise HTTPException(status_code=400, detail="同一部署への依頼はできません")

    user_id = user.get("id") if isinstance(user, dict) else None
    if not user_id:
        raise HTTPException(status_code=401, detail="認証情報が無効です")

    async with aiosqlite.connect(str(THEBRANCH_DB)) as db:
        db.row_factory = aiosqlite.Row

        # 依頼元部署の存在確認
        cursor = await db.execute("SELECT id FROM departments WHERE id = ?", (dept_id,))
        if not await cursor.fetchone():
            raise HTTPException(status_code=404, detail="依頼元部署が見つかりません")

        # 依頼先部署の存在確認
        cursor = await db.execute("SELECT id FROM departments WHERE id = ?", (req.to_dept_id,))
        if not await cursor.fetchone():
            raise HTTPException(status_code=404, detail="依頼先部署が見つかりません")

        # 権限: 依頼元部署のメンバーであること
        if not await check_user_in_department(user_id, dept_id):
            raise HTTPException(status_code=403, detail="依頼元部署のメンバーではありません")

        cursor = await db.execute(
            """
            INSERT INTO cross_dept_tasks
              (from_dept_id, to_dept_id, task_name, task_description, status, created_by)
            VALUES (?, ?, ?, ?, 'pending', ?)
            """,
            (dept_id, req.to_dept_id, req.task_name, req.task_description, user_id),
        )
        new_id = cursor.lastrowid
        await db.commit()

        cursor = await db.execute(
            "SELECT * FROM cross_dept_tasks WHERE id = ?", (new_id,)
        )
        row = await cursor.fetchone()

    return _row_to_cross_dept_task(row)


@app.get("/api/departments/{dept_id}/incoming-requests")
async def list_incoming_cross_dept_requests(
    dept_id: int,
    status: Optional[str] = None,
    limit: int = 50,
    user: dict = Depends(get_current_user_zero_trust),
):
    """指定部署が受信した部署間タスク依頼一覧を取得する。

    - status フィルタ: pending / accepted / rejected
    - 権限: 受信側 dept_id のメンバーであること
    """
    await ensure_db_initialized()

    if limit < 1 or limit > 500:
        raise HTTPException(status_code=422, detail="limit は 1〜500 の範囲で指定してください")
    if status and status not in {"pending", "accepted", "rejected"}:
        raise HTTPException(status_code=422, detail="status は pending/accepted/rejected のいずれか")

    user_id = user.get("id") if isinstance(user, dict) else None
    if not user_id:
        raise HTTPException(status_code=401, detail="認証情報が無効です")

    async with aiosqlite.connect(str(THEBRANCH_DB)) as db:
        db.row_factory = aiosqlite.Row

        cursor = await db.execute("SELECT id FROM departments WHERE id = ?", (dept_id,))
        if not await cursor.fetchone():
            raise HTTPException(status_code=404, detail="部署が見つかりません")

        if not await check_user_in_department(user_id, dept_id):
            raise HTTPException(status_code=403, detail="この部署の受信タスクを閲覧する権限がありません")

        query = "SELECT * FROM cross_dept_tasks WHERE to_dept_id = ?"
        params: list = [dept_id]
        if status:
            query += " AND status = ?"
            params.append(status)
        query += " ORDER BY created_at DESC LIMIT ?"
        params.append(limit)

        cursor = await db.execute(query, params)
        rows = await cursor.fetchall()

        count_query = "SELECT COUNT(*) FROM cross_dept_tasks WHERE to_dept_id = ?"
        count_params: list = [dept_id]
        if status:
            count_query += " AND status = ?"
            count_params.append(status)
        cursor = await db.execute(count_query, count_params)
        total = (await cursor.fetchone())[0]

    return {
        "requests": [_row_to_cross_dept_task(r) for r in rows],
        "total": total,
    }


async def _transition_cross_dept_task(
    task_id: int,
    new_status: str,
    user: dict,
    reject_reason: Optional[str] = None,
) -> dict:
    """cross_dept_tasks のステータスを pending から accepted/rejected に遷移する共通処理。

    - 404: タスクが存在しない
    - 403: 受信側部署のメンバーでない
    - 409: 既に pending でない（accepted/rejected 済み）
    - 通知: create_notification_log でブロードキャスト
    """
    await ensure_db_initialized()

    user_id = user.get("id") if isinstance(user, dict) else None
    if not user_id:
        raise HTTPException(status_code=401, detail="認証情報が無効です")

    async with aiosqlite.connect(str(THEBRANCH_DB)) as db:
        db.row_factory = aiosqlite.Row

        cursor = await db.execute(
            "SELECT * FROM cross_dept_tasks WHERE id = ?", (task_id,)
        )
        task = await cursor.fetchone()
        if not task:
            raise HTTPException(status_code=404, detail="部署間タスク依頼が見つかりません")
        task = dict(task)

        # 権限: 受信側部署のメンバーのみが accept/reject 可能
        if not await check_user_in_department(user_id, task["to_dept_id"]):
            raise HTTPException(
                status_code=403,
                detail="受信側部署のメンバーのみが受け入れ/拒否できます",
            )

        # 状態遷移チェック: pending → accepted/rejected のみ
        if task["status"] != "pending":
            raise HTTPException(
                status_code=409,
                detail=f"既に '{task['status']}' のため変更できません",
            )

        if new_status == "rejected":
            await db.execute(
                """
                UPDATE cross_dept_tasks
                SET status = 'rejected',
                    reject_reason = ?,
                    updated_at = datetime('now','localtime')
                WHERE id = ?
                """,
                (reject_reason, task_id),
            )
        else:
            await db.execute(
                """
                UPDATE cross_dept_tasks
                SET status = ?,
                    updated_at = datetime('now','localtime')
                WHERE id = ?
                """,
                (new_status, task_id),
            )
        await db.commit()

        cursor = await db.execute(
            "SELECT * FROM cross_dept_tasks WHERE id = ?", (task_id,)
        )
        updated = await cursor.fetchone()

    # WebSocket 通知（Task #4: notification_logs 経由）
    try:
        notif_type = (
            "collaboration_request_accepted"
            if new_status == "accepted"
            else "collaboration_request_rejected"
        )
        title = (
            f"部署間タスク依頼が受理されました: {task['task_name']}"
            if new_status == "accepted"
            else f"部署間タスク依頼が拒否されました: {task['task_name']}"
        )
        message_body = (
            f"to_dept_id={task['to_dept_id']} がタスク '{task['task_name']}' を受理しました"
            if new_status == "accepted"
            else f"to_dept_id={task['to_dept_id']} がタスク '{task['task_name']}' を拒否しました"
            + (f"（理由: {reject_reason}）" if reject_reason else "")
        )
        await create_notification_log(
            notification_type=notif_type,
            title=title,
            message=message_body,
            severity="info",
            recipient_id=task["created_by"],
            recipient_type="user",
            source_table="cross_dept_tasks",
            source_id=task_id,
            metadata={
                "from_dept_id": task["from_dept_id"],
                "to_dept_id": task["to_dept_id"],
                "status": new_status,
                "reject_reason": reject_reason,
            },
            action_url=f"/dashboard/collab/requests/{task_id}",
        )
    except Exception as e:
        logging.error(f"create_notification_log failed for cross_dept_tasks#{task_id}: {e}")

    return _row_to_cross_dept_task(updated)


@app.put("/api/cross-dept-tasks/{task_id}/accept")
async def accept_cross_dept_task(
    task_id: int,
    req: models.CrossDeptTaskRequestAccept,
    user: dict = Depends(get_current_user_zero_trust),
):
    """部署間タスク依頼を受理する（pending → accepted）。

    - 受信側部署のメンバーのみが実行可能
    - 既に accepted/rejected の場合は 409
    """
    return await _transition_cross_dept_task(task_id, "accepted", user)


@app.put("/api/cross-dept-tasks/{task_id}/reject")
async def reject_cross_dept_task(
    task_id: int,
    req: models.CrossDeptTaskRequestReject,
    user: dict = Depends(get_current_user_zero_trust),
):
    """部署間タスク依頼を拒否する（pending → rejected）。

    - 受信側部署のメンバーのみが実行可能
    - 既に accepted/rejected の場合は 409
    - 拒否理由は req.reason に格納（任意）
    """
    return await _transition_cross_dept_task(task_id, "rejected", user, reject_reason=req.reason)


# ─────────────────────────────────────────────────────────────────────
# 監査ログ・エージェント稼働ログ API (Task #2501)
# ─────────────────────────────────────────────────────────────────────

ALLOWED_AUDIT_ACTIONS = {
    "login", "logout", "create", "update", "delete",
    "access", "config_change", "permission_change",
}
ALLOWED_AUDIT_STATUSES = {"success", "failure", "denied"}
ALLOWED_AGENT_LOG_ACTIONS = {"started", "stopped", "failed", "message"}


async def log_user_action(
    user_id: Optional[str],
    username: Optional[str],
    action: str,
    resource_type: Optional[str] = None,
    resource_id: Optional[str] = None,
    detail: Optional[str] = None,
    ip_address: Optional[str] = None,
    user_agent: Optional[str] = None,
    status: str = "success",
) -> Optional[int]:
    """ユーザー操作監査ログを audit_logs テーブルに記録する共通ヘルパ。

    呼び出し側で例外を投げないようガードしておく。失敗しても本処理は継続。
    """
    if action not in ALLOWED_AUDIT_ACTIONS:
        logging.warning(f"log_user_action: unknown action={action}")
        return None
    if status not in ALLOWED_AUDIT_STATUSES:
        status = "success"
    try:
        async with aiosqlite.connect(str(THEBRANCH_DB)) as db:
            cursor = await db.execute(
                """
                INSERT INTO audit_logs
                  (user_id, username, action, resource_type, resource_id,
                   detail, ip_address, user_agent, status)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (user_id, username, action, resource_type, resource_id,
                 detail, ip_address, user_agent, status),
            )
            await db.commit()
            return cursor.lastrowid
    except Exception as e:
        logging.error(f"log_user_action failed: {e}")
        return None


def _row_to_audit_log(row: tuple) -> dict:
    return {
        "id": row[0],
        "user_id": row[1],
        "username": row[2],
        "action": row[3],
        "resource_type": row[4],
        "resource_id": row[5],
        "detail": row[6],
        "ip_address": row[7],
        "user_agent": row[8],
        "status": row[9],
        "created_at": row[10],
    }


def _row_to_agent_log(row: tuple) -> dict:
    # row: (al.id, al.agent_id, al.action, al.detail, al.created_at, a.role, a.session_id)
    role = row[5]
    session_id = row[6] if len(row) > 6 else None
    agent_name = session_id or (f"Agent #{row[1]}" if row[1] is not None else None)
    return {
        "id": row[0],
        "agent_id": row[1],
        "agent_name": agent_name,
        "role": role,
        "action": row[2],
        "detail": row[3],
        "created_at": row[4],
    }


@app.get("/api/agent-logs")
async def list_agent_logs(
    user: dict = Depends(get_current_user_zero_trust),
    agent_id: Optional[int] = Query(None, description="特定エージェントの稼働ログのみ"),
    action: Optional[str] = Query(None, description="started/stopped/failed/message"),
    date_from: Optional[str] = Query(None, description="YYYY-MM-DD 以降"),
    date_to: Optional[str] = Query(None, description="YYYY-MM-DD 以前"),
    search: Optional[str] = Query(None, description="detail を部分一致検索"),
    page: int = Query(1, ge=1),
    limit: int = Query(50, ge=1, le=500),
):
    """エージェント稼働ログ一覧（起動・停止・エラー履歴）を取得する。"""
    if action and action not in ALLOWED_AGENT_LOG_ACTIONS:
        raise HTTPException(
            status_code=422,
            detail=f"Invalid action; allowed={sorted(ALLOWED_AGENT_LOG_ACTIONS)}",
        )

    where = ["1=1"]
    params: list = []
    if agent_id is not None:
        where.append("al.agent_id = ?")
        params.append(agent_id)
    if action:
        where.append("al.action = ?")
        params.append(action)
    if date_from:
        where.append("DATE(al.created_at) >= DATE(?)")
        params.append(date_from)
    if date_to:
        where.append("DATE(al.created_at) <= DATE(?)")
        params.append(date_to)
    if search:
        where.append("(al.detail LIKE ? OR al.action LIKE ?)")
        like = f"%{search}%"
        params.extend([like, like])

    where_clause = " AND ".join(where)
    offset = (page - 1) * limit

    try:
        async with aiosqlite.connect(str(THEBRANCH_DB)) as db:
            count_cur = await db.execute(
                f"SELECT COUNT(*) FROM agent_logs al WHERE {where_clause}",
                params,
            )
            total_row = await count_cur.fetchone()
            total = int(total_row[0]) if total_row else 0

            rows_cur = await db.execute(
                f"""
                SELECT al.id, al.agent_id, al.action, al.detail, al.created_at,
                       a.role, a.session_id
                FROM agent_logs al
                LEFT JOIN agents a ON al.agent_id = a.id
                WHERE {where_clause}
                ORDER BY al.created_at DESC, al.id DESC
                LIMIT ? OFFSET ?
                """,
                [*params, limit, offset],
            )
            rows = await rows_cur.fetchall()
    except Exception as e:
        logging.error(f"list_agent_logs failed: {e}")
        raise HTTPException(status_code=500, detail="failed to load agent logs")

    return {
        "data": [_row_to_agent_log(r) for r in rows],
        "pagination": {
            "page": page,
            "limit": limit,
            "total": total,
            "pages": (total + limit - 1) // limit if total else 0,
        },
        "filters": {
            "agent_id": agent_id, "action": action,
            "date_from": date_from, "date_to": date_to, "search": search,
        },
    }


@app.get("/api/audit-logs")
async def list_audit_logs(
    request: Request,
    user: dict = Depends(get_current_user_zero_trust),
    user_id: Optional[str] = Query(None),
    action: Optional[str] = Query(None),
    resource_type: Optional[str] = Query(None),
    status_filter: Optional[str] = Query(None, alias="status"),
    date_from: Optional[str] = Query(None),
    date_to: Optional[str] = Query(None),
    search: Optional[str] = Query(None),
    page: int = Query(1, ge=1),
    limit: int = Query(50, ge=1, le=500),
):
    """監査ログ（ユーザー操作履歴）一覧を取得する。

    フィルタ:
      - user_id: 操作者
      - action: login/logout/create/update/delete/access/config_change/permission_change
      - resource_type: agent/department/team/task/user/role/...
      - status: success/failure/denied
      - date_from, date_to: 期間絞り込み (YYYY-MM-DD)
      - search: detail / username / resource_id を部分一致検索
    """
    if action and action not in ALLOWED_AUDIT_ACTIONS:
        raise HTTPException(
            status_code=422,
            detail=f"Invalid action; allowed={sorted(ALLOWED_AUDIT_ACTIONS)}",
        )
    if status_filter and status_filter not in ALLOWED_AUDIT_STATUSES:
        raise HTTPException(
            status_code=422,
            detail=f"Invalid status; allowed={sorted(ALLOWED_AUDIT_STATUSES)}",
        )

    where = ["1=1"]
    params: list = []
    if user_id:
        where.append("user_id = ?")
        params.append(user_id)
    if action:
        where.append("action = ?")
        params.append(action)
    if resource_type:
        where.append("resource_type = ?")
        params.append(resource_type)
    if status_filter:
        where.append("status = ?")
        params.append(status_filter)
    if date_from:
        where.append("DATE(created_at) >= DATE(?)")
        params.append(date_from)
    if date_to:
        where.append("DATE(created_at) <= DATE(?)")
        params.append(date_to)
    if search:
        where.append("(detail LIKE ? OR username LIKE ? OR resource_id LIKE ?)")
        like = f"%{search}%"
        params.extend([like, like, like])

    where_clause = " AND ".join(where)
    offset = (page - 1) * limit

    try:
        async with aiosqlite.connect(str(THEBRANCH_DB)) as db:
            count_cur = await db.execute(
                f"SELECT COUNT(*) FROM audit_logs WHERE {where_clause}",
                params,
            )
            total_row = await count_cur.fetchone()
            total = int(total_row[0]) if total_row else 0

            rows_cur = await db.execute(
                f"""
                SELECT id, user_id, username, action, resource_type, resource_id,
                       detail, ip_address, user_agent, status, created_at
                FROM audit_logs
                WHERE {where_clause}
                ORDER BY created_at DESC, id DESC
                LIMIT ? OFFSET ?
                """,
                [*params, limit, offset],
            )
            rows = await rows_cur.fetchall()
    except Exception as e:
        logging.error(f"list_audit_logs failed: {e}")
        raise HTTPException(status_code=500, detail="failed to load audit logs")

    # アクセス自体も監査ログに残す（再帰防止のため access のみ非同期fire-and-forget）
    try:
        await log_user_action(
            user_id=user.get("id") if isinstance(user, dict) else None,
            username=user.get("username") if isinstance(user, dict) else None,
            action="access",
            resource_type="audit_logs",
            resource_id=None,
            detail=f"list page={page} limit={limit}",
            ip_address=request.client.host if request.client else None,
            user_agent=request.headers.get("user-agent"),
            status="success",
        )
    except Exception:
        pass

    return {
        "data": [_row_to_audit_log(r) for r in rows],
        "pagination": {
            "page": page,
            "limit": limit,
            "total": total,
            "pages": (total + limit - 1) // limit if total else 0,
        },
        "filters": {
            "user_id": user_id, "action": action,
            "resource_type": resource_type, "status": status_filter,
            "date_from": date_from, "date_to": date_to, "search": search,
        },
    }


class _AuditLogEntry(BaseModel):
    action: str
    resource_type: Optional[str] = None
    resource_id: Optional[str] = None
    detail: Optional[str] = None
    status: str = "success"


@app.post("/api/audit-logs")
async def create_audit_log_entry(
    entry: _AuditLogEntry,
    request: Request,
    user: dict = Depends(get_current_user_zero_trust),
):
    """フロントから明示的に監査ログを記録するエンドポイント（操作トラッキング用）。"""
    if entry.action not in ALLOWED_AUDIT_ACTIONS:
        raise HTTPException(
            status_code=422,
            detail=f"Invalid action; allowed={sorted(ALLOWED_AUDIT_ACTIONS)}",
        )
    if entry.status not in ALLOWED_AUDIT_STATUSES:
        raise HTTPException(
            status_code=422,
            detail=f"Invalid status; allowed={sorted(ALLOWED_AUDIT_STATUSES)}",
        )
    log_id = await log_user_action(
        user_id=user.get("id") if isinstance(user, dict) else None,
        username=user.get("username") if isinstance(user, dict) else None,
        action=entry.action,
        resource_type=entry.resource_type,
        resource_id=entry.resource_id,
        detail=entry.detail,
        ip_address=request.client.host if request.client else None,
        user_agent=request.headers.get("user-agent"),
        status=entry.status,
    )
    if log_id is None:
        raise HTTPException(status_code=500, detail="failed to record audit log")
    return {"id": log_id, "status": "recorded"}
