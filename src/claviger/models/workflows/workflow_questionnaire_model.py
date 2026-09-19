from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class WorkflowQuestionnaireOption:
    """Describe one selectable logical catalog entry."""

    catalog_key: str
    entry_key: str
    label: str
    description: str | None
    emoji: str | None

    target_role_ids: tuple[int, ...]
    selected: bool


@dataclass(frozen=True, slots=True)
class WorkflowQuestionnaireCatalog:
    """Describe one catalog section exposed by a workflow questionnaire."""

    catalog_key: str
    display_name: str
    description: str | None
    options: tuple[WorkflowQuestionnaireOption, ...]


@dataclass(frozen=True, slots=True)
class WorkflowQuestionnaire:
    """Describe the complete current questionnaire for one workflow member."""

    guild_id: int
    workflow_key: str
    command_name: str
    title: str
    description: str | None

    primary_role_id: int

    catalogs: tuple[WorkflowQuestionnaireCatalog, ...]
    managed_catalog_role_ids: tuple[int, ...]

    ai_enabled: bool
    ai_role_id: int | None
    ai_editable: bool
    ai_preference: bool


@dataclass(frozen=True, slots=True)
class WorkflowQuestionnaireCatalogSubmission:
    """Preserve what one modal actually presented and what the member selected."""

    catalog_key: str
    visible_entry_keys: tuple[str, ...]
    selected_entry_keys: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class WorkflowQuestionnaireSubmission:
    """Describe one questionnaire submission without Discord-specific objects."""

    catalogs: tuple[WorkflowQuestionnaireCatalogSubmission, ...]
    ai_preference: bool | None = None
