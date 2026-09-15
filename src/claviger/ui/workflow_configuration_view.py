import logging

import discord

from claviger.models.workflow_configuration_model import (
    WorkflowResourceSelection,
)
from claviger.services.workflow_configuration_coordinator_service import (
    WorkflowConfigurationCoordinatorService,
)
from claviger.ui.workflow_configuration_session import (
    WorkflowConfigurationSession,
    WorkflowUiResource,
)

logger = logging.getLogger(__name__)


RESOURCE_LABELS: dict[
    WorkflowUiResource,
    str,
] = {
    "category": "catégorie du workflow",
    "management_channel": "salon de gestion",
    "execution_channel": "salon d'exécution",
    "primary_role": "rôle principal",
    "ai_preference_role": "rôle de préférence IA",
}


# ---------------------------------------------------------------------------
# Shared interaction safety
# ---------------------------------------------------------------------------


async def _reject_foreign_actor(
    interaction: discord.Interaction,
    *,
    session: WorkflowConfigurationSession,
) -> bool:
    """Reject interactions outside the user and guild owning this UI session."""

    if interaction.user.id != session.actor_id:
        await interaction.response.send_message(
            "Cette configuration appartient à un autre utilisateur.",
            ephemeral=True,
        )
        return True

    if interaction.guild is None or interaction.guild.id != session.guild_id:
        await interaction.response.send_message(
            "Cette configuration doit rester sur le serveur qui l'a créée.",
            ephemeral=True,
        )
        return True

    return False


def _optional_text(
    value: str,
) -> str | None:
    """Normalize one optional Discord modal text input."""

    normalized = value.strip()

    return normalized or None


# ---------------------------------------------------------------------------
# Workflow metadata modal
# ---------------------------------------------------------------------------


class WorkflowMetadataModal(discord.ui.Modal):
    """Collect workflow metadata before selecting Discord resources."""

    def __init__(
        self,
        *,
        coordinator: WorkflowConfigurationCoordinatorService,
        session: WorkflowConfigurationSession,
        admin_command_name: str,
    ) -> None:
        super().__init__(
            title="Configurer un workflow",
        )

        self.coordinator = coordinator
        self.session = session
        self.admin_command_name = admin_command_name

        self.title_input = discord.ui.TextInput(
            label="Nom du workflow",
            placeholder="Ex. Membres",
            required=True,
            max_length=100,
        )

        self.description_input = discord.ui.TextInput(
            label="Description",
            placeholder="Optionnelle",
            required=False,
            max_length=1000,
            style=discord.TextStyle.paragraph,
        )

        self.command_name_input = discord.ui.TextInput(
            label="Commande Discord",
            placeholder="Ex. membre",
            required=True,
            max_length=32,
        )

        self.command_description_input = discord.ui.TextInput(
            label="Description de la commande",
            placeholder="Optionnelle — générée automatiquement si vide",
            required=False,
            max_length=100,
        )

        self.role_prefix_input = discord.ui.TextInput(
            label="Préfixe des rôles questionnaire",
            placeholder="Ex. interest-",
            required=True,
            max_length=100,
        )

        self.add_item(
            self.title_input,
        )
        self.add_item(
            self.description_input,
        )
        self.add_item(
            self.command_name_input,
        )
        self.add_item(
            self.command_description_input,
        )
        self.add_item(
            self.role_prefix_input,
        )

    async def on_submit(
        self,
        interaction: discord.Interaction,
    ) -> None:
        """Store metadata locally and continue to structural configuration."""

        if await _reject_foreign_actor(
            interaction,
            session=self.session,
        ):
            return

        self.session.title = self.title_input.value.strip()
        self.session.description = _optional_text(
            self.description_input.value,
        )
        self.session.command_name = self.command_name_input.value.strip()
        self.session.command_description = _optional_text(
            self.command_description_input.value,
        )
        self.session.questionnaire_role_prefix = self.role_prefix_input.value.strip()

        await _edit_resource_step(
            interaction,
            coordinator=self.coordinator,
            session=self.session,
            resource="category",
            admin_command_name=self.admin_command_name,
        )


# ---------------------------------------------------------------------------
# Resource creation modal
# ---------------------------------------------------------------------------


