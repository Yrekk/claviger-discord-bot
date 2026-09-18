from unittest.mock import AsyncMock, Mock

import discord
import pytest

from claviger.models.admin.guild_admin_configuration_model import (
    GuildAdminConfiguration,
)
from claviger.reporting.discord_bootstrap_dm import DiscordBootstrapDMReporter
from claviger.reporting.event import (
    ReportEvent,
    ReportSeverity,
)
from claviger.reporting.reporter import ReporterUnavailableError
from claviger.repositories.admin.guild_admin_configuration_repository import (
    GuildAdminConfigurationRepository,
)


def _event(
    *,
    severity: ReportSeverity = ReportSeverity.ERROR,
    actor_id: int | None = 42,
) -> ReportEvent:
    """Create one actor-scoped bootstrap incident."""

    return ReportEvent(
        event_type="admin.configuration.failed",
        severity=severity,
        title="Configuration ADMIN impossible",
        summary="La permission Gérer les salons est manquante.",
        details="AdminStructureProvisioningPermissionError",
        guild_id=123,
        guild_label="Laboratorium",
        actor_id=actor_id,
        actor_label="Yrekk",
    )


def _client() -> Mock:
    """Create one deterministic Discord client and DM target."""

    client = Mock(
        spec=discord.Client,
    )
    user = Mock(
        spec=discord.User,
    )
    user.send = AsyncMock()

    client.get_user.return_value = user
    client.fetch_user = AsyncMock(
        return_value=user,
    )

    return client


def _repository() -> Mock:
    """Create one ADMIN routing repository mock."""

    repository = Mock(
        spec=GuildAdminConfigurationRepository,
    )
    repository.get = AsyncMock(
        return_value=None,
    )

    return repository


@pytest.mark.asyncio
async def test_bootstrap_dm_sends_incident_when_admin_is_missing() -> None:
    """Deliver bootstrap incidents directly while no ADMIN routing exists."""

    client = _client()
    repository = _repository()
    reporter = DiscordBootstrapDMReporter(
        client=client,
        repository=repository,
    )
    event = _event()

    await reporter.report(
        event,
    )

    repository.get.assert_awaited_once_with(
        123,
    )
    client.get_user.assert_called_once_with(
        42,
    )
    client.fetch_user.assert_not_awaited()

    user = client.get_user.return_value
    user.send.assert_awaited_once()

    embed = user.send.await_args.kwargs["embed"]

    assert embed.title == event.title
    assert embed.description == event.summary
    assert embed.footer.text == "Claviger · Incident de bootstrap"


@pytest.mark.asyncio
async def test_bootstrap_dm_skips_when_admin_routing_is_complete() -> None:
    """Stop actor DMs as soon as normal ADMIN reporting is operational."""

    client = _client()
    repository = _repository()
    repository.get.return_value = GuildAdminConfiguration(
        guild_id=123,
        category_id=100,
        command_channel_id=200,
        activity_forum_id=201,
        error_forum_id=202,
    )

    reporter = DiscordBootstrapDMReporter(
        client=client,
        repository=repository,
    )

    await reporter.report(
        _event(),
    )

    repository.get.assert_awaited_once_with(
        123,
    )
    client.get_user.assert_not_called()


@pytest.mark.asyncio
async def test_bootstrap_dm_silently_ignores_info_events() -> None:
    """Treat normal INFO traffic as non-applicable without warning noise."""

    client = _client()
    repository = _repository()
    reporter = DiscordBootstrapDMReporter(
        client=client,
        repository=repository,
    )

    await reporter.report(
        _event(
            severity=ReportSeverity.INFO,
        )
    )

    repository.get.assert_not_awaited()
    client.get_user.assert_not_called()


@pytest.mark.asyncio
async def test_bootstrap_dm_rejects_actorless_incidents() -> None:
    """Keep genuinely unroutable bootstrap incidents observable."""

    client = _client()
    repository = _repository()
    reporter = DiscordBootstrapDMReporter(
        client=client,
        repository=repository,
    )

    with pytest.raises(
        ReporterUnavailableError,
        match="actor-scoped",
    ):
        await reporter.report(
            _event(
                actor_id=None,
            )
        )

    client.get_user.assert_not_called()
