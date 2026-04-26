"""プロジェクト管理 API ルーター"""

from typing import Optional
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from workflow.services import project_service

router = APIRouter(prefix="/api/projects", tags=["projects"])


class TaskSpec(BaseModel):
    key: Optional[str] = None
    title: str
    description: Optional[str] = ""
    specialist_type: Optional[str] = "engineer"
    execution: Optional[str] = "sequential"
    depends_on: Optional[str] = None
    priority: Optional[int] = 2
    estimated_hours: Optional[float] = 0.0


class WorkflowSpec(BaseModel):
    name: str
    description: Optional[str] = ""
    execution_mode: Optional[str] = "sequential"
    tasks: list[TaskSpec] = []


class ProjectSpec(BaseModel):
    name: str
    description: Optional[str] = ""
    status: Optional[str] = "active"
    workflows: list[WorkflowSpec] = []


class ProjectUpdate(BaseModel):
    name: Optional[str] = None
    description: Optional[str] = None
    status: Optional[str] = None


@router.get("")
def list_projects(status: Optional[str] = None):
    return project_service.list_projects(status=status)


@router.post("", status_code=201)
def create_project(spec: ProjectSpec):
    try:
        return project_service.create_project_from_spec(spec.model_dump())
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.get("/{project_id}")
def get_project(project_id: int):
    result = project_service.get_project_detail(project_id)
    if not result:
        raise HTTPException(status_code=404, detail=f"Project #{project_id} not found")
    return result


@router.patch("/{project_id}")
def update_project(project_id: int, body: ProjectUpdate):
    ok = project_service.update_project(project_id, **body.model_dump(exclude_none=True))
    if not ok:
        raise HTTPException(status_code=404, detail=f"Project #{project_id} not found or no valid fields")
    return {"ok": True}


@router.delete("/{project_id}")
def delete_project(project_id: int):
    return project_service.delete_project(project_id)
