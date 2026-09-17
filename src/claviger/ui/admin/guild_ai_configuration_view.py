import logging
from collections.abc import Awaitable, Callable

import discord

from claviger.models.runtime.guild_ai_configuration_model import (
    GuildAIConfigurationInspection,
    GuildAIConfigurationInspectionState,
)
from claviger.services.runtime.guild_ai_configuration_coordinator_service import (
    GuildAIConfigurationAfterRoleCreationError,
    GuildAIConfigurationCoordinatorService,
)
from claviger.services.runtime.guild_ai_configuration_service import (
    GuildAIConfigurationError,
)
from claviger.services.runtime.guild_ai_role_provisioning_service import (
    GuildAIRoleProvisioningError,
)

logger = logging.getLogger(__name__)

WorkflowContinuation = Callable[[discord.Interaction], Awaitable[None]]

_ROLE_CONFIGURATION_STATES = {
    GuildAIConfigurationInspectionState.ENABLED_ROLE_MISSING,
    GuildAIConfigurationInspectionState.ENABLED_ROLE_NOT_FOUND,
    GuildAIConfigurationInspectionState.ENABLED_ROLE_UNUSABLE,
}


async def _reject_foreign_actor(
    interaction: discord.Interaction,
    *,
    actor_id: int,
    guild_id: int,
) -> bool:
    """Reject a component interaction that does not own this configuration flow."""

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


def _role_configuration_content(
    inspection: GuildAIConfigurationInspection,
) -> str:
    """Translate one backend AI role state into a Discord repair prompt."""

    if inspection.state == GuildAIConfigurationInspectionState.ENABLED_ROLE_MISSING:
        issue = "L'IA est activée, mais aucun rôle IA n'est encore configuré."

    elif inspection.state == GuildAIConfigurationInspectionState.ENABLED_ROLE_NOT_FOUND:
        issue = "Le rôle IA enregistré n'existe plus sur ce serveur."

    elif inspection.state == GuildAIConfigurationInspectionState.ENABLED_ROLE_UNUSABLE:
        role_label = inspection.role_name or "le rôle enregistré"
        issue = (
            f"Le rôle IA `{role_label}` existe encore, mais Claviger ne peut "
            "plus le gérer en sécurité."
        )

    else:
        issue = "La configuration du rôle IA doit être réparée avant de continuer."

    return (
        f"**Configuration IA du serveur**\n\n{issue}\n\n"
        "Choisis un rôle existant que Claviger peut gérer, ou crée un nouveau rôle. "
        "Le backend revalidera toujours le choix avant de l'enregistrer."
    )


async def _continue_when_ready(
    interaction: discord.Interaction,
    *,
    inspection: GuildAIConfigurationInspection,
    continuation: WorkflowContinuation,
    success_content: str,
) -> None:
    """Finish the AI stage and continue only when backend readiness allows it."""

    if not inspection.is_ready_for_workflows:
        raise RuntimeError(
            "Guild AI configuration did not become ready after a successful mutation."
        )

    await interaction.edit_original_response(
        content=success_content,
        view=None,
    )

    await continuation(
        interaction,
    )


class GuildAIConfigurationChoiceView(discord.ui.View):
    """Collect the explicit guild-level choice to enable or disable AI access."""

    def __init__(
        self,
        *,
        coordinator: GuildAIConfigurationCoordinatorService,
        actor_id: int,
        guild_id: int,
        continuation: WorkflowContinuation,
    ) -> None:
        super().__init__(timeout=300)
        self.coordinator = coordinator
        self.actor_id = actor_id
        self.guild_id = guild_id
        self.continuation = continuation

    @discord.ui.button(
        label="Activer l'IA",
        style=discord.ButtonStyle.success,
    )
    async def enable_ai(
        self,
        interaction: discord.Interaction,
        _: discord.ui.Button,
    ) -> None:
        """Enable AI and either reuse a valid role or request role configuration."""

        if await _reject_foreign_actor(
            interaction,
            actor_id=self.actor_id,
            guild_id=self.guild_id,
        ):
            return

        if interaction.guild is None:
            return

        await interaction.response.defer()

        try:
            inspection = await self.coordinator.enable(
                interaction.guild,
            )

        except Exception:
            logger.exception(
                "Unable to enable guild AI configuration for guild %s.",
                self.guild_id,
            )
            await interaction.followup.send(
                "Impossible d'activer la configuration IA du serveur.",
                ephemeral=True,
            )
            return

        if inspection.is_ready_for_workflows:
            self.stop()
            await _continue_when_ready(
                interaction,
                inspection=inspection,
                continuation=self.continuation,
                success_content=(
                    "✅ **IA activée pour le serveur.**\n\n"
                    "Le rôle IA déjà enregistré est toujours valide. "
                    "La configuration des workflows peut continuer."
                ),
            )
            return

        if inspection.state in _ROLE_CONFIGURATION_STATES:
            await interaction.edit_original_response(
                content=_role_configuration_content(inspection),
                view=GuildAIRoleSelectionView(
                    coordinator=self.coordinator,
                    actor_id=self.actor_id,
                    guild_id=self.guild_id,
                    continuation=self.continuation,
                ),
            )
            return

        await interaction.edit_original_response(
            content=(
                "❌ L'IA a été activée, mais Claviger ne peut pas valider son rôle "
                "actuellement. Relance `config-server` après avoir vérifié les "
                "permissions du bot."
            ),
            view=None,
        )

    @discord.ui.button(
        label="Laisser l'IA désactivée",
        style=discord.ButtonStyle.secondary,
    )
    async def disable_ai(
        self,
        interaction: discord.Interaction,
        _: discord.ui.Button,
    ) -> None:
        """Persist the explicit opt-out and continue without using the AI role."""

        if await _reject_foreign_actor(
            interaction,
            actor_id=self.actor_id,
            guild_id=self.guild_id,
        ):
            return

        if interaction.guild is None:
            return

        await interaction.response.defer()

        try:
            inspection = await self.coordinator.disable(
                interaction.guild,
            )

        except Exception:
            logger.exception(
                "Unable to disable guild AI configuration for guild %s.",
                self.guild_id,
            )
            await interaction.followup.send(
                "Impossible d'enregistrer la désactivation de l'IA.",
                ephemeral=True,
            )
            return

        self.stop()

        await _continue_when_ready(
            interaction,
            inspection=inspection,
            continuation=self.continuation,
            success_content=(
                "✅ **IA désactivée pour le serveur.**\n\n"
                "Aucun rôle IA ne sera utilisé. La configuration des workflows "
                "peut continuer."
            ),
        )


