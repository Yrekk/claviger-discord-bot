import pytest

from claviger.models.member_interest import MemberInterest
from claviger.models.role_channel_discovery_model import (
    DiscordChannelSnapshot,
    DiscordRoleSnapshot,
    GuildRoleChannelSnapshot,
)
from claviger.services.catalog_sync_planner_service import (
    CatalogSyncPlanner,
)


def create_current_interest(
    *,
    role_id: int = 100,
    role_name: str = "interest-ia",
    catalog_key: str = "ia",
    channel_id: int = 200,
    channel_name: str = "ia",
    role_manageable: bool = True,
    discord_present: bool = True,
    channel_present: bool = True,
    mapping_valid: bool = True,
    matches_policy: bool = True,
) -> MemberInterest:
    """Create one existing member interest for planner tests."""

    return MemberInterest(
        guild_id=123,
        role_id=role_id,
        role_name=role_name,
        catalog_key=catalog_key,
        channel_id=channel_id,
        channel_name=channel_name,
        label="IA",
        description="Intelligence artificielle.",
        emoji="🤖",
        sort_order=10,
        enabled=True,
        discord_present=discord_present,
        role_manageable=role_manageable,
        channel_present=channel_present,
        mapping_valid=mapping_valid,
        matches_policy=matches_policy,
    )


def create_snapshot(
    *,
    roles: tuple[DiscordRoleSnapshot, ...],
    channels: tuple[DiscordChannelSnapshot, ...],
) -> GuildRoleChannelSnapshot:
    """Create an immutable Discord snapshot."""

    return GuildRoleChannelSnapshot(
        roles=roles,
        channels=channels,
    )


def test_plan_creates_new_valid_interest() -> None:
    """Create a new role when exactly one channel is mapped."""

    snapshot = create_snapshot(
        roles=(
            DiscordRoleSnapshot(
                role_id=100,
                role_name="interest-ia",
                role_manageable=True,
                explicit_channel_ids=(200,),
            ),
        ),
        channels=(
            DiscordChannelSnapshot(
                channel_id=200,
                channel_name="ia",
            ),
        ),
    )

    plan = CatalogSyncPlanner().build_plan(
        [],
        snapshot,
        prefix="interest-",
    )

    assert len(plan.creates) == 1

    created = plan.creates[0]

    assert created.role_id == 100
    assert created.catalog_key == "ia"
    assert created.channel_id == 200
    assert created.role_manageable is True

    assert plan.change_count == 1


def test_plan_uses_same_logic_for_access_prefix() -> None:
    """Discover adult access roles without special planner logic."""

    snapshot = create_snapshot(
        roles=(
            DiscordRoleSnapshot(
                role_id=100,
                role_name="access-ia-futa",
                role_manageable=True,
                explicit_channel_ids=(200,),
            ),
        ),
        channels=(
            DiscordChannelSnapshot(
                channel_id=200,
                channel_name="ia-futa",
            ),
        ),
    )

    plan = CatalogSyncPlanner().build_plan(
        [],
        snapshot,
        prefix="access-",
    )

    assert len(plan.creates) == 1
    assert plan.creates[0].catalog_key == "ia-futa"


def test_plan_warns_about_new_role_without_channel() -> None:
    """Do not create catalog rows with missing channel mappings."""

    snapshot = create_snapshot(
        roles=(
            DiscordRoleSnapshot(
                role_id=100,
                role_name="interest-ia",
                role_manageable=True,
                explicit_channel_ids=(),
            ),
        ),
        channels=(),
    )

    plan = CatalogSyncPlanner().build_plan(
        [],
        snapshot,
        prefix="interest-",
    )

    assert plan.creates == ()
    assert len(plan.warnings) == 1
    assert plan.warnings[0].code == "missing_channel_mapping"


def test_plan_warns_about_ambiguous_channel_mapping() -> None:
    """Do not create catalog rows mapped to several channels."""

    snapshot = create_snapshot(
        roles=(
            DiscordRoleSnapshot(
                role_id=100,
                role_name="interest-ia",
                role_manageable=True,
                explicit_channel_ids=(
                    200,
                    201,
                ),
            ),
        ),
        channels=(
            DiscordChannelSnapshot(
                channel_id=200,
                channel_name="ia-one",
            ),
            DiscordChannelSnapshot(
                channel_id=201,
                channel_name="ia-two",
            ),
        ),
    )

    plan = CatalogSyncPlanner().build_plan(
        [],
        snapshot,
        prefix="interest-",
    )

    assert plan.creates == ()
    assert len(plan.warnings) == 1
    assert plan.warnings[0].code == "ambiguous_channel_mapping"
    assert plan.warnings[0].channel_count == 2


