import discord

from claviger.constants.role_names import AI_OPTION_ROLE_NAME
from claviger.models.adult_access_questionnaire_model import (
    AdultAccessQuestionnaire,
)
from claviger.repositories.access_catalog_repository import (
    AccessCatalogRepository,
)
from claviger.services.adult_access_workflow_service import (
    AdultAccessWorkflowService,
)


class AdultAccessQuestionnaireService:
    """Build the adult-access questionnaire state for a Discord member."""

    def __init__(
        self,
        repository: AccessCatalogRepository,
        workflow_service: AdultAccessWorkflowService,
    ) -> None:
        self.repository = repository
        self.workflow_service = workflow_service

    async def build_for_member(
        self,
        guild_id: int,
        member: discord.Member,
    ) -> AdultAccessQuestionnaire:
        """Build available choices and the member's current selections."""

        accesses = await self.repository.list_for_guild(
            guild_id,
        )

        themes = self.workflow_service.build_themes(
            accesses,
        )

        member_role_ids = {role.id for role in member.roles}

        selected_theme_keys = tuple(
            theme.theme_key
            for theme in themes
            if theme.base_access.role_id in member_role_ids
        )

        include_ai = any(role.name == AI_OPTION_ROLE_NAME for role in member.roles)

        return AdultAccessQuestionnaire(
            themes=themes,
            selected_theme_keys=selected_theme_keys,
            include_ai=include_ai,
        )
