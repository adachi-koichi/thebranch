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
    onboarding_completed: int = 0


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
    parent_id: Optional[int] = None


class ParentChangeRequest(BaseModel):
    parent_id: Optional[int] = None


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


class OnboardingRequest(BaseModel):
    dept_name: str
    dept_type: str
    agent_role: str
    agent_tasks: str
    agent_model: str = "claude-sonnet-4-6"


class OnboardingCompleteResponse(BaseModel):
    success: bool
    dept_id: int
    agent_id: int
    message: str = "ウィザード完了。エージェント起動中..."


class APICallCreate(BaseModel):
    department_id: int
    agent_id: Optional[int] = None
    api_provider: str
    model_name: Optional[str] = None
    input_tokens: int
    output_tokens: int
    cache_read_tokens: int = 0
    cache_creation_tokens: int = 0
    cost_usd: float
    status: str = "completed"
    error_message: Optional[str] = None
    request_timestamp: int


class APICallResponse(APICallCreate):
    id: int
    created_at: str
    updated_at: str

    class Config:
        from_attributes = True


class CostRecordResponse(BaseModel):
    id: int
    department_id: int
    year: int
    month: int
    total_cost_usd: float
    api_call_count: int
    failed_call_count: int
    average_cost_per_call: float
    top_model: Optional[str]
    created_at: str
    updated_at: str

    class Config:
        from_attributes = True


class MonthlyBudgetCreate(BaseModel):
    department_id: int
    year: int
    month: int
    budget_usd: float
    notes: Optional[str] = None


class MonthlyBudgetResponse(MonthlyBudgetCreate):
    id: int
    created_at: str
    updated_at: str

    class Config:
        from_attributes = True


class CostAlertResponse(BaseModel):
    id: int
    department_id: int
    alert_type: str
    threshold_percent: Optional[float]
    current_cost_usd: float
    budget_usd: float
    message: str
    status: str
    resolved_at: Optional[str]
    resolved_by: Optional[str]
    resolution_note: Optional[str]
    created_at: str
    updated_at: str

    class Config:
        from_attributes = True


class DepartmentCostSummary(BaseModel):
    department_id: int
    department_name: str
    current_month: int
    current_year: int
    budget: Optional[float]
    spent: float
    remaining: float
    utilization_percent: float
    api_call_count: int


class BudgetComparisonResponse(BaseModel):
    budget: Optional[float]
    spent: float
    remaining: float
    utilization_percent: float
    alerts: List[CostAlertResponse] = []


class RoleResponse(BaseModel):
    role_key: str
    role_label: str
    min_members: int
    max_members: int
    supervisor_role_key: Optional[str] = None


class ProcessResponse(BaseModel):
    process_key: str
    process_label: str
    frequency: str
    estimated_hours: Optional[float] = None


class DepartmentTemplateDetailResponse(BaseModel):
    id: int
    name: str
    category: str
    total_roles: int
    total_processes: int
    roles: List[RoleResponse] = []
    processes: List[ProcessResponse] = []


class DepartmentTemplateListResponse(BaseModel):
    id: int
    name: str
    category: str
    total_roles: int
    total_processes: int


class DepartmentCreateRequest(BaseModel):
    name: str
    template_id: int
    org_id: Optional[str] = None


class DepartmentCreateResponse(BaseModel):
    id: int
    name: str
    template_id: int
    created_at: str
