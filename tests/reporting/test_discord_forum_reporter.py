from unittest.mock import AsyncMock, Mock

import discord
import pytest

from claviger.models.admin.guild_admin_configuration_model import (
    GuildAdminConfiguration,
)
from claviger.reporting.discord_forum import (
    DiscordForumReporter,
)
from claviger.reporting.event import (
    ReportEvent,
    ReportSeverity,
)
from claviger.repositories.admin.guild_admin_configuration_repository import (
    GuildAdminConfigurationRepository,
)

GUILD_ID = 123
ACTIVITY_FORUM_ID = 1002
ERROR_FORUM_ID = 1003


def create_client() -> Mock:
    """Create a mocked Discord client."""

    client = Mock(
        spec=discord.Client,
    )

    client.get_channel = Mock()
    client.fetch_channel = AsyncMock()

    return client


def create_repository() -> Mock:
    """Create a mocked guild ADMIN configuration repository."""

    repository = Mock(
        spec=GuildAdminConfigurationRepository,
    )

    repository.get = AsyncMock()

    return repository


def create_forum() -> Mock:
    """Create a mocked Discord forum channel."""

    forum = Mock(
        spec=discord.ForumChannel,
    )

    forum.create_thread = AsyncMock()

    return forum


def create_configuration(
    *,
    guild_id: int = GUILD_ID,
    activity_forum_id: int = ACTIVITY_FORUM_ID,
    error_forum_id: int | None = ERROR_FORUM_ID,
) -> GuildAdminConfiguration:
    """Create deterministic guild-specific ADMIN routing."""

    return GuildAdminConfiguration(
        guild_id=guild_id,
        category_id=1000,
        command_channel_id=1001,
        activity_forum_id=activity_forum_id,
        error_forum_id=error_forum_id,
    )


def create_event(
    *,
    severity: ReportSeverity = ReportSeverity.ERROR,
    guild_id: int | None = GUILD_ID,
) -> ReportEvent:
    """Create a structured report used by Discord reporter tests."""

    return ReportEvent(
        event_type="database.initialize.failed",
        severity=severity,
        title="Database initialization failed",
        summary="SQLite could not be initialized.",
        details="Permission denied.",
        guild_id=guild_id,
        guild_label="Succumbrae Atrium",
        actor_id=456,
        actor_label="Yrekk",
    )


@pytest.mark.asyncio
async def test_discord_reporter_routes_info_to_guild_activity_forum() -> None:
    """Route normal activity to the emitting guild's activity forum."""

    client = create_client()
    repository = create_repository()
    forum = create_forum()

    repository.get.return_value = create_configuration()
    client.get_channel.return_value = forum

    reporter = DiscordForumReporter(
        client=client,
        repository=repository,
    )

    await reporter.report(
        create_event(
            severity=ReportSeverity.INFO,
        )
    )

    repository.get.assert_awaited_once_with(
        GUILD_ID,
    )

    client.get_channel.assert_called_once_with(
        ACTIVITY_FORUM_ID,
    )

    client.fetch_channel.assert_not_awaited()
    forum.create_thread.assert_awaited_once()


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "severity",
    [
        ReportSeverity.WARNING,
        ReportSeverity.ERROR,
        ReportSeverity.CRITICAL,
    ],
)
async def test_discord_reporter_routes_incidents_to_guild_error_forum(
    severity: ReportSeverity,
) -> None:
    """Route every incident severity to the emitting guild's error forum."""

    client = create_client()
    repository = create_repository()
    forum = create_forum()

    repository.get.return_value = create_configuration()
    client.get_channel.return_value = forum

    reporter = DiscordForumReporter(
        client=client,
        repository=repository,
    )

    await reporter.report(
        create_event(
            severity=severity,
        )
    )

    repository.get.assert_awaited_once_with(
        GUILD_ID,
    )

    client.get_channel.assert_called_once_with(
        ERROR_FORUM_ID,
    )

    forum.create_thread.assert_awaited_once()


@pytest.mark.asyncio
async def test_discord_reporter_uses_configuration_of_event_guild() -> None:
    """Never reuse another guild's administrative report destination."""

    client = create_client()
    repository = create_repository()
    forum = create_forum()

    other_guild_id = 999
    other_error_forum_id = 9994

    repository.get.return_value = create_configuration(
        guild_id=other_guild_id,
        activity_forum_id=9993,
        error_forum_id=other_error_forum_id,
    )

    client.get_channel.return_value = forum

    reporter = DiscordForumReporter(
        client=client,
        repository=repository,
    )

    await reporter.report(
        create_event(
            guild_id=other_guild_id,
        )
    )

    repository.get.assert_awaited_once_with(
        other_guild_id,
    )

    client.get_channel.assert_called_once_with(
        other_error_forum_id,
    )


