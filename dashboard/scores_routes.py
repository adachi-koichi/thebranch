import sqlite3
from pathlib import Path
from typing import Optional

from fastapi import APIRouter, HTTPException, Header
from pydantic import BaseModel

from dashboard import auth

router = APIRouter(prefix="/api/agents", tags=["agents"])

THEBRANCH_DB = Path(__file__).parent / "data" / "thebranch.sqlite"


class ScoreModel(BaseModel):
    id: Optional[int] = None
    agent_id: str
    agent_name: str
    completion_rate: float = 0.0
    quality_score: float = 0.0
    performance_score: float = 0.0
    overall_score: float = 0.0
    total_tasks: int = 0
    completed_tasks: int = 0
    last_updated: Optional[str] = None

    class Config:
        from_attributes = True


def _rows_to_scores(rows):
    cols = ["id", "agent_id", "agent_name", "completion_rate", "quality_score",
            "performance_score", "overall_score", "total_tasks", "completed_tasks",
            "last_updated"]
    return [dict(zip(cols, row)) for row in rows]


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
        "SELECT id, agent_id, agent_name, completion_rate, quality_score, "
        "performance_score, overall_score, total_tasks, completed_tasks, last_updated "
        "FROM agent_scores ORDER BY overall_score DESC"
    )
    rows = cursor.fetchall()
    conn.close()

    return _rows_to_scores(rows)


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
            (agent_id, agent_name, completion_rate, total_tasks, completed_tasks,
             quality_score, performance_score, overall_score)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        ON CONFLICT(agent_id) DO UPDATE SET
            agent_name = excluded.agent_name,
            completion_rate = excluded.completion_rate,
            total_tasks = excluded.total_tasks,
            completed_tasks = excluded.completed_tasks,
            quality_score = excluded.quality_score,
            performance_score = excluded.performance_score,
            overall_score = excluded.overall_score,
            last_updated = CURRENT_TIMESTAMP
        """,
        (
            score_data.agent_id, score_data.agent_name,
            score_data.completion_rate, score_data.total_tasks,
            score_data.completed_tasks, score_data.quality_score,
            score_data.performance_score, score_data.overall_score,
        ),
    )
    conn.commit()

    cursor.execute(
        "SELECT id, agent_id, agent_name, completion_rate, quality_score, "
        "performance_score, overall_score, total_tasks, completed_tasks, last_updated "
        "FROM agent_scores WHERE agent_id = ?",
        (score_data.agent_id,),
    )
    row = cursor.fetchone()
    conn.close()

    return _rows_to_scores([row])[0]
