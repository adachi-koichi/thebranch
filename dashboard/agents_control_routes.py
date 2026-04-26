"""Agent lifecycle management routes (Task #2784)."""
import subprocess
from datetime import datetime
from pathlib import Path
from typing import Optional
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
import aiosqlite

router = APIRouter()

DASHBOARD_DIR = Path(__file__).parent
THEBRANCH_DB = DASHBOARD_DIR / "data" / "thebranch.sqlite"
TMUX_BIN = "/opt/homebrew/bin/tmux"


class DeployRequest(BaseModel):
    pass


class AgentStartRequest(BaseModel):
    pass


class AgentStopRequest(BaseModel):
    pass


class AgentStatusResponse(BaseModel):
    id: int
    department_id: int
    role: str
    status: str
    session_id: str
    started_at: str
    stopped_at: Optional[str] = None
    error_message: Optional[str] = None
    created_at: str
    updated_at: str

    class Config:
        from_attributes = True


class DeployResponse(BaseModel):
    department_id: int
    department_name: str
    deployed_agents: list


@router.post("/api/departments/{dept_id}/deploy")
async def deploy_department(dept_id: int, req: DeployRequest = None):
    """部署をデプロイ（全エージェント起動）"""
    async with aiosqlite.connect(str(THEBRANCH_DB)) as db:
        db.row_factory = aiosqlite.Row

        cursor = await db.execute("SELECT id, name FROM departments WHERE id = ?", (dept_id,))
        dept = await cursor.fetchone()
        if not dept:
            raise HTTPException(status_code=404, detail="Department not found")

        cursor = await db.execute(
            "SELECT id, session_id FROM agents WHERE department_id = ? AND status != 'stopped'",
            (dept_id,),
        )
        agents = await cursor.fetchall()

        results = []
        for agent in agents:
            try:
                session_name = agent["session_id"]
                subprocess.run([TMUX_BIN, "new-session", "-d", "-s", session_name], check=False)

                now = datetime.utcnow().isoformat()
                await db.execute(
                    "UPDATE agents SET status = 'running', started_at = ? WHERE id = ?",
                    (now, agent["id"]),
                )
                await db.commit()

                results.append({"agent_id": agent["id"], "status": "running"})
            except Exception as e:
                results.append({"agent_id": agent["id"], "error": str(e)})

        return DeployResponse(
            department_id=dept_id, department_name=dept["name"], deployed_agents=results
        )


@router.post("/api/agents/{agent_id}/start")
async def start_agent(agent_id: int, req: AgentStartRequest = None):
    """エージェントを起動"""
    async with aiosqlite.connect(str(THEBRANCH_DB)) as db:
        db.row_factory = aiosqlite.Row

        cursor = await db.execute(
            "SELECT id, session_id, role FROM agents WHERE id = ?", (agent_id,)
        )
        agent = await cursor.fetchone()
        if not agent:
            raise HTTPException(status_code=404, detail="Agent not found")

        try:
            session_name = agent["session_id"]
            subprocess.run([TMUX_BIN, "new-session", "-d", "-s", session_name], check=False)

            now = datetime.utcnow().isoformat()
            await db.execute(
                "UPDATE agents SET status = 'running', started_at = ?, error_message = NULL WHERE id = ?",
                (now, agent_id),
            )
            await db.commit()

            return {
                "agent_id": agent_id,
                "status": "running",
                "session_id": session_name,
                "role": agent["role"],
                "started_at": now,
            }
        except Exception as e:
            await db.execute(
                "UPDATE agents SET status = 'failed', error_message = ? WHERE id = ?",
                (str(e), agent_id),
            )
            await db.commit()
            raise HTTPException(status_code=500, detail=f"Failed to start agent: {str(e)}")


@router.post("/api/agents/{agent_id}/stop")
async def stop_agent(agent_id: int, req: AgentStopRequest = None):
    """エージェントを停止"""
    async with aiosqlite.connect(str(THEBRANCH_DB)) as db:
        db.row_factory = aiosqlite.Row

        cursor = await db.execute(
            "SELECT id, session_id FROM agents WHERE id = ?", (agent_id,)
        )
        agent = await cursor.fetchone()
        if not agent:
            raise HTTPException(status_code=404, detail="Agent not found")

        try:
            session_name = agent["session_id"]
            subprocess.run([TMUX_BIN, "kill-session", "-t", session_name], check=False)

            now = datetime.utcnow().isoformat()
            await db.execute(
                "UPDATE agents SET status = 'stopped', stopped_at = ? WHERE id = ?",
                (now, agent_id),
            )
            await db.commit()

            return {"agent_id": agent_id, "status": "stopped", "session_id": session_name, "stopped_at": now}
        except Exception as e:
            raise HTTPException(status_code=500, detail=f"Failed to stop agent: {str(e)}")


@router.get("/api/agents/{agent_id}/status")
async def get_agent_status(agent_id: int) -> AgentStatusResponse:
    """エージェントのステータスを取得"""
    async with aiosqlite.connect(str(THEBRANCH_DB)) as db:
        db.row_factory = aiosqlite.Row

        cursor = await db.execute(
            "SELECT id, department_id, session_id, role, status, started_at, stopped_at, error_message, created_at, updated_at FROM agents WHERE id = ?",
            (agent_id,),
        )
        agent = await cursor.fetchone()
        if not agent:
            raise HTTPException(status_code=404, detail="Agent not found")

        return AgentStatusResponse(**dict(agent))
