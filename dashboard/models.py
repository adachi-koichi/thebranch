from datetime import datetime
from enum import Enum
from typing import Optional, List
from pydantic import BaseModel, EmailStr, field_validator


class UserRole(str, Enum):
    owner = "owner"
    manager = "manager"
    member = "member"


class UserBase(BaseModel):
    username: str
    email: EmailStr


class UserCreate(UserBase):
    password: str


class UserResponse(UserBase):
    id: str
    role: UserRole = UserRole.member
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


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# API Token Management Models (#2525)
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

class APITokenCreate(BaseModel):
    name: str
    scope: str
    expires_in_days: Optional[int] = None


class APITokenResponse(BaseModel):
    id: str
    name: str
    scope: str
    created_at: datetime
    last_used_at: Optional[datetime] = None
    expires_at: Optional[datetime] = None
    revoked: bool = False

    class Config:
        from_attributes = True


class APITokenCreateResponse(BaseModel):
    id: str
    name: str
    token: str
    scope: str
    created_at: datetime
    expires_at: Optional[datetime] = None


class APITokenListResponse(BaseModel):
    tokens: List[APITokenResponse]


class UserOnboardingProgressCreate(BaseModel):
    user_id: str
    current_step: int = 0
    vision_input: Optional[str] = None


class UserOnboardingProgressUpdate(BaseModel):
    current_step: Optional[int] = None
    vision_input: Optional[str] = None


class UserOnboardingProgressResponse(BaseModel):
    onboarding_id: str
    user_id: str
    current_step: int
    vision_input: Optional[str] = None
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True
    onboarding_completed: int = 0


class OnboardingStateCreate(BaseModel):
    user_id: str
    current_step: int = 1
    organization_type: Optional[str] = None
    department_choice: Optional[str] = None


class OnboardingStateUpdate(BaseModel):
    current_step: Optional[int] = None
    organization_type: Optional[str] = None
    department_choice: Optional[str] = None


class OnboardingStateResponse(BaseModel):
    id: int
    user_id: str
    current_step: int
    organization_type: Optional[str] = None
    department_choice: Optional[str] = None
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


class OnboardingStatusResponse(BaseModel):
    user_id: str
    current_step: int
    organization_type: Optional[str] = None
    department_choice: Optional[str] = None
    onboarding_completed: bool


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


class InvitationCreate(BaseModel):
    max_uses: int = 1
    expires_in_days: int = 7


class InvitationResponse(BaseModel):
    id: str
    team_id: int
    token: str
    created_by: str
    created_at: datetime
    expires_at: datetime
    max_uses: int
    used_count: int
    status: str
    accepted_by_users: List[str] = []

    class Config:
        from_attributes = True


class TeamMemberCreate(BaseModel):
    user_id: str
    role: str = "member"


class TeamMemberResponse(BaseModel):
    id: str
    team_id: int
    user_id: str
    role: str
    invited_by: Optional[str] = None
    accepted_at: Optional[datetime] = None
    joined_at: datetime
    status: str

    class Config:
        from_attributes = True


class TeamMemberDetailResponse(TeamMemberResponse):
    user: Optional[UserResponse] = None


class InviteTokenRequest(BaseModel):
    token: str


class InviteAcceptRequest(BaseModel):
    token: str
    username: Optional[str] = None
    email: Optional[str] = None


class TeamWithMembersResponse(BaseModel):
    id: int
    department_id: int
    name: str
    slug: str
    description: Optional[str]
    status: str
    members: List[TeamMemberDetailResponse] = []
    member_count: int = 0
    created_at: str
    updated_at: str

    class Config:
        from_attributes = True


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


class CostRecordRequest(BaseModel):
    department_id: int
    agent_id: Optional[int] = None
    api_provider: str
    model_name: Optional[str] = None
    input_tokens: int
    output_tokens: int
    cache_read_tokens: int = 0
    cache_creation_tokens: int = 0
    cost_usd: float


class DepartmentCostResponse(BaseModel):
    year: int
    month: int
    budget: float
    spent: float
    remaining: float
    utilization_percent: float
    api_call_count: int


