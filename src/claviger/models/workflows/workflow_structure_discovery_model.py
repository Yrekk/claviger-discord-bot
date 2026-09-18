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

    # Effective permissions remain observational. They describe current Discord
    # behavior but are not used as the structural workflow marker.
    everyone_can_view: bool
    everyone_can_send: bool

    bot_can_view: bool
    bot_can_send: bool

    # Structural workflow discovery uses the explicit @everyone send_messages
    # overwrite as its deterministic marker:
    #
    # True:
    #     @everyone explicitly may send messages in this channel.
    #
    # False:
    #     @everyone explicitly may not send messages in this channel.
    #
    # None:
    #     No explicit channel-level marker exists. Inherited behavior is not
    #     enough to classify the channel as part of a workflow structure.
    everyone_send_override: bool | None = None

    # The application-role overwrite remains available as observational data
    # for later diagnostics or reconciliation. It is not a discovery criterion.
    application_role_send_override: bool | None = None


@dataclass(frozen=True, slots=True)
class WorkflowRoleCandidate:
    """Describe one Discord role the application can safely manage."""

    role_id: int
    role_name: str


@dataclass(frozen=True, slots=True)
class WorkflowStructureCandidate:
    """Describe one Discord category matching the workflow structural contract.

    A structure candidate is intentionally semantic-free. Discovery recognizes
    only explicit @everyone channel-level send markers inside one category:

    - one or more protected channels with send_messages explicitly denied;
    - one or more interactive channels with send_messages explicitly allowed.

    Visibility, role names, channel names, application permissions and inherited
    permissions do not participate in recognition.

    The service does not decide which protected channel is the management
    channel or which interactive channel is the execution channel when several
    possibilities exist. That choice belongs to the human configuration flow.
    """

    category: WorkflowCategoryCandidate
    protected_channels: tuple[WorkflowTextChannelCandidate, ...]
    interactive_channels: tuple[WorkflowTextChannelCandidate, ...]

    # Persistence enrichment may annotate an otherwise reusable Discord
    # structure with commands already bound to it. Discovery itself never
    # decides whether sharing is allowed.
    configured_command_names: tuple[str, ...] = ()

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
