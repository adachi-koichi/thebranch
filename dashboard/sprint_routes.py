from fastapi import APIRouter, HTTPException, Depends, Query
from pathlib import Path
from typing import Optional
import aiosqlite

from dashboard.auth import get_current_user_zero_trust
from dashboard.sprint_models import (
    SprintCreate,
    SprintUpdate,
    SprintResponse,
    SprintTaskCreate,
    SprintTaskUpdate,
    SprintTaskResponse,
)

router = APIRouter(prefix="/api/sprint", tags=["sprint"])
THEBRANCH_DB = Path(__file__).parent / "data" / "thebranch.sqlite"


@router.get("/plans")
async def list_sprints(
    department_id: Optional[int] = None,
    status: Optional[str] = None,
    current_user: dict = Depends(get_current_user_zero_trust),
):
    async with aiosqlite.connect(str(THEBRANCH_DB)) as db:
        db.row_factory = aiosqlite.Row
        query = "SELECT * FROM sprint WHERE 1=1"
        params = []

        if department_id:
            query += " AND department_id = ?"
            params.append(department_id)
        if status:
            query += " AND status = ?"
            params.append(status)

        query += " ORDER BY sprint_start_date DESC"
        cursor = await db.execute(query, params)
        rows = await cursor.fetchall()

    return [dict(r) for r in rows]


@router.post("/plans")
async def create_sprint(
    sprint: SprintCreate, current_user: dict = Depends(get_current_user_zero_trust)
):
    async with aiosqlite.connect(str(THEBRANCH_DB)) as db:
        cursor = await db.execute(
            """INSERT INTO sprint
               (department_id, name, status, sprint_start_date, sprint_end_date, target_velocity, created_at, updated_at)
               VALUES (?, ?, ?, ?, ?, ?, datetime('now','localtime'), datetime('now','localtime'))""",
            (
                sprint.department_id,
                sprint.name,
                "active",
                sprint.sprint_start_date,
                sprint.sprint_end_date,
                sprint.target_velocity,
            ),
        )
        await db.commit()
        sprint_id = cursor.lastrowid

        cursor = await db.execute("SELECT * FROM sprint WHERE id = ?", (sprint_id,))
        cursor.row_factory = aiosqlite.Row
        result = await cursor.fetchone()

    return dict(result) if result else {"id": sprint_id}


@router.get("/plans/{sprint_id}")
async def get_sprint(
    sprint_id: int, current_user: dict = Depends(get_current_user_zero_trust)
):
    async with aiosqlite.connect(str(THEBRANCH_DB)) as db:
        db.row_factory = aiosqlite.Row
        cursor = await db.execute("SELECT * FROM sprint WHERE id = ?", (sprint_id,))
        result = await cursor.fetchone()

    if not result:
        raise HTTPException(status_code=404, detail="Sprint not found")

    return dict(result)


@router.put("/plans/{sprint_id}")
async def update_sprint(
    sprint_id: int,
    sprint: SprintUpdate,
    current_user: dict = Depends(get_current_user_zero_trust),
):
    async with aiosqlite.connect(str(THEBRANCH_DB)) as db:
        db.row_factory = aiosqlite.Row

        cursor = await db.execute("SELECT * FROM sprint WHERE id = ?", (sprint_id,))
        existing = await cursor.fetchone()
        if not existing:
            raise HTTPException(status_code=404, detail="Sprint not found")

        updates = []
        params = []
        if sprint.name is not None:
            updates.append("name = ?")
            params.append(sprint.name)
        if sprint.status is not None:
            updates.append("status = ?")
            params.append(sprint.status)
        if sprint.target_velocity is not None:
            updates.append("target_velocity = ?")
            params.append(sprint.target_velocity)

        if updates:
            updates.append("updated_at = datetime('now','localtime')")
            query = f"UPDATE sprint SET {', '.join(updates)} WHERE id = ?"
            params.append(sprint_id)
            await db.execute(query, params)
            await db.commit()

        cursor = await db.execute("SELECT * FROM sprint WHERE id = ?", (sprint_id,))
        result = await cursor.fetchone()

    return dict(result)