class CostSummaryItem(BaseModel):
    department_id: int
    year: int
    month: int
    total_cost_usd: float
    api_call_count: int
    failed_call_count: int = 0
    top_model: Optional[str] = None


class CostSummaryResponse(BaseModel):
    items: List[CostSummaryItem]


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


class ProcessConfig(BaseModel):
    process_key: str
    priority: str = "normal"
    enabled: bool = True


class CustomizeTemplateRequest(BaseModel):
    template_id: int
    department_name: str
    manager_name: str
    org_id: str
    member_count: int
    monthly_budget: int
    processes: List[ProcessConfig] = []


class CustomizeTemplateResponse(BaseModel):
    department_id: int
    organization_id: str
    created_at: str


class VisionInputRequest(BaseModel):
    onboarding_id: str
    vision_input: str


class VisionInputResponse(BaseModel):
    success: bool
    onboarding_id: str
    current_step: int
    message: str = "ビジョンを保存しました"


class TemplateSuggestion(BaseModel):
    template_id: int
    name: str
    category: str
    total_roles: int
    total_processes: int
    reason: str
    rank: int


class DepartmentSuggestionRequest(BaseModel):
    onboarding_id: str


class DepartmentSuggestionResponse(BaseModel):
    success: bool
    suggestions: List[TemplateSuggestion]
    current_step: int = 1
    message: str = "部署提案を取得しました"


# Step 2-3 用追加モデル

class TemplateConfig(BaseModel):
    members_count: int
    budget_monthly: int
    roles: List[str]


class SuggestResponse(BaseModel):
    onboarding_id: str
    suggestions: List[TemplateSuggestion]


class DetailedSetupRequest(BaseModel):
    onboarding_id: str
    template_id: Optional[int] = None
    dept_name: str
    manager_name: str
    members_count: int
    budget: int
    kpi: str
    integrations: Optional[dict] = None


class BudgetValidation(BaseModel):
    status: str
    monthly_per_person: float
    market_benchmark: float
    message: str


class SetupResponse(BaseModel):
    success: bool
    budget_validation: BudgetValidation
    initial_tasks: List['InitialTask'] = []
    current_step: int = 2
    message: str = "セットアップ完了。初期タスクを生成しました"


class InitialTask(BaseModel):
    task_id: str
    title: str
    description: str
    budget: float
    deadline: str
    assigned_to: str


class ExecuteRequest(BaseModel):
    onboarding_id: str
    template_id: Optional[int] = None
    dept_name: Optional[str] = None


class ExecuteResponse(BaseModel):
    dept_id: int
    tasks_created: List[InitialTask]
    agent_status: str
    dashboard_url: str
    completed_at: str


# Agent Decision Transparency Models
class AgentDecisionFactorCreate(BaseModel):
    factor_type: str
    factor_name: str
    factor_value: Optional[str] = None
    weight: float = 1.0
    description: Optional[str] = None
    order_sequence: int = 0


class AgentDecisionFactorResponse(AgentDecisionFactorCreate):
    id: int
    decision_log_id: int
    created_at: str


class AgentDecisionLogCreate(BaseModel):
    agent_id: int
    department_id: Optional[int] = None
    decision_type: str
    decision_summary: str
    reasoning: str
    context: Optional[str] = None
    confidence_score: float = 0.8
    input_data: Optional[str] = None
    output_data: Optional[str] = None
    impact_assessment: Optional[str] = None
    factors: List[AgentDecisionFactorCreate] = []


class AgentDecisionLogResponse(BaseModel):
    id: int
    agent_id: int
    department_id: Optional[int]
    decision_type: str
    decision_summary: str
    reasoning: str
    context: Optional[str]
    confidence_score: float
    input_data: Optional[str]
    output_data: Optional[str]
    status: str
    impact_assessment: Optional[str]
    factors: List[AgentDecisionFactorResponse] = []
    created_at: str
    updated_at: str


class AgentActionAuditCreate(BaseModel):
    agent_id: int
    decision_log_id: Optional[int] = None
    action_type: str
    action_detail: str
    result_status: str = "pending"
    result_detail: Optional[str] = None
    affected_entity_type: Optional[str] = None
    affected_entity_id: Optional[str] = None


