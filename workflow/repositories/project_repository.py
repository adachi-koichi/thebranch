"""プロジェクトリポジトリ — thebranch.sqlite への CRUD アクセス"""

import sqlite3
from datetime import datetime
from pathlib import Path
from typing import Optional

DB_PATH = Path(__file__).parent.parent.parent / "dashboard" / "data" / "thebranch.sqlite"


def _connect() -> sqlite3.Connection:
    db = sqlite3.connect(str(DB_PATH))
    db.row_factory = sqlite3.Row
    db.execute("PRAGMA foreign_keys = ON")
    return db


def migrate(db: sqlite3.Connection) -> None:
    """projects / project_workflows テーブルを作成（冪等）"""
    sql_path = Path(__file__).parent.parent.parent / "dashboard" / "migrations" / "011_create_projects_tables.sql"
    db.executescript(sql_path.read_text(encoding="utf-8"))
    db.commit()


# ──────────────── Project ────────────────

def create_project(name: str, description: str = "", status: str = "active") -> int:
    now = datetime.utcnow().isoformat()
    with _connect() as db:
        migrate(db)
        cur = db.execute(
            "INSERT INTO projects (name, description, status, created_at, updated_at) VALUES (?,?,?,?,?)",
            (name, description, status, now, now),
        )
        db.commit()
        return cur.lastrowid


def get_project(project_id: int) -> Optional[dict]:
    with _connect() as db:
        migrate(db)
        row = db.execute("SELECT * FROM projects WHERE id=?", (project_id,)).fetchone()
        return dict(row) if row else None


def list_projects(status: Optional[str] = None, limit: int = 100) -> list[dict]:
    with _connect() as db:
        migrate(db)
        if status:
            rows = db.execute(
                "SELECT * FROM projects WHERE status=? ORDER BY id DESC LIMIT ?",
                (status, limit),
            ).fetchall()
        else:
            rows = db.execute(
                "SELECT * FROM projects ORDER BY id DESC LIMIT ?", (limit,)
            ).fetchall()
        return [dict(r) for r in rows]


def update_project(project_id: int, **fields) -> bool:
    allowed = {"name", "description", "status"}
    updates = {k: v for k, v in fields.items() if k in allowed and v is not None}
    if not updates:
        return False
    updates["updated_at"] = datetime.utcnow().isoformat()
    set_clause = ", ".join(f"{k}=?" for k in updates)
    values = list(updates.values()) + [project_id]
    with _connect() as db:
        db.execute(f"UPDATE projects SET {set_clause} WHERE id=?", values)
        db.commit()
    return True


def delete_project(project_id: int) -> list[int]:
    """プロジェクトと関連する workflow_templates を削除。削除した wf_id リストを返す"""
    with _connect() as db:
        migrate(db)
        wf_ids = [
            r[0] for r in db.execute(
                "SELECT workflow_id FROM project_workflows WHERE project_id=?", (project_id,)
            ).fetchall()
        ]
        db.execute("DELETE FROM projects WHERE id=?", (project_id,))
        for wf_id in wf_ids:
            db.execute("DELETE FROM workflow_templates WHERE id=?", (wf_id,))
        db.commit()
    return wf_ids


# ──────────────── Workflow ────────────────

def add_workflow_to_project(
    project_id: int,
    workflow_id: int,
    workflow_order: int = 0,
    execution_mode: str = "sequential",
) -> int:
    with _connect() as db:
        migrate(db)
        cur = db.execute(
            "INSERT OR REPLACE INTO project_workflows (project_id, workflow_id, workflow_order, execution_mode) VALUES (?,?,?,?)",
            (project_id, workflow_id, workflow_order, execution_mode),
        )
        db.commit()
        return cur.lastrowid


def get_project_workflows(project_id: int) -> list[dict]:
    with _connect() as db:
        migrate(db)
        rows = db.execute(
            """SELECT pw.id, pw.workflow_order, pw.execution_mode,
                      wt.id AS workflow_id, wt.name, wt.description, wt.status
               FROM project_workflows pw
               JOIN workflow_templates wt ON wt.id = pw.workflow_id
               WHERE pw.project_id = ?
               ORDER BY pw.workflow_order""",
            (project_id,),
        ).fetchall()
        return [dict(r) for r in rows]


def get_workflow_with_tasks(workflow_id: int) -> Optional[dict]:
    with _connect() as db:
        wt = db.execute(
            "SELECT * FROM workflow_templates WHERE id=?", (workflow_id,)
        ).fetchone()
        if not wt:
            return None
        phases = db.execute(
            "SELECT * FROM wf_template_phases WHERE template_id=? ORDER BY phase_order",
            (workflow_id,),
        ).fetchall()
        result = {**dict(wt), "phases": []}
        for phase in phases:
            tasks = db.execute(
                "SELECT * FROM wf_template_tasks WHERE phase_id=? ORDER BY task_order",
                (phase["id"],),
            ).fetchall()
            result["phases"].append({**dict(phase), "tasks": [dict(t) for t in tasks]})
        return result