def test_plan_does_nothing_when_catalog_is_already_synchronized() -> None:
    """Avoid unnecessary writes when Discord and SQLite already agree."""

    current = create_current_interest()

    snapshot = create_snapshot(
        roles=(
            DiscordRoleSnapshot(
                role_id=100,
                role_name="interest-ia",
                role_manageable=True,
                explicit_channel_ids=(200,),
            ),
        ),
        channels=(
            DiscordChannelSnapshot(
                channel_id=200,
                channel_name="ia",
            ),
        ),
    )

    plan = CatalogSyncPlanner().build_plan(
        [current],
        snapshot,
        prefix="interest-",
    )

    assert plan.creates == ()
    assert plan.refreshes == ()
    assert plan.state_updates == ()
    assert plan.warnings == ()
    assert plan.change_count == 0


def test_plan_refreshes_changed_discord_owned_data() -> None:
    """Refresh role, channel and manageability changes."""

    current = create_current_interest()

    snapshot = create_snapshot(
        roles=(
            DiscordRoleSnapshot(
                role_id=100,
                role_name="interest-games",
                role_manageable=False,
                explicit_channel_ids=(201,),
            ),
        ),
        channels=(
            DiscordChannelSnapshot(
                channel_id=201,
                channel_name="gaming",
            ),
        ),
    )

    plan = CatalogSyncPlanner().build_plan(
        [current],
        snapshot,
        prefix="interest-",
    )

    assert len(plan.refreshes) == 1

    refresh = plan.refreshes[0]

    assert refresh.role_name == "interest-games"
    assert refresh.catalog_key == "games"
    assert refresh.channel_id == 201
    assert refresh.channel_name == "gaming"
    assert refresh.role_manageable is False


def test_plan_marks_deleted_role_without_losing_channel_history() -> None:
    """Mark missing roles while preserving still-existing channel identity."""

    current = create_current_interest()

    snapshot = create_snapshot(
        roles=(),
        channels=(
            DiscordChannelSnapshot(
                channel_id=200,
                channel_name="ia-renamed",
            ),
        ),
    )

    plan = CatalogSyncPlanner().build_plan(
        [current],
        snapshot,
        prefix="interest-",
    )

    assert len(plan.state_updates) == 1

    state = plan.state_updates[0]

    assert state.role_name is None
    assert state.channel_name == "ia-renamed"

    assert state.discord_present is False
    assert state.role_manageable is False
    assert state.channel_present is True
    assert state.mapping_valid is False
    assert state.matches_policy is False


def test_plan_marks_role_renamed_outside_policy() -> None:
    """Keep observing known roles that no longer match the catalog prefix."""

    current = create_current_interest()

    snapshot = create_snapshot(
        roles=(
            DiscordRoleSnapshot(
                role_id=100,
                role_name="legacy-ia",
                role_manageable=True,
                explicit_channel_ids=(200,),
            ),
        ),
        channels=(
            DiscordChannelSnapshot(
                channel_id=200,
                channel_name="ia",
            ),
        ),
    )

    plan = CatalogSyncPlanner().build_plan(
        [current],
        snapshot,
        prefix="interest-",
    )

    assert len(plan.state_updates) == 1

    state = plan.state_updates[0]

    assert state.role_name == "legacy-ia"
    assert state.catalog_key is None

    assert state.discord_present is True
    assert state.channel_present is True
    assert state.mapping_valid is True
    assert state.matches_policy is False


def test_plan_distinguishes_present_channel_from_invalid_mapping() -> None:
    """Keep channel presence separate from role mapping validity."""

    current = create_current_interest()

    snapshot = create_snapshot(
        roles=(
            DiscordRoleSnapshot(
                role_id=100,
                role_name="interest-ia",
                role_manageable=True,
                explicit_channel_ids=(),
            ),
        ),
        channels=(
            DiscordChannelSnapshot(
                channel_id=200,
                channel_name="ia-renamed",
            ),
        ),
    )

    plan = CatalogSyncPlanner().build_plan(
        [current],
        snapshot,
        prefix="interest-",
    )

    assert len(plan.state_updates) == 1

    state = plan.state_updates[0]

    assert state.channel_present is True
    assert state.channel_name == "ia-renamed"
    assert state.mapping_valid is False
    assert state.matches_policy is True

    assert len(plan.warnings) == 1
    assert plan.warnings[0].code == "missing_channel_mapping"


def test_plan_rejects_empty_prefix() -> None:
    """Prevent a catalog from accidentally matching every Discord role."""

    snapshot = create_snapshot(
        roles=(),
        channels=(),
    )

    with pytest.raises(
        ValueError,
    ):
        CatalogSyncPlanner().build_plan(
            [],
            snapshot,
            prefix="",
        )