class AgentActionAuditResponse(AgentActionAuditCreate):
    id: int
    created_at: str


class DecisionExplanationReportCreate(BaseModel):
    decision_log_id: int
    explanation_summary: str
    explanation_html: Optional[str] = None
    generated_by: str = "system"
    generation_method: str = "rule_based"


class DecisionExplanationReportResponse(DecisionExplanationReportCreate):
    id: int
    created_at: str


class TransparencyReportResponse(BaseModel):
    agent_id: int
    agent_role: Optional[str]
    total_decisions: int
    decision_breakdown: dict
    confidence_avg: float
    recent_decisions: List[AgentDecisionLogResponse] = []
    action_audit_trail: List[AgentActionAuditResponse] = []


class SLAPolicyCreate(BaseModel):
    name: str
    response_time_limit_ms: int
    uptime_percentage: float
    error_rate_limit: float
    enabled: bool = True


class SLAPolicyUpdate(BaseModel):
    name: Optional[str] = None
    response_time_limit_ms: Optional[int] = None
    uptime_percentage: Optional[float] = None
    error_rate_limit: Optional[float] = None
    enabled: Optional[bool] = None


class SLAPolicyResponse(SLAPolicyCreate):
    id: int
    created_at: str
    updated_at: str

    class Config:
        from_attributes = True


class SLAMetricCreate(BaseModel):
    policy_id: int
    response_time_ms: Optional[int] = None
    uptime_percentage: Optional[float] = None
    error_rate: Optional[float] = None


class SLAMetricResponse(SLAMetricCreate):
    id: int
    measured_at: str

    class Config:
        from_attributes = True


class SLAViolationCreate(BaseModel):
    policy_id: int
    metric_id: int
    violation_type: str
    severity: str
    details: Optional[str] = None
    alert_sent: bool = False


class SLAViolationResponse(SLAViolationCreate):
    id: int
    resolved_at: Optional[str] = None
    created_at: str

    class Config:
        from_attributes = True


class SLAMetricsDetailResponse(BaseModel):
    policy_id: int
    policy_name: str
    metrics: List[SLAMetricResponse] = []
    violations: List[SLAViolationResponse] = []
    latest_metric: Optional[SLAMetricResponse] = None
    violation_count: int = 0
    compliance_rate: float = 0.0

    class Config:
        from_attributes = True


# Multi-tenant Authentication Models
class SignupRequest(BaseModel):
    username: str
    email: EmailStr
    password: str
    org_id: Optional[str] = "default"


class SignupResponse(BaseModel):
    success: bool
    user_id: str
    message: str


class LoginRequest(BaseModel):
    username: str
    password: str
    org_id: Optional[str] = "default"


class LoginResponse(BaseModel):
    success: bool
    token: str
    user_id: str
    org_id: str
    expires_at: datetime
    message: str


class LogoutRequest(BaseModel):
    pass


class LogoutResponse(BaseModel):
    success: bool
    message: str


class AuthTokenValidationResponse(BaseModel):
    success: bool
    user_id: Optional[str] = None
    org_id: Optional[str] = None
    message: str


# Resource Allocation Models
class ResourceAllocationRequest(BaseModel):
    department_id: int
    resource_type: str
    required_amount: int
    reason: Optional[str] = None


class ResourceAllocationApprovalRequest(BaseModel):
    approved_amount: int
    approval_reason: Optional[str] = None
    approved_by: Optional[str] = None


class DepartmentResourceResponse(BaseModel):
    id: int
    department_id: int
    resource_type: str
    total_allocated: int
    current_used: int
    reserved: int
    unit: str
    created_at: str
    updated_at: str


class ResourceAllocationResponse(BaseModel):
    id: int
    department_id: int
    resource_type: str
    amount: int
    priority: int
    status: str
    allocated_at: Optional[str]
    expires_at: Optional[str]
    created_at: str
    updated_at: str


class ResourceRequestResponse(BaseModel):
    id: int
    department_id: int
    resource_type: str
    required_amount: int
    reason: Optional[str]
    status: str
    approved_amount: Optional[int]
    approval_reason: Optional[str]
    approved_by: Optional[str]
    requested_at: str
    approved_at: Optional[str]
    created_at: str
    updated_at: str


