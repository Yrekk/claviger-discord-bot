from collections.abc import Iterable

from claviger.models.adult_access_questionnaire_model import (
    AdultAccessQuestionnaire,
)
from claviger.models.noctis_role_plan_model import (
    NoctisRolePlan,
)
from claviger.services.adult_access_workflow_service import (
    AdultAccessWorkflowService,
)


class NoctisRolePlannerService:
    """Plan Discord role changes for the /noctis workflow."""

    def __init__(
        self,
        workflow_service: AdultAccessWorkflowService,
    ) -> None:
        self.workflow_service = workflow_service

    def build_plan(
        self,
        questionnaire: AdultAccessQuestionnaire,
        selected_theme_keys: Iterable[str],
        *,
        include_ai: bool,
        member_role_ids: Iterable[int],
        adult_role_id: int,
        ai_option_role_id: int,
    ) -> NoctisRolePlan:
        """Build the desired role changes without modifying Discord."""

        current_role_ids = set(
            member_role_ids,
        )

        selected_theme_keys = tuple(dict.fromkeys(selected_theme_keys))

        desired_access_role_ids = self.workflow_service.resolve_role_ids(
            questionnaire.themes,
            selected_theme_keys,
            include_ai=include_ai,
        )

        managed_access_role_ids: set[int] = set()

        for theme in questionnaire.themes:
            managed_access_role_ids.add(theme.base_access.role_id)

            if theme.ai_access is not None:
                managed_access_role_ids.add(theme.ai_access.role_id)

        desired_access_set = set(
            desired_access_role_ids,
        )

        add_role_ids: list[int] = []
        remove_role_ids: list[int] = []

        if adult_role_id not in current_role_ids:
            add_role_ids.append(
                adult_role_id,
            )

        for role_id in desired_access_role_ids:
            if role_id not in current_role_ids:
                add_role_ids.append(
                    role_id,
                )

        if include_ai:
            if ai_option_role_id not in current_role_ids:
                add_role_ids.append(
                    ai_option_role_id,
                )
        elif ai_option_role_id in current_role_ids:
            remove_role_ids.append(
                ai_option_role_id,
            )

        for theme in questionnaire.themes:
            candidate_role_ids = [
                theme.base_access.role_id,
            ]

            if theme.ai_access is not None:
                candidate_role_ids.append(
                    theme.ai_access.role_id,
                )

            for role_id in candidate_role_ids:
                if (
                    role_id in current_role_ids
                    and role_id in managed_access_role_ids
                    and role_id not in desired_access_set
                ):
                    remove_role_ids.append(
                        role_id,
                    )

        return NoctisRolePlan(
            add_role_ids=tuple(add_role_ids),
            remove_role_ids=tuple(remove_role_ids),
        )