class WorkflowResourceNameModal(discord.ui.Modal):
    """Collect the cosmetic name of one Discord resource to create."""

    def __init__(
        self,
        *,
        coordinator: WorkflowConfigurationCoordinatorService,
        session: WorkflowConfigurationSession,
        resource: WorkflowUiResource,
        admin_command_name: str,
    ) -> None:
        super().__init__(
            title=f"Créer : {RESOURCE_LABELS[resource]}"[:45],
        )

        self.coordinator = coordinator
        self.session = session
        self.resource = resource
        self.admin_command_name = admin_command_name

        self.name_input = discord.ui.TextInput(
            label="Nom",
            placeholder="Nom à créer sur Discord",
            required=True,
            max_length=100,
        )

        self.add_item(
            self.name_input,
        )

    async def on_submit(
        self,
        interaction: discord.Interaction,
    ) -> None:
        """Store one create selection and continue the wizard."""

        if await _reject_foreign_actor(
            interaction,
            session=self.session,
        ):
            return

        self.session.set_resource(
            self.resource,
            WorkflowResourceSelection(
                mode="create",
                name=self.name_input.value.strip(),
            ),
        )

        await _advance_after_resource(
            interaction,
            coordinator=self.coordinator,
            session=self.session,
            resource=self.resource,
            admin_command_name=self.admin_command_name,
        )


# ---------------------------------------------------------------------------
# Existing Discord resource selectors
# ---------------------------------------------------------------------------


class _ExistingChannelSelect(discord.ui.ChannelSelect):
    """Select one existing category or text channel by Discord identity."""

    def __init__(
        self,
        *,
        resource: WorkflowUiResource,
    ) -> None:
        if resource == "category":
            channel_types = [
                discord.ChannelType.category,
            ]
            placeholder = "Choisir une catégorie existante"

        else:
            channel_types = [
                discord.ChannelType.text,
            ]
            placeholder = "Choisir un salon texte existant"

        super().__init__(
            placeholder=placeholder,
            min_values=1,
            max_values=1,
            channel_types=channel_types,
        )

        self.resource = resource

    async def callback(
        self,
        interaction: discord.Interaction,
    ) -> None:
        """Validate the chosen Discord identity against discovery."""

        view = self.view

        if not isinstance(
            view,
            WorkflowExistingResourceView,
        ):
            raise RuntimeError("Workflow channel selector is detached from its view.")

        if await _reject_foreign_actor(
            interaction,
            session=view.session,
        ):
            return

        selected_id = self.values[0].id

        if self.resource == "category":
            candidate = next(
                (
                    category
                    for category in view.session.discovery.categories
                    if category.category_id == selected_id
                ),
                None,
            )

            if candidate is None:
                await interaction.response.send_message(
                    "Cette catégorie n'est plus disponible dans le snapshot.",
                    ephemeral=True,
                )
                return

        else:
            candidate = next(
                (
                    channel
                    for channel in view.session.discovery.text_channels
                    if channel.channel_id == selected_id
                ),
                None,
            )

            if candidate is None:
                await interaction.response.send_message(
                    "Ce salon texte n'est plus disponible dans le snapshot.",
                    ephemeral=True,
                )
                return

            category = view.session.category

            if (
                category is None
                or category.mode != "existing"
                or candidate.category_id != category.resource_id
            ):
                await interaction.response.send_message(
                    (
                        "Ce salon n'appartient pas à la catégorie sélectionnée "
                        "pour ce workflow."
                    ),
                    ephemeral=True,
                )
                return

        view.session.set_resource(
            self.resource,
            WorkflowResourceSelection(
                mode="existing",
                resource_id=selected_id,
            ),
        )

        await _advance_after_resource(
            interaction,
            coordinator=view.coordinator,
            session=view.session,
            resource=self.resource,
            admin_command_name=view.admin_command_name,
        )


