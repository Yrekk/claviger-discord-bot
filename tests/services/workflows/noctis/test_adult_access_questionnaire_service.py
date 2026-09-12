from unittest.mock import AsyncMock, Mock

import discord
import pytest

from claviger.models.adult_access import AdultAccess
from claviger.repositories.access_catalog_repository import (
    AccessCatalogRepository,
)
from claviger.services.adult_access_questionnaire_service import (
    AdultAccessQuestionnaireService,
)
from claviger.services.adult_access_workflow_service import (
    AdultAccessWorkflowService,
)


def create_access(
    *,
    role_id: int,
    access_key: str,
    label: str = "Theme",
    sort_order: int = 10,
) -> AdultAccess:
    """Create one publicly ready adult-access entry."""

    return AdultAccess(
        guild_id=123,
        role_id=role_id,
        role_name=f"access-{access_key}",
        catalog_key=access_key,
        channel_id=role_id + 1000,
        channel_name=access_key,
        label=label,
        description="Description",
        emoji=None,
        sort_order=sort_order,
        enabled=True,
        discord_present=True,
        role_manageable=True,
        channel_present=True,
        mapping_valid=True,
        matches_policy=True,
    )


def create_member(
    *roles: tuple[int, str],
) -> Mock:
    """Create a Discord member with the requested roles."""

    member = Mock(
        spec=discord.Member,
    )

    member.roles = []

    for role_id, role_name in roles:
        role = Mock(
            spec=discord.Role,
        )
        role.id = role_id
        role.name = role_name

        member.roles.append(
            role,
        )

    return member


@pytest.mark.asyncio
async def test_build_for_member_restores_existing_choices() -> None:
    """Restore selected themes and the global IA preference."""

    repository = Mock(
        spec=AccessCatalogRepository,
    )

    repository.list_for_guild = AsyncMock(
        return_value=[
            create_access(
                role_id=10,
                access_key="no-ia-yuri",
                label="Yuri",
            ),
            create_access(
                role_id=11,
                access_key="ia-yuri",
                label="Yuri IA",
            ),
            create_access(
                role_id=20,
                access_key="no-ia-bdsm",
                label="Shibari - BDSM",
            ),
            create_access(
                role_id=21,
                access_key="ia-bdsm",
                label="Shibari - BDSM IA",
            ),
        ]
    )

    member = create_member(
        (10, "access-no-ia-yuri"),
        (999, "option-ia"),
    )

    service = AdultAccessQuestionnaireService(
        repository=repository,
        workflow_service=AdultAccessWorkflowService(),
    )

    questionnaire = await service.build_for_member(
        123,
        member,
    )

    repository.list_for_guild.assert_awaited_once_with(
        123,
    )

    assert tuple(theme.theme_key for theme in questionnaire.themes) == (
        "bdsm",
        "yuri",
    )

    assert questionnaire.selected_theme_keys == ("yuri",)

    assert questionnaire.include_ai is True


@pytest.mark.asyncio
async def test_build_for_member_uses_option_role_as_ai_source_of_truth() -> None:
    """Do not infer the IA preference from technical IA access roles."""

    repository = Mock(
        spec=AccessCatalogRepository,
    )

    repository.list_for_guild = AsyncMock(
        return_value=[
            create_access(
                role_id=10,
                access_key="no-ia-yuri",
            ),
            create_access(
                role_id=11,
                access_key="ia-yuri",
            ),
        ]
    )

    member = create_member(
        (10, "access-no-ia-yuri"),
        (11, "access-ia-yuri"),
    )

    service = AdultAccessQuestionnaireService(
        repository=repository,
        workflow_service=AdultAccessWorkflowService(),
    )

    questionnaire = await service.build_for_member(
        123,
        member,
    )

    assert questionnaire.selected_theme_keys == ("yuri",)

    assert questionnaire.include_ai is False


@pytest.mark.asyncio
async def test_build_for_member_returns_empty_selection_for_new_member() -> None:
    """Return available themes without preselecting anything."""

    repository = Mock(
        spec=AccessCatalogRepository,
    )

    repository.list_for_guild = AsyncMock(
        return_value=[
            create_access(
                role_id=10,
                access_key="no-ia-yuri",
                label="Yuri",
            ),
            create_access(
                role_id=11,
                access_key="ia-yuri",
                label="Yuri IA",
            ),
        ]
    )

    member = create_member()

    service = AdultAccessQuestionnaireService(
        repository=repository,
        workflow_service=AdultAccessWorkflowService(),
    )

    questionnaire = await service.build_for_member(
        123,
        member,
    )

    assert len(questionnaire.themes) == 1
    assert questionnaire.selected_theme_keys == ()
    assert questionnaire.include_ai is False
