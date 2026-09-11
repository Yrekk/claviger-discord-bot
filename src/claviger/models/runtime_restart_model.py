from dataclasses import dataclass, field


@dataclass(frozen=True, slots=True)
class RuntimeRestartRequest:
    """Transient data required to complete a Discord-requested restart."""

    application_id: int

    interaction_token: str = field(
        repr=False,
    )

    command_tree_signature: str | None = None
