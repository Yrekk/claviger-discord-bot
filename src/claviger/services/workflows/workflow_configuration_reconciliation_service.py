from dataclasses import replace

from claviger.models.workflow_configuration_model import (
    WorkflowConfigurationSpec,
    WorkflowResourceSelection,
)
from claviger.models.workflow_structure_discovery_model import (
    WorkflowCategoryCandidate,
    WorkflowRoleCandidate,
    WorkflowStructureDiscoveryResult,
    WorkflowTextChannelCandidate,
)


class WorkflowConfigurationReconciliationError(RuntimeError):
    """Base error raised when a valid draft cannot fit current Discord state."""


class WorkflowResourceUnavailableError(WorkflowConfigurationReconciliationError):
    """Raised when a selected Discord resource no longer exists or is unusable."""


class WorkflowMutationPermissionError(WorkflowConfigurationReconciliationError):
    """Raised when the requested configuration requires unavailable permissions."""


class WorkflowCategoryMismatchError(WorkflowConfigurationReconciliationError):
    """Raised when selected workflow channels do not belong to its category."""


class WorkflowAiPreferenceRoleRequiredError(WorkflowConfigurationReconciliationError):
    """Raised when enabling AI requires an explicit first capability role."""


class WorkflowAiPreferenceRoleConflictError(WorkflowConfigurationReconciliationError):
    """Raised when a frontend tries to replace the guild-wide AI role."""


class WorkflowRoleCollisionError(WorkflowConfigurationReconciliationError):
    """Raised when one role receives incompatible workflow semantics."""


