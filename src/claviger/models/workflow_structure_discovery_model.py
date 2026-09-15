from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class WorkflowCategoryCandidate:
    """Describe one Discord category available to workflow configuration."""

    category_id: int
    category_name: str

    # Visibility is observational only. Workflow configuration may later decide
    # whether existing permissions are already suitable or need explicit repair.
    everyone_can_view: bool
    bot_can_view: bool


@dataclass(frozen=True, slots=True)
class WorkflowTextChannelCandidate:
    """Describe one Discord text channel available to workflow configuration."""

    channel_id: int
    channel_name: str

    # None means that the channel currently lives outside any category.
    category_id: int | None

    # These effective permissions allow reconciliation to distinguish between
    # a directly reusable channel and one that would require safe provisioning.
    everyone_can_view: bool
    everyone_can_send: bool

    bot_can_view: bool
    bot_can_send: bool


@dataclass(frozen=True, slots=True)
class WorkflowRoleCandidate:
    """Describe one Discord role Claviger can safely manage."""

    role_id: int
    role_name: str


@dataclass(frozen=True, slots=True)
class WorkflowStructureDiscoveryResult:
    """Describe the Discord resources visible to workflow configuration."""

    categories: tuple[WorkflowCategoryCandidate, ...]
    text_channels: tuple[WorkflowTextChannelCandidate, ...]
    manageable_roles: tuple[WorkflowRoleCandidate, ...]

    # Creation capability is exposed independently from discovered resources.
    # A frontend can therefore hide or disable "create" choices without trying
    # a Discord mutation first.
    can_create_channels: bool
    can_create_roles: bool
