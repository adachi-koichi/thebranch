import asyncio
import json
import os
import re
import shutil
import sqlite3
import subprocess
import time
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from datetime import datetime
from typing import AsyncGenerator, Optional

import aiosqlite
import yaml
from fastapi import FastAPI, HTTPException, WebSocket, WebSocketDisconnect, Header
from fastapi.responses import HTMLResponse, StreamingResponse
from pydantic import BaseModel

from . import auth
from . import models
from workflow.repositories.template import TemplateRepository
from workflow.services.template import TemplateService
from workflow.validation.template import TemplateValidator

TASKS_DB = Path.home() / ".claude" / "skills" / "task-manager-sqlite" / "data" / "tasks.sqlite"
SESSIONS_DIR = Path.home() / ".claude" / "sessions"
PROJECTS_DIR = Path.home() / ".claude" / "projects"
TASK_SCRIPT = Path.home() / ".claude" / "skills" / "task-manager-sqlite" / "scripts" / "task.py"
PORTS_YAML = Path(__file__).parent.parent / "ports.yaml"
MONITORING_YAML = Path(__file__).parent.parent / "monitoring.yaml"
TMUX_BIN = shutil.which("tmux") or "/opt/homebrew/bin/tmux"

app = FastAPI()

DASHBOARD_DIR = Path(__file__).parent
THEBRANCH_DB = DASHBOARD_DIR / "data" / "thebranch.sqlite"

# ──────────────────────────────────────────────
# Workflow Services
# ──────────────────────────────────────────────

template_repo = None
template_service = None

def init_workflow_services():
    global template_repo, template_service
    if template_repo is None:
        template_repo = TemplateRepository(str(THEBRANCH_DB))
        template_service = TemplateService(template_repo, TemplateValidator(template_repo))

def get_template_service():
    if template_service is None:
        init_workflow_services()
    return template_service

def get_template_repo():
    if template_repo is None:
        init_workflow_services()
    return template_repo


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
async def get_ports():
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
async def get_tasks(status: str = "", category: str = "", dir_filter: str = "", limit: int = 0):
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


@app.post("/api/tasks")
async def create_task(req: CreateTaskRequest):
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
async def update_task_status(task_id: int, req: UpdateStatusRequest):
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
async def reorder_tasks(req: ReorderRequest):
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
async def get_dashboard_summary():
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
async def export_tasks(format: str = "json"):
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
async def get_tasks_stats(days: int = 30):
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
async def get_agent_performance():
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
async def patch_task(task_id: int, req: PatchTaskRequest):
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
async def get_department_templates():
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
async def get_agents():
    return await get_agents_data()


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
async def stream_agents():
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
async def get_projects(status: str = "incomplete"):
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
async def api_daemons():
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
async def get_panes():
    """tmuxペイン状態をJSON形式で返す"""
    try:
        return _list_panes()
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# ──────────────────────────────────────────────
# Workflows
# ──────────────────────────────────────────────

@app.get("/api/workflows/instances")
async def get_wf_instances(status: str = ""):
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
async def get_wf_templates():
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
async def get_self_improvement():
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
async def get_sessions():
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
async def get_costs():
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
async def get_metrics():
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
async def get_alerts():
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
async def resolve_alert(alert_id: str):
    resolved_ids = _load_resolved_alerts()
    resolved_ids.add(alert_id)
    _save_resolved_alerts(resolved_ids)
    return {"ok": True}


# ──────────────────────────────────────────────
# Gantt
# ──────────────────────────────────────────────

@app.get("/api/gantt")
async def get_gantt(status: str = "incomplete", dir_filter: str = ""):
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
async def get_dag(status: str = "incomplete"):
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
async def api_cycle_stats(limit: int = 100):
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
async def api_orchestrate_history(limit: int = 100):
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
async def api_orchestrate_performance(limit: int = 100):
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
async def get_session_detail(session_name: str):
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
async def get_stats():
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
async def get_projects_summary():
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
async def get_trend(hours: int = 24):
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
async def get_stats_history(hours: int = 24):
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
async def get_alerts_pending(days: int = 7):
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
async def get_tasks_pending_alert(days: int = 7):
    """長期pendingタスク警告一覧（/api/alerts/pending のエイリアス）。"""
    return await get_alerts_pending(days=days)


# ──────────────────────────────────────────────
# Long-pending alert (#451)
# ──────────────────────────────────────────────

@app.get("/api/alerts/pending-long")
async def get_alerts_pending_long(minutes: int = 60):
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
async def get_cycle_timings(limit: int = 50):
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
async def get_cycle_stats(limit: int = 100):
    """最新N件サイクル統計（/api/cycle-stats のエイリアス）。"""
    return await api_cycle_stats(limit=limit)


# ──────────────────────────────────────────────
# Health history (#524)
# ──────────────────────────────────────────────

HEALTH_HISTORY_FILE = Path.home() / ".claude" / "orchestrator" / "health_history.jsonl"
_health_history_lock = asyncio.Lock()


