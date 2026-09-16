from claviger.models.admin_configuration_reconciliation_model import (
    AdminConfigurationReconciliationDecision,
    AdminConfigurationReconciliationResult,
)
from claviger.models.admin_structure_discovery_model import (
    AdminCategoryCandidate,
    AdminChannelCandidate,
    AdminChannelType,
    AdminStructureDiscoveryResult,
)
from claviger.models.guild_admin_configuration_model import (
    GuildAdminConfiguration,
)


class AdminConfigurationReconciliationService:
    """Compare persisted ADMIN configuration with observed Discord state."""

    def reconcile(
        self,
        *,
        discovery: AdminStructureDiscoveryResult,
        configuration: GuildAdminConfiguration | None,
    ) -> AdminConfigurationReconciliationResult:
        """Return the next safe administrative configuration action."""

        if configuration is None:
            return self._reconcile_without_configuration(
                discovery,
            )

        return self._reconcile_existing_configuration(
            discovery=discovery,
            configuration=configuration,
        )

    def _reconcile_without_configuration(
        self,
        discovery: AdminStructureDiscoveryResult,
    ) -> AdminConfigurationReconciliationResult:
        """Reconcile Discord when no ADMIN configuration exists in SQLite."""

        if not discovery.categories:
            return AdminConfigurationReconciliationResult(
                decision=AdminConfigurationReconciliationDecision.CREATE,
                category=None,
            )

        if discovery.is_ambiguous:
            return AdminConfigurationReconciliationResult(
                decision=(AdminConfigurationReconciliationDecision.NEEDS_CHOICE),
                category=None,
                issues=(
                    (
                        "Several administrative categories were discovered "
                        "and no persisted configuration identifies one."
                    ),
                ),
            )

        category = discovery.single_candidate

        if category is None:
            raise RuntimeError(
                "Unambiguous admin discovery did not provide a category."
            )

        issues = self._get_candidate_issues(
            category,
        )

        if issues:
            return AdminConfigurationReconciliationResult(
                decision=AdminConfigurationReconciliationDecision.COMPLETE,
                category=category,
                issues=issues,
            )

        return AdminConfigurationReconciliationResult(
            decision=AdminConfigurationReconciliationDecision.IMPORT,
            category=category,
        )

    def _reconcile_existing_configuration(
        self,
        *,
        discovery: AdminStructureDiscoveryResult,
        configuration: GuildAdminConfiguration,
    ) -> AdminConfigurationReconciliationResult:
        """Validate one persisted configuration against Discord reality."""

        category = self._find_category(
            discovery,
            category_id=configuration.category_id,
        )

        if category is None:
            missing_issue = (
                "The configured administrative category "
                f"{configuration.category_id} no longer exists in discovery."
            )

            if not discovery.categories:
                return AdminConfigurationReconciliationResult(
                    decision=AdminConfigurationReconciliationDecision.CREATE,
                    category=None,
                    issues=(missing_issue,),
                )

            return AdminConfigurationReconciliationResult(
                decision=(AdminConfigurationReconciliationDecision.NEEDS_CHOICE),
                category=None,
                issues=(
                    missing_issue,
                    (
                        "Other administrative category candidates exist, "
                        "so Claviger will not replace the persisted category "
                        "automatically."
                    ),
                ),
            )

        issues = self._get_configuration_issues(
            category=category,
            configuration=configuration,
        )

        if issues:
            return AdminConfigurationReconciliationResult(
                decision=AdminConfigurationReconciliationDecision.COMPLETE,
                category=category,
                issues=issues,
            )

        return AdminConfigurationReconciliationResult(
            decision=AdminConfigurationReconciliationDecision.KEEP,
            category=category,
        )

    def _get_candidate_issues(
        self,
        category: AdminCategoryCandidate,
    ) -> tuple[str, ...]:
        """Describe why an unconfigured Discord category is not ready."""

        issues: list[str] = []

        if not category.is_private:
            issues.append(
                "The administrative category is visible to @everyone "
                "or contains a publicly visible child."
            )

        if not category.bot_can_view:
            issues.append("Claviger cannot view the administrative category.")

        if not category.text_channels:
            issues.append("No text channel is available for administrative commands.")

        if len(category.forum_channels) < 2:
            issues.append(
                "At least two forums are required for activity and error reports."
            )

        if not category.usable_text_channels:
            issues.append(
                "Claviger cannot use any discovered administrative text channel."
            )

        if len(category.usable_forum_channels) < 2:
            issues.append("Claviger cannot use at least two administrative forums.")

        return tuple(
            issues,
        )

    def _get_configuration_issues(
        self,
        *,
        category: AdminCategoryCandidate,
        configuration: GuildAdminConfiguration,
    ) -> tuple[str, ...]:
        """Validate configured Discord IDs against the observed category."""

        issues: list[str] = []

        if not category.is_private:
            issues.append(
                "The configured administrative category is not fully private."
            )

        if not category.bot_can_view:
            issues.append(
                "Claviger cannot view the configured administrative category."
            )

        issues.extend(
            self._validate_configured_channel(
                category=category,
                channel_id=configuration.activity_forum_id,
                expected_type="forum",
                label="activity forum",
            )
        )

        if configuration.command_channel_id is None:
            issues.append("No administrative command channel is configured.")

        else:
            issues.extend(
                self._validate_configured_channel(
                    category=category,
                    channel_id=configuration.command_channel_id,
                    expected_type="text",
                    label="command channel",
                )
            )

        if configuration.error_forum_id is None:
            issues.append("No error report forum is configured.")

        else:
            issues.extend(
                self._validate_configured_channel(
                    category=category,
                    channel_id=configuration.error_forum_id,
                    expected_type="forum",
                    label="error forum",
                )
            )

            if configuration.error_forum_id == configuration.activity_forum_id:
                issues.append("Activity and error reports reference the same forum.")

        return tuple(
            issues,
        )

    def _validate_configured_channel(
        self,
        *,
        category: AdminCategoryCandidate,
        channel_id: int,
        expected_type: AdminChannelType,
        label: str,
    ) -> tuple[str, ...]:
        """Validate one configured Discord channel against discovery."""

        channel = self._find_channel(
            category,
            channel_id=channel_id,
        )

        if channel is None:
            return (f"The configured {label} {channel_id} is missing from Discord.",)

        issues: list[str] = []

        if channel.channel_type != expected_type:
            issues.append(
                f"The configured {label} {channel_id} has the wrong channel type."
            )

        if not channel.is_private:
            issues.append(
                f"The configured {label} {channel_id} is visible to @everyone."
            )

        if not channel.bot_usable:
            issues.append(f"Claviger cannot use the configured {label} {channel_id}.")

        return tuple(
            issues,
        )

    @staticmethod
    def _find_category(
        discovery: AdminStructureDiscoveryResult,
        *,
        category_id: int,
    ) -> AdminCategoryCandidate | None:
        """Resolve one configured category from discovery."""

        return next(
            (
                category
                for category in discovery.categories
                if category.category_id == category_id
            ),
            None,
        )

    @staticmethod
    def _find_channel(
        category: AdminCategoryCandidate,
        *,
        channel_id: int,
    ) -> AdminChannelCandidate | None:
        """Resolve one configured channel inside an admin category."""

        return next(
            (
                channel
                for channel in category.channels
                if channel.channel_id == channel_id
            ),
            None,
        )