@router.delete("/plans/{sprint_id}")
async def delete_sprint(
    sprint_id: int, current_user: dict = Depends(get_current_user_zero_trust)
):
    async with aiosqlite.connect(str(THEBRANCH_DB)) as db:
        cursor = await db.execute("SELECT * FROM sprint WHERE id = ?", (sprint_id,))
        existing = await cursor.fetchone()
        if not existing:
            raise HTTPException(status_code=404, detail="Sprint not found")

        await db.execute("DELETE FROM sprint WHERE id = ?", (sprint_id,))
        await db.commit()

    return {"message": "Sprint deleted"}


@router.get("/plans/{sprint_id}/tasks")
async def list_sprint_tasks(
    sprint_id: int, current_user: dict = Depends(get_current_user_zero_trust)
):
    async with aiosqlite.connect(str(THEBRANCH_DB)) as db:
        db.row_factory = aiosqlite.Row
        cursor = await db.execute(
            "SELECT * FROM sprint_task WHERE sprint_id = ? ORDER BY created_at DESC",
            (sprint_id,),
        )
        rows = await cursor.fetchall()

    return [dict(r) for r in rows]


@router.post("/plans/{sprint_id}/tasks")
async def add_sprint_task(
    sprint_id: int,
    task: SprintTaskCreate,
    current_user: dict = Depends(get_current_user_zero_trust),
):
    async with aiosqlite.connect(str(THEBRANCH_DB)) as db:
        cursor = await db.execute("SELECT * FROM sprint WHERE id = ?", (sprint_id,))
        sprint = await cursor.fetchone()
        if not sprint:
            raise HTTPException(status_code=404, detail="Sprint not found")

        cursor = await db.execute(
            """INSERT INTO sprint_task
               (sprint_id, task_key, title, story_points, status, assigned_to, created_at, updated_at)
               VALUES (?, ?, ?, ?, ?, ?, datetime('now','localtime'), datetime('now','localtime'))""",
            (
                sprint_id,
                task.task_key,
                task.title,
                task.story_points,
                task.status,
                task.assigned_to,
            ),
        )
        await db.commit()
        task_id = cursor.lastrowid

        cursor = await db.execute("SELECT * FROM sprint_task WHERE id = ?", (task_id,))
        cursor.row_factory = aiosqlite.Row
        result = await cursor.fetchone()

    return dict(result) if result else {"id": task_id}


@router.patch("/tasks/{task_id}")
async def update_sprint_task(
    task_id: int,
    task: SprintTaskUpdate,
    current_user: dict = Depends(get_current_user_zero_trust),
):
    async with aiosqlite.connect(str(THEBRANCH_DB)) as db:
        db.row_factory = aiosqlite.Row

        cursor = await db.execute("SELECT * FROM sprint_task WHERE id = ?", (task_id,))
        existing = await cursor.fetchone()
        if not existing:
            raise HTTPException(status_code=404, detail="Task not found")

        updates = []
        params = []
        if task.title is not None:
            updates.append("title = ?")
            params.append(task.title)
        if task.story_points is not None:
            updates.append("story_points = ?")
            params.append(task.story_points)
        if task.status is not None:
            updates.append("status = ?")
            params.append(task.status)
        if task.assigned_to is not None:
            updates.append("assigned_to = ?")
            params.append(task.assigned_to)

        if updates:
            updates.append("updated_at = datetime('now','localtime')")
            query = f"UPDATE sprint_task SET {', '.join(updates)} WHERE id = ?"
            params.append(task_id)
            await db.execute(query, params)
            await db.commit()

        cursor = await db.execute("SELECT * FROM sprint_task WHERE id = ?", (task_id,))
        result = await cursor.fetchone()

    return dict(result)