class _ExistingRoleSelect(discord.ui.RoleSelect):
    """Select one existing role that discovery considers manageable."""

    def __init__(
        self,
        *,
        resource: WorkflowUiResource,
    ) -> None:
        super().__init__(
            placeholder="Choisir un rôle existant",
            min_values=1,
            max_values=1,
        )

        self.resource = resource

    async def callback(
        self,
        interaction: discord.Interaction,
    ) -> None:
        """Reject role choices outside Claviger's manageable hierarchy."""

        view = self.view

        if not isinstance(
            view,
            WorkflowExistingResourceView,
        ):
            raise RuntimeError("Workflow role selector is detached from its view.")

        if await _reject_foreign_actor(
            interaction,
            session=view.session,
        ):
            return

        selected_id = self.values[0].id

        candidate = next(
            (
                role
                for role in view.session.discovery.manageable_roles
                if role.role_id == selected_id
            ),
            None,
        )

        if candidate is None:
            await interaction.response.send_message(
                (
                    "Ce rôle n'est pas gérable par Claviger. "
                    "Vérifie la hiérarchie des rôles."
                ),
                ephemeral=True,
            )
            return

        view.session.set_resource(
            self.resource,
            WorkflowResourceSelection(
                mode="existing",
                resource_id=selected_id,
            ),
        )

        await _advance_after_resource(
            interaction,
            coordinator=view.coordinator,
            session=view.session,
            resource=self.resource,
            admin_command_name=view.admin_command_name,
        )


class WorkflowExistingResourceView(discord.ui.View):
    """Expose Discord-native selectors without a 25-option manual menu limit."""

    def __init__(
        self,
        *,
        coordinator: WorkflowConfigurationCoordinatorService,
        session: WorkflowConfigurationSession,
        resource: WorkflowUiResource,
        admin_command_name: str,
    ) -> None:
        super().__init__(
            timeout=300,
        )

        self.coordinator = coordinator
        self.session = session
        self.resource = resource
        self.admin_command_name = admin_command_name

        if resource in {
            "category",
            "management_channel",
            "execution_channel",
        }:
            self.add_item(
                _ExistingChannelSelect(
                    resource=resource,
                )
            )

        else:
            self.add_item(
                _ExistingRoleSelect(
                    resource=resource,
                )
            )


# ---------------------------------------------------------------------------
# Existing/create mode selection
# ---------------------------------------------------------------------------


class _ResourceModeButton(discord.ui.Button):
    """Choose whether one workflow resource is reused or created."""

    def __init__(
        self,
        *,
        mode: str,
        disabled: bool,
    ) -> None:
        if mode == "existing":
            label = "Utiliser l'existant"
            style = discord.ButtonStyle.secondary

        elif mode == "create":
            label = "Créer"
            style = discord.ButtonStyle.primary

        else:
            raise ValueError(f"Unsupported workflow resource mode: {mode!r}.")

        super().__init__(
            label=label,
            style=style,
            disabled=disabled,
        )

        self.mode = mode

    async def callback(
        self,
        interaction: discord.Interaction,
    ) -> None:
        """Open the appropriate existing-resource selector or creation modal."""

        view = self.view

        if not isinstance(
            view,
            WorkflowResourceModeView,
        ):
            raise RuntimeError("Workflow mode button is detached from its view.")

        if await _reject_foreign_actor(
            interaction,
            session=view.session,
        ):
            return

        if self.mode == "existing":
            await interaction.response.edit_message(
                content=(
                    f"**{RESOURCE_LABELS[view.resource].capitalize()}**\n\n"
                    "Choisis la ressource Discord à réutiliser."
                ),
                view=WorkflowExistingResourceView(
                    coordinator=view.coordinator,
                    session=view.session,
                    resource=view.resource,
                    admin_command_name=view.admin_command_name,
                ),
            )
            return

        await interaction.response.send_modal(
            WorkflowResourceNameModal(
                coordinator=view.coordinator,
                session=view.session,
                resource=view.resource,
                admin_command_name=view.admin_command_name,
            )
        )


class WorkflowResourceModeView(discord.ui.View):
    """Choose existing-or-create for one workflow Discord resource."""

    def __init__(
        self,
        *,
        coordinator: WorkflowConfigurationCoordinatorService,
        session: WorkflowConfigurationSession,
        resource: WorkflowUiResource,
        admin_command_name: str,
    ) -> None:
        super().__init__(
            timeout=300,
        )

        self.coordinator = coordinator
        self.session = session
        self.resource = resource
        self.admin_command_name = admin_command_name

        self.add_item(
            _ResourceModeButton(
                mode="existing",
                disabled=not self._can_reuse_existing(),
            )
        )

        self.add_item(
            _ResourceModeButton(
                mode="create",
                disabled=not self._can_create(),
            )
        )

    def _can_reuse_existing(
        self,
    ) -> bool:
        """Return whether discovery exposes at least one compatible resource."""

        discovery = self.session.discovery

        if self.resource == "category":
            return bool(
                discovery.categories,
            )

        if self.resource in {
            "management_channel",
            "execution_channel",
        }:
            category = self.session.category

            if (
                category is None
                or category.mode != "existing"
                or category.resource_id is None
            ):
                return False

            return any(
                channel.category_id == category.resource_id
                for channel in discovery.text_channels
            )

        return bool(
            discovery.manageable_roles,
        )

    def _can_create(
        self,
    ) -> bool:
        """Return whether Discord permissions allow this resource type creation."""

        if self.resource in {
            "category",
            "management_channel",
            "execution_channel",
        }:
            return self.session.discovery.can_create_channels

        return self.session.discovery.can_create_roles


