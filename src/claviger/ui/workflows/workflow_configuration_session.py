from dataclasses import dataclass
from typing import Literal

from claviger.models.workflows.workflow_configuration_model import (
    WorkflowConfigurationDraft,
    WorkflowResourceSelection,
)
from claviger.models.workflows.workflow_structure_discovery_model import (
    WorkflowStructureCandidate,
    WorkflowStructureDiscoveryResult,
)

WorkflowUiResource = Literal[
    "category",
    "management_channel",
    "execution_channel",
    "primary_role",
]

WorkflowCandidateChannelResource = Literal[
    "management_channel",
    "execution_channel",
]


@dataclass(slots=True)
class WorkflowConfigurationSession:
    """Hold temporary Discord UI choices before backend configuration starts."""

    guild_id: int
    actor_id: int
    discovery: WorkflowStructureDiscoveryResult

    # The UI stores only the identity of the structural candidate selected by
    # the human. Candidate recognition itself belongs exclusively to discovery.
    selected_structure_category_id: int | None = None

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

    def select_structure_candidate(
        self,
        *,
        category_id: int,
    ) -> WorkflowStructureCandidate:
        """Apply one human-selected structural candidate to the UI session.

        Discovery already decided which categories satisfy the workflow
        structural contract. This method only records the user's selection.

        Unique protected or interactive channels are selected automatically
        because no ambiguity remains. Multiple candidates stay unresolved until
        the user explicitly chooses one through the UI.
        """

        candidate = next(
            (
                candidate
                for candidate in self.discovery.workflow_candidates
                if candidate.category.category_id == category_id
            ),
            None,
        )

        if candidate is None:
            raise ValueError("Selected workflow structure is not present in discovery.")

        self.selected_structure_category_id = category_id

        self.category = WorkflowResourceSelection(
            mode="existing",
            resource_id=candidate.category.category_id,
        )

        self.management_channel = (
            WorkflowResourceSelection(
                mode="existing",
                resource_id=candidate.protected_channels[0].channel_id,
            )
            if len(candidate.protected_channels) == 1
            else None
        )

        self.execution_channel = (
            WorkflowResourceSelection(
                mode="existing",
                resource_id=candidate.interactive_channels[0].channel_id,
            )
            if len(candidate.interactive_channels) == 1
            else None
        )

        return candidate

    def select_structure_channel(
        self,
        *,
        resource: WorkflowCandidateChannelResource,
        channel_id: int,
    ) -> None:
        """Record one explicit channel choice inside the selected structure."""

        candidate = self.get_selected_structure_candidate()

        if candidate is None:
            raise RuntimeError(
                "A workflow structure must be selected before choosing its channels."
            )

        if resource == "management_channel":
            allowed_channels = candidate.protected_channels

        elif resource == "execution_channel":
            allowed_channels = candidate.interactive_channels

        else:
            raise ValueError(
                f"Unsupported workflow structure channel resource: {resource!r}."
            )

        if not any(channel.channel_id == channel_id for channel in allowed_channels):
            raise ValueError(
                "Selected channel does not belong to the chosen workflow structure."
            )

        self.set_resource(
            resource,
            WorkflowResourceSelection(
                mode="existing",
                resource_id=channel_id,
            ),
        )

    def get_selected_structure_candidate(
        self,
    ) -> WorkflowStructureCandidate | None:
        """Return the structural candidate currently selected by the user."""

        category_id = self.selected_structure_category_id

        if category_id is None:
            return None

        return next(
            (
                candidate
                for candidate in self.discovery.workflow_candidates
                if candidate.category.category_id == category_id
            ),
            None,
        )

    def has_complete_selected_structure(
        self,
    ) -> bool:
        """Return whether a detected structure has all required channel choices."""

        return (
            self.get_selected_structure_candidate() is not None
            and self.category is not None
            and self.management_channel is not None
            and self.execution_channel is not None
        )

    def clear_selected_structure(
        self,
    ) -> None:
        """Leave structural discovery mode and return to manual configuration."""

        self.selected_structure_category_id = None
        self.category = None
        self.management_channel = None
        self.execution_channel = None

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
