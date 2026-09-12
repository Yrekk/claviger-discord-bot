from claviger.models.admin_configuration_reconciliation_model import (
    AdminConfigurationReconciliationDecision,
)
from claviger.models.admin_structure_discovery_model import (
    AdminCategoryCandidate,
    AdminChannelCandidate,
    AdminStructureDiscoveryResult,
)
from claviger.models.guild_admin_configuration_model import (
    GuildAdminConfiguration,
)
from claviger.services.admin_configuration_reconciliation_service import (
    AdminConfigurationReconciliationService,
)


def _channel(
    *,
    channel_id: int,
    channel_name: str,
    channel_type: str,
    private: bool = True,
    bot_usable: bool = True,
) -> AdminChannelCandidate:
    """Create one deterministic discovery channel."""

    return AdminChannelCandidate(
        channel_id=channel_id,
        channel_name=channel_name,
        channel_type=channel_type,
        everyone_can_view=not private,
        bot_can_view=bot_usable,
        bot_can_send=bot_usable,
    )


def _category(
    *,
    category_id: int = 100,
    category_name: str = "admin",
    channels: tuple[AdminChannelCandidate, ...] = (),
    private: bool = True,
    bot_can_view: bool = True,
) -> AdminCategoryCandidate:
    """Create one deterministic administrative category."""

    return AdminCategoryCandidate(
        category_id=category_id,
        category_name=category_name,
        everyone_can_view=not private,
        bot_can_view=bot_can_view,
        has_public_child=any(channel.everyone_can_view for channel in channels),
        channels=channels,
    )


def _ready_category(
    *,
    category_id: int = 100,
    category_name: str = "admin",
) -> AdminCategoryCandidate:
    """Create one complete private administrative category."""

    return _category(
        category_id=category_id,
        category_name=category_name,
        channels=(
            _channel(
                channel_id=200,
                channel_name="commands",
                channel_type="text",
            ),
            _channel(
                channel_id=201,
                channel_name="activity",
                channel_type="forum",
            ),
            _channel(
                channel_id=202,
                channel_name="errors",
                channel_type="forum",
            ),
        ),
    )


def _complete_configuration(
    *,
    category_id: int = 100,
) -> GuildAdminConfiguration:
    """Create one complete persisted ADMIN configuration."""

    return GuildAdminConfiguration(
        guild_id=123,
        category_id=category_id,
        activity_forum_id=201,
        command_channel_id=200,
        error_forum_id=202,
    )


def test_reconcile_without_configuration_or_candidate_returns_create() -> None:
    """Create a new ADMIN structure when Discord has no candidate."""

    result = AdminConfigurationReconciliationService().reconcile(
        discovery=AdminStructureDiscoveryResult(
            categories=(),
        ),
        configuration=None,
    )

    assert result.decision == AdminConfigurationReconciliationDecision.CREATE

    assert result.category is None
    assert result.issues == ()


def test_reconcile_ready_candidate_without_configuration_returns_import() -> None:
    """Import one usable existing Discord structure."""

    category = _ready_category()

    result = AdminConfigurationReconciliationService().reconcile(
        discovery=AdminStructureDiscoveryResult(
            categories=(category,),
        ),
        configuration=None,
    )

    assert result.decision == AdminConfigurationReconciliationDecision.IMPORT

    assert result.category == category
    assert result.issues == ()


def test_reconcile_incomplete_candidate_returns_complete() -> None:
    """Complete one existing but structurally incomplete ADMIN category."""

    category = _category(
        channels=(
            _channel(
                channel_id=201,
                channel_name="activity",
                channel_type="forum",
            ),
        ),
    )

    result = AdminConfigurationReconciliationService().reconcile(
        discovery=AdminStructureDiscoveryResult(
            categories=(category,),
        ),
        configuration=None,
    )

    assert result.decision == AdminConfigurationReconciliationDecision.COMPLETE

    assert result.category == category
    assert result.issues


def test_reconcile_multiple_unconfigured_candidates_requires_choice() -> None:
    """Never guess which ADMIN category should be adopted."""

    result = AdminConfigurationReconciliationService().reconcile(
        discovery=AdminStructureDiscoveryResult(
            categories=(
                _ready_category(
                    category_id=100,
                ),
                _ready_category(
                    category_id=101,
                ),
            ),
        ),
        configuration=None,
    )

    assert result.decision == AdminConfigurationReconciliationDecision.NEEDS_CHOICE

    assert result.category is None
    assert result.issues


