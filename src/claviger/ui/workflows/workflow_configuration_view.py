import logging

import discord

from claviger.models.workflows.workflow_configuration_model import (
    WorkflowResourceSelection,
)
from claviger.reporting.event import ReportEvent, ReportSeverity
from claviger.reporting.service import ReportService
from claviger.services.workflows.workflow_configuration_coordinator_service import (
    WorkflowConfigurationCoordinatorService,
)
from claviger.services.workflows.workflow_configuration_validation_service import (
    WorkflowConfigurationValidationError,
)
from claviger.ui.workflows.workflow_configuration_session import (
    WorkflowCandidateChannelResource,
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


def _normalize_command_name(
    value: str,
) -> str:
    """Normalize the slash users naturally type before backend validation."""

    normalized = value.strip()

    if normalized.startswith("/"):
        normalized = normalized[1:]

    return normalized


def _optional_text(
    value: str,
) -> str | None:
    """Normalize one optional Discord modal text input."""

    normalized = value.strip()

    return normalized or None


def _display_channel_names(
    channels: tuple,
) -> str:
    """Return readable channel names without exposing Discord identities."""

    if not channels:
        return "aucun"

    return ", ".join(f"`#{channel.channel_name}`" for channel in channels)


def _detected_structures_content(
    session: WorkflowConfigurationSession,
) -> str:
    """Render structural candidates already recognized by backend discovery."""

    candidates = session.discovery.workflow_candidates

    if not candidates:
        return (
            "**Configuration des workflows**\n\n"
            "Aucune structure de workflow compatible n'a été détectée.\n\n"
            "Tu peux créer un nouveau workflow et sélectionner ou créer "
            "ses ressources manuellement."
        )

    lines = [
        "**Structures de workflow détectées**",
        "",
        (
            "L'application a reconnu les structures ci-dessous uniquement "
            "à partir de leur organisation et de leurs permissions."
        ),
        "",
    ]

    visible_candidates = candidates[:10]

    for candidate in visible_candidates:
        lines.extend(
            [
                f"**{candidate.category.category_name}**",
                (
                    "- Salons protégés : "
                    f"{_display_channel_names(candidate.protected_channels)}"
                ),
                (
                    "- Salons interactifs : "
                    f"{_display_channel_names(candidate.interactive_channels)}"
                ),
            ]
        )

        if candidate.configured_command_names:
            commands = ", ".join(
                f"`/{command_name}`"
                for command_name in candidate.configured_command_names
            )
            lines.append(
                f"- Workflow(s) déjà configuré(s) : {commands}"
            )

        lines.append("")

    remaining = len(candidates) - len(visible_candidates)

    if remaining > 0:
        lines.extend(
            [
                f"*{remaining} autre(s) structure(s) compatible(s) détectée(s).*",
                "",
            ]
        )

    lines.append(
        "Choisis une structure détectée à réutiliser, "
        "ou crée un nouveau workflow manuellement."
    )

    return "\n".join(lines)


def _selected_structure_content(
    session: WorkflowConfigurationSession,
) -> str:
    """Render the structure selected by the human before metadata collection."""

    candidate = session.get_selected_structure_candidate()

    if candidate is None:
        raise RuntimeError("No workflow structure is currently selected.")

    return (
        "**Structure de workflow sélectionnée**\n\n"
        f"- Catégorie : **{candidate.category.category_name}**\n"
        "- Salons protégés : "
        f"{_display_channel_names(candidate.protected_channels)}\n"
        "- Salons interactifs : "
        f"{_display_channel_names(candidate.interactive_channels)}"
    )


def _structure_channel_choice_content(
    session: WorkflowConfigurationSession,
    *,
    resource: WorkflowCandidateChannelResource,
) -> str:
    """Explain one ambiguous channel choice without making it for the user."""

    candidate = session.get_selected_structure_candidate()

    if candidate is None:
        raise RuntimeError("No workflow structure is currently selected.")

    base = _selected_structure_content(
        session,
    )

    if resource == "management_channel":
        return (
            f"{base}\n\n"
            "**Choix nécessaire — salon de gestion / règles**\n\n"
            "Plusieurs salons protégés correspondent au pattern. "
            "Choisis celui qui doit servir de salon de gestion du workflow."
        )

    return (
        f"{base}\n\n"
        "**Choix nécessaire — salon d'exécution**\n\n"
        "Plusieurs salons interactifs correspondent au pattern. "
        "Choisis celui dans lequel la commande du workflow doit être utilisée."
    )


# ---------------------------------------------------------------------------
# Workflow metadata modal
# ---------------------------------------------------------------------------


class WorkflowMetadataModal(discord.ui.Modal):
    """Collect workflow metadata after structural selection when available."""

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
        """Store metadata locally and continue to remaining resource choices."""

        if await _reject_foreign_actor(
            interaction,
            session=self.session,
        ):
            return

        self.session.title = self.title_input.value.strip()
        self.session.description = _optional_text(
            self.description_input.value,
        )
        self.session.command_name = _normalize_command_name(
            self.command_name_input.value,
        )
        self.session.command_description = _optional_text(
            self.command_description_input.value,
        )
        self.session.questionnaire_role_prefix = self.role_prefix_input.value.strip()

        if self.session.selected_structure_category_id is not None:
            if not self.session.has_complete_selected_structure():
                raise RuntimeError(
                    "Selected workflow structure is incomplete before metadata."
                )

            # Category, management channel and execution channel already come
            # from the backend-recognized structure. Continue directly with the
            # first resource that discovery cannot infer: the primary role.
            await _edit_resource_step(
                interaction,
                coordinator=self.coordinator,
                session=self.session,
                resource="primary_role",
                admin_command_name=self.admin_command_name,
            )
            return

        # Manual workflow creation keeps the historical granular resource flow.
        await _edit_resource_step(
            interaction,
            coordinator=self.coordinator,
            session=self.session,
            resource="category",
            admin_command_name=self.admin_command_name,
        )


# ---------------------------------------------------------------------------
# Detected workflow structure selection
# ---------------------------------------------------------------------------


async def _open_metadata_modal(
    interaction: discord.Interaction,
    *,
    coordinator: WorkflowConfigurationCoordinatorService,
    session: WorkflowConfigurationSession,
    admin_command_name: str,
) -> None:
    """Open metadata collection after structural choices are complete."""

    if not session.has_complete_selected_structure():
        raise RuntimeError(
            "Workflow metadata cannot start from an incomplete detected structure."
        )

    await interaction.response.send_modal(
        WorkflowMetadataModal(
            coordinator=coordinator,
            session=session,
            admin_command_name=admin_command_name,
        )
    )


async def _continue_after_structure_selection(
    interaction: discord.Interaction,
    *,
    coordinator: WorkflowConfigurationCoordinatorService,
    session: WorkflowConfigurationSession,
    admin_command_name: str,
) -> None:
    """Request only unresolved structural choices before metadata collection."""

    if session.management_channel is None:
        await interaction.response.edit_message(
            content=_structure_channel_choice_content(
                session,
                resource="management_channel",
            ),
            view=WorkflowDetectedStructureChannelView(
                coordinator=coordinator,
                session=session,
                resource="management_channel",
                admin_command_name=admin_command_name,
            ),
        )
        return

    if session.execution_channel is None:
        await interaction.response.edit_message(
            content=_structure_channel_choice_content(
                session,
                resource="execution_channel",
            ),
            view=WorkflowDetectedStructureChannelView(
                coordinator=coordinator,
                session=session,
                resource="execution_channel",
                admin_command_name=admin_command_name,
            ),
        )
        return

    await _open_metadata_modal(
        interaction,
        coordinator=coordinator,
        session=session,
        admin_command_name=admin_command_name,
    )


async def _apply_detected_structure_choice(
    interaction: discord.Interaction,
    *,
    coordinator: WorkflowConfigurationCoordinatorService,
    session: WorkflowConfigurationSession,
    category_id: int,
    admin_command_name: str,
) -> None:
    """Apply one category already recognized as a structural workflow candidate."""

    try:
        session.select_structure_candidate(
            category_id=category_id,
        )

    except ValueError:
        await interaction.response.send_message(
            (
                "Cette catégorie ne fait pas partie des structures "
                "de workflow détectées."
            ),
            ephemeral=True,
        )
        return

    await _continue_after_structure_selection(
        interaction,
        coordinator=coordinator,
        session=session,
        admin_command_name=admin_command_name,
    )


class _DetectedStructureSelect(discord.ui.Select):
    """Select one exact backend-provided workflow structure."""

    def __init__(
        self,
        *,
        session: WorkflowConfigurationSession,
    ) -> None:
        options = []

        for candidate in session.discovery.workflow_candidates:
            description = (
                f"{len(candidate.protected_channels)} protégé(s) • "
                f"{len(candidate.interactive_channels)} interactif(s)"
            )

            if len(candidate.configured_command_names) == 1:
                description += (
                    " • "
                    f"/{candidate.configured_command_names[0]} déjà configuré"
                )
            elif candidate.configured_command_names:
                description += (
                    " • "
                    f"{len(candidate.configured_command_names)} workflows déjà configurés"
                )

            options.append(
                discord.SelectOption(
                    label=candidate.category.category_name[:100],
                    value=str(candidate.category.category_id),
                    description=description[:100],
                )
            )

        super().__init__(
            placeholder="Choisir une structure détectée",
            min_values=1,
            max_values=1,
            options=options,
        )

    async def callback(
        self,
        interaction: discord.Interaction,
    ) -> None:
        """Forward an exact discovery candidate to the session."""

        view = self.view

        if not isinstance(
            view,
            WorkflowDetectedStructureView,
        ):
            raise RuntimeError("Workflow structure selector is detached from its view.")

        if await _reject_foreign_actor(
            interaction,
            session=view.session,
        ):
            return

        await _apply_detected_structure_choice(
            interaction,
            coordinator=view.coordinator,
            session=view.session,
            category_id=int(self.values[0]),
            admin_command_name=view.admin_command_name,
        )


class _DetectedStructureCategorySelect(discord.ui.ChannelSelect):
    """Fallback category selector when more than 25 structures are discovered."""

    def __init__(
        self,
    ) -> None:
        super().__init__(
            placeholder="Choisir une catégorie détectée",
            min_values=1,
            max_values=1,
            channel_types=[
                discord.ChannelType.category,
            ],
        )

    async def callback(
        self,
        interaction: discord.Interaction,
    ) -> None:
        """Validate the native Discord category against backend discovery."""

        view = self.view

        if not isinstance(
            view,
            WorkflowDetectedStructureView,
        ):
            raise RuntimeError(
                "Workflow structure category selector is detached from its view."
            )

        if await _reject_foreign_actor(
            interaction,
            session=view.session,
        ):
            return

        await _apply_detected_structure_choice(
            interaction,
            coordinator=view.coordinator,
            session=view.session,
            category_id=self.values[0].id,
            admin_command_name=view.admin_command_name,
        )


class WorkflowDetectedStructureView(discord.ui.View):
    """Present structural candidates already recognized by backend discovery."""

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

        if len(session.discovery.workflow_candidates) <= 25:
            self.add_item(
                _DetectedStructureSelect(
                    session=session,
                )
            )

        else:
            # Discord string selects are limited to 25 options. The native
            # category selector remains scalable; its callback still validates
            # the chosen ID against backend discovery before accepting it.
            self.add_item(_DetectedStructureCategorySelect())

    @discord.ui.button(
        label="Créer un nouveau workflow",
        style=discord.ButtonStyle.secondary,
        row=1,
    )
    async def create_new(
        self,
        interaction: discord.Interaction,
        _: discord.ui.Button,
    ) -> None:
        """Leave detected-structure reuse and start the manual creation path."""

        if await _reject_foreign_actor(
            interaction,
            session=self.session,
        ):
            return

        self.session.clear_selected_structure()

        await interaction.response.send_modal(
            WorkflowMetadataModal(
                coordinator=self.coordinator,
                session=self.session,
                admin_command_name=self.admin_command_name,
            )
        )


def _structure_channels_for_resource(
    session: WorkflowConfigurationSession,
    *,
    resource: WorkflowCandidateChannelResource,
) -> tuple:
    """Return channels exposed by discovery for one structural UI choice."""

    candidate = session.get_selected_structure_candidate()

    if candidate is None:
        raise RuntimeError("No workflow structure is currently selected.")

    if resource == "management_channel":
        return candidate.protected_channels

    return candidate.interactive_channels


async def _apply_detected_structure_channel_choice(
    interaction: discord.Interaction,
    *,
    coordinator: WorkflowConfigurationCoordinatorService,
    session: WorkflowConfigurationSession,
    resource: WorkflowCandidateChannelResource,
    channel_id: int,
    admin_command_name: str,
) -> None:
    """Store one human choice among backend-provided structural channels."""

    try:
        session.select_structure_channel(
            resource=resource,
            channel_id=channel_id,
        )

    except (RuntimeError, ValueError):
        await interaction.response.send_message(
            (
                "Ce salon ne fait pas partie des choix compatibles "
                "fournis par la structure sélectionnée."
            ),
            ephemeral=True,
        )
        return

    await _continue_after_structure_selection(
        interaction,
        coordinator=coordinator,
        session=session,
        admin_command_name=admin_command_name,
    )


class _DetectedStructureChannelSelect(discord.ui.Select):
    """Select one exact channel from a backend-recognized structure."""

    def __init__(
        self,
        *,
        session: WorkflowConfigurationSession,
        resource: WorkflowCandidateChannelResource,
    ) -> None:
        channels = _structure_channels_for_resource(
            session,
            resource=resource,
        )

        if resource == "management_channel":
            placeholder = "Choisir le salon de gestion / règles"
        else:
            placeholder = "Choisir le salon d'exécution"

        options = [
            discord.SelectOption(
                label=f"#{channel.channel_name}"[:100],
                value=str(channel.channel_id),
            )
            for channel in channels
        ]

        super().__init__(
            placeholder=placeholder,
            min_values=1,
            max_values=1,
            options=options,
        )

        self.resource = resource

    async def callback(
        self,
        interaction: discord.Interaction,
    ) -> None:
        """Forward one exact structural channel choice to the session."""

        view = self.view

        if not isinstance(
            view,
            WorkflowDetectedStructureChannelView,
        ):
            raise RuntimeError(
                "Workflow structure channel selector is detached from its view."
            )

        if await _reject_foreign_actor(
            interaction,
            session=view.session,
        ):
            return

        await _apply_detected_structure_channel_choice(
            interaction,
            coordinator=view.coordinator,
            session=view.session,
            resource=self.resource,
            channel_id=int(self.values[0]),
            admin_command_name=view.admin_command_name,
        )


class _DetectedStructureNativeChannelSelect(discord.ui.ChannelSelect):
    """Fallback native selector for more than 25 compatible channels."""

    def __init__(
        self,
        *,
        resource: WorkflowCandidateChannelResource,
    ) -> None:
        if resource == "management_channel":
            placeholder = "Choisir le salon de gestion / règles"
        else:
            placeholder = "Choisir le salon d'exécution"

        super().__init__(
            placeholder=placeholder,
            min_values=1,
            max_values=1,
            channel_types=[
                discord.ChannelType.text,
            ],
        )

        self.resource = resource

    async def callback(
        self,
        interaction: discord.Interaction,
    ) -> None:
        """Validate one native Discord selection against the candidate channels."""

        view = self.view

        if not isinstance(
            view,
            WorkflowDetectedStructureChannelView,
        ):
            raise RuntimeError(
                "Workflow native structure selector is detached from its view."
            )

        if await _reject_foreign_actor(
            interaction,
            session=view.session,
        ):
            return

        await _apply_detected_structure_channel_choice(
            interaction,
            coordinator=view.coordinator,
            session=view.session,
            resource=self.resource,
            channel_id=self.values[0].id,
            admin_command_name=view.admin_command_name,
        )


class WorkflowDetectedStructureChannelView(discord.ui.View):
    """Collect one unresolved channel role inside a detected structure."""

    def __init__(
        self,
        *,
        coordinator: WorkflowConfigurationCoordinatorService,
        session: WorkflowConfigurationSession,
        resource: WorkflowCandidateChannelResource,
        admin_command_name: str,
    ) -> None:
        super().__init__(
            timeout=300,
        )

        self.coordinator = coordinator
        self.session = session
        self.resource = resource
        self.admin_command_name = admin_command_name

        channels = _structure_channels_for_resource(
            session,
            resource=resource,
        )

        if len(channels) <= 25:
            self.add_item(
                _DetectedStructureChannelSelect(
                    session=session,
                    resource=resource,
                )
            )

        else:
            self.add_item(
                _DetectedStructureNativeChannelSelect(
                    resource=resource,
                )
            )

    @discord.ui.button(
        label="Créer plutôt un nouveau workflow",
        style=discord.ButtonStyle.secondary,
        row=1,
    )
    async def create_new(
        self,
        interaction: discord.Interaction,
        _: discord.ui.Button,
    ) -> None:
        """Abandon structural reuse without mutating Discord."""

        if await _reject_foreign_actor(
            interaction,
            session=self.session,
        ):
            return

        self.session.clear_selected_structure()

        await interaction.response.send_modal(
            WorkflowMetadataModal(
                coordinator=self.coordinator,
                session=self.session,
                admin_command_name=self.admin_command_name,
            )
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

        selected_id = int(
            self.values[0],
        )

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


class _ExistingRoleSelect(discord.ui.Select):
    """Select one role from the backend-filtered workflow candidate list."""

    def __init__(
        self,
        *,
        resource: WorkflowUiResource,
        session: WorkflowConfigurationSession,
    ) -> None:
        roles = session.discovery.manageable_roles[:25]

        super().__init__(
            placeholder="Choisir un rôle existant",
            min_values=1,
            max_values=1,
            options=[
                discord.SelectOption(
                    label=role.role_name[:100],
                    value=str(role.role_id),
                )
                for role in roles
            ],
        )

        self.resource = resource

    async def callback(
        self,
        interaction: discord.Interaction,
    ) -> None:
        """Reject role choices outside the application's manageable hierarchy."""

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

        try:
            selected_id = int(
                self.values[0],
            )
        except (TypeError, ValueError):
            await interaction.response.send_message(
                "La sélection de rôle reçue est invalide.",
                ephemeral=True,
            )
            return

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
                    "Ce rôle n'est pas gérable par l'application. "
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
    """Expose selectors built from the backend-approved resource snapshot."""

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
                    session=session,
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
# Final review and backend handoff
# ---------------------------------------------------------------------------


async def _emit_workflow_configuration_failed(
    interaction: discord.Interaction,
    *,
    session: WorkflowConfigurationSession,
    error: Exception,
) -> None:
    """Emit one genuine backend failure through the configured report pipeline."""

    report_service = session.report_service
    guild = interaction.guild

    if report_service is None or guild is None:
        return

    await report_service.emit(
        ReportEvent(
            event_type="workflow.configuration.failed",
            severity=ReportSeverity.ERROR,
            title="Échec de configuration d'un workflow",
            summary=(
                "Claviger n'a pas pu enregistrer ou provisionner le workflow."
            ),
            details=f"{type(error).__name__}: {error}",
            guild_id=guild.id,
            guild_label=guild.name,
            actor_id=interaction.user.id,
            actor_label=interaction.user.display_name,
        )
    )


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

        except WorkflowConfigurationValidationError as error:
            logger.info(
                "Workflow configuration rejected by validation for guild %s: %s",
                self.session.guild_id,
                error,
            )

            await interaction.edit_original_response(
                content=(
                    "❌ La configuration contient une valeur invalide.\n\n"
                    f"{error}"
                ),
                view=None,
            )
            return

        except Exception as error:
            logger.exception(
                "Interactive workflow configuration failed for guild %s.",
                self.session.guild_id,
            )

            await _emit_workflow_configuration_failed(
                interaction,
                session=self.session,
                error=error,
            )

            await interaction.edit_original_response(
                content=(
                    "❌ La configuration du workflow a échoué.\n\n"
                    "Un incident backend a été signalé dans le reporting ADMIN."
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
                f"`{configuration.questionnaire_role_prefix}`\n\n"
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
            "sur le serveur ou demander à l'application de la créer."
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
    }

    if resource == "primary_role":
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
            f"`{session.questionnaire_role_prefix}`\n\n"
            "**Aucune mutation Discord ou SQLite n'a encore eu lieu.**"
        ),
        view=WorkflowConfigurationReviewView(
            coordinator=coordinator,
            session=session,
            admin_command_name=admin_command_name,
        ),
    )


# ---------------------------------------------------------------------------
# Manual workflow configuration entry point
# ---------------------------------------------------------------------------


class WorkflowConfigurationStartView(discord.ui.View):
    """Start manual workflow configuration when no structure is reused."""

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
        label="Créer un nouveau workflow",
        style=discord.ButtonStyle.primary,
    )
    async def start(
        self,
        interaction: discord.Interaction,
        _: discord.ui.Button,
    ) -> None:
        """Open metadata collection for one manual workflow session."""

        if await _reject_foreign_actor(
            interaction,
            session=self.session,
        ):
            return

        self.session.clear_selected_structure()

        await interaction.response.send_modal(
            WorkflowMetadataModal(
                coordinator=self.coordinator,
                session=self.session,
                admin_command_name=self.admin_command_name,
            )
        )


# ---------------------------------------------------------------------------
# Public workflow-configuration entry point
# ---------------------------------------------------------------------------


async def run_workflow_configuration(
    interaction: discord.Interaction,
    *,
    coordinator: WorkflowConfigurationCoordinatorService,
    admin_command_name: str,
    report_service: ReportService | None = None,
) -> None:
    """Open the Discord frontend over the shared workflow backend contract."""

    guild = interaction.guild

    if guild is None:
        raise RuntimeError("Interactive workflow configuration requires a guild.")

    try:
        discovery = await coordinator.discover_resources(
            guild,
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
        report_service=report_service,
    )

    if discovery.workflow_candidates:
        await interaction.followup.send(
            _detected_structures_content(
                session,
            ),
            ephemeral=True,
            view=WorkflowDetectedStructureView(
                coordinator=coordinator,
                session=session,
                admin_command_name=admin_command_name,
            ),
        )
        return

    await interaction.followup.send(
        _detected_structures_content(
            session,
        ),
        ephemeral=True,
        view=WorkflowConfigurationStartView(
            coordinator=coordinator,
            session=session,
            admin_command_name=admin_command_name,
        ),
    )
