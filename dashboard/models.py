from datetime import datetime
from typing import Optional, List
from pydantic import BaseModel, EmailStr


class UserBase(BaseModel):
    username: str
    email: EmailStr


class UserCreate(UserBase):
    password: str


class UserResponse(UserBase):
    id: str
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


class SessionCreate(BaseModel):
    username: str
    password: str


class SessionResponse(BaseModel):
    token: str
    user_id: str
    expires_at: datetime


class UserRoleCreate(BaseModel):
    role: str


class UserRoleResponse(BaseModel):
    id: str
    user_id: str
    role: str
    created_at: datetime

    class Config:
        from_attributes = True


class UserDetailResponse(UserResponse):
    roles: List[UserRoleResponse] = []


class AgentConfig(BaseModel):
    role: str
    tasks: str
    model: str = "claude-sonnet-4-6"


class DepartmentCreate(BaseModel):
    name: str
    slug: str
    description: Optional[str] = None
    parent_id: Optional[int] = None
    budget: Optional[float] = None


class DepartmentUpdate(BaseModel):
    name: Optional[str] = None
    description: Optional[str] = None
    budget: Optional[float] = None
    status: Optional[str] = None


class DepartmentResponse(BaseModel):
    id: int
    name: str
    slug: str
    description: Optional[str]
    parent_id: Optional[int]
    budget: Optional[float]
    status: str
    agent_count: int = 0
    team_count: int = 0
    created_at: str
    updated_at: str


class DepartmentDetailResponse(DepartmentResponse):
    parent: Optional[dict] = None


class DepartmentAgentCreate(BaseModel):
    agent_id: int
    role: str


class DepartmentAgentResponse(BaseModel):
    department_id: int
    agent_id: int
    agent: dict
    role: str
    joined_at: str


class AgentCreate(BaseModel):
    department_id: int
    role: str


class AgentResponse(BaseModel):
    id: int
    department_id: int
    session_id: str
    role: str
    status: str
    started_at: str
    stopped_at: Optional[str] = None
    error_message: Optional[str] = None
    created_at: str
    updated_at: str


class AgentLogCreate(BaseModel):
    action: str
    detail: Optional[str] = None


class AgentLogResponse(BaseModel):
    id: int
    agent_id: int
    action: str
    detail: Optional[str] = None
    created_at: str
    role: Optional[str] = None


class TeamCreate(BaseModel):
    name: str
    slug: str
    description: Optional[str] = None
    status: str = "active"


class TeamUpdate(BaseModel):
    name: Optional[str] = None
    description: Optional[str] = None
    status: Optional[str] = None


class TeamResponse(BaseModel):
    id: int
    department_id: int
    name: str
    slug: str
    description: Optional[str]
    status: str
    created_at: str
    updated_at: str


class RelationCreate(BaseModel):
    dept_b_id: int
    relation_type: str
    description: Optional[str] = None


class MissionCreate(BaseModel):
    workflow_id: int
    task_ids: List[int]
    custom_prompt: Optional[str] = None
    target_completion: Optional[str] = None
    priority: int = 3


class MissionResponse(BaseModel):
    id: int
    agent_id: int
    workflow_id: int
    name: str
    status: str
    priority: int
    custom_prompt: Optional[str]
    target_completion: Optional[str]
    created_at: str
    updated_at: str

    class Config:
        from_attributes = True


class MissionDetailResponse(MissionResponse):
    tasks: List[dict] = []
