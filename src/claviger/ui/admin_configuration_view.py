import logging

import discord

from claviger.models.admin_configuration_reconciliation_model import (
    AdminConfigurationReconciliationDecision,
)
from claviger.models.admin_structure_discovery_model import (
    AdminCategoryCandidate,
    AdminChannelCandidate,
)
from claviger.services.admin_configuration_coordinator_service import (
    AdminConfigurationCoordinatorService,
)

logger = logging.getLogger(__name__)

MAX_SELECT_OPTIONS = 25


async def _reject_foreign_actor(
    interaction: discord.Interaction,
    *,
    actor_id: int,
    guild_id: int,
) -> bool:
    """Reject a component interaction that does not belong to the workflow owner."""

    if interaction.user.id != actor_id:
        await interaction.response.send_message(
            "Ce contrôle appartient à un autre utilisateur.",
            ephemeral=True,
        )
        return True

    if interaction.guild is None or interaction.guild.id != guild_id:
        await interaction.response.send_message(
            "Cette action doit être utilisée sur le serveur qui l'a créée.",
            ephemeral=True,
        )
        return True

    return False


def _build_channel_options(
    channels: tuple[AdminChannelCandidate, ...],
) -> list[discord.SelectOption]:
    """Build deterministic select options for one ADMIN channel type."""

    if not channels:
        raise ValueError("ADMIN routing requires at least one selectable channel.")

    if len(channels) > MAX_SELECT_OPTIONS:
        raise ValueError(
            "Discord select menus support at most 25 ADMIN channel choices."
        )

    return [
        discord.SelectOption(
            label=channel.channel_name,
            value=str(channel.channel_id),
            description=f"ID {channel.channel_id}",
        )
        for channel in channels
    ]


def _build_category_options(
    categories: tuple[AdminCategoryCandidate, ...],
) -> list[discord.SelectOption]:
    """Build deterministic select options for explicit ADMIN category choice."""

    if not categories:
        raise ValueError("No ADMIN category candidate is available for selection.")

    if len(categories) > MAX_SELECT_OPTIONS:
        raise ValueError(
            "Discord select menus support at most 25 ADMIN category choices."
        )

    return [
        discord.SelectOption(
            label=category.category_name,
            value=str(category.category_id),
            description=f"ID {category.category_id}",
        )
        for category in categories
    ]


class _RoutingSelect(discord.ui.Select):
    """Store one explicit routing choice on its parent view."""

    def __init__(
        self,
        *,
        placeholder: str,
        options: list[discord.SelectOption],
        target_attribute: str,
        row: int,
    ) -> None:
        super().__init__(
            placeholder=placeholder,
            min_values=1,
            max_values=1,
            options=options,
            row=row,
        )

        self.target_attribute = target_attribute

    async def callback(
        self,
        interaction: discord.Interaction,
    ) -> None:
        """Record the selected Discord channel ID without persisting yet."""

        view = self.view

        if not isinstance(
            view,
            AdminRoutingSelectionView,
        ):
            raise RuntimeError("ADMIN routing select is detached from its view.")

        if await _reject_foreign_actor(
            interaction,
            actor_id=view.actor_id,
            guild_id=view.guild_id,
        ):
            return

        setattr(
            view,
            self.target_attribute,
            int(self.values[0]),
        )

        await interaction.response.defer()