@app.get("/api/health/history")
async def get_health_history(hours: int = 24):
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
async def get_health_detail():
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
async def get_sessions_summary():
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
async def get_sessions_active():
    """アクティブ（alive）なセッション一覧を返す。"""
    all_sessions = await get_sessions()
    active = [s for s in all_sessions if s.get("alive")]
    return active


# ──────────────────────────────────────────────
# Sessions status (#1509)
# ──────────────────────────────────────────────

@app.get("/api/sessions/status")
async def get_sessions_status():
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
async def create_session(req: RegisterSessionRequest):
    """セッション情報を登録する（JSON ファイルとして保存）。"""
    return await _register_session(req)


@app.post("/api/sessions/register")
async def register_session(req: RegisterSessionRequest):
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
async def bulk_create_tasks(req: BulkCreateTasksRequest):
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
async def get_logs_alerts(limit: int = 500):
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
async def get_session_task_assignments():
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
async def get_workflow_instances():
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
async def get_loop_stats(limit: int = 50):
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
async def get_health_all():
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
async def get_kpi():
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
async def get_activity(limit: int = 50):
    task_events = await _build_activity_from_db(limit=limit)
    alert_events = _build_activity_from_alerts(limit=20)
    all_events = task_events + alert_events
    all_events.sort(key=lambda e: e["ts"], reverse=True)
    return {"events": all_events[:limit]}


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
# Agent Rankings
# ──────────────────────────────────────────────

@app.get("/api/agent-rankings")
async def get_agent_rankings():
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
    success, message = await auth.create_user(user.username, user.email, user.password)
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
    user_id, token = await auth.authenticate_user(credentials.username, credentials.password)
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
async def add_role(role_req: models.UserRoleCreate, authorization: Optional[str] = Header(None)):
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


# ──────────────────────────────────────────────
# Departments (#2362) & Agents (#2391)
# ──────────────────────────────────────────────

THEBRANCH_DB = DASHBOARD_DIR / "data" / "thebranch.sqlite"

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
async def create_department(dept_req: models.DepartmentCreate):
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
async def list_departments(status: str = "", parent_id: int = None, page: int = 1, limit: int = 20):
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

@app.get("/api/departments/{dept_id}")
async def get_department(dept_id: int):
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
async def update_department(dept_id: int, update_req: models.DepartmentUpdate):
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
        if update_req.budget is not None:
            updates.append("budget = ?")
            params.append(update_req.budget)
        if update_req.status:
            updates.append("status = ?")
            params.append(update_req.status)

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

@app.delete("/api/departments/{dept_id}", status_code=204)
async def delete_department(dept_id: int):
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
async def list_department_templates(category: str = "", status: str = "active"):
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
async def add_agent_to_department(dept_id: int, agent_req: models.DepartmentAgentCreate):
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
async def list_department_agents(dept_id: int):
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
async def remove_agent_from_department(dept_id: int, agent_id: int):
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
async def create_agent(agent_req: models.AgentCreate):
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
async def get_agent(agent_id: int):
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
async def list_department_agents_managed(dept_id: int):
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
async def stop_agent(agent_id: int):
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
async def stream_activity_feed(dept_id: int):
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
    mission_req: models.MissionCreate
):
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
async def get_agent_mission(dept_id: int, agent_id: int):
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
async def create_team(dept_id: int, team_req: models.TeamCreate):
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
async def list_teams(dept_id: int):
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
async def get_team(dept_id: int, team_id: int):
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
async def update_team(dept_id: int, team_id: int, update_req: models.TeamUpdate):
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
async def delete_team(dept_id: int, team_id: int):
    await ensure_db_initialized()
    async with aiosqlite.connect(str(THEBRANCH_DB)) as db:
        await db.execute(
            "DELETE FROM teams WHERE id = ? AND department_id = ?",
            (team_id, dept_id),
        )
        await db.commit()


# Department Relations

@app.post("/api/departments/{dept_id}/relations", status_code=201)
async def create_relation(dept_id: int, rel_req: models.RelationCreate):
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
async def list_relations(dept_id: int):
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
async def delete_relation(dept_id: int, related_dept_id: int):
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
async def get_department_metrics(dept_id: int):
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
async def create_template(req: CreateTemplateRequest):
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
async def list_templates(status: Optional[str] = None, limit: int = 50, offset: int = 0):
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
async def get_template(template_id: int):
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
async def create_phase(template_id: int, req: CreatePhaseRequest):
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
async def create_task_def(template_id: int, phase_id: int, req: CreateTaskRequest):
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
async def publish_template(template_id: int):
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
# Onboarding
# ──────────────────────────────────────────────

@app.post("/api/onboarding/complete", status_code=201, response_model=models.OnboardingCompleteResponse)
async def complete_onboarding(
    req: models.OnboardingRequest,
    authorization: Optional[str] = Header(None)
):
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
# Entry point
# ──────────────────────────────────────────────

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=7002)
