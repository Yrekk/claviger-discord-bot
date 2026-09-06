import discord

from claviger.models.catalog_next_selection_model import (
    CatalogNextSelection,
)
from claviger.policies.guild_policy import GuildPolicy
from claviger.services.catalog_next_coordinator_service import (
    CatalogNextCoordinatorService,
)


class CatalogMetadataModal(discord.ui.Modal):
    """Edit the human metadata of one catalog entry."""

    def __init__(
        self,
        *,
        coordinator: CatalogNextCoordinatorService,
        policy: GuildPolicy,
        selection: CatalogNextSelection,
        actor_id: int,
    ) -> None:
        super().__init__(
            title=f"Configurer {selection.entry.role_name}"[:45],
        )

        self.coordinator = coordinator
        self.policy = policy
        self.selection = selection
        self.actor_id = actor_id

        self.label_input = discord.ui.TextInput(
            label="Libellé",
            placeholder="Nom affiché à l'utilisateur",
            default=selection.entry.label,
            required=True,
            max_length=100,
        )

        self.description_input = discord.ui.TextInput(
            label="Description",
            placeholder="Description affichée à l'utilisateur",
            default=selection.entry.description,
            required=True,
            max_length=1000,
            style=discord.TextStyle.paragraph,
        )

        self.emoji_input = discord.ui.TextInput(
            label="Emoji",
            placeholder="Optionnel — ex. 🎮",
            default=selection.entry.emoji,
            required=False,
            max_length=100,
        )

        self.add_item(
            self.label_input,
        )
        self.add_item(
            self.description_input,
        )
        self.add_item(
            self.emoji_input,
        )

    async def on_submit(
        self,
        interaction: discord.Interaction,
    ) -> None:
        """Persist metadata and offer the next incomplete entry."""

        if interaction.guild is None:
            await interaction.response.send_message(
                "Cette action doit être utilisée sur un serveur.",
                ephemeral=True,
            )
            return

        if interaction.user.id != self.actor_id:
            await interaction.response.send_message(
                "Cette configuration appartient à un autre utilisateur.",
                ephemeral=True,
            )
            return

        emoji = self.emoji_input.value.strip() or None

        try:
            await self.coordinator.update_metadata(
                interaction.guild.id,
                self.policy,
                self.selection.catalog_key,
                self.selection.entry.role_id,
                label=self.label_input.value.strip(),
                description=self.description_input.value.strip(),
                emoji=emoji,
            )

        except Exception:
            await interaction.response.send_message(
                (
                    "Échec de l'enregistrement des métadonnées. "
                    "Aucune étape suivante n'a été ouverte."
                ),
                ephemeral=True,
            )
            return

        try:
            next_selection = await self.coordinator.get_next(
                interaction.guild.id,
                self.policy,
            )

        except Exception:
            await interaction.response.send_message(
                (
                    f"✅ `{self.selection.entry.role_name}` configuré.\n\n"
                    "Impossible de déterminer automatiquement l'entrée "
                    "suivante. Relance `/claviger catalog next`."
                ),
                ephemeral=True,
            )
            return

        if next_selection is None:
            await interaction.response.send_message(
                (
                    f"✅ `{self.selection.entry.role_name}` configuré.\n\n"
                    "Tous les catalogues disponibles sont configurés."
                ),
                ephemeral=True,
            )
            return

        # Local import avoids a circular dependency between the modal
        # and the view that can open another modal.
        from claviger.ui.catalog_next_view import CatalogNextView

        await interaction.response.send_message(
            f"✅ `{self.selection.entry.role_name}` configuré.",
            ephemeral=True,
            view=CatalogNextView(
                coordinator=self.coordinator,
                policy=self.policy,
                actor_id=self.actor_id,
            ),
        )
