"""Management dashboard routes — no auth required (internal use)."""
import aiosqlite
from pathlib import Path
from fastapi import APIRouter, HTTPException
from fastapi.responses import HTMLResponse
from pydantic import BaseModel
from typing import Optional

router = APIRouter()

DASHBOARD_DIR = Path(__file__).parent
THEBRANCH_DB = DASHBOARD_DIR / "data" / "thebranch.sqlite"
TASKS_DB = Path.home() / ".claude" / "skills" / "task-manager-sqlite" / "data" / "tasks.sqlite"


@router.get("/manage", response_class=HTMLResponse)
async def manage_dashboard():
    html_path = DASHBOARD_DIR / "manage.html"
    return HTMLResponse(content=html_path.read_text(encoding="utf-8"))


@router.get("/api/manage/departments")
async def manage_get_departments():
    async with aiosqlite.connect(str(THEBRANCH_DB)) as db:
        db.row_factory = aiosqlite.Row
        cursor = await db.execute(
            "SELECT id, name, description, created_at, updated_at FROM departments ORDER BY name"
        )
        rows = await cursor.fetchall()
    return [dict(r) for r in rows]


@router.get("/api/manage/tasks")
async def manage_get_tasks(status: str = "", limit: int = 200):
    if not TASKS_DB.exists():
        return []
    async with aiosqlite.connect(str(TASKS_DB)) as db:
        db.row_factory = aiosqlite.Row
        if status and status != "all":
            cursor = await db.execute(
                "SELECT id, title, description, status, priority, category, dir, session_id, created_at, updated_at, phase, assignee FROM dev_tasks WHERE status = ? ORDER BY id DESC LIMIT ?",
                (status, limit),
            )
        else:
            cursor = await db.execute(
                "SELECT id, title, description, status, priority, category, dir, session_id, created_at, updated_at, phase, assignee FROM dev_tasks ORDER BY id DESC LIMIT ?",
                (limit,),
            )
        rows = await cursor.fetchall()
    return [dict(r) for r in rows]


@router.get("/api/manage/projects")
async def manage_get_projects():
    if not TASKS_DB.exists():
        return []
    async with aiosqlite.connect(str(TASKS_DB)) as db:
        db.row_factory = aiosqlite.Row
        try:
            cursor = await db.execute(
                "SELECT id, name, description, status, created_at, updated_at FROM projects ORDER BY id DESC LIMIT 100"
            )
            rows = await cursor.fetchall()
            return [dict(r) for r in rows]
        except Exception:
            return []


class ManageProjectCreate(BaseModel):
    name: str
    description: str = ""
    status: str = "active"


class ManageProjectUpdate(BaseModel):
    name: Optional[str] = None
    description: Optional[str] = None
    status: Optional[str] = None


class ManageWorkflowCreate(BaseModel):
    name: str
    nodes: list = []
    edges: list = []


@router.post("/api/manage/projects")
async def manage_create_project(req: ManageProjectCreate):
    if not TASKS_DB.exists():
        raise HTTPException(status_code=503, detail="Tasks DB not found")
    import re
    slug = re.sub(r"[^a-z0-9-]", "-", req.name.lower()).strip("-")
    async with aiosqlite.connect(str(TASKS_DB)) as db:
        try:
            await db.execute(
                "INSERT INTO projects (name, slug, description, status) VALUES (?, ?, ?, ?)",
                (req.name, slug, req.description, req.status),
            )
            await db.commit()
            cursor = await db.execute("SELECT last_insert_rowid()")
            row = await cursor.fetchone()
            return {"id": row[0], "name": req.name, "description": req.description, "status": req.status}
        except Exception as e:
            raise HTTPException(status_code=500, detail=str(e))


