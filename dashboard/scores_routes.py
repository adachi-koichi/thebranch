import sqlite3
from pathlib import Path
from typing import Optional

from fastapi import APIRouter, HTTPException, Header
from pydantic import BaseModel

from dashboard import auth

router = APIRouter(prefix="/api/agents", tags=["agents"])
dept_router = APIRouter(prefix="/api/departments", tags=["departments"])

THEBRANCH_DB = Path(__file__).parent / "data" / "thebranch.sqlite"

AGENT_COLS = [
    "id", "agent_id", "agent_name", "department", "completion_rate",
    "quality_score", "performance_score", "overall_score",
    "total_tasks", "completed_tasks", "last_updated",
]


class ScoreModel(BaseModel):
    id: Optional[int] = None
    agent_id: str
    agent_name: str
    department: Optional[str] = "未割り当て"
    completion_rate: float = 0.0
    quality_score: float = 0.0
    performance_score: float = 0.0
    overall_score: float = 0.0
    total_tasks: int = 0
    completed_tasks: int = 0
    last_updated: Optional[str] = None

    class Config:
        from_attributes = True


class DepartmentScore(BaseModel):
    department: str
    agent_count: int
    avg_completion_rate: float
    avg_quality_score: float
    avg_performance_score: float
    avg_overall_score: float
    total_tasks: int
    completed_tasks: int
    top_agent: Optional[str] = None


def _rows_to_scores(rows):
    return [dict(zip(AGENT_COLS, row)) for row in rows]


@router.get("/scores", response_model=list[ScoreModel])
async def get_agent_scores(authorization: Optional[str] = Header(None)):
    if authorization:
        token = authorization.replace("Bearer ", "")
        user_id, _ = await auth.verify_token(token)
        if not user_id:
            raise HTTPException(status_code=401, detail="Unauthorized")

    conn = sqlite3.connect(str(THEBRANCH_DB))
    cursor = conn.cursor()
    cursor.execute(
        "SELECT id, agent_id, agent_name, department, completion_rate, quality_score, "
        "performance_score, overall_score, total_tasks, completed_tasks, last_updated "
        "FROM agent_scores ORDER BY overall_score DESC"
    )
    rows = cursor.fetchall()
    conn.close()
    return _rows_to_scores(rows)


@dept_router.get("/scores", response_model=list[DepartmentScore])
async def get_department_scores(authorization: Optional[str] = Header(None)):
    if authorization:
        token = authorization.replace("Bearer ", "")
        user_id, _ = await auth.verify_token(token)
        if not user_id:
            raise HTTPException(status_code=401, detail="Unauthorized")

    conn = sqlite3.connect(str(THEBRANCH_DB))
    cursor = conn.cursor()
    cursor.execute(
        """
        SELECT
            department,
            COUNT(*) AS agent_count,
            ROUND(AVG(completion_rate), 4) AS avg_completion_rate,
            ROUND(AVG(quality_score), 2)   AS avg_quality_score,
            ROUND(AVG(performance_score), 2) AS avg_performance_score,
            ROUND(AVG(overall_score), 2)   AS avg_overall_score,
            SUM(total_tasks)               AS total_tasks,
            SUM(completed_tasks)           AS completed_tasks
        FROM agent_scores
        GROUP BY department
        ORDER BY avg_overall_score DESC
        """
    )
    dept_rows = cursor.fetchall()
    dept_cols = [
        "department", "agent_count", "avg_completion_rate",
        "avg_quality_score", "avg_performance_score", "avg_overall_score",
        "total_tasks", "completed_tasks",
    ]
    results = [dict(zip(dept_cols, r)) for r in dept_rows]

    # 各部署のトップエージェント名を付加
    for dept in results:
        cursor.execute(
            "SELECT agent_name FROM agent_scores WHERE department = ? "
            "ORDER BY overall_score DESC LIMIT 1",
            (dept["department"],),
        )
        row = cursor.fetchone()
        dept["top_agent"] = row[0] if row else None

    conn.close()
    return results


# ──────────────────────────────────────────────
# GET /api/agents/{agent_id}/score
# POST /api/agents/{agent_id}/score
# ──────────────────────────────────────────────

class ScoreUpdateRequest(BaseModel):
    agent_name: str
    department: Optional[str] = "未割り当て"
    total_tasks: int = 0
    completed_tasks: int = 0
    quality_score: float = 0.0
    performance_score: float = 0.0


class AgentScoreDetail(ScoreModel):
    history: list[dict] = []


def _calc_overall(completion_rate: float, quality_score: float, performance_score: float) -> float:
    """完了率40% + 品質30% + パフォーマンス30%"""
    return round(completion_rate * 0.4 + quality_score * 0.3 + performance_score * 0.3, 2)