class ApiKeyCreate(BaseModel):
    name: str
    description: Optional[str] = None
    rate_limit_per_minute: int = 100


class ApiKeyResponse(BaseModel):
    id: str
    name: str
    description: Optional[str] = None
    created_at: datetime
    last_used_at: Optional[datetime] = None
    expires_at: Optional[datetime] = None
    is_active: bool
    rate_limit_per_minute: int

    class Config:
        from_attributes = True


class ApiKeyWithSecret(ApiKeyResponse):
    key: str


class ApiKeyUsageResponse(BaseModel):
    id: str
    endpoint: str
    method: str
    status_code: int
    response_time_ms: int
    timestamp: datetime
    ip_address: Optional[str] = None
    user_agent: Optional[str] = None

    class Config:
        from_attributes = True


class ApiKeyPermissionCreate(BaseModel):
    resource_type: str
    action: str


class ApiKeyPermissionResponse(BaseModel):
    id: str
    resource_type: str
    action: str

    class Config:
        from_attributes = True


class AgentEvaluationCreate(BaseModel):
    agent_id: str
    completion_rate: float  # 0.0-100.0
    quality_score: float    # 1.0-5.0
    overall_score: float    # 計算済みスコア


class AgentEvaluationUpdate(BaseModel):
    completion_rate: Optional[float] = None
    quality_score: Optional[float] = None
    overall_score: Optional[float] = None


class AgentEvaluationResponse(BaseModel):
    id: int
    agent_id: str
    completion_rate: float
    quality_score: float
    overall_score: float
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


class EvaluationHistoryCreate(BaseModel):
    agent_id: str
    completion_rate: float
    quality_score: float
    overall_score: float


class EvaluationHistoryResponse(BaseModel):
    id: int
    agent_id: str
    completion_rate: float
    quality_score: float
    overall_score: float
    created_at: datetime

    class Config:
        from_attributes = True


# =====================================================================
# 部署間コラボレーション関連スキーマ (Task #2414)
# =====================================================================

class CrossDepartmentRequestCreate(BaseModel):
    requesting_department_id: int
    receiving_department_id: int
    request_type: str  # task_request, resource_request, skill_request
    priority: int = 3
    description: Optional[str] = None

    @field_validator('request_type')
    @classmethod
    def validate_request_type(cls, v):
        if v not in ['task_request', 'resource_request', 'skill_request']:
            raise ValueError('Invalid request_type')
        return v

    @field_validator('priority')
    @classmethod
    def validate_priority(cls, v):
        if not (1 <= v <= 5):
            raise ValueError('Priority must be between 1 and 5')
        return v


class CrossDepartmentRequestResponse(CrossDepartmentRequestCreate):
    id: int
    status: str
    created_at: str
    updated_at: str

    class Config:
        from_attributes = True


class TaskSharingCreate(BaseModel):
    request_id: int
    task_id: int
    sharing_terms: Optional[str] = None


class TaskSharingResponse(TaskSharingCreate):
    id: int
    status: str
    created_at: str

    class Config:
        from_attributes = True


class AgentEvaluationCreate(BaseModel):
    agent_id: str
    completion_rate: float  # 0.0-100.0
    quality_score: float    # 1.0-5.0
    overall_score: float    # 計算済みスコア


class AgentEvaluationUpdate(BaseModel):
    completion_rate: Optional[float] = None
    quality_score: Optional[float] = None
    overall_score: Optional[float] = None


class AgentEvaluationResponse(BaseModel):
    id: int
    agent_id: str
    completion_rate: float
    quality_score: float
    overall_score: float
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


class EvaluationHistoryCreate(BaseModel):
    agent_id: str
    completion_rate: float
    quality_score: float
    overall_score: float


class EvaluationHistoryResponse(BaseModel):
    id: int
    agent_id: str
    completion_rate: float
    quality_score: float
    overall_score: float
    created_at: datetime

    class Config:
        from_attributes = True


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# Slack/Discord Integration Models
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