def test_reconcile_valid_complete_configuration_returns_keep() -> None:
    """Keep one persisted configuration that still matches Discord."""

    category = _ready_category()

    result = AdminConfigurationReconciliationService().reconcile(
        discovery=AdminStructureDiscoveryResult(
            categories=(category,),
        ),
        configuration=_complete_configuration(),
    )

    assert result.decision == AdminConfigurationReconciliationDecision.KEEP

    assert result.category == category
    assert result.issues == ()


def test_reconcile_incomplete_persisted_configuration_returns_complete() -> None:
    """Complete a bootstrap configuration missing normal ADMIN destinations."""

    category = _ready_category()

    configuration = GuildAdminConfiguration(
        guild_id=123,
        category_id=100,
        activity_forum_id=201,
        command_channel_id=None,
        error_forum_id=None,
    )

    result = AdminConfigurationReconciliationService().reconcile(
        discovery=AdminStructureDiscoveryResult(
            categories=(category,),
        ),
        configuration=configuration,
    )

    assert result.decision == AdminConfigurationReconciliationDecision.COMPLETE

    assert result.category == category
    assert result.issues


def test_reconcile_missing_configured_channel_returns_complete() -> None:
    """Repair persisted IDs when one configured channel disappeared."""

    category = _category(
        channels=(
            _channel(
                channel_id=200,
                channel_name="commands",
                channel_type="text",
            ),
            _channel(
                channel_id=201,
                channel_name="activity",
                channel_type="forum",
            ),
        ),
    )

    result = AdminConfigurationReconciliationService().reconcile(
        discovery=AdminStructureDiscoveryResult(
            categories=(category,),
        ),
        configuration=_complete_configuration(),
    )

    assert result.decision == AdminConfigurationReconciliationDecision.COMPLETE

    assert result.category == category

    assert any("202" in issue for issue in result.issues)


def test_reconcile_public_configured_structure_returns_complete() -> None:
    """Repair a configured ADMIN structure that became publicly visible."""

    category = _ready_category()

    public_category = AdminCategoryCandidate(
        category_id=category.category_id,
        category_name=category.category_name,
        everyone_can_view=True,
        bot_can_view=True,
        has_public_child=False,
        channels=category.channels,
    )

    result = AdminConfigurationReconciliationService().reconcile(
        discovery=AdminStructureDiscoveryResult(
            categories=(public_category,),
        ),
        configuration=_complete_configuration(),
    )

    assert result.decision == AdminConfigurationReconciliationDecision.COMPLETE

    assert result.issues


def test_missing_configured_category_without_alternative_returns_create() -> None:
    """Recreate ADMIN when the persisted category disappeared completely."""

    result = AdminConfigurationReconciliationService().reconcile(
        discovery=AdminStructureDiscoveryResult(
            categories=(),
        ),
        configuration=_complete_configuration(),
    )

    assert result.decision == AdminConfigurationReconciliationDecision.CREATE

    assert result.category is None
    assert result.issues


def test_missing_configured_category_with_alternative_requires_choice() -> None:
    """Never silently replace a persisted ADMIN category with another one."""

    alternative = _ready_category(
        category_id=999,
    )

    result = AdminConfigurationReconciliationService().reconcile(
        discovery=AdminStructureDiscoveryResult(
            categories=(alternative,),
        ),
        configuration=_complete_configuration(
            category_id=100,
        ),
    )

    assert result.decision == AdminConfigurationReconciliationDecision.NEEDS_CHOICE

    assert result.category is None
    assert result.issues


def test_valid_persisted_category_wins_over_other_admin_candidates() -> None:
    """Use persisted Discord identity even when other ADMIN categories exist."""

    configured = _ready_category(
        category_id=100,
    )

    unrelated = _ready_category(
        category_id=999,
    )

    result = AdminConfigurationReconciliationService().reconcile(
        discovery=AdminStructureDiscoveryResult(
            categories=(
                configured,
                unrelated,
            ),
        ),
        configuration=_complete_configuration(
            category_id=100,
        ),
    )

    assert result.decision == AdminConfigurationReconciliationDecision.KEEP

    assert result.category == configured
    assert result.issues == ()