async def _require_write_auth(authorization: Optional[str]) -> str:
    if not authorization:
        raise HTTPException(status_code=401, detail="Unauthorized")
    token = authorization.removeprefix("Bearer ")
    user_id, _ = await auth.verify_token(token)
    if not user_id:
        raise HTTPException(status_code=403, detail="Forbidden")
    return user_id


@router.get("/{agent_id}/score", response_model=AgentScoreDetail)
async def get_single_agent_score(
    agent_id: str,
    authorization: Optional[str] = Header(None),
):
    if authorization:
        token = authorization.removeprefix("Bearer ")
        user_id, _ = await auth.verify_token(token)
        if not user_id:
            raise HTTPException(status_code=401, detail="Unauthorized")

    conn = sqlite3.connect(str(THEBRANCH_DB))
    conn.row_factory = sqlite3.Row
    row = conn.execute(
        "SELECT id, agent_id, agent_name, department, completion_rate, quality_score, "
        "performance_score, overall_score, total_tasks, completed_tasks, last_updated "
        "FROM agent_scores WHERE agent_id = ?",
        (agent_id,),
    ).fetchone()

    if not row:
        conn.close()
        raise HTTPException(status_code=404, detail=f"Agent '{agent_id}' not found")

    score = dict(row)
    history_rows = conn.execute(
        "SELECT id, agent_id, metric_date, completion_rate, quality_score, "
        "performance_score, overall_score, total_tasks, completed_tasks, created_at "
        "FROM performance_metrics WHERE agent_id = ? "
        "ORDER BY metric_date DESC LIMIT 30",
        (agent_id,),
    ).fetchall()
    conn.close()

    score["history"] = [dict(r) for r in history_rows]
    return score


@router.post("/{agent_id}/score", response_model=AgentScoreDetail)
async def record_agent_score(
    agent_id: str,
    body: ScoreUpdateRequest,
    authorization: Optional[str] = Header(None),
):
    """スコアを計算・UPSERT し、performance_metrics に日次スナップショットを記録する"""
    await _require_write_auth(authorization)

    completion_rate = (
        body.completed_tasks / body.total_tasks * 100 if body.total_tasks > 0 else 0.0
    )
    overall = _calc_overall(completion_rate, body.quality_score, body.performance_score)

    conn = sqlite3.connect(str(THEBRANCH_DB))
    conn.row_factory = sqlite3.Row
    conn.execute(
        """
        INSERT INTO agent_scores
            (agent_id, agent_name, department, completion_rate, total_tasks,
             completed_tasks, quality_score, performance_score, overall_score)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        ON CONFLICT(agent_id) DO UPDATE SET
            agent_name        = excluded.agent_name,
            department        = excluded.department,
            completion_rate   = excluded.completion_rate,
            total_tasks       = excluded.total_tasks,
            completed_tasks   = excluded.completed_tasks,
            quality_score     = excluded.quality_score,
            performance_score = excluded.performance_score,
            overall_score     = excluded.overall_score,
            last_updated      = CURRENT_TIMESTAMP
        """,
        (
            agent_id, body.agent_name, body.department,
            completion_rate, body.total_tasks, body.completed_tasks,
            body.quality_score, body.performance_score, overall,
        ),
    )
    # 日次スナップショット（同日は重複させない）
    conn.execute(
        """
        INSERT OR IGNORE INTO performance_metrics
            (agent_id, metric_date, completion_rate, quality_score, performance_score,
             overall_score, total_tasks, completed_tasks)
        VALUES (?, date('now'), ?, ?, ?, ?, ?, ?)
        """,
        (
            agent_id, completion_rate, body.quality_score, body.performance_score,
            overall, body.total_tasks, body.completed_tasks,
        ),
    )
    conn.commit()

    score = dict(conn.execute(
        "SELECT id, agent_id, agent_name, department, completion_rate, quality_score, "
        "performance_score, overall_score, total_tasks, completed_tasks, last_updated "
        "FROM agent_scores WHERE agent_id = ?",
        (agent_id,),
    ).fetchone())
    history_rows = conn.execute(
        "SELECT id, agent_id, metric_date, completion_rate, quality_score, "
        "performance_score, overall_score, total_tasks, completed_tasks, created_at "
        "FROM performance_metrics WHERE agent_id = ? "
        "ORDER BY metric_date DESC LIMIT 30",
        (agent_id,),
    ).fetchall()
    conn.close()

    score["history"] = [dict(r) for r in history_rows]
    return score


# ──────────────────────────────────────────────
# GET /api/departments/{dept_id}/metrics
# ──────────────────────────────────────────────

class DepartmentMetrics(BaseModel):
    department_id: int
    department_name: str
    agent_count: int
    total_tasks: int
    completed_tasks: int
    avg_completion_rate: float
    avg_quality_score: float
    avg_performance_score: float
    avg_overall_score: float
    top_agent: Optional[str] = None
    agents: list[dict] = []