# ---------------------------------------------------------------------------
# AI configuration
# ---------------------------------------------------------------------------


class _AiChoiceButton(discord.ui.Button):
    """Enable or disable the shared AI preference context for this workflow."""

    def __init__(
        self,
        *,
        enabled: bool,
    ) -> None:
        super().__init__(
            label=("Activer l'IA" if enabled else "Sans IA"),
            style=(
                discord.ButtonStyle.primary
                if enabled
                else discord.ButtonStyle.secondary
            ),
        )

        self.enabled_choice = enabled

    async def callback(
        self,
        interaction: discord.Interaction,
    ) -> None:
        """Apply the workflow-local AI choice and continue."""

        view = self.view

        if not isinstance(
            view,
            WorkflowAiChoiceView,
        ):
            raise RuntimeError("Workflow AI button is detached from its view.")

        if await _reject_foreign_actor(
            interaction,
            session=view.session,
        ):
            return

        view.session.ai_enabled = self.enabled_choice

        if not self.enabled_choice:
            view.session.ai_preference_role = None

            await _edit_review(
                interaction,
                coordinator=view.coordinator,
                session=view.session,
                admin_command_name=view.admin_command_name,
            )
            return

        if view.session.persisted_ai_preference_role_id is not None:
            # Reconciliation will inject the existing guild-wide role. The UI
            # deliberately does not create a second representation of it.
            view.session.ai_preference_role = None

            await _edit_review(
                interaction,
                coordinator=view.coordinator,
                session=view.session,
                admin_command_name=view.admin_command_name,
            )
            return

        await _edit_resource_step(
            interaction,
            coordinator=view.coordinator,
            session=view.session,
            resource="ai_preference_role",
            admin_command_name=view.admin_command_name,
        )


class WorkflowAiChoiceView(discord.ui.View):
    """Choose whether the workflow exposes the shared AI preference context."""

    def __init__(
        self,
        *,
        coordinator: WorkflowConfigurationCoordinatorService,
        session: WorkflowConfigurationSession,
        admin_command_name: str,
    ) -> None:
        super().__init__(
            timeout=300,
        )

        self.coordinator = coordinator
        self.session = session
        self.admin_command_name = admin_command_name

        self.add_item(
            _AiChoiceButton(
                enabled=False,
            )
        )

        self.add_item(
            _AiChoiceButton(
                enabled=True,
            )
        )


# ---------------------------------------------------------------------------
# Final review and backend handoff
# ---------------------------------------------------------------------------