class _CategorySelect(discord.ui.Select):
    """Resolve one explicit ADMIN category before semantic routing."""

    def __init__(
        self,
        *,
        categories: tuple[AdminCategoryCandidate, ...],
    ) -> None:
        super().__init__(
            placeholder="Choisir la catégorie ADMIN",
            min_values=1,
            max_values=1,
            options=_build_category_options(
                categories,
            ),
        )

    async def callback(
        self,
        interaction: discord.Interaction,
    ) -> None:
        """Prepare the chosen category and continue to routing selection."""

        view = self.view

        if not isinstance(
            view,
            AdminCategorySelectionView,
        ):
            raise RuntimeError("ADMIN category select is detached from its view.")

        if await _reject_foreign_actor(
            interaction,
            actor_id=view.actor_id,
            guild_id=view.guild_id,
        ):
            return

        if interaction.guild is None:
            return

        category_id = int(
            self.values[0],
        )

        await interaction.response.defer()

        try:
            category = await view.coordinator.prepare_category(
                interaction.guild,
                category_id,
            )

            routing_view = AdminRoutingSelectionView(
                coordinator=view.coordinator,
                category=category,
                actor_id=view.actor_id,
                admin_command_name=view.admin_command_name,
            ).bind_guild(
                view.guild_id,
            )

        except Exception:
            logger.exception(
                "Unable to prepare explicitly selected ADMIN category %s for guild %s.",
                category_id,
                view.guild_id,
            )

            await interaction.edit_original_response(
                content=(
                    "❌ Impossible de préparer cette catégorie ADMIN. "
                    "Aucune configuration n'a été enregistrée."
                ),
                view=None,
            )
            return

        await interaction.edit_original_response(
            content=(
                f"**Catégorie ADMIN sélectionnée :** `{category.category_name}`\n\n"
                "Choisis explicitement le salon de commandes, le forum "
                "d'activité et le forum d'erreurs. Les noms ne sont jamais "
                "utilisés pour déduire automatiquement leur fonction."
            ),
            view=routing_view,
        )


class AdminRoutingSelectionView(discord.ui.View):
    """Collect explicit command/activity/error routing for one ADMIN category."""

    def __init__(
        self,
        *,
        coordinator: AdminConfigurationCoordinatorService,
        category: AdminCategoryCandidate,
        actor_id: int,
        admin_command_name: str,
    ) -> None:
        super().__init__(
            timeout=300,
        )

        self.coordinator = coordinator
        self.category = category
        self.actor_id = actor_id
        self.guild_id: int | None = None
        self.admin_command_name = admin_command_name

        self.command_channel_id: int | None = None
        self.activity_forum_id: int | None = None
        self.error_forum_id: int | None = None

        self.add_item(
            _RoutingSelect(
                placeholder="Salon des commandes administratives",
                options=_build_channel_options(
                    category.usable_text_channels,
                ),
                target_attribute="command_channel_id",
                row=0,
            )
        )

        forum_options = _build_channel_options(
            category.usable_forum_channels,
        )

        self.add_item(
            _RoutingSelect(
                placeholder="Forum des activités",
                options=forum_options,
                target_attribute="activity_forum_id",
                row=1,
            )
        )

        self.add_item(
            _RoutingSelect(
                placeholder="Forum des erreurs",
                options=_build_channel_options(
                    category.usable_forum_channels,
                ),
                target_attribute="error_forum_id",
                row=2,
            )
        )

    def bind_guild(
        self,
        guild_id: int,
    ) -> "AdminRoutingSelectionView":
        """Bind the view to the guild that owns the configuration workflow."""

        if guild_id <= 0:
            raise ValueError("Discord guild ID must be greater than zero.")

        self.guild_id = guild_id
        return self

    @discord.ui.button(
        label="Enregistrer la configuration",
        style=discord.ButtonStyle.success,
        row=3,
    )
    async def save_configuration(
        self,
        interaction: discord.Interaction,
        _: discord.ui.Button,
    ) -> None:
        """Validate the complete explicit routing and persist it atomically."""

        if self.guild_id is None:
            raise RuntimeError("ADMIN routing view is not bound to a guild.")

        if await _reject_foreign_actor(
            interaction,
            actor_id=self.actor_id,
            guild_id=self.guild_id,
        ):
            return

        if interaction.guild is None:
            return

        if (
            self.command_channel_id is None
            or self.activity_forum_id is None
            or self.error_forum_id is None
        ):
            await interaction.response.send_message(
                "Sélectionne les trois destinations avant d'enregistrer.",
                ephemeral=True,
            )
            return

        if self.activity_forum_id == self.error_forum_id:
            await interaction.response.send_message(
                "Le forum d'activité et le forum d'erreurs doivent être différents.",
                ephemeral=True,
            )
            return

        try:
            configuration = await self.coordinator.save_explicit_routing(
                interaction.guild,
                category_id=self.category.category_id,
                command_channel_id=self.command_channel_id,
                activity_forum_id=self.activity_forum_id,
                error_forum_id=self.error_forum_id,
            )

        except Exception:
            logger.exception(
                "Unable to persist explicit ADMIN routing for guild %s.",
                self.guild_id,
            )

            await interaction.response.send_message(
                (
                    "❌ Impossible d'enregistrer cette configuration ADMIN. "
                    "Discord a peut-être changé depuis l'ouverture du sélecteur."
                ),
                ephemeral=True,
            )
            return

        self.stop()

        await interaction.response.edit_message(
            content=(
                "✅ **Configuration ADMIN enregistrée.**\n\n"
                f"- Catégorie : `{configuration.category_id}`\n"
                f"- Commandes : <#{configuration.command_channel_id}>\n"
                f"- Activité : <#{configuration.activity_forum_id}>\n"
                f"- Erreurs : <#{configuration.error_forum_id}>\n\n"
                f"Utilise `/{self.admin_command_name} restart` pour reconstruire "
                "la surface de commandes de ce serveur."
            ),
            view=None,
        )