@dept_router.get("/{dept_id}/metrics", response_model=DepartmentMetrics)
async def get_department_metrics(
    dept_id: int,
    authorization: Optional[str] = Header(None),
):
    if authorization:
        token = authorization.removeprefix("Bearer ")
        user_id, _ = await auth.verify_token(token)
        if not user_id:
            raise HTTPException(status_code=401, detail="Unauthorized")

    conn = sqlite3.connect(str(THEBRANCH_DB))
    conn.row_factory = sqlite3.Row

    dept_row = conn.execute(
        "SELECT id, name FROM departments WHERE id = ?", (dept_id,)
    ).fetchone()
    if not dept_row:
        conn.close()
        raise HTTPException(status_code=404, detail=f"Department {dept_id} not found")

    dept = dict(dept_row)

    # 部署に属するエージェントのスコアを集計（agents.session_id = agent_scores.agent_id）
    agent_rows = conn.execute(
        """
        SELECT
            a.session_id,
            a.role,
            COALESCE(s.agent_name, a.role)    AS agent_name,
            COALESCE(s.completion_rate, 0.0)  AS completion_rate,
            COALESCE(s.quality_score, 0.0)    AS quality_score,
            COALESCE(s.performance_score, 0.0) AS performance_score,
            COALESCE(s.overall_score, 0.0)    AS overall_score,
            COALESCE(s.total_tasks, 0)        AS total_tasks,
            COALESCE(s.completed_tasks, 0)    AS completed_tasks
        FROM agents a
        LEFT JOIN agent_scores s ON s.agent_id = a.session_id
        WHERE a.department_id = ?
        ORDER BY COALESCE(s.overall_score, 0.0) DESC
        """,
        (dept_id,),
    ).fetchall()

    task_agg = conn.execute(
        """
        SELECT
            COUNT(*)                                               AS total_tasks,
            SUM(CASE WHEN status = 'completed' THEN 1 ELSE 0 END) AS completed_tasks
        FROM tasks WHERE department_id = ?
        """,
        (dept_id,),
    ).fetchone()
    conn.close()

    agents_list = [dict(r) for r in agent_rows]
    agent_count = len(agents_list)
    total_tasks = task_agg["total_tasks"] or 0
    completed_tasks = task_agg["completed_tasks"] or 0

    if agent_count > 0:
        avg_completion = sum(a["completion_rate"] for a in agents_list) / agent_count
        avg_quality = sum(a["quality_score"] for a in agents_list) / agent_count
        avg_performance = sum(a["performance_score"] for a in agents_list) / agent_count
        avg_overall = sum(a["overall_score"] for a in agents_list) / agent_count
        top_agent = agents_list[0]["agent_name"]
    else:
        avg_completion = avg_quality = avg_performance = avg_overall = 0.0
        top_agent = None

    return {
        "department_id": dept["id"],
        "department_name": dept["name"],
        "agent_count": agent_count,
        "total_tasks": total_tasks,
        "completed_tasks": completed_tasks,
        "avg_completion_rate": round(avg_completion, 2),
        "avg_quality_score": round(avg_quality, 2),
        "avg_performance_score": round(avg_performance, 2),
        "avg_overall_score": round(avg_overall, 2),
        "top_agent": top_agent,
        "agents": agents_list,
    }


@router.post("/scores", response_model=ScoreModel)
async def upsert_agent_score(
    score_data: ScoreModel,
    authorization: Optional[str] = Header(None),
):
    if authorization:
        token = authorization.replace("Bearer ", "")
        user_id, _ = await auth.verify_token(token)
        if not user_id:
            raise HTTPException(status_code=403, detail="Forbidden")

    conn = sqlite3.connect(str(THEBRANCH_DB))
    cursor = conn.cursor()
    cursor.execute(
        """
        INSERT INTO agent_scores
            (agent_id, agent_name, department, completion_rate, total_tasks,
             completed_tasks, quality_score, performance_score, overall_score)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        ON CONFLICT(agent_id) DO UPDATE SET
            agent_name = excluded.agent_name,
            department = excluded.department,
            completion_rate = excluded.completion_rate,
            total_tasks = excluded.total_tasks,
            completed_tasks = excluded.completed_tasks,
            quality_score = excluded.quality_score,
            performance_score = excluded.performance_score,
            overall_score = excluded.overall_score,
            last_updated = CURRENT_TIMESTAMP
        """,
        (
            score_data.agent_id, score_data.agent_name, score_data.department,
            score_data.completion_rate, score_data.total_tasks,
            score_data.completed_tasks, score_data.quality_score,
            score_data.performance_score, score_data.overall_score,
        ),
    )
    conn.commit()

    cursor.execute(
        "SELECT id, agent_id, agent_name, department, completion_rate, quality_score, "
        "performance_score, overall_score, total_tasks, completed_tasks, last_updated "
        "FROM agent_scores WHERE agent_id = ?",
        (score_data.agent_id,),
    )
    row = cursor.fetchone()
    conn.close()
    return _rows_to_scores([row])[0]
