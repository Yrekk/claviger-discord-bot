from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class ResolvedWorkflowConfiguration:
    """Describe one workflow whose Discord resources have stable identities."""

    guild_id: int
    workflow_key: str

    title: str
    description: str | None

    command_name: str
    command_description: str

    # Structural resources are resolved before persistence. The repository must
    # never store temporary frontend choices such as "create this resource".
    category_id: int
    management_channel_id: int
    execution_channel_id: int
    primary_role_id: int

    # Questionnaire discovery remains represented by the generic catalog model.
    questionnaire_role_prefix: str

    # None means that this workflow does not expose the AI preference context.
    # When present, the ID refers to the guild-wide role implementing the
    # existing "ai_preference" capability.
    ai_preference_role_id: int | None = None