class WorkflowConfigurationReviewView(discord.ui.View):
    """Require explicit confirmation before Discord or SQLite mutation begins."""

    def __init__(
        self,
        *,
        coordinator: WorkflowConfigurationCoordinatorService,
        session: WorkflowConfigurationSession,
        admin_command_name: str,
    ) -> None:
        super().__init__(
            timeout=300,
        )

        self.coordinator = coordinator
        self.session = session
        self.admin_command_name = admin_command_name

    @discord.ui.button(
        label="Créer / enregistrer le workflow",
        style=discord.ButtonStyle.success,
    )
    async def confirm(
        self,
        interaction: discord.Interaction,
        _: discord.ui.Button,
    ) -> None:
        """Submit the complete draft to the authoritative backend pipeline."""

        if await _reject_foreign_actor(
            interaction,
            session=self.session,
        ):
            return

        if interaction.guild is None:
            return

        await interaction.response.defer()

        try:
            result = await self.coordinator.configure(
                guild=interaction.guild,
                draft=self.session.to_draft(),
            )

        except Exception:
            logger.exception(
                "Interactive workflow configuration failed for guild %s.",
                self.session.guild_id,
            )

            await interaction.edit_original_response(
                content=(
                    "❌ La configuration du workflow a échoué.\n\n"
                    "Le backend a refusé ou interrompu l'opération. "
                    "Consulte les logs et les rapports avant de recommencer."
                ),
                view=None,
            )
            return

        configuration = result.configuration

        mutation_lines: list[str] = []

        if result.created_category_id is not None:
            mutation_lines.append(f"- Catégorie créée : `{result.created_category_id}`")

        mutation_lines.extend(
            f"- Salon créé : <#{channel_id}>"
            for channel_id in result.created_channel_ids
        )

        mutation_lines.extend(
            f"- Rôle créé : <@&{role_id}>" for role_id in result.created_role_ids
        )

        if result.category_permissions_repaired:
            mutation_lines.append("- Permissions de la catégorie réparées")

        mutation_lines.extend(
            f"- Permissions réparées : <#{channel_id}>"
            for channel_id in result.repaired_channel_ids
        )

        mutation_summary = (
            "\n".join(
                mutation_lines,
            )
            if mutation_lines
            else "- Aucune ressource Discord n'a dû être créée ou réparée"
        )

        await interaction.edit_original_response(
            content=(
                "✅ **Workflow configuré et enregistré.**\n\n"
                f"- Workflow : `{configuration.workflow_key}`\n"
                f"- Commande : `/{configuration.command_name}`\n"
                f"- Catégorie : `{configuration.category_id}`\n"
                f"- Gestion : <#{configuration.management_channel_id}>\n"
                f"- Exécution : <#{configuration.execution_channel_id}>\n"
                f"- Rôle principal : <@&{configuration.primary_role_id}>\n"
                f"- Préfixe questionnaire : "
                f"`{configuration.questionnaire_role_prefix}`\n"
                f"- IA : "
                f"{'activée' if configuration.ai_preference_role_id else 'désactivée'}"
                "\n\n"
                "**Mutations Discord**\n"
                f"{mutation_summary}\n\n"
                f"Utilise `/{self.admin_command_name} restart` "
                "pour reconstruire la surface de commandes."
            ),
            view=None,
        )


# ---------------------------------------------------------------------------
# Wizard navigation
# ---------------------------------------------------------------------------


async def _edit_resource_step(
    interaction: discord.Interaction,
    *,
    coordinator: WorkflowConfigurationCoordinatorService,
    session: WorkflowConfigurationSession,
    resource: WorkflowUiResource,
    admin_command_name: str,
) -> None:
    """Display existing-or-create choices for one workflow resource."""

    await interaction.response.edit_message(
        content=(
            f"**Configurer : {RESOURCE_LABELS[resource]}**\n\n"
            "Tu peux réutiliser une ressource compatible déjà présente "
            "sur le serveur ou demander à Claviger de la créer."
        ),
        view=WorkflowResourceModeView(
            coordinator=coordinator,
            session=session,
            resource=resource,
            admin_command_name=admin_command_name,
        ),
    )


async def _advance_after_resource(
    interaction: discord.Interaction,
    *,
    coordinator: WorkflowConfigurationCoordinatorService,
    session: WorkflowConfigurationSession,
    resource: WorkflowUiResource,
    admin_command_name: str,
) -> None:
    """Move to the next configuration stage after one resource choice."""

    next_resource: dict[
        WorkflowUiResource,
        WorkflowUiResource | None,
    ] = {
        "category": "management_channel",
        "management_channel": "execution_channel",
        "execution_channel": "primary_role",
        "primary_role": None,
        "ai_preference_role": None,
    }

    if resource == "primary_role":
        await interaction.response.edit_message(
            content=(
                "**Préférence IA**\n\n"
                "Choisis si ce workflow doit exposer la préférence IA. "
                "Si le serveur possède déjà le contexte `ai_preference`, "
                "son rôle sera automatiquement réutilisé."
            ),
            view=WorkflowAiChoiceView(
                coordinator=coordinator,
                session=session,
                admin_command_name=admin_command_name,
            ),
        )
        return

    if resource == "ai_preference_role":
        await _edit_review(
            interaction,
            coordinator=coordinator,
            session=session,
            admin_command_name=admin_command_name,
        )
        return

    target = next_resource[resource]

    if target is None:
        raise RuntimeError(f"No workflow configuration step follows {resource!r}.")

    await _edit_resource_step(
        interaction,
        coordinator=coordinator,
        session=session,
        resource=target,
        admin_command_name=admin_command_name,
    )