class AdminCategorySelectionView(discord.ui.View):
    """Require explicit category identity before routing an ambiguous ADMIN setup."""

    def __init__(
        self,
        *,
        coordinator: AdminConfigurationCoordinatorService,
        categories: tuple[AdminCategoryCandidate, ...],
        actor_id: int,
        guild_id: int,
        admin_command_name: str,
    ) -> None:
        super().__init__(
            timeout=300,
        )

        self.coordinator = coordinator
        self.actor_id = actor_id
        self.guild_id = guild_id
        self.admin_command_name = admin_command_name

        self.add_item(
            _CategorySelect(
                categories=categories,
            )
        )


class AdminConfigurationStartView(discord.ui.View):
    """Continue guild ADMIN configuration directly after DB maintenance."""

    def __init__(
        self,
        *,
        coordinator: AdminConfigurationCoordinatorService,
        actor_id: int,
        guild_id: int,
        admin_command_name: str,
    ) -> None:
        super().__init__(
            timeout=300,
        )

        self.coordinator = coordinator
        self.actor_id = actor_id
        self.guild_id = guild_id
        self.admin_command_name = admin_command_name

    @discord.ui.button(
        label="Configurer le serveur",
        style=discord.ButtonStyle.primary,
    )
    async def configure_server(
        self,
        interaction: discord.Interaction,
        _: discord.ui.Button,
    ) -> None:
        """Launch the normal config-server backend without an intermediate restart."""

        if await _reject_foreign_actor(
            interaction,
            actor_id=self.actor_id,
            guild_id=self.guild_id,
        ):
            return

        await interaction.response.defer(
            ephemeral=True,
        )

        await run_admin_configuration(
            interaction,
            coordinator=self.coordinator,
            admin_command_name=self.admin_command_name,
        )


async def _send_routing_prompt(
    interaction: discord.Interaction,
    *,
    coordinator: AdminConfigurationCoordinatorService,
    category_id: int,
    actor_id: int,
    admin_command_name: str,
) -> None:
    """Prepare one category and expose explicit semantic routing choices."""

    if interaction.guild is None:
        raise RuntimeError("ADMIN routing requires a guild interaction.")

    category = await coordinator.prepare_category(
        interaction.guild,
        category_id,
    )

    view = AdminRoutingSelectionView(
        coordinator=coordinator,
        category=category,
        actor_id=actor_id,
        admin_command_name=admin_command_name,
    ).bind_guild(
        interaction.guild.id,
    )

    await interaction.followup.send(
        (
            f"**Catégorie ADMIN :** `{category.category_name}`\n\n"
            "Choisis explicitement les trois destinations ci-dessous. "
            "Claviger ne déduit jamais leur fonction à partir de leur nom."
        ),
        ephemeral=True,
        view=view,
    )


