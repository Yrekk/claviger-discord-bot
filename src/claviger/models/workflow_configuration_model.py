from dataclasses import dataclass
from typing import Literal

# A configurable Discord resource can either reuse something that already
# exists on the guild or request that Claviger creates it later.
WorkflowResourceMode = Literal[
    "existing",
    "create",
]


@dataclass(frozen=True, slots=True)
class WorkflowResourceSelection:
    """Describe one existing-or-create choice made by a configuration UI."""

    mode: WorkflowResourceMode

    # Existing resources are referenced exclusively through their stable
    # Discord snowflake. Their human-readable name is discovered from Discord.
    resource_id: int | None = None

    # Creation requests carry the desired human-readable name. The future
    # provisioning service will translate this into the appropriate Discord
    # category, channel or role creation operation.
    name: str | None = None


@dataclass(frozen=True, slots=True)
class WorkflowConfigurationDraft:
    """Describe raw workflow configuration submitted by any frontend."""

    guild_id: int

    # workflow_key is an internal stable identity. A creation UI may omit it;
    # validation will then derive the initial key from the command name.
    workflow_key: str | None

    title: str
    description: str | None

    command_name: str
    command_description: str | None

    # Structural Discord resources.
    category: WorkflowResourceSelection
    management_channel: WorkflowResourceSelection
    execution_channel: WorkflowResourceSelection
    primary_role: WorkflowResourceSelection

    # Questionnaire discovery remains catalog-oriented. This value will later
    # become the role_prefix of the catalog bound to this workflow.
    questionnaire_role_prefix: str

    # This is an interface-level choice, not a second persisted AI model.
    # The coordinator translates True into the shared ai_preference context
    # binding and False into the absence of that editable context.
    ai_enabled: bool

    # A guild that already owns the ai_preference capability does not need to
    # provide this selection again. For a new capability, frontends may select
    # an existing manageable role or request creation of one.
    ai_preference_role: WorkflowResourceSelection | None = None


@dataclass(frozen=True, slots=True)
class WorkflowConfigurationSpec:
    """Describe one normalized workflow configuration ready for coordination."""

    guild_id: int

    workflow_key: str

    title: str
    description: str | None

    command_name: str
    command_description: str

    category: WorkflowResourceSelection
    management_channel: WorkflowResourceSelection
    execution_channel: WorkflowResourceSelection
    primary_role: WorkflowResourceSelection

    questionnaire_role_prefix: str
    ai_enabled: bool

    # None is valid while reconciliation can reuse an already persisted
    # guild-wide ai_preference role.
    ai_preference_role: WorkflowResourceSelection | None = None
