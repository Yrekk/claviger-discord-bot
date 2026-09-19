from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class CatalogMetadataIssue:
    """Describe missing human metadata for one logical questionnaire entry."""

    entry_key: str
    label: str | None
    missing_fields: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class CatalogRoleIssue:
    """Describe one live or persisted catalog role requiring attention."""

    role_name: str
    channel_names: tuple[str, ...]
    reasons: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class WorkflowCatalogSectionDiagnostic:
    """Describe one catalog bound to a workflow."""

    catalog_key: str
    display_name: str
    role_prefix: str

    detected_role_names: tuple[str, ...]
    linked_channel_names: tuple[str, ...]

    entry_count: int
    complete_entry_count: int
    incomplete_entries: tuple[CatalogMetadataIssue, ...]

    unsynced_role_names: tuple[str, ...]
    role_issues: tuple[CatalogRoleIssue, ...]


@dataclass(frozen=True, slots=True)
class WorkflowCatalogDiagnostic:
    """Describe structure and questionnaire readiness for one workflow."""

    workflow_key: str
    title: str
    command_name: str

    category_name: str | None
    management_channel_name: str | None
    execution_channel_names: tuple[str, ...]

    primary_role_name: str | None
    primary_role_explicit_channel_names: tuple[str, ...]

    ai_questionnaire_owner: bool
    structure_issues: tuple[str, ...]

    catalogs: tuple[WorkflowCatalogSectionDiagnostic, ...]


@dataclass(frozen=True, slots=True)
class GuildCatalogDiagnosticResult:
    """Describe every configured workflow catalog for one Discord guild."""

    workflows: tuple[WorkflowCatalogDiagnostic, ...]
