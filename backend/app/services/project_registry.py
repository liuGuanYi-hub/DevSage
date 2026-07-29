"""Project registry and local role capability boundaries for DevSage."""

from __future__ import annotations

from dataclasses import dataclass
import json
import os
from pathlib import Path
import re
from typing import Any


class ProjectRegistryError(ValueError):
    """Raised when a project manifest or project boundary is invalid."""


ROLE_ACTIONS: dict[str, tuple[str, ...]] = {
    "viewer": ("read", "search", "agent"),
    "editor": ("read", "search", "agent", "writeback_preview", "writeback_approve"),
    "operator": (
        "read",
        "search",
        "agent",
        "writeback_preview",
        "writeback_approve",
        "code_write_preview",
        "code_write_approve",
        "manage_project",
    ),
}
DEFAULT_ACTOR_ID = "local-demo"


@dataclass(frozen=True)
class ProjectDefinition:
    project_id: str
    name: str
    source_root: str
    description: str
    roles: tuple[str, ...] = ("viewer", "editor", "operator")
    members: tuple[tuple[str, str], ...] = (
        (DEFAULT_ACTOR_ID, "operator"),
        ("local-viewer", "viewer"),
        ("local-editor", "editor"),
    )

    def to_dict(self) -> dict[str, Any]:
        return {
            "project_id": self.project_id,
            "name": self.name,
            "source_root": self.source_root,
            "description": self.description,
            "roles": [
                {"role": role, "actions": list(ROLE_ACTIONS[role])}
                for role in self.roles
            ],
        }


class ProjectRegistry:
    """Read-only project definitions confined to the configured project root."""

    _PROJECT_ID_PATTERN = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_-]{1,63}$")

    def __init__(
        self,
        project_root: str | Path,
        definitions: tuple[ProjectDefinition, ...] | None = None,
    ) -> None:
        self.project_root = Path(project_root).expanduser().resolve()
        self._definitions = definitions or (
            ProjectDefinition(
                project_id="sample-data",
                name="DevMind 脱敏样例知识库",
                source_root="sample-data",
                description="用于离线演示的文档、代码、配置、Git 和 Issue 样例。",
            ),
        )
        self._validate_definitions()

    @classmethod
    def from_environment(cls, project_root: str | Path) -> "ProjectRegistry":
        manifest_value = os.getenv("DEVSAGE_PROJECT_MANIFEST", "").strip()
        if not manifest_value:
            return cls(project_root)
        manifest_path = Path(manifest_value).expanduser()
        if manifest_path.is_absolute():
            raise ProjectRegistryError("project manifest must be relative to project root")
        root = Path(project_root).expanduser().resolve()
        manifest_path = (root / manifest_path).resolve()
        try:
            manifest_path.relative_to(root)
            payload = json.loads(manifest_path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError, ValueError) as exc:
            raise ProjectRegistryError("project manifest could not be loaded") from exc
        if not isinstance(payload, list):
            raise ProjectRegistryError("project manifest must contain a list")
        definitions = tuple(
            _definition_from_manifest_item(item)
            for item in payload
            if isinstance(item, dict)
        )
        return cls(root, definitions)

    def list_projects(self) -> tuple[ProjectDefinition, ...]:
        return self._definitions

    def get(self, project_id: str) -> ProjectDefinition:
        for definition in self._definitions:
            if definition.project_id == project_id:
                return definition
        raise ProjectRegistryError(f"project not found: {project_id}")

    def resolve_source_root(self, project_id: str) -> Path:
        definition = self.get(project_id)
        resolved = (self.project_root / definition.source_root).resolve()
        try:
            resolved.relative_to(self.project_root)
        except ValueError as exc:
            raise ProjectRegistryError("project source root escaped project root") from exc
        if not resolved.is_dir():
            raise ProjectRegistryError(f"project source root is not a directory: {project_id}")
        return resolved

    def role_for(self, project_id: str, actor_id: str) -> str:
        """Resolve a configured local actor to one role for a project."""

        definition = self.get(project_id)
        actor = actor_id.strip()
        if not actor:
            raise ProjectRegistryError("actor id must not be empty")
        assignments = dict(definition.members)
        try:
            return assignments[actor]
        except KeyError as exc:
            raise ProjectRegistryError("actor is not a member of the project") from exc

    def require_action(self, project_id: str, actor_id: str, action: str) -> str:
        """Return the actor role or reject an action outside its capability boundary."""

        role = self.role_for(project_id, actor_id)
        if action not in ROLE_ACTIONS[role]:
            raise ProjectRegistryError(
                f"role {role} is not allowed to perform action {action}"
            )
        return role

    def _validate_definitions(self) -> None:
        ids: set[str] = set()
        for definition in self._definitions:
            if not self._PROJECT_ID_PATTERN.fullmatch(definition.project_id):
                raise ProjectRegistryError("project id has an invalid format")
            if definition.project_id in ids:
                raise ProjectRegistryError("project ids must be unique")
            ids.add(definition.project_id)
            if not definition.name.strip() or not definition.source_root.strip():
                raise ProjectRegistryError("project name and source root are required")
            if not set(definition.roles).issubset(ROLE_ACTIONS):
                raise ProjectRegistryError("project contains an unsupported role")
            member_ids: set[str] = set()
            for actor_id, role in definition.members:
                if not actor_id.strip() or actor_id in member_ids:
                    raise ProjectRegistryError("project members must be unique and non-empty")
                if role not in ROLE_ACTIONS or role not in definition.roles:
                    raise ProjectRegistryError("project member contains an unsupported role")
                member_ids.add(actor_id)


def _definition_from_manifest_item(item: dict[str, Any]) -> ProjectDefinition:
    """Build a definition while keeping local-demo compatibility for old manifests."""

    roles = tuple(str(role) for role in item.get("roles", ROLE_ACTIONS))
    raw_members = item.get("members")
    if raw_members is None:
        fallback_role = "operator" if "operator" in roles else (roles[0] if roles else "")
        raw_members = {DEFAULT_ACTOR_ID: fallback_role} if fallback_role else {}
    if not isinstance(raw_members, dict):
        raise ProjectRegistryError("project members must be an object")
    return ProjectDefinition(
        project_id=str(item["project_id"]),
        name=str(item["name"]),
        source_root=str(item["source_root"]),
        description=str(item.get("description", "")),
        roles=roles,
        members=tuple((str(actor), str(role)) for actor, role in raw_members.items()),
    )
