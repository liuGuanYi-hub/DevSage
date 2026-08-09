"""API contracts for project registry discovery."""

from __future__ import annotations

from pydantic import BaseModel


class ProjectRoleResponse(BaseModel):
    role: str
    actions: list[str]


class ProjectMemberResponse(BaseModel):
    actor_id: str
    role: str
    actions: list[str]


class ProjectResponse(BaseModel):
    project_id: str
    name: str
    source_root: str
    description: str
    source_kind: str = "workspace"
    read_only: bool = False
    roles: list[ProjectRoleResponse]
    members: list[ProjectMemberResponse]


class ProjectListResponse(BaseModel):
    items: list[ProjectResponse]
    total: int