async def run_admin_configuration(
    interaction: discord.Interaction,
    *,
    coordinator: AdminConfigurationCoordinatorService,
    admin_command_name: str,
) -> None:
    """Run the shared interactive ADMIN configuration flow for one guild."""

    guild = interaction.guild

    if guild is None:
        raise RuntimeError("Interactive ADMIN configuration requires a guild.")

    try:
        result = await coordinator.configure(
            guild,
        )

        decision = result.reconciliation.decision

        if decision == AdminConfigurationReconciliationDecision.KEEP:
            await interaction.followup.send(
                "Configuration du serveur valide. Aucun changement n'était nécessaire.",
                ephemeral=True,
            )
            return

        if decision == AdminConfigurationReconciliationDecision.CREATE:
            await interaction.followup.send(
                (
                    "✅ Configuration du serveur créée avec succès. "
                    "La structure ADMIN privée et son routage ont été enregistrés.\n\n"
                    f"Utilise `/{admin_command_name} restart` pour activer "
                    "la surface complète de commandes."
                ),
                ephemeral=True,
            )
            return

        if decision == AdminConfigurationReconciliationDecision.COMPLETE:
            if result.configuration_after is not None:
                message = (
                    "✅ La structure ADMIN a été réparée ou complétée. "
                    "Le routage persistant est maintenant exploitable."
                )

                if (
                    result.configuration_before is None
                    or not result.configuration_before.is_complete
                ):
                    message += (
                        "\n\n"
                        f"Utilise `/{admin_command_name} restart` pour activer "
                        "la surface complète de commandes."
                    )

                await interaction.followup.send(
                    message,
                    ephemeral=True,
                )
                return

            category_id = result.provisioning.category_id

            if category_id is None and result.reconciliation.category is not None:
                category_id = result.reconciliation.category.category_id

            if category_id is None:
                raise RuntimeError(
                    "COMPLETE ADMIN configuration did not identify a category."
                )

            await _send_routing_prompt(
                interaction,
                coordinator=coordinator,
                category_id=category_id,
                actor_id=interaction.user.id,
                admin_command_name=admin_command_name,
            )
            return

        if decision == AdminConfigurationReconciliationDecision.IMPORT:
            category = result.reconciliation.category

            if category is None:
                raise RuntimeError("IMPORT ADMIN configuration has no category.")

            await _send_routing_prompt(
                interaction,
                coordinator=coordinator,
                category_id=category.category_id,
                actor_id=interaction.user.id,
                admin_command_name=admin_command_name,
            )
            return

        if decision == AdminConfigurationReconciliationDecision.NEEDS_CHOICE:
            categories = await coordinator.discover_candidates(
                guild,
            )

            if not categories:
                raise RuntimeError(
                    "ADMIN configuration requires a choice but no category is available."
                )

            await interaction.followup.send(
                (
                    "Plusieurs structures ADMIN sont possibles, ou la structure "
                    "persistée ne correspond plus à Discord. Choisis explicitement "
                    "la catégorie à utiliser."
                ),
                ephemeral=True,
                view=AdminCategorySelectionView(
                    coordinator=coordinator,
                    categories=categories,
                    actor_id=interaction.user.id,
                    guild_id=guild.id,
                    admin_command_name=admin_command_name,
                ),
            )
            return

        raise RuntimeError(
            f"Unsupported ADMIN reconciliation decision: {decision!r}."
        )

    except Exception:
        logger.exception(
            "Interactive ADMIN configuration failed for guild %s.",
            guild.id,
        )

        await interaction.followup.send(
            (
                "❌ Échec de la configuration du serveur. "
                "Aucune déduction automatique supplémentaire n'a été faite."
            ),
            ephemeral=True,
        )
