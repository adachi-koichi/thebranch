"""プロジェクトサービス — ビジネスロジック層

Project > Workflow > Phase > Task の階層を一括作成・管理する。

入力 spec フォーマット:
{
  "name": "プロジェクト名",
  "description": "説明",
  "status": "active",          # optional
  "workflows": [
    {
      "name": "ワークフロー名",
      "description": "説明",
      "execution_mode": "sequential",   # sequential | parallel（直前 workflow との関係）
      "tasks": [
        {
          "key":              "task-001",
          "title":            "タスクタイトル",
          "description":      "説明",
          "specialist_type":  "engineer",   # engineer | designer | researcher | product_manager
          "execution":        "sequential", # sequential | parallel（フェーズ内での並行実行）
          "depends_on":       "task-000",   # optional
          "priority":         1,            # 1=high 2=medium 3=low
          "estimated_hours":  2.0
        }
      ]
    }
  ]
}
"""

import sqlite3
from datetime import datetime
from pathlib import Path
from typing import Optional

from workflow.repositories import project_repository as repo

DB_PATH = Path(__file__).parent.parent.parent / "dashboard" / "data" / "thebranch.sqlite"


def _connect():
    db = sqlite3.connect(str(DB_PATH))
    db.row_factory = sqlite3.Row
    db.execute("PRAGMA foreign_keys = ON")
    return db


def create_project_from_spec(spec: dict) -> dict:
    """spec 定義からプロジェクト・ワークフロー・タスクを一括作成"""
    now = datetime.utcnow().isoformat()

    with _connect() as db:
        repo.migrate(db)

        project_id = _insert_project(db, spec, now)
        wf_count = 0

        for wf_order, wf_spec in enumerate(spec.get("workflows", [])):
            wf_id = _insert_workflow(db, wf_spec, now)
            db.execute(
                "INSERT OR REPLACE INTO project_workflows "
                "(project_id, workflow_id, workflow_order, execution_mode) VALUES (?,?,?,?)",
                (project_id, wf_id, wf_order, wf_spec.get("execution_mode", "sequential")),
            )
            _insert_tasks_to_workflow(db, wf_id, wf_spec.get("tasks", []), now)
            wf_count += 1

        db.commit()

    return {
        "ok": True,
        "project_id": project_id,
        "project_name": spec["name"],
        "workflows_created": wf_count,
    }


def get_project_detail(project_id: int) -> Optional[dict]:
    """プロジェクト詳細（ワークフロー・フェーズ・タスク含む）"""
    project = repo.get_project(project_id)
    if not project:
        return None

    workflows_raw = repo.get_project_workflows(project_id)
    workflows = []
    for wf in workflows_raw:
        detail = repo.get_workflow_with_tasks(wf["workflow_id"])
        if detail:
            detail["execution_mode"] = wf["execution_mode"]
            detail["workflow_order"] = wf["workflow_order"]
            workflows.append(detail)

    return {**project, "workflows": workflows}


def list_projects(status: Optional[str] = None) -> list[dict]:
    return repo.list_projects(status=status)


def update_project(project_id: int, **fields) -> bool:
    return repo.update_project(project_id, **fields)


def delete_project(project_id: int) -> dict:
    deleted_wfs = repo.delete_project(project_id)
    return {"ok": True, "deleted_project_id": project_id, "deleted_workflows": len(deleted_wfs)}


# ──────────────── Internal helpers ────────────────

def _insert_project(db, spec: dict, now: str) -> int:
    cur = db.execute(
        "INSERT INTO projects (name, description, status, created_at, updated_at) VALUES (?,?,?,?,?)",
        (spec["name"], spec.get("description", ""), spec.get("status", "active"), now, now),
    )
    return cur.lastrowid


def _insert_workflow(db, wf_spec: dict, now: str) -> int:
    cur = db.execute(
        "INSERT INTO workflow_templates (name, description, status, created_at, updated_at, created_by) VALUES (?,?,?,?,?,?)",
        (wf_spec["name"], wf_spec.get("description", ""), "active", now, now, "project-service"),
    )
    return cur.lastrowid


def _insert_tasks_to_workflow(db, wf_id: int, tasks: list, now: str):
    """タスクを execution モードでフェーズ分けして挿入"""
    phase_groups: list[list[dict]] = []
    current_parallel: list[dict] = []

    for task in tasks:
        if task.get("execution") == "parallel":
            current_parallel.append(task)
        else:
            if current_parallel:
                phase_groups.append(current_parallel)
                current_parallel = []
            phase_groups.append([task])
    if current_parallel:
        phase_groups.append(current_parallel)

    for phase_order, group in enumerate(phase_groups):
        is_parallel = 1 if len(group) > 1 else 0
        phase_key = f"phase-{phase_order+1:03d}"
        phase_label = " / ".join(t.get("title", t.get("key", "")) for t in group)
        specialist_type = group[0].get("specialist_type", "engineer")

        cur = db.execute(
            """INSERT INTO wf_template_phases
               (template_id, phase_key, phase_label, specialist_type, phase_order, is_parallel)
               VALUES (?,?,?,?,?,?)""",
            (wf_id, phase_key, phase_label, specialist_type, phase_order, is_parallel),
        )
        phase_id = cur.lastrowid

        for task_order, task in enumerate(group):
            db.execute(
                """INSERT INTO wf_template_tasks
                   (phase_id, template_id, task_key, task_title, task_description,
                    depends_on_key, priority, estimated_hours, task_order)
                   VALUES (?,?,?,?,?,?,?,?,?)""",
                (
                    phase_id, wf_id,
                    task.get("key", f"task-{phase_order}-{task_order}"),
                    task["title"],
                    task.get("description", ""),
                    task.get("depends_on"),
                    task.get("priority", 2),
                    task.get("estimated_hours", 0.0),
                    task_order,
                ),
            )
