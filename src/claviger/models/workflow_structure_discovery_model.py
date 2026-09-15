from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class WorkflowCategoryCandidate:
    """Describe one Discord category available to workflow configuration."""

    category_id: int
    category_name: str

    # Visibility remains observational. Structural workflow discovery does not
    # infer any semantic meaning from the category name.
    everyone_can_view: bool
    bot_can_view: bool


@dataclass(frozen=True, slots=True)
class WorkflowTextChannelCandidate:
    """Describe one Discord text channel available to workflow configuration."""

    channel_id: int
    channel_name: str

    # None means that the channel currently lives outside any category.
    category_id: int | None

    # Effective permissions describe what @everyone and the authenticated bot
    # can actually do in the channel after Discord resolves inheritance and
    # overwrites.
    everyone_can_view: bool
    everyone_can_send: bool

    bot_can_view: bool
    bot_can_send: bool

    # Structural workflow discovery also needs to distinguish an explicit
    # application-role permission from an effective permission inherited from
    # another source.
    #
    # True:
    #     The application's Discord role explicitly allows sending messages.
    #
    # False:
    #     The application's Discord role explicitly denies sending messages.
    #
    # None:
    #     No explicit send_messages overwrite exists for that role.
    application_role_send_override: bool | None = None


@dataclass(frozen=True, slots=True)
class WorkflowRoleCandidate:
    """Describe one Discord role the application can safely manage."""

    role_id: int
    role_name: str


@dataclass(frozen=True, slots=True)
class WorkflowStructureCandidate:
    """Describe one Discord category matching the workflow structural contract.

    A structure candidate is intentionally semantic-free. Discovery knows only
    that the category contains both kinds of channels required by the workflow
    contract:

    - one or more protected channels where @everyone cannot send messages and
      the application role explicitly can;
    - one or more interactive channels where @everyone can communicate.

    The service does not decide which protected channel is the rules/management
    channel or which interactive channel is the execution channel when several
    possibilities exist. That choice belongs to the human configuration flow.
    """

    category: WorkflowCategoryCandidate
    protected_channels: tuple[WorkflowTextChannelCandidate, ...]
    interactive_channels: tuple[WorkflowTextChannelCandidate, ...]

    @property
    def requires_protected_channel_choice(self) -> bool:
        """Return whether several protected channels require a human choice."""

        return len(self.protected_channels) > 1

    @property
    def requires_interactive_channel_choice(self) -> bool:
        """Return whether several interactive channels require a human choice."""

        return len(self.interactive_channels) > 1


@dataclass(frozen=True, slots=True)
class WorkflowStructureDiscoveryResult:
    """Describe Discord resources and recognized workflow structures."""

    categories: tuple[WorkflowCategoryCandidate, ...]
    text_channels: tuple[WorkflowTextChannelCandidate, ...]
    manageable_roles: tuple[WorkflowRoleCandidate, ...]

    # Creation capability remains part of the historical read-model contract.
    can_create_channels: bool
    can_create_roles: bool

    # Structural candidates are additive. The empty default preserves callers
    # that only need the historical atomic resource snapshot.
    workflow_candidates: tuple[WorkflowStructureCandidate, ...] = ()
