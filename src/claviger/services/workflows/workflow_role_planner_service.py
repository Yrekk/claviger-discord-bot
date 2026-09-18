from claviger.models.workflows.workflow_questionnaire_model import (
    WorkflowQuestionnaire,
    WorkflowQuestionnaireSubmission,
)
from claviger.models.workflows.workflow_role_plan_model import WorkflowRolePlan


class WorkflowQuestionnaireSubmissionError(ValueError):
    """Raised when submitted questionnaire state no longer matches the current form."""


class WorkflowRolePlannerService:
    """Plan generic workflow role changes without touching Discord."""

    def build_plan(
        self,
        *,
        questionnaire: WorkflowQuestionnaire,
        submission: WorkflowQuestionnaireSubmission,
        member_role_ids: set[int],
    ) -> WorkflowRolePlan:
        """Build exact role operations for a validated questionnaire submission."""

        current_catalogs = {
            catalog.catalog_key: catalog
            for catalog in questionnaire.catalogs
        }
        submitted_catalogs = {
            catalog.catalog_key: catalog
            for catalog in submission.catalogs
        }

        if set(current_catalogs) != set(submitted_catalogs):
            raise WorkflowQuestionnaireSubmissionError(
                "Questionnaire catalogs changed while the form was open."
            )

        desired_role_ids: list[int] = [
            questionnaire.primary_role_id,
        ]

        for catalog_key, current_catalog in current_catalogs.items():
            submitted = submitted_catalogs[catalog_key]

            visible_keys = tuple(
                option.entry_key
                for option in current_catalog.options
            )

            if submitted.visible_entry_keys != visible_keys:
                raise WorkflowQuestionnaireSubmissionError(
                    "Questionnaire options changed while the form was open."
                )

            selected_keys = set(
                submitted.selected_entry_keys,
            )
            known_keys = set(
                visible_keys,
            )

            unknown_keys = selected_keys - known_keys

            if unknown_keys:
                unknown_text = ", ".join(
                    sorted(
                        unknown_keys,
                    )
                )
                raise WorkflowQuestionnaireSubmissionError(
                    f"Unknown questionnaire entries: {unknown_text}."
                )

            desired_role_ids.extend(
                option.target_role_id
                for option in current_catalog.options
                if option.entry_key in selected_keys
            )

        if questionnaire.ai_editable:
            if submission.ai_preference is None:
                raise WorkflowQuestionnaireSubmissionError(
                    "AI preference is required for the questionnaire owner workflow."
                )

            if submission.ai_preference != questionnaire.ai_preference:
                raise WorkflowQuestionnaireSubmissionError(
                    "AI preference changed while the form was open."
                )

            if questionnaire.ai_role_id is None:
                raise WorkflowQuestionnaireSubmissionError(
                    "AI role is unavailable for the owner workflow."
                )

            if questionnaire.ai_preference:
                desired_role_ids.append(
                    questionnaire.ai_role_id,
                )
        elif submission.ai_preference is not None:
            raise WorkflowQuestionnaireSubmissionError(
                "Only the questionnaire owner workflow may edit AI preference."
            )

        desired_role_ids = list(
            dict.fromkeys(
                desired_role_ids,
            )
        )
        desired_role_id_set = set(
            desired_role_ids,
        )

        managed_role_ids = set(
            questionnaire.managed_catalog_role_ids,
        )

        if questionnaire.ai_editable and questionnaire.ai_role_id is not None:
            managed_role_ids.add(
                questionnaire.ai_role_id,
            )

        add_role_ids = tuple(
            role_id
            for role_id in desired_role_ids
            if role_id not in member_role_ids
        )

        remove_role_ids = tuple(
            sorted(
                role_id
                for role_id in managed_role_ids
                if role_id in member_role_ids
                and role_id not in desired_role_id_set
            )
        )

        return WorkflowRolePlan(
            add_role_ids=add_role_ids,
            remove_role_ids=remove_role_ids,
        )
