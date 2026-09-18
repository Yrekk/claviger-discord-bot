# Standard library
from pathlib import Path

# Runtime
from claviger import bot as bot_module
from claviger.bot import ClavigerBot


def _patch_runtime_configuration(
    monkeypatch,
    tmp_path: Path,
) -> None:
    """Provide deterministic environment-backed configuration for composition tests."""

    # Claviger keeps the historical guild ID only as a policy/bootstrap anchor.
    # Runtime guild selection remains event-driven and is not derived from it.
    monkeypatch.setattr(
        bot_module,
        "get_discord_guild_id",
        lambda: 123,
    )

    monkeypatch.setattr(
        bot_module,
        "get_discord_bot_user_id",
        lambda: 456,
    )

    monkeypatch.setattr(
        bot_module,
        "get_database_path",
        lambda: tmp_path / "claviger.db",
    )


def test_bot_composes_shared_workflow_configuration_pipeline(
    monkeypatch,
    tmp_path: Path,
) -> None:
    """Keep every workflow configuration layer wired through one application graph."""

    _patch_runtime_configuration(
        monkeypatch,
        tmp_path,
    )

    bot = ClavigerBot()

    # Persistence belongs to the shared application database and is not owned by
    # the Discord UI. Future frontends must therefore reuse this same repository.
    assert bot.workflow_configuration_repository is not None
    assert bot.workflow_definition_repository is not None
    assert bot.workflow_configuration_inspection_service is not None

    # Validation, discovery, reconciliation and provisioning stay explicit. This
    # prevents Discord components from quietly accumulating domain behavior.
    assert bot.workflow_configuration_validation_service is not None
    assert bot.workflow_structure_discovery_service is not None
    assert bot.workflow_configuration_reconciliation_service is not None
    assert bot.workflow_structure_provisioning_service is not None
    assert bot.workflow_configuration_coordinator_service is not None

    coordinator = bot.workflow_configuration_coordinator_service

    assert coordinator.repository is bot.workflow_configuration_repository
    assert (
        coordinator.validation_service
        is bot.workflow_configuration_validation_service
    )
    assert (
        coordinator.discovery_service
        is bot.workflow_structure_discovery_service
    )
    assert (
        coordinator.inspection_service
        is bot.workflow_configuration_inspection_service
    )
    assert (
        coordinator.reconciliation_service
        is bot.workflow_configuration_reconciliation_service
    )
    assert (
        coordinator.provisioning_service
        is bot.workflow_structure_provisioning_service
    )

    # Role hierarchy rules must remain centralized. Both observation and mutation
    # depend on the same RoleDiscoveryService instead of inventing local variants.
    assert (
        bot.workflow_structure_discovery_service.role_discovery_service
        is bot.role_discovery_service
    )
    assert (
        bot.workflow_structure_provisioning_service.role_discovery_service
        is bot.role_discovery_service
    )
    assert (
        bot.workflow_structure_provisioning_service.inspection_service
        is bot.workflow_configuration_inspection_service
    )



def test_bot_composes_generic_questionnaire_runtime(
    monkeypatch,
    tmp_path: Path,
) -> None:
    """Keep generic questionnaire planning and execution in the application graph."""

    _patch_runtime_configuration(
        monkeypatch,
        tmp_path,
    )

    bot = ClavigerBot()

    assert bot.catalog_entry_repository is not None
    assert bot.role_manager_service is not None
    assert bot.workflow_questionnaire_planner_service is not None
    assert bot.workflow_role_planner_service is not None
    assert bot.workflow_role_executor_service is not None
    assert bot.workflow_questionnaire_coordinator_service is not None

    coordinator = bot.workflow_questionnaire_coordinator_service

    assert coordinator.workflow_repository is bot.workflow_definition_repository
    assert coordinator.catalog_entry_repository is bot.catalog_entry_repository
    assert coordinator.ai_repository is bot.guild_ai_configuration_repository
    assert (
        coordinator.owner_repository
        is bot.guild_ai_questionnaire_owner_repository
    )
    assert (
        coordinator.questionnaire_planner
        is bot.workflow_questionnaire_planner_service
    )
    assert coordinator.role_planner is bot.workflow_role_planner_service
    assert coordinator.role_executor is bot.workflow_role_executor_service
