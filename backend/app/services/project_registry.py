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
        "issue_write_preview",
        "issue_write_approve",
        "manage_project",
    ),
    "vault_viewer": ("read", "search", "agent", "index"),
}
DEFAULT_ACTOR_ID = "local-demo"
OBSIDIAN_PROJECT_ID = "obsidian-vault"


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
    external_path: Path | None = None
    read_only: bool = False
    source_kind: str = "workspace"

    def to_dict(self) -> dict[str, Any]:
        return {
            "project_id": self.project_id,
            "name": self.name,
            "source_root": self.source_root,
            "description": self.description,
            "source_kind": self.source_kind,
            "read_only": self.read_only,
            "roles": [
                {"role": role, "actions": list(ROLE_ACTIONS[role])}
                for role in self.roles
            ],
            "members": [
                {
                    "actor_id": actor_id,
                    "role": role,
                    "actions": list(ROLE_ACTIONS[role]),
                }
                for actor_id, role in self.members
            ],
        }


class ProjectRegistry:
    """Read-only project definitions with explicit workspace or external Vault boundaries."""

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
            definitions: list[ProjectDefinition] = [
                ProjectDefinition(
                    project_id="sample-data",
                    name="DevMind 脱敏样例知识库",
                    source_root="sample-data",
                    description="用于离线演示的文档、代码、配置、Git 和 Issue 样例。",
                )
            ]
            obsidian_path = os.getenv("DEVSAGE_OBSIDIAN_VAULT_PATH", "").strip()
            if obsidian_path:
                definitions.append(
                    ProjectDefinition(
                        project_id=OBSIDIAN_PROJECT_ID,
                        name="Obsidian Vault（外部只读）",
                        source_root=OBSIDIAN_PROJECT_ID,
                        description="只读读取外部 Obsidian Vault；索引快照和所有 DevSage 写回仍留在 DevSage 项目内。",
                        roles=("vault_viewer",),
                        members=(("obsidian-viewer", "vault_viewer"),),
                        external_path=Path(obsidian_path).expanduser().resolve(),
                        read_only=True,
                        source_kind="obsidian_vault",
                    )
                )
            return cls(project_root, tuple(definitions))
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
        if definition.external_path is not None:
            resolved = definition.external_path.expanduser().resolve()
        else:
            resolved = (self.project_root / definition.source_root).resolve()
            try:
                resolved.relative_to(self.project_root)
            except ValueError as exc:
                raise ProjectRegistryError("project source root escaped project root") from exc
        if not resolved.is_dir():
            raise ProjectRegistryError(f"project source root is not a directory: {project_id}")
        return resolved

    def external_sources(self) -> dict[str, Path]:
        """Return approved logical-to-filesystem mappings for external read-only sources."""

        return {
            definition.source_root: self.resolve_source_root(definition.project_id)
            for definition in self._definitions
            if definition.external_path is not None
        }

    def is_external_source_root(self, source_root: str) -> bool:
        """Identify logical roots that must go through project authorization."""

        return any(
            definition.source_root == source_root and definition.external_path is not None
            for definition in self._definitions
        )

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
            if definition.source_kind not in {"workspace", "obsidian_vault"}:
                raise ProjectRegistryError("project contains an unsupported source kind")
            if definition.external_path is not None:
                if not definition.external_path.is_absolute():
                    raise ProjectRegistryError("external project path must be absolute")
                if not definition.read_only or definition.source_kind != "obsidian_vault":
                    raise ProjectRegistryError("external project sources must be read-only Obsidian Vaults")
                if not set(definition.roles).issubset({"vault_viewer"}):
                    raise ProjectRegistryError("external Obsidian Vaults may only use vault_viewer")
            member_ids: set[str] = set()
            for actor_id, role in definition.members:
                if not actor_id.strip() or actor_id in member_ids:
                    raise ProjectRegistryError("project members must be unique and non-empty")
                if role not in ROLE_ACTIONS or role not in definition.roles:
                    raise ProjectRegistryError("project member contains an unsupported role")
                member_ids.add(actor_id)


def _definition_from_manifest_item(item: dict[str, Any]) -> ProjectDefinition:
    """Build a definition while keeping local-demo compatibility for old manifests."""

    roles = tuple(str(role) for role in item.get("roles", ("viewer", "editor", "operator")))
    raw_members = item.get("members")
    if raw_members is None:
        fallback_role = "operator" if "operator" in roles else (roles[0] if roles else "")
        raw_members = {DEFAULT_ACTOR_ID: fallback_role} if fallback_role else {}
    if not isinstance(raw_members, dict):
        raise ProjectRegistryError("project members must be an object")
    external_path_value = item.get("external_path")
    external_path_env = item.get("external_path_env")
    if external_path_value is not None and external_path_env is not None:
        raise ProjectRegistryError("project cannot define both external_path and external_path_env")
    if external_path_env is not None:
        if not isinstance(external_path_env, str) or not external_path_env.strip():
            raise ProjectRegistryError("external_path_env must be a non-empty string")
        external_path_value = os.getenv(external_path_env.strip(), "").strip()
        if not external_path_value:
            raise ProjectRegistryError(f"external project path environment variable is empty: {external_path_env}")
    external_path = (
        Path(str(external_path_value)).expanduser().resolve()
        if external_path_value is not None
        else None
    )
    return ProjectDefinition(
        project_id=str(item["project_id"]),
        name=str(item["name"]),
        source_root=str(item["source_root"]),
        description=str(item.get("description", "")),
        roles=roles,
        members=tuple((str(actor), str(role)) for actor, role in raw_members.items()),
        external_path=external_path,
        read_only=bool(item.get("read_only", False)),
        source_kind=str(item.get("source_kind", "obsidian_vault" if external_path else "workspace")),
    )
