from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class RolePatternAnomaly:
    """Describe one live Discord role conflicting with workflow catalog semantics."""

    role_name: str
    workflow_labels: tuple[str, ...]
    channel_names: tuple[str, ...]
    reasons: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class GuildRoleDiagnosticResult:
    """Describe workflow-aware role usage for one Discord guild."""

    bot_role_name: str

    ai_enabled: bool | None
    ai_role_name: str | None
    ai_role_missing: bool

    workflow_primary_role_names: tuple[str, ...]
    configured_catalog_role_names: tuple[str, ...]

    unconfigured_manageable_role_names: tuple[str, ...]
    unmanageable_role_names: tuple[str, ...]

    pattern_anomalies: tuple[RolePatternAnomaly, ...]