@router.patch("/api/manage/projects/{project_id}")
async def manage_update_project(project_id: int, req: ManageProjectUpdate):
    if not TASKS_DB.exists():
        raise HTTPException(status_code=503, detail="Tasks DB not found")
    updates = {k: v for k, v in req.model_dump().items() if v is not None}
    if not updates:
        raise HTTPException(status_code=400, detail="No fields to update")
    set_clause = ", ".join(f"{k} = ?" for k in updates)
    values = list(updates.values()) + [project_id]
    async with aiosqlite.connect(str(TASKS_DB)) as db:
        await db.execute(f"UPDATE projects SET {set_clause} WHERE id = ?", values)
        await db.commit()
    return {"ok": True}


@router.get("/api/manage/stats")
async def manage_get_stats():
    result: dict = {"departments": 0, "tasks": {}, "projects": 0}
    try:
        async with aiosqlite.connect(str(THEBRANCH_DB)) as db:
            cursor = await db.execute("SELECT COUNT(*) FROM departments")
            row = await cursor.fetchone()
            result["departments"] = row[0] if row else 0
    except Exception:
        pass
    if TASKS_DB.exists():
        async with aiosqlite.connect(str(TASKS_DB)) as db:
            cursor = await db.execute(
                "SELECT status, COUNT(*) as cnt FROM dev_tasks GROUP BY status"
            )
            rows = await cursor.fetchall()
            result["tasks"] = {r[0]: r[1] for r in rows}
            try:
                cursor = await db.execute("SELECT COUNT(*) FROM projects")
                row = await cursor.fetchone()
                result["projects"] = row[0] if row else 0
            except Exception:
                result["projects"] = 0
    return result


@router.get("/api/manage/workflows")
async def manage_get_workflows():
    if not TASKS_DB.exists():
        return []
    async with aiosqlite.connect(str(TASKS_DB)) as db:
        db.row_factory = aiosqlite.Row
        try:
            cursor = await db.execute(
                "SELECT id, name, description, created_at, updated_at FROM workflow_templates ORDER BY id DESC LIMIT 100"
            )
            rows = await cursor.fetchall()
            return [dict(r) for r in rows]
        except Exception:
            return []


@router.post("/api/manage/workflows")
async def manage_create_workflow(req: ManageWorkflowCreate):
    if not TASKS_DB.exists():
        raise HTTPException(status_code=503, detail="Tasks DB not found")
    import json
    from datetime import datetime
    async with aiosqlite.connect(str(TASKS_DB)) as db:
        try:
            workflow_data = {
                "nodes": req.nodes,
                "edges": req.edges,
            }
            desc = json.dumps(workflow_data)
            now = datetime.utcnow().isoformat()
            await db.execute(
                "INSERT INTO workflow_templates (name, description, status, created_at, updated_at) VALUES (?, ?, ?, ?, ?)",
                (req.name, desc, "active", now, now),
            )
            await db.commit()
            cursor = await db.execute("SELECT last_insert_rowid()")
            row = await cursor.fetchone()
            return {"id": row[0], "name": req.name, "nodes": req.nodes, "edges": req.edges}
        except Exception as e:
            raise HTTPException(status_code=500, detail=str(e))


@router.get("/api/manage/workflows/{wf_id}")
async def manage_get_workflow(wf_id: int):
    if not TASKS_DB.exists():
        raise HTTPException(status_code=503, detail="Tasks DB not found")
    async with aiosqlite.connect(str(TASKS_DB)) as db:
        db.row_factory = aiosqlite.Row
        try:
            cursor = await db.execute(
                "SELECT id, name, description, created_at, updated_at FROM workflow_templates WHERE id = ?",
                (wf_id,),
            )
            row = await cursor.fetchone()
            if not row:
                raise HTTPException(status_code=404, detail="Workflow not found")
            import json
            result = dict(row)
            try:
                workflow_data = json.loads(result["description"] or "{}")
                result["nodes"] = workflow_data.get("nodes", [])
                result["edges"] = workflow_data.get("edges", [])
            except:
                result["nodes"] = []
                result["edges"] = []
            return result
        except Exception as e:
            raise HTTPException(status_code=500, detail=str(e))