class _GuildAIRoleSelect(discord.ui.RoleSelect):
    """Collect one existing Discord role without persisting on selection."""

    def __init__(self) -> None:
        super().__init__(
            placeholder="Choisir le rôle IA du serveur",
            min_values=1,
            max_values=1,
            row=0,
        )

    async def callback(
        self,
        interaction: discord.Interaction,
    ) -> None:
        """Store the selected role ID until explicit confirmation."""

        view = self.view

        if not isinstance(view, GuildAIRoleSelectionView):
            raise RuntimeError("Guild AI role select is detached from its view.")

        if await _reject_foreign_actor(
            interaction,
            actor_id=view.actor_id,
            guild_id=view.guild_id,
        ):
            return

        role = self.values[0]
        view.selected_role_id = role.id
        view.selected_role_name = role.name

        await interaction.response.defer()


class GuildAIRoleCreationModal(discord.ui.Modal, title="Créer le rôle IA"):
    """Collect the human-readable name of a new guild-wide AI role."""

    role_name = discord.ui.TextInput(
        label="Nom du rôle IA",
        placeholder="Accès IA",
        min_length=1,
        max_length=100,
    )

    def __init__(
        self,
        *,
        coordinator: GuildAIConfigurationCoordinatorService,
        actor_id: int,
        guild_id: int,
        continuation: WorkflowContinuation,
    ) -> None:
        super().__init__()
        self.coordinator = coordinator
        self.actor_id = actor_id
        self.guild_id = guild_id
        self.continuation = continuation

    async def on_submit(
        self,
        interaction: discord.Interaction,
    ) -> None:
        """Create, validate and persist the new AI role before continuing."""

        if await _reject_foreign_actor(
            interaction,
            actor_id=self.actor_id,
            guild_id=self.guild_id,
        ):
            return

        if interaction.guild is None:
            return

        await interaction.response.defer()

        try:
            inspection = await self.coordinator.create_and_assign_role(
                interaction.guild,
                str(self.role_name.value),
            )

        except GuildAIConfigurationAfterRoleCreationError as error:
            logger.exception(
                "AI role %s was created but could not be persisted for guild %s.",
                error.role_id,
                self.guild_id,
            )
            await interaction.followup.send(
                (
                    f"Le rôle <@&{error.role_id}> a été créé, mais son association "
                    "à la configuration IA n'a pas pu être enregistrée. "
                    "Aucune autre étape n'a été lancée."
                ),
                ephemeral=True,
            )
            return

        except (GuildAIRoleProvisioningError, GuildAIConfigurationError, ValueError) as error:
            await interaction.followup.send(
                f"Impossible de créer ce rôle IA : {error}",
                ephemeral=True,
            )
            return

        except Exception:
            logger.exception(
                "Unexpected AI role creation failure for guild %s.",
                self.guild_id,
            )
            await interaction.followup.send(
                "Impossible de créer et enregistrer le rôle IA.",
                ephemeral=True,
            )
            return

        await _continue_when_ready(
            interaction,
            inspection=inspection,
            continuation=self.continuation,
            success_content=(
                "✅ **Rôle IA créé et enregistré.**\n\n"
                f"Rôle : <@&{inspection.configuration.ai_role_id}>\n\n"
                "La configuration des workflows peut continuer."
            ),
        )