async def _edit_review(
    interaction: discord.Interaction,
    *,
    coordinator: WorkflowConfigurationCoordinatorService,
    session: WorkflowConfigurationSession,
    admin_command_name: str,
) -> None:
    """Display the complete human review before the first real mutation."""

    if (
        session.title is None
        or session.command_name is None
        or session.questionnaire_role_prefix is None
    ):
        raise RuntimeError("Workflow review requires complete metadata.")

    await interaction.response.edit_message(
        content=(
            "**Résumé du workflow**\n\n"
            f"- Nom : `{session.title}`\n"
            f"- Commande : `/{session.command_name}`\n"
            f"- Catégorie : {session.describe_resource('category')}\n"
            f"- Salon de gestion : "
            f"{session.describe_resource('management_channel')}\n"
            f"- Salon d'exécution : "
            f"{session.describe_resource('execution_channel')}\n"
            f"- Rôle principal : "
            f"{session.describe_resource('primary_role')}\n"
            f"- Préfixe questionnaire : "
            f"`{session.questionnaire_role_prefix}`\n"
            f"- IA : {session.describe_ai_preference_role()}\n\n"
            "**Aucune mutation Discord ou SQLite n'a encore eu lieu.**"
        ),
        view=WorkflowConfigurationReviewView(
            coordinator=coordinator,
            session=session,
            admin_command_name=admin_command_name,
        ),
    )


# ---------------------------------------------------------------------------
# Public workflow-configuration entry point
# ---------------------------------------------------------------------------


class WorkflowConfigurationStartView(discord.ui.View):
    """Start one workflow configuration session after discovery is complete."""

    def __init__(
        self,
        *,
        coordinator: WorkflowConfigurationCoordinatorService,
        session: WorkflowConfigurationSession,
        admin_command_name: str,
    ) -> None:
        super().__init__(
            timeout=300,
        )

        self.coordinator = coordinator
        self.session = session
        self.admin_command_name = admin_command_name

    @discord.ui.button(
        label="Créer / configurer un workflow",
        style=discord.ButtonStyle.primary,
    )
    async def start(
        self,
        interaction: discord.Interaction,
        _: discord.ui.Button,
    ) -> None:
        """Open metadata collection for this frontend session."""

        if await _reject_foreign_actor(
            interaction,
            session=self.session,
        ):
            return

        await interaction.response.send_modal(
            WorkflowMetadataModal(
                coordinator=self.coordinator,
                session=self.session,
                admin_command_name=self.admin_command_name,
            )
        )


async def run_workflow_configuration(
    interaction: discord.Interaction,
    *,
    coordinator: WorkflowConfigurationCoordinatorService,
    admin_command_name: str,
) -> None:
    """Open the Discord frontend over the shared workflow backend contract."""

    guild = interaction.guild

    if guild is None:
        raise RuntimeError("Interactive workflow configuration requires a guild.")

    try:
        discovery = await coordinator.discover_resources(
            guild,
        )

        ai_preference_role_id = await coordinator.get_ai_preference_role_id(
            guild.id,
        )

    except Exception:
        logger.exception(
            "Unable to prepare workflow configuration UI for guild %s.",
            guild.id,
        )

        await interaction.followup.send(
            (
                "❌ Impossible de préparer la configuration des workflows. "
                "Aucune ressource Discord n'a été modifiée."
            ),
            ephemeral=True,
        )
        return

    session = WorkflowConfigurationSession(
        guild_id=guild.id,
        actor_id=interaction.user.id,
        discovery=discovery,
        persisted_ai_preference_role_id=(ai_preference_role_id),
    )

    await interaction.followup.send(
        (
            "**Configuration des workflows**\n\n"
            "Claviger a analysé les catégories, salons texte et rôles "
            "actuellement disponibles. Tu peux maintenant créer un workflow "
            "en réutilisant l'existant ou en créant les ressources manquantes."
        ),
        ephemeral=True,
        view=WorkflowConfigurationStartView(
            coordinator=coordinator,
            session=session,
            admin_command_name=admin_command_name,
        ),
    )
