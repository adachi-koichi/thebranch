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
    type: str
    description: Optional[str] = ""
    agent: AgentConfig
    kpi_target: Optional[str] = ""


class DepartmentResponse(BaseModel):
    id: str
    name: str
    type: str
    description: Optional[str]
    agent: dict
    kpi_target: Optional[str]
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True
