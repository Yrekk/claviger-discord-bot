import discord

from claviger.models.member_interest_questionnaire_model import (
    MemberInterestQuestionnaire,
)
from claviger.models.role_channel_catalog_model import (
    RoleChannelCatalogEntry,
)
from claviger.repositories.interest_catalog_repository import (
    InterestCatalogRepository,
)


class MemberInterestQuestionnaireService:
    """Build the member interest questionnaire from the guild catalog."""

    def __init__(
        self,
        repository: InterestCatalogRepository,
    ) -> None:
        self.repository = repository

    async def build_for_member(
        self,
        *,
        guild_id: int,
        member: discord.Member,
    ) -> MemberInterestQuestionnaire:
        """Build the public interest selection for one Discord member."""

        catalog_entries = await self.repository.list_for_guild(
            guild_id,
        )

        interests = tuple(
            sorted(
                (
                    interest
                    for interest in catalog_entries
                    if self._is_publicly_available(
                        interest,
                    )
                ),
                key=lambda interest: (
                    interest.sort_order,
                    interest.catalog_key,
                ),
            )
        )

        member_role_ids = {role.id for role in member.roles}

        selected_interest_keys = tuple(
            interest.catalog_key
            for interest in interests
            if interest.role_id in member_role_ids
        )

        return MemberInterestQuestionnaire(
            interests=interests,
            selected_interest_keys=selected_interest_keys,
        )

    @staticmethod
    def _is_publicly_available(
        interest: RoleChannelCatalogEntry,
    ) -> bool:
        """Return whether an interest is safe to expose publicly."""

        return (
            interest.enabled
            and interest.is_configured
            and interest.discord_present
            and interest.role_manageable
            and interest.channel_present
            and interest.mapping_valid
            and interest.matches_policy
        )
