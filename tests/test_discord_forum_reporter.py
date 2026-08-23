from unittest.mock import AsyncMock, Mock

from attrs import fields
import discord
import pytest

from claviger.reporting.discord_forum import (
    DiscordForumReporter,
)
from claviger.reporting.event import (
    ReportEvent,
    ReportSeverity,
)


FORUM_ID = 123


def create_client() -> Mock:
    """Create a mocked Discord client."""
    client = Mock(
        spec=discord.Client,
    )

    client.get_channel = Mock()
    client.fetch_channel = AsyncMock()

    return client


def create_forum() -> Mock:
    """Create a mocked Discord forum channel."""
    forum = Mock(
        spec=discord.ForumChannel,
    )

    forum.create_thread = AsyncMock()

    return forum


def create_event() -> ReportEvent:
    """Create a structured report used by Discord reporter tests."""
    return ReportEvent(
        event_type="database.initialize.failed",
        severity=ReportSeverity.ERROR,
        title="Database initialization failed",
        summary="SQLite could not be initialized.",
        details="Permission denied.",
        guild_id=123,
        guild_label="Succumbrae Atrium",
        actor_id=456,
        actor_label="Yrekk",
    )


@pytest.mark.asyncio
async def test_discord_reporter_uses_cached_forum() -> None:
    """Publish reports using the cached forum when available."""
    client = create_client()
    forum = create_forum()

    client.get_channel.return_value = forum

    reporter = DiscordForumReporter(
        client,
        FORUM_ID,
    )

    await reporter.report(
        create_event(),
    )

    client.get_channel.assert_called_once_with(
        FORUM_ID,
    )

    client.fetch_channel.assert_not_awaited()
    forum.create_thread.assert_awaited_once()


@pytest.mark.asyncio
async def test_discord_reporter_fetches_uncached_forum() -> None:
    """Fetch the configured forum when it is not available in cache."""
    client = create_client()
    forum = create_forum()

    client.get_channel.return_value = None
    client.fetch_channel.return_value = forum

    reporter = DiscordForumReporter(
        client,
        FORUM_ID,
    )

    await reporter.report(
        create_event(),
    )

    client.fetch_channel.assert_awaited_once_with(
        FORUM_ID,
    )

    forum.create_thread.assert_awaited_once()


@pytest.mark.asyncio
async def test_discord_reporter_rejects_non_forum_channel() -> None:
    """Reject a configured report destination that is not a forum."""
    client = create_client()

    text_channel = Mock(
        spec=discord.TextChannel,
    )

    client.get_channel.return_value = text_channel

    reporter = DiscordForumReporter(
        client,
        FORUM_ID,
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
    forum = create_forum()

    client.get_channel.return_value = forum

    reporter = DiscordForumReporter(
        client,
        FORUM_ID,
    )

    event = create_event()

    await reporter.report(
        event,
    )

    call = forum.create_thread.await_args

    assert call.kwargs["name"] == (
        "[ERROR] Database initialization failed"
    )

    embed = call.kwargs["embed"]

    assert embed.title == event.title
    assert embed.description == event.summary
    assert embed.timestamp == event.occurred_at

    fields = {
        field.name: field.value
        for field in embed.fields
    }

    assert fields["Événement"] == (
        "`database.initialize.failed`"
    )
    assert fields["Sévérité"] == "ERROR"
    assert fields["Serveur"] == event.guild_label
    assert fields["Acteur"] == event.actor_label
    assert fields["Détails"] == event.details

    assert "Guild" not in fields