@pytest.mark.asyncio
async def test_discord_reporter_fetches_uncached_forum() -> None:
    """Fetch the guild-selected forum when it is not available in cache."""

    client = create_client()
    repository = create_repository()
    forum = create_forum()

    repository.get.return_value = create_configuration()
    client.get_channel.return_value = None
    client.fetch_channel.return_value = forum

    reporter = DiscordForumReporter(
        client=client,
        repository=repository,
    )

    await reporter.report(
        create_event(),
    )

    client.fetch_channel.assert_awaited_once_with(
        ERROR_FORUM_ID,
    )

    forum.create_thread.assert_awaited_once()


@pytest.mark.asyncio
async def test_discord_reporter_rejects_event_without_guild() -> None:
    """Reject Discord routing when the report has no guild context."""

    client = create_client()
    repository = create_repository()

    reporter = DiscordForumReporter(
        client=client,
        repository=repository,
    )

    with pytest.raises(
        RuntimeError,
        match="requires a guild-scoped ReportEvent",
    ):
        await reporter.report(
            create_event(
                guild_id=None,
            )
        )

    repository.get.assert_not_awaited()
    client.get_channel.assert_not_called()


@pytest.mark.asyncio
async def test_discord_reporter_rejects_unconfigured_guild() -> None:
    """Reject Discord routing when the guild has no persisted ADMIN config."""

    client = create_client()
    repository = create_repository()

    repository.get.return_value = None

    reporter = DiscordForumReporter(
        client=client,
        repository=repository,
    )

    with pytest.raises(
        RuntimeError,
        match="has no ADMIN configuration",
    ):
        await reporter.report(
            create_event(),
        )

    repository.get.assert_awaited_once_with(
        GUILD_ID,
    )

    client.get_channel.assert_not_called()


@pytest.mark.asyncio
async def test_discord_reporter_rejects_incident_without_error_forum() -> None:
    """Fail closed when incident routing is incomplete for the event guild."""

    client = create_client()
    repository = create_repository()

    repository.get.return_value = create_configuration(
        error_forum_id=None,
    )

    reporter = DiscordForumReporter(
        client=client,
        repository=repository,
    )

    with pytest.raises(
        RuntimeError,
        match="has no error forum configured",
    ):
        await reporter.report(
            create_event(
                severity=ReportSeverity.ERROR,
            )
        )

    client.get_channel.assert_not_called()


@pytest.mark.asyncio
async def test_discord_reporter_rejects_non_forum_channel() -> None:
    """Reject a guild report destination that is not a Discord forum."""

    client = create_client()
    repository = create_repository()

    text_channel = Mock(
        spec=discord.TextChannel,
    )

    repository.get.return_value = create_configuration()
    client.get_channel.return_value = text_channel

    reporter = DiscordForumReporter(
        client=client,
        repository=repository,
    )

    with pytest.raises(
        RuntimeError,
        match="is not a Discord forum",
    ):
        await reporter.report(
            create_event(),
        )


@pytest.mark.asyncio
async def test_discord_reporter_builds_structured_embed() -> None:
    """Publish event information in a structured Discord embed."""

    client = create_client()
    repository = create_repository()
    forum = create_forum()

    repository.get.return_value = create_configuration()
    client.get_channel.return_value = forum

    reporter = DiscordForumReporter(
        client=client,
        repository=repository,
    )

    event = create_event()

    await reporter.report(
        event,
    )

    call = forum.create_thread.await_args

    assert call.kwargs["name"] == ("[ERROR] Database initialization failed")

    embed = call.kwargs["embed"]

    assert embed.title == event.title
    assert embed.description == event.summary
    assert embed.timestamp == event.occurred_at

    fields = {
        field.name: field.value
        for field in embed.fields
    }

    assert fields["Événement"] == ("`database.initialize.failed`")
    assert fields["Sévérité"] == "ERROR"
    assert fields["Serveur"] == event.guild_label
    assert fields["Acteur"] == event.actor_label
    assert fields["Détails"] == event.details

    assert "Guild" not in fields
