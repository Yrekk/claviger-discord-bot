from claviger.models.member_interest_questionnaire_model import (
    MemberInterestQuestionnaire,
)
from claviger.models.member_role_plan_model import (
    MemberRolePlan,
)


class UnknownMemberInterestError(ValueError):
    """Raised when a submitted interest is not part of the questionnaire."""


class MemberRolePlannerService:
    """Plan member and interest role changes without touching Discord."""

    def build_plan(
        self,
        *,
        questionnaire: MemberInterestQuestionnaire,
        selected_interest_keys: tuple[str, ...],
        member_role_ids: set[int],
        member_role_id: int,
    ) -> MemberRolePlan:
        """Build the role mutations required by a member selection."""

        selected_keys = set(
            selected_interest_keys,
        )

        known_keys = {interest.catalog_key for interest in questionnaire.interests}

        unknown_keys = selected_keys - known_keys

        if unknown_keys:
            unknown_text = ", ".join(
                sorted(unknown_keys),
            )

            raise UnknownMemberInterestError(
                f"Unknown member interest keys: {unknown_text}."
            )

        desired_interest_role_ids = tuple(
            interest.role_id
            for interest in questionnaire.interests
            if interest.catalog_key in selected_keys
        )

        desired_interest_role_id_set = set(
            desired_interest_role_ids,
        )

        add_role_ids: list[int] = []
        remove_role_ids: list[int] = []

        if member_role_id not in member_role_ids:
            add_role_ids.append(
                member_role_id,
            )

        for role_id in desired_interest_role_ids:
            if role_id not in member_role_ids:
                add_role_ids.append(
                    role_id,
                )

        for interest in questionnaire.interests:
            if (
                interest.role_id in member_role_ids
                and interest.role_id not in desired_interest_role_id_set
            ):
                remove_role_ids.append(
                    interest.role_id,
                )

        return MemberRolePlan(
            add_role_ids=tuple(
                add_role_ids,
            ),
            remove_role_ids=tuple(
                remove_role_ids,
            ),
        )
