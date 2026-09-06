import discord

from claviger.policies.guild_policy import GuildPolicy
from claviger.services.catalog_next_coordinator_service import (
    CatalogNextCoordinatorService,
)
from claviger.ui.catalog_metadata_modal import (
    CatalogMetadataModal,
)


class CatalogNextView(discord.ui.View):
    """Offer a button to configure the next incomplete catalog entry."""

    def __init__(
        self,
        *,
        coordinator: CatalogNextCoordinatorService,
        policy: GuildPolicy,
        actor_id: int,
    ) -> None:
        super().__init__(
            timeout=300,
        )

        self.coordinator = coordinator
        self.policy = policy
        self.actor_id = actor_id

    @discord.ui.button(
        label="Configurer le suivant",
        style=discord.ButtonStyle.primary,
    )
    async def configure_next(
        self,
        interaction: discord.Interaction,
        _: discord.ui.Button,
    ) -> None:
        """Open the next incomplete catalog entry."""

        if interaction.user.id != self.actor_id:
            await interaction.response.send_message(
                "Ce bouton appartient à un autre utilisateur.",
                ephemeral=True,
            )
            return

        if interaction.guild is None:
            await interaction.response.send_message(
                "Cette action doit être utilisée sur un serveur.",
                ephemeral=True,
            )
            return

        try:
            selection = await self.coordinator.get_next(
                interaction.guild.id,
                self.policy,
            )

        except Exception:
            await interaction.response.send_message(
                (
                    "Impossible de déterminer l'entrée suivante. "
                    "Relance `/claviger catalog next`."
                ),
                ephemeral=True,
            )
            return

        if selection is None:
            await interaction.response.edit_message(
                content="Tous les catalogues disponibles sont configurés.",
                view=None,
            )
            return

        await interaction.response.send_modal(
            CatalogMetadataModal(
                coordinator=self.coordinator,
                policy=self.policy,
                selection=selection,
                actor_id=self.actor_id,
            )
        )
