from dataclasses import dataclass, field


@dataclass(frozen=True, slots=True)
class RuntimeRestartRequest:
    """Transient data required to complete a Discord-requested restart.

    Attributes:
        application_id:
            Discord application ID required to edit the original interaction
            response after restart.

        interaction_token:
            Discord interaction token required to edit the original ephemeral
            response. The token is excluded from object representation.

        guild_command_tree_signatures:
            Immutable snapshot of command-tree signatures indexed by Discord
            guild ID before the previous runtime instance shuts down.
    """

    application_id: int

    interaction_token: str = field(
        repr=False,
    )

    guild_command_tree_signatures: tuple[tuple[int, str], ...] = ()

    def command_tree_signature_for(
        self,
        guild_id: int,
    ) -> str | None:
        """Return the previous command-tree signature for one guild.

        Args:
            guild_id:
                Discord guild snowflake whose previous command tree is being
                queried.

        Returns:
            str | None:
                Previous command-tree signature when the guild existed in the
                runtime snapshot, otherwise None.
        """

        for registered_guild_id, signature in self.guild_command_tree_signatures:
            if registered_guild_id == guild_id:
                return signature

        return None
