from collections.abc import Mapping

from claviger.models.catalogs.catalog_entry_model import CatalogEntry, CatalogEntryTarget
from claviger.models.workflows.workflow_definition_model import WorkflowDefinition
from claviger.models.workflows.workflow_questionnaire_model import (
    WorkflowQuestionnaire,
    WorkflowQuestionnaireCatalog,
    WorkflowQuestionnaireOption,
)


class WorkflowQuestionnairePlanningError(ValueError):
    """Base error raised while converting persisted workflow state into a questionnaire."""


class WorkflowQuestionnaireTargetConflictError(WorkflowQuestionnairePlanningError):
    """Raised when one logical entry mixes incompatible target semantics."""


class WorkflowQuestionnairePlannerService:
    """Build generic questionnaires without touching Discord or persistence."""

    def build(
        self,
        *,
        workflow: WorkflowDefinition,
        entries_by_catalog: Mapping[str, tuple[CatalogEntry, ...]],
        member_role_ids: set[int],
        ai_enabled: bool,
        ai_role_id: int | None,
        owner_workflow_key: str | None,
        requested_ai_preference: bool | None = None,
    ) -> WorkflowQuestionnaire:
        """Build one deterministic questionnaire for the current member state."""

        if not workflow.enabled:
            raise WorkflowQuestionnairePlanningError("Workflow is disabled.")

        if workflow.primary_role_id is None or workflow.primary_role_id <= 0:
            raise WorkflowQuestionnairePlanningError(
                "Workflow primary role is not configured."
            )

        ai_ready = ai_enabled and ai_role_id is not None
        current_ai_preference = bool(
            ai_ready
            and ai_role_id is not None
            and ai_role_id in member_role_ids
        )
        ai_editable = bool(
            ai_ready
            and owner_workflow_key == workflow.workflow_key
        )

        if requested_ai_preference is not None and not ai_editable:
            raise WorkflowQuestionnairePlanningError(
                "This workflow is not allowed to edit the guild AI preference."
            )

        effective_ai_preference = (
            requested_ai_preference
            if ai_editable and requested_ai_preference is not None
            else current_ai_preference
        )

        catalogs: list[WorkflowQuestionnaireCatalog] = []
        managed_role_ids: list[int] = []

        for binding in workflow.catalogs:
            catalog = binding.catalog

            if not binding.enabled or not catalog.enabled:
                continue

            entries = entries_by_catalog.get(
                catalog.catalog_key,
                (),
            )

            options: list[WorkflowQuestionnaireOption] = []

            for entry in entries:
                if not entry.enabled:
                    continue

                managed_role_ids.extend(
                    target.role_id
                    for target in entry.targets
                )

                target = self._resolve_target(
                    entry,
                    ai_preference=effective_ai_preference,
                )

                if target is None:
                    continue

                selected = any(
                    candidate.role_id in member_role_ids
                    for candidate in entry.targets
                )

                options.append(
                    WorkflowQuestionnaireOption(
                        catalog_key=catalog.catalog_key,
                        entry_key=entry.entry_key,
                        label=entry.label or entry.entry_key,
                        description=entry.description,
                        emoji=entry.emoji,
                        target_role_id=target.role_id,
                        selected=selected,
                    )
                )

            if options:
                catalogs.append(
                    WorkflowQuestionnaireCatalog(
                        catalog_key=catalog.catalog_key,
                        display_name=catalog.display_name,
                        description=catalog.description,
                        options=tuple(options),
                    )
                )

        return WorkflowQuestionnaire(
            guild_id=workflow.guild_id,
            workflow_key=workflow.workflow_key,
            command_name=workflow.command_name,
            title=workflow.title,
            description=workflow.description,
            primary_role_id=workflow.primary_role_id,
            catalogs=tuple(catalogs),
            managed_catalog_role_ids=tuple(
                dict.fromkeys(
                    managed_role_ids,
                )
            ),
            ai_enabled=ai_ready,
            ai_role_id=ai_role_id if ai_ready else None,
            ai_editable=ai_editable,
            ai_preference=effective_ai_preference,
        )

    @staticmethod
    def _resolve_target(
        entry: CatalogEntry,
        *,
        ai_preference: bool,
    ) -> CatalogEntryTarget | None:
        """Resolve the concrete target representing one logical entry."""

        by_variant: dict[str, CatalogEntryTarget] = {}

        for target in entry.targets:
            if target.variant in by_variant:
                raise WorkflowQuestionnaireTargetConflictError(
                    "Catalog entry contains duplicate target variants: "
                    f"{entry.catalog_key}/{entry.entry_key}."
                )

            by_variant[target.variant] = target

        base = by_variant.get("base")
        no_ai = by_variant.get("no_ai")
        ai = by_variant.get("ai")

        if base is not None and (no_ai is not None or ai is not None):
            raise WorkflowQuestionnaireTargetConflictError(
                "Catalog entry mixes base and AI-variant targets: "
                f"{entry.catalog_key}/{entry.entry_key}."
            )

        if base is not None:
            return base if base.is_available else None

        target = ai if ai_preference else no_ai

        if target is None or not target.is_available:
            return None

        return target
