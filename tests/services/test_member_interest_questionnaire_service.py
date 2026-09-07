from unittest.mock import AsyncMock, Mock

import discord
import pytest

from claviger.models.role_channel_catalog_model import (
    RoleChannelCatalogEntry,
)
from claviger.repositories.interest_catalog_repository import (
    InterestCatalogRepository,
)
from claviger.services.member_interest_questionnaire_service import (
    MemberInterestQuestionnaireService,
)


def create_interest(
    *,
    key: str,
    role_id: int,
    sort_order: int = 0,
    enabled: bool = True,
    is_configured: bool = True,
    discord_present: bool = True,
    role_manageable: bool = True,
    channel_present: bool = True,
    mapping_valid: bool = True,
    matches_policy: bool = True,
) -> Mock:
    """Create a catalog interest for questionnaire tests."""

    interest = Mock(
        spec=RoleChannelCatalogEntry,
    )

    interest.catalog_key = key
    interest.role_id = role_id
    interest.sort_order = sort_order

    interest.enabled = enabled
    interest.is_configured = is_configured
    interest.discord_present = discord_present
    interest.role_manageable = role_manageable
    interest.channel_present = channel_present
    interest.mapping_valid = mapping_valid
    interest.matches_policy = matches_policy

    return interest


def create_member(
    *role_ids: int,
) -> Mock:
    """Create a Discord member holding the requested role IDs."""

    member = Mock(
        spec=discord.Member,
    )

    roles = []

    for role_id in role_ids:
        role = Mock(
            spec=discord.Role,
        )
        role.id = role_id
        roles.append(
            role,
        )

    member.roles = roles

    return member


def create_service(
    *interests: RoleChannelCatalogEntry,
) -> tuple[
    MemberInterestQuestionnaireService,
    Mock,
]:
    """Create the questionnaire service with a mocked repository."""

    repository = Mock(
        spec=InterestCatalogRepository,
    )

    repository.list_for_guild = AsyncMock(
        return_value=list(
            interests,
        )
    )

    return (
        MemberInterestQuestionnaireService(
            repository,
        ),
        repository,
    )


@pytest.mark.asyncio
async def test_questionnaire_exposes_only_publicly_available_interests() -> None:
    """Hide incomplete or technically invalid catalog entries."""

    valid = create_interest(
        key="musicae",
        role_id=10,
    )

    disabled = create_interest(
        key="codex",
        role_id=20,
        enabled=False,
    )

    invalid_mapping = create_interest(
        key="ludus",
        role_id=30,
        mapping_valid=False,
    )

    service, repository = create_service(
        valid,
        disabled,
        invalid_mapping,
    )

    questionnaire = await service.build_for_member(
        guild_id=123,
        member=create_member(),
    )

    assert questionnaire.interests == (valid,)

    assert questionnaire.selected_interest_keys == ()

    repository.list_for_guild.assert_awaited_once_with(
        123,
    )


@pytest.mark.asyncio
async def test_questionnaire_restores_current_member_selections() -> None:
    """Preselect interests whose Discord roles are already held."""

    musicae = create_interest(
        key="musicae",
        role_id=10,
        sort_order=10,
    )

    codex = create_interest(
        key="codex",
        role_id=20,
        sort_order=20,
    )

    ludus = create_interest(
        key="ludus",
        role_id=30,
        sort_order=30,
    )

    service, _ = create_service(
        musicae,
        codex,
        ludus,
    )

    questionnaire = await service.build_for_member(
        guild_id=123,
        member=create_member(
            10,
            30,
            999,
        ),
    )

    assert questionnaire.selected_interest_keys == (
        "musicae",
        "ludus",
    )


@pytest.mark.asyncio
async def test_questionnaire_uses_canonical_catalog_order() -> None:
    """Order interests deterministically by sort order then catalog key."""

    ludus = create_interest(
        key="ludus",
        role_id=30,
        sort_order=20,
    )

    musicae = create_interest(
        key="musicae",
        role_id=10,
        sort_order=10,
    )

    codex = create_interest(
        key="codex",
        role_id=20,
        sort_order=10,
    )

    service, _ = create_service(
        ludus,
        musicae,
        codex,
    )

    questionnaire = await service.build_for_member(
        guild_id=123,
        member=create_member(
            10,
            20,
            30,
        ),
    )

    assert tuple(interest.catalog_key for interest in questionnaire.interests) == (
        "codex",
        "musicae",
        "ludus",
    )

    assert questionnaire.selected_interest_keys == (
        "codex",
        "musicae",
        "ludus",
    )
