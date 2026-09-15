from dataclasses import dataclass
from typing import Literal

from claviger.models.workflow_configuration_model import (
    WorkflowConfigurationDraft,
    WorkflowResourceSelection,
)
from claviger.models.workflow_structure_discovery_model import (
    WorkflowStructureDiscoveryResult,
)

WorkflowUiResource = Literal[
    "category",
    "management_channel",
    "execution_channel",
    "primary_role",
    "ai_preference_role",
]


@dataclass(slots=True)
class WorkflowConfigurationSession:
    """Hold temporary Discord UI choices before backend configuration starts."""

    guild_id: int
    actor_id: int
    discovery: WorkflowStructureDiscoveryResult
    persisted_ai_preference_role_id: int | None = None

    # Metadata is intentionally frontend-local until final confirmation.
    title: str | None = None
    description: str | None = None
    command_name: str | None = None
    command_description: str | None = None
    questionnaire_role_prefix: str | None = None

    # Discord resources remain expressed through the same frontend-neutral
    # existing/create contract used by the future Web interface.
    category: WorkflowResourceSelection | None = None
    management_channel: WorkflowResourceSelection | None = None
    execution_channel: WorkflowResourceSelection | None = None
    primary_role: WorkflowResourceSelection | None = None

    ai_enabled: bool = False
    ai_preference_role: WorkflowResourceSelection | None = None

    def set_resource(
        self,
        resource: WorkflowUiResource,
        selection: WorkflowResourceSelection,
    ) -> None:
        """Record one temporary resource choice without touching Discord."""

        setattr(
            self,
            resource,
            selection,
        )

    def get_resource(
        self,
        resource: WorkflowUiResource,
    ) -> WorkflowResourceSelection | None:
        """Return one temporary resource choice."""

        return getattr(
            self,
            resource,
        )

    def to_draft(
        self,
    ) -> WorkflowConfigurationDraft:
        """Build the frontend-neutral draft submitted to the backend coordinator."""

        if (
            self.title is None
            or self.command_name is None
            or self.questionnaire_role_prefix is None
        ):
            raise RuntimeError("Workflow metadata is incomplete.")

        if (
            self.category is None
            or self.management_channel is None
            or self.execution_channel is None
            or self.primary_role is None
        ):
            raise RuntimeError("Workflow Discord resource configuration is incomplete.")

        return WorkflowConfigurationDraft(
            guild_id=self.guild_id,
            # The stable workflow key is derived from the validated command name
            # for a newly configured workflow.
            workflow_key=None,
            title=self.title,
            description=self.description,
            command_name=self.command_name,
            command_description=self.command_description,
            category=self.category,
            management_channel=self.management_channel,
            execution_channel=self.execution_channel,
            primary_role=self.primary_role,
            questionnaire_role_prefix=self.questionnaire_role_prefix,
            ai_enabled=self.ai_enabled,
            ai_preference_role=self.ai_preference_role,
        )

    def describe_resource(
        self,
        resource: WorkflowUiResource,
    ) -> str:
        """Return one readable UI label without treating names as identity."""

        selection = self.get_resource(
            resource,
        )

        if selection is None:
            return "Non configuré"

        if selection.mode == "create":
            return f"Créer `{selection.name}`"

        resource_id = selection.resource_id

        if resource_id is None:
            return "Identité Discord invalide"

        name = self._find_existing_name(
            resource,
            resource_id=resource_id,
        )

        if name is None:
            return f"ID `{resource_id}`"

        return f"`{name}` (`{resource_id}`)"

    def describe_ai_preference_role(
        self,
    ) -> str:
        """Return the effective AI preference role displayed in the review UI."""

        if not self.ai_enabled:
            return "Désactivée"

        if self.persisted_ai_preference_role_id is not None:
            role_id = self.persisted_ai_preference_role_id

            role_name = self._find_role_name(
                role_id,
            )

            if role_name is not None:
                return f"Activée — rôle existant `{role_name}` (`{role_id}`)"

            return f"Activée — rôle existant `{role_id}`"

        if self.ai_preference_role is None:
            return "Activée — rôle non configuré"

        return f"Activée — {self.describe_resource('ai_preference_role')}"

    def _find_existing_name(
        self,
        resource: WorkflowUiResource,
        *,
        resource_id: int,
    ) -> str | None:
        """Resolve one cosmetic Discord name from the discovery snapshot."""

        if resource == "category":
            candidate = next(
                (
                    category
                    for category in self.discovery.categories
                    if category.category_id == resource_id
                ),
                None,
            )

            return candidate.category_name if candidate is not None else None

        if resource in {
            "management_channel",
            "execution_channel",
        }:
            candidate = next(
                (
                    channel
                    for channel in self.discovery.text_channels
                    if channel.channel_id == resource_id
                ),
                None,
            )

            return candidate.channel_name if candidate is not None else None

        return self._find_role_name(
            resource_id,
        )

    def _find_role_name(
        self,
        role_id: int,
    ) -> str | None:
        """Resolve one cosmetic role name from manageable discovery candidates."""

        candidate = next(
            (
                role
                for role in self.discovery.manageable_roles
                if role.role_id == role_id
            ),
            None,
        )

        return candidate.role_name if candidate is not None else None