class GuildAIRoleSelectionView(discord.ui.View):
    """Select an existing AI role or request creation of a new one."""

    def __init__(
        self,
        *,
        coordinator: GuildAIConfigurationCoordinatorService,
        actor_id: int,
        guild_id: int,
        continuation: WorkflowContinuation,
    ) -> None:
        super().__init__(timeout=300)
        self.coordinator = coordinator
        self.actor_id = actor_id
        self.guild_id = guild_id
        self.continuation = continuation
        self.selected_role_id: int | None = None
        self.selected_role_name: str | None = None
        self.add_item(_GuildAIRoleSelect())

    @discord.ui.button(
        label="Utiliser ce rôle",
        style=discord.ButtonStyle.success,
        row=1,
    )
    async def confirm_existing_role(
        self,
        interaction: discord.Interaction,
        _: discord.ui.Button,
    ) -> None:
        """Revalidate and persist the explicitly selected existing role."""

        if await _reject_foreign_actor(
            interaction,
            actor_id=self.actor_id,
            guild_id=self.guild_id,
        ):
            return

        if interaction.guild is None:
            return

        if self.selected_role_id is None:
            await interaction.response.send_message(
                "Sélectionne d'abord un rôle IA.",
                ephemeral=True,
            )
            return

        await interaction.response.defer()

        try:
            inspection = await self.coordinator.assign_role(
                interaction.guild,
                self.selected_role_id,
            )

        except GuildAIConfigurationError as error:
            await interaction.followup.send(
                f"Ce rôle ne peut pas être utilisé : {error}",
                ephemeral=True,
            )
            return

        except Exception:
            logger.exception(
                "Unable to persist selected AI role %s for guild %s.",
                self.selected_role_id,
                self.guild_id,
            )
            await interaction.followup.send(
                "Impossible d'enregistrer ce rôle IA.",
                ephemeral=True,
            )
            return

        self.stop()

        role_label = self.selected_role_name or str(self.selected_role_id)

        await _continue_when_ready(
            interaction,
            inspection=inspection,
            continuation=self.continuation,
            success_content=(
                "✅ **Rôle IA enregistré.**\n\n"
                f"Rôle : `{role_label}` (<@&{self.selected_role_id}>)\n\n"
                "La configuration des workflows peut continuer."
            ),
        )

    @discord.ui.button(
        label="Créer un nouveau rôle",
        style=discord.ButtonStyle.primary,
        row=1,
    )
    async def create_role(
        self,
        interaction: discord.Interaction,
        _: discord.ui.Button,
    ) -> None:
        """Open the explicit role-creation modal without mutating yet."""

        if await _reject_foreign_actor(
            interaction,
            actor_id=self.actor_id,
            guild_id=self.guild_id,
        ):
            return

        await interaction.response.send_modal(
            GuildAIRoleCreationModal(
                coordinator=self.coordinator,
                actor_id=self.actor_id,
                guild_id=self.guild_id,
                continuation=self.continuation,
            )
        )


async def run_guild_ai_configuration(
    interaction: discord.Interaction,
    *,
    coordinator: GuildAIConfigurationCoordinatorService,
    continuation: WorkflowContinuation,
) -> bool:
    """Run the guild AI stage and report whether workflows may start immediately."""

    guild = interaction.guild

    if guild is None:
        raise RuntimeError("Interactive guild AI configuration requires a guild.")

    try:
        inspection = await coordinator.inspect(
            guild,
        )

    except Exception:
        logger.exception(
            "Unable to inspect guild AI configuration for guild %s.",
            guild.id,
        )
        await interaction.followup.send(
            "Impossible de vérifier la configuration IA du serveur.",
            ephemeral=True,
        )
        return False

    if inspection.is_ready_for_workflows:
        return True

    if inspection.state in {
        GuildAIConfigurationInspectionState.MISSING,
        GuildAIConfigurationInspectionState.UNCONFIGURED,
    }:
        await interaction.followup.send(
            (
                "**Configuration IA du serveur**\n\n"
                "Souhaites-tu activer les accès au contenu IA sur ce serveur ? "
                "Ce choix est global à la guild et sera partagé par les workflows."
            ),
            ephemeral=True,
            view=GuildAIConfigurationChoiceView(
                coordinator=coordinator,
                actor_id=interaction.user.id,
                guild_id=guild.id,
                continuation=continuation,
            ),
        )
        return False

    if inspection.state in _ROLE_CONFIGURATION_STATES:
        await interaction.followup.send(
            _role_configuration_content(inspection),
            ephemeral=True,
            view=GuildAIRoleSelectionView(
                coordinator=coordinator,
                actor_id=interaction.user.id,
                guild_id=guild.id,
                continuation=continuation,
            ),
        )
        return False

    await interaction.followup.send(
        (
            "❌ Claviger ne peut pas valider la configuration IA actuellement. "
            "Vérifie son état membre et ses permissions de rôles avant de relancer "
            "`config-server`."
        ),
        ephemeral=True,
    )
    return False