class IntegrationConfigCreate(BaseModel):
    integration_type: str  # 'slack' or 'discord'
    organization_id: str
    webhook_url: str
    webhook_secret: str
    channel_id: Optional[str] = None
    channel_name: Optional[str] = None
    is_active: int = 1
    notify_on_agent_status: int = 1
    notify_on_task_delegation: int = 1
    notify_on_cost_alert: int = 1
    notify_on_approval_request: int = 1
    notify_on_error_event: int = 1
    notify_on_system_alert: int = 1
    metadata: Optional[str] = None
    created_by: Optional[str] = None


class IntegrationConfigUpdate(BaseModel):
    integration_type: Optional[str] = None
    organization_id: Optional[str] = None
    webhook_url: Optional[str] = None
    webhook_secret: Optional[str] = None
    channel_id: Optional[str] = None
    channel_name: Optional[str] = None
    is_active: Optional[int] = None
    notify_on_agent_status: Optional[int] = None
    notify_on_task_delegation: Optional[int] = None
    notify_on_cost_alert: Optional[int] = None
    notify_on_approval_request: Optional[int] = None
    notify_on_error_event: Optional[int] = None
    notify_on_system_alert: Optional[int] = None
    metadata: Optional[str] = None


class IntegrationConfigResponse(BaseModel):
    id: int
    integration_type: str
    organization_id: str
    webhook_url: str
    channel_id: Optional[str] = None
    channel_name: Optional[str] = None
    is_active: int
    notify_on_agent_status: int
    notify_on_task_delegation: int
    notify_on_cost_alert: int
    notify_on_approval_request: int
    notify_on_error_event: int
    notify_on_system_alert: int
    metadata: Optional[str] = None
    created_by: Optional[str] = None
    created_at: str
    updated_at: str
    last_verified_at: Optional[str] = None

    class Config:
        from_attributes = True


class SlackWebhookPayload(BaseModel):
    type: str
    challenge: Optional[str] = None
    event: Optional[dict] = None
    token: Optional[str] = None
    team_id: Optional[str] = None


class DiscordWebhookPayload(BaseModel):
    type: int
    data: Optional[dict] = None
    member: Optional[dict] = None
    guild_id: Optional[str] = None
    channel_id: Optional[str] = None


class WebhookEventResponse(BaseModel):
    id: int
    event_id: str
    integration_config_id: Optional[int] = None
    event_type: str
    event_source: str
    processing_status: str
    error_message: Optional[str] = None
    notification_id: Optional[int] = None
    received_at: str
    processed_at: Optional[str] = None

    class Config:
        from_attributes = True


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# Agent Score Models (Task #2485)
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

class ScoreModel(BaseModel):
    id: int
    agent_id: str
    agent_name: str
    completion_rate: float
    quality_score: float
    performance_score: float
    overall_score: float
    total_tasks: int
    completed_tasks: int
    last_updated: str

    class Config:
        from_attributes = True


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# Cross Department Collaboration Models (Task #2486)
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

class CrossDeptTaskCreate(BaseModel):
    title: str
    description: Optional[str] = None
    receiving_dept_id: int
    priority: str = "medium"
    deadline: Optional[str] = None

    @field_validator("priority")
    @classmethod
    def validate_priority(cls, v: str) -> str:
        allowed = {"low", "medium", "high", "urgent"}
        if v not in allowed:
            raise ValueError(f"priority must be one of {allowed}")
        return v


class CrossDeptTaskStatusUpdate(BaseModel):
    status: str
    comment: Optional[str] = None

    @field_validator("status")
    @classmethod
    def validate_status(cls, v: str) -> str:
        allowed = {"pending", "acknowledged", "in_progress", "completed", "rejected"}
        if v not in allowed:
            raise ValueError(f"status must be one of {allowed}")
        return v


class DeptCollabNotificationReadRequest(BaseModel):
    pass


# ─────────────────────────────────────────────────────────
# Cross-Department Tasks (Task #2486)
# 部署間タスク依頼: cross_dept_tasks テーブル用 Pydantic モデル
# Note: 既存の CrossDeptTaskCreate (cross_department_tasks 用) と
#       命名衝突を避けるため Request 接尾辞を付与
# ─────────────────────────────────────────────────────────

