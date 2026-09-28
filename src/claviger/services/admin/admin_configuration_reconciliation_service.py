from claviger.models.admin.admin_configuration_reconciliation_model import (
    AdminConfigurationFindingCode,
    AdminConfigurationReconciliationDecision,
    AdminConfigurationReconciliationResult,
)
from claviger.models.admin.admin_structure_discovery_model import (
    AdminCategoryCandidate,
    AdminChannelCandidate,
    AdminChannelType,
    AdminStructureDiscoveryResult,
)
from claviger.models.admin.guild_admin_configuration_model import (
    GuildAdminConfiguration,
)
from claviger.models.inspection import InspectionFinding


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
                decision=AdminConfigurationReconciliationDecision.NEEDS_CHOICE,
                category=None,
                findings=(
                    InspectionFinding(
                        AdminConfigurationFindingCode.MULTIPLE_CATEGORIES.value,
                        details={
                            "candidate_count": len(discovery.categories),
                        },
                    ),
                ),
            )

        category = discovery.single_candidate

        if category is None:
            raise RuntimeError(
                "Unambiguous admin discovery did not provide a category."
            )

        findings = self._get_candidate_findings(
            category,
        )

        if findings:
            return AdminConfigurationReconciliationResult(
                decision=AdminConfigurationReconciliationDecision.COMPLETE,
                category=category,
                findings=findings,
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
            findings = [
                InspectionFinding(
                    AdminConfigurationFindingCode.CONFIGURED_CATEGORY_MISSING.value,
                    details={
                        "category_id": configuration.category_id,
                    },
                ),
            ]

            if not discovery.categories:
                return AdminConfigurationReconciliationResult(
                    decision=AdminConfigurationReconciliationDecision.CREATE,
                    category=None,
                    findings=tuple(findings),
                )

            findings.append(
                InspectionFinding(
                    AdminConfigurationFindingCode.MULTIPLE_CATEGORIES.value,
                    details={
                        "candidate_count": len(discovery.categories),
                    },
                )
            )

            return AdminConfigurationReconciliationResult(
                decision=AdminConfigurationReconciliationDecision.NEEDS_CHOICE,
                category=None,
                findings=tuple(findings),
            )

        findings = self._get_configuration_findings(
            category=category,
            configuration=configuration,
        )

        if findings:
            return AdminConfigurationReconciliationResult(
                decision=AdminConfigurationReconciliationDecision.COMPLETE,
                category=category,
                findings=findings,
            )

        return AdminConfigurationReconciliationResult(
            decision=AdminConfigurationReconciliationDecision.KEEP,
            category=category,
        )

    def _get_candidate_findings(
        self,
        category: AdminCategoryCandidate,
    ) -> tuple[InspectionFinding, ...]:
        """Describe why an unconfigured Discord category is not ready."""

        findings: list[InspectionFinding] = []

        if not category.is_private:
            findings.append(
                InspectionFinding(
                    AdminConfigurationFindingCode.CATEGORY_PUBLIC.value,
                    details={
                        "category_id": category.category_id,
                    },
                )
            )

        if not category.bot_can_view:
            findings.append(
                InspectionFinding(
                    (
                        AdminConfigurationFindingCode
                        .CATEGORY_APPLICATION_UNAVAILABLE.value
                    ),
                    details={
                        "category_id": category.category_id,
                    },
                )
            )

        if not category.text_channels:
            findings.append(
                InspectionFinding(
                    AdminConfigurationFindingCode.TEXT_CHANNEL_MISSING.value,
                    details={
                        "category_id": category.category_id,
                        "required_count": 1,
                        "actual_count": 0,
                    },
                )
            )

        if len(category.forum_channels) < 2:
            findings.append(
                InspectionFinding(
                    AdminConfigurationFindingCode.FORUM_COUNT_INSUFFICIENT.value,
                    details={
                        "category_id": category.category_id,
                        "required_count": 2,
                        "actual_count": len(category.forum_channels),
                    },
                )
            )

        if not category.usable_text_channels:
            findings.append(
                InspectionFinding(
                    (
                        AdminConfigurationFindingCode
                        .USABLE_TEXT_CHANNEL_MISSING.value
                    ),
                    details={
                        "category_id": category.category_id,
                        "required_count": 1,
                        "actual_count": 0,
                    },
                )
            )

        if len(category.usable_forum_channels) < 2:
            findings.append(
                InspectionFinding(
                    (
                        AdminConfigurationFindingCode
                        .USABLE_FORUM_COUNT_INSUFFICIENT.value
                    ),
                    details={
                        "category_id": category.category_id,
                        "required_count": 2,
                        "actual_count": len(category.usable_forum_channels),
                    },
                )
            )

        return tuple(findings)

    def _get_configuration_findings(
        self,
        *,
        category: AdminCategoryCandidate,
        configuration: GuildAdminConfiguration,
    ) -> tuple[InspectionFinding, ...]:
        """Validate configured Discord IDs against the observed category."""

        findings: list[InspectionFinding] = []

        if not category.is_private:
            findings.append(
                InspectionFinding(
                    AdminConfigurationFindingCode.CATEGORY_PUBLIC.value,
                    details={
                        "category_id": category.category_id,
                    },
                )
            )

        if not category.bot_can_view:
            findings.append(
                InspectionFinding(
                    (
                        AdminConfigurationFindingCode
                        .CATEGORY_APPLICATION_UNAVAILABLE.value
                    ),
                    details={
                        "category_id": category.category_id,
                    },
                )
            )

        findings.extend(
            self._validate_configured_channel(
                category=category,
                channel_id=configuration.activity_forum_id,
                expected_type="forum",
                purpose="activity_forum",
            )
        )

        if configuration.command_channel_id is None:
            findings.append(
                InspectionFinding(
                    AdminConfigurationFindingCode.COMMAND_CHANNEL_MISSING.value,
                )
            )

        else:
            findings.extend(
                self._validate_configured_channel(
                    category=category,
                    channel_id=configuration.command_channel_id,
                    expected_type="text",
                    purpose="command_channel",
                )
            )

        if configuration.error_forum_id is None:
            findings.append(
                InspectionFinding(
                    AdminConfigurationFindingCode.ERROR_FORUM_MISSING.value,
                )
            )

        else:
            findings.extend(
                self._validate_configured_channel(
                    category=category,
                    channel_id=configuration.error_forum_id,
                    expected_type="forum",
                    purpose="error_forum",
                )
            )

            if configuration.error_forum_id == configuration.activity_forum_id:
                findings.append(
                    InspectionFinding(
                        AdminConfigurationFindingCode.DESTINATIONS_COLLIDE.value,
                        details={
                            "channel_id": configuration.error_forum_id,
                        },
                    )
                )

        return tuple(findings)

    def _validate_configured_channel(
        self,
        *,
        category: AdminCategoryCandidate,
        channel_id: int,
        expected_type: AdminChannelType,
        purpose: str,
    ) -> tuple[InspectionFinding, ...]:
        """Validate one configured channel against current Discord discovery."""

        channel = self._find_channel(
            category,
            channel_id=channel_id,
        )

        if channel is None:
            return (
                InspectionFinding(
                    AdminConfigurationFindingCode.CHANNEL_MISSING.value,
                    details={
                        "channel_id": channel_id,
                        "purpose": purpose,
                    },
                ),
            )

        findings: list[InspectionFinding] = []

        if channel.channel_type != expected_type:
            findings.append(
                InspectionFinding(
                    AdminConfigurationFindingCode.CHANNEL_WRONG_TYPE.value,
                    details={
                        "channel_id": channel_id,
                        "purpose": purpose,
                        "expected_type": expected_type,
                        "actual_type": channel.channel_type,
                    },
                )
            )

        if not channel.is_private:
            findings.append(
                InspectionFinding(
                    AdminConfigurationFindingCode.CHANNEL_PUBLIC.value,
                    details={
                        "channel_id": channel_id,
                        "purpose": purpose,
                    },
                )
            )

        if not channel.bot_usable:
            findings.append(
                InspectionFinding(
                    AdminConfigurationFindingCode.CHANNEL_APPLICATION_UNUSABLE.value,
                    details={
                        "channel_id": channel_id,
                        "purpose": purpose,
                    },
                )
            )

        return tuple(findings)

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
