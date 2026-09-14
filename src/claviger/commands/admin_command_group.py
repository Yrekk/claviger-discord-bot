import discord
from discord import app_commands

RECOVERY_COMMAND_NAMES = frozenset(
    {
        "database",
        "restart",
        "config-server",
    }
)


class GuildAdminCommandGroup(app_commands.Group):
    """Restrict normal ADMIN commands to the configured command channel."""

    def __init__(
        self,
        *,
        name: str,
        description: str,
        command_channel_id: int | None,
    ) -> None:
        super().__init__(
            name=name,
            description=description,
        )

        self.command_channel_id = command_channel_id

    async def interaction_check(
        self,
        interaction: discord.Interaction,
    ) -> bool:
        """Allow recovery commands everywhere and route normal ADMIN commands."""

        root_child = interaction.command

        while (
            root_child is not None and getattr(root_child, "parent", None) is not self
        ):
            root_child = getattr(
                root_child,
                "parent",
                None,
            )

        if (
            root_child is not None
            and getattr(root_child, "name", None) in RECOVERY_COMMAND_NAMES
        ):
            return True

        if interaction.guild is None:
            await interaction.response.send_message(
                "Cette commande doit être utilisée sur un serveur.",
                ephemeral=True,
            )
            return False

        if self.command_channel_id is None:
            await interaction.response.send_message(
                (
                    "La configuration ADMIN de ce serveur ne définit aucun "
                    "salon de commandes. "
                    f"Utilise `/{self.name} config-server`."
                ),
                ephemeral=True,
            )
            return False

        if interaction.channel_id == self.command_channel_id:
            return True

        await interaction.response.send_message(
            (
                "Cette commande administrative doit être utilisée dans "
                f"<#{self.command_channel_id}>."
            ),
            ephemeral=True,
        )

        return False