class WorkflowConfigurationReconciliationService:
    """Reconcile one validated workflow specification with Discord discovery."""

    def reconcile(
        self,
        *,
        configuration: WorkflowConfigurationSpec,
        discovery: WorkflowStructureDiscoveryResult,
        persisted_ai_preference_role_id: int | None = None,
    ) -> WorkflowConfigurationSpec:
        """Return a Discord-compatible specification or reject it fail-closed."""

        category = self._reconcile_category(
            configuration.category,
            discovery=discovery,
        )

        selected_category_id = (
            category.resource_id if category.mode == "existing" else None
        )

        category_will_be_created = category.mode == "create"

        management_channel = self._reconcile_channel(
            configuration.management_channel,
            discovery=discovery,
            selected_category_id=selected_category_id,
            category_will_be_created=category_will_be_created,
            resource_label="management channel",
            require_private_writes=True,
        )

        execution_channel = self._reconcile_channel(
            configuration.execution_channel,
            discovery=discovery,
            selected_category_id=selected_category_id,
            category_will_be_created=category_will_be_created,
            resource_label="execution channel",
            require_private_writes=False,
        )

        primary_role = self._reconcile_role(
            configuration.primary_role,
            discovery=discovery,
            resource_label="primary role",
        )

        ai_preference_role = self._reconcile_ai_preference_role(
            configuration=configuration,
            discovery=discovery,
            persisted_ai_preference_role_id=(persisted_ai_preference_role_id),
        )

        self._reject_role_collision(
            primary_role=primary_role,
            ai_preference_role=ai_preference_role,
        )

        return replace(
            configuration,
            category=category,
            management_channel=management_channel,
            execution_channel=execution_channel,
            primary_role=primary_role,
            ai_preference_role=ai_preference_role,
        )

    def _reconcile_category(
        self,
        selection: WorkflowResourceSelection,
        *,
        discovery: WorkflowStructureDiscoveryResult,
    ) -> WorkflowResourceSelection:
        """Validate one existing-or-create workflow category choice."""

        if selection.mode == "create":
            self._require_channel_mutation_permission(
                discovery,
                resource_label="workflow category",
            )

            return selection

        category = self._find_category(
            discovery,
            category_id=selection.resource_id,
        )

        if category is None:
            raise WorkflowResourceUnavailableError(
                "Selected workflow category no longer exists."
            )

        # Lack of visibility is repairable only when Claviger can mutate channel
        # permissions. The provisioning layer performs that repair later.
        if not category.bot_can_view and not discovery.can_create_channels:
            raise WorkflowMutationPermissionError(
                "Claviger cannot access or repair the selected workflow category."
            )

        return selection

    def _reconcile_channel(
        self,
        selection: WorkflowResourceSelection,
        *,
        discovery: WorkflowStructureDiscoveryResult,
        selected_category_id: int | None,
        category_will_be_created: bool,
        resource_label: str,
        require_private_writes: bool,
    ) -> WorkflowResourceSelection:
        """Validate one workflow text-channel choice against its category."""

        if selection.mode == "create":
            self._require_channel_mutation_permission(
                discovery,
                resource_label=resource_label,
            )

            return selection

        if category_will_be_created:
            raise WorkflowCategoryMismatchError(
                f"Existing {resource_label} cannot belong to a category "
                "that has not been created yet."
            )

        channel = self._find_text_channel(
            discovery,
            channel_id=selection.resource_id,
        )

        if channel is None:
            raise WorkflowResourceUnavailableError(
                f"Selected {resource_label} no longer exists."
            )

        if channel.category_id != selected_category_id:
            raise WorkflowCategoryMismatchError(
                f"Selected {resource_label} does not belong to the "
                "selected workflow category."
            )

        requires_repair = (
            not channel.bot_can_view
            or not channel.bot_can_send
            or (require_private_writes and channel.everyone_can_send)
        )

        if requires_repair and not discovery.can_create_channels:
            raise WorkflowMutationPermissionError(
                f"Selected {resource_label} requires permission repair, "
                "but Claviger cannot manage channels."
            )

        return selection

    def _reconcile_role(
        self,
        selection: WorkflowResourceSelection,
        *,
        discovery: WorkflowStructureDiscoveryResult,
        resource_label: str,
    ) -> WorkflowResourceSelection:
        """Validate one existing-or-create manageable role choice."""

        if selection.mode == "create":
            if not discovery.can_create_roles:
                raise WorkflowMutationPermissionError(
                    f"Claviger cannot create the selected {resource_label}."
                )

            return selection

        role = self._find_role(
            discovery,
            role_id=selection.resource_id,
        )

        if role is None:
            raise WorkflowResourceUnavailableError(
                f"Selected {resource_label} is not manageable by Claviger."
            )

        return selection

    def _reconcile_ai_preference_role(
        self,
        *,
        configuration: WorkflowConfigurationSpec,
        discovery: WorkflowStructureDiscoveryResult,
        persisted_ai_preference_role_id: int | None,
    ) -> WorkflowResourceSelection | None:
        """Resolve the guild-wide AI capability role for one workflow."""

        if not configuration.ai_enabled:
            return None

        selected_role = configuration.ai_preference_role

        if persisted_ai_preference_role_id is not None:
            persisted_role = self._find_role(
                discovery,
                role_id=persisted_ai_preference_role_id,
            )

            if persisted_role is None:
                raise WorkflowResourceUnavailableError(
                    "The persisted AI preference role is no longer "
                    "manageable by Claviger."
                )

            if selected_role is not None:
                if (
                    selected_role.mode != "existing"
                    or selected_role.resource_id != persisted_ai_preference_role_id
                ):
                    raise WorkflowAiPreferenceRoleConflictError(
                        "This guild already uses another role for AI preference."
                    )

            # Frontends do not need to ask for the role again once the capability
            # has a stable guild-wide Discord identity.
            return WorkflowResourceSelection(
                mode="existing",
                resource_id=persisted_ai_preference_role_id,
            )

        if selected_role is None:
            raise WorkflowAiPreferenceRoleRequiredError(
                "Enabling AI for the first time requires an AI preference role."
            )

        return self._reconcile_role(
            selected_role,
            discovery=discovery,
            resource_label="AI preference role",
        )

    @staticmethod
    def _reject_role_collision(
        *,
        primary_role: WorkflowResourceSelection,
        ai_preference_role: WorkflowResourceSelection | None,
    ) -> None:
        """Keep membership and AI-preference semantics on distinct roles."""

        if ai_preference_role is None:
            return

        if (
            primary_role.mode == "existing"
            and ai_preference_role.mode == "existing"
            and primary_role.resource_id == ai_preference_role.resource_id
        ):
            raise WorkflowRoleCollisionError(
                "Primary role and AI preference role must be different."
            )

        if (
            primary_role.mode == "create"
            and ai_preference_role.mode == "create"
            and primary_role.name is not None
            and ai_preference_role.name is not None
            and primary_role.name.casefold() == ai_preference_role.name.casefold()
        ):
            raise WorkflowRoleCollisionError(
                "Primary role and AI preference role must use different names."
            )

    @staticmethod
    def _require_channel_mutation_permission(
        discovery: WorkflowStructureDiscoveryResult,
        *,
        resource_label: str,
    ) -> None:
        """Require Discord channel-management capability before mutation."""

        if discovery.can_create_channels:
            return

        raise WorkflowMutationPermissionError(
            f"Claviger cannot create or repair the selected {resource_label}."
        )

    @staticmethod
    def _find_category(
        discovery: WorkflowStructureDiscoveryResult,
        *,
        category_id: int | None,
    ) -> WorkflowCategoryCandidate | None:
        """Resolve one discovered category by stable Discord identity."""

        if category_id is None:
            return None

        return next(
            (
                category
                for category in discovery.categories
                if category.category_id == category_id
            ),
            None,
        )

    @staticmethod
    def _find_text_channel(
        discovery: WorkflowStructureDiscoveryResult,
        *,
        channel_id: int | None,
    ) -> WorkflowTextChannelCandidate | None:
        """Resolve one discovered text channel by stable Discord identity."""

        if channel_id is None:
            return None

        return next(
            (
                channel
                for channel in discovery.text_channels
                if channel.channel_id == channel_id
            ),
            None,
        )

    @staticmethod
    def _find_role(
        discovery: WorkflowStructureDiscoveryResult,
        *,
        role_id: int | None,
    ) -> WorkflowRoleCandidate | None:
        """Resolve one manageable role by stable Discord identity."""

        if role_id is None:
            return None

        return next(
            (role for role in discovery.manageable_roles if role.role_id == role_id),
            None,
        )