class CrossDeptTaskRequestCreate(BaseModel):
    """部署間タスク依頼作成リクエスト"""
    to_dept_id: int
    task_name: str
    task_description: Optional[str] = None

    @field_validator("task_name")
    @classmethod
    def validate_task_name(cls, v: str) -> str:
        if not v or not v.strip():
            raise ValueError("task_name must not be empty")
        if len(v) > 500:
            raise ValueError("task_name must be 500 characters or less")
        return v.strip()


class CrossDeptTaskRequestResponse(BaseModel):
    """部署間タスク依頼レスポンス"""
    id: int
    from_dept_id: int
    to_dept_id: int
    task_name: str
    task_description: Optional[str] = None
    status: str
    created_by: Optional[str] = None
    reject_reason: Optional[str] = None
    created_at: str
    updated_at: str


class CrossDeptTaskRequestAccept(BaseModel):
    """部署間タスク受け入れリクエスト（任意コメント）"""
    comment: Optional[str] = None


class CrossDeptTaskRequestReject(BaseModel):
    """部署間タスク拒否リクエスト（任意理由）"""
    reason: Optional[str] = None


class CrossDeptTaskRequestListResponse(BaseModel):
    """部署間タスク依頼一覧レスポンス"""
    requests: List[CrossDeptTaskRequestResponse]
    total: int


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# Agent Messaging & Notification Models (#2547)
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

class TaskCompletionEventExecutor(BaseModel):
    """タスク完了イベント実行者情報"""
    user_id: str
    username: str
    role: str


class TaskCompletionEventMetadata(BaseModel):
    """タスク完了イベントメタデータ"""
    tag_ids: Optional[List[str]] = None
    category: Optional[str] = None
    phase: Optional[str] = None


class TaskCompletionEvent(BaseModel):
    """タスク完了イベント"""
    type: str = "task.completed"
    timestamp: str
    task_id: int
    task_title: Optional[str] = None
    workflow_id: str
    team_name: str
    executor: TaskCompletionEventExecutor
    status: str = "completed"
    priority: int = 3
    completion_time_ms: Optional[int] = None
    metadata: TaskCompletionEventMetadata


class WebhookRetryPolicy(BaseModel):
    """Webhook リトライポリシー"""
    max_retries: int = 3
    retry_backoff_ms: int = 1000
    timeout_ms: int = 5000


class WebhookSubscriptionCreate(BaseModel):
    """Webhook 登録リクエスト"""
    name: str
    event_type: str = "task.completed"
    target_url: str
    auth_type: str
    secret_key: str
    is_active: bool = True
    retry_policy: Optional[WebhookRetryPolicy] = None
    headers: Optional[dict] = None


class WebhookSubscriptionResponse(BaseModel):
    """Webhook 登録レスポンス"""
    webhook_id: str
    name: str
    event_type: str
    target_url: str
    is_active: bool
    created_at: str
    last_triggered_at: Optional[str] = None
    trigger_count: int = 0


class WebhookListResponse(BaseModel):
    """Webhook 一覧レスポンス"""
    webhooks: List[WebhookSubscriptionResponse]
    total: int


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# Subscription Management Models (#2548)
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

class SubscriptionPlanFeatures(BaseModel):
    """プランの機能フラグ"""
    max_agents: int
    api_calls_per_month: int
    storage_gb: int
    email_support: bool
    priority_support: bool = False


class SubscriptionPlan(BaseModel):
    """プランマスタ情報"""
    id: str
    name: str
    description: Optional[str] = None
    price_jpy: int
    features: SubscriptionPlanFeatures


class SubscriptionResponse(BaseModel):
    """サブスクリプション情報"""
    id: str
    user_id: str
    plan: str
    status: str
    current_period_start: datetime
    current_period_end: datetime
    canceled_at: Optional[datetime] = None
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


class SubscriptionPlanChangeRequest(BaseModel):
    """プラン変更リクエスト"""
    plan: str


class SubscriptionPlanListResponse(BaseModel):
    """プランリスト レスポンス"""
    plans: List[SubscriptionPlan]
