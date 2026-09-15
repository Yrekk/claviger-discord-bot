from unittest.mock import AsyncMock, Mock

import discord
import pytest
from discord import app_commands

from claviger.reporting.command_observability import CommandObservabilityService
from claviger.reporting.command_tree import ClavigerCommandTree

pytestmark = pytest.mark.asyncio


def _tree() -> tuple[discord.Client, ClavigerCommandTree, Mock]:
    """Create one command tree with an injected observability service."""

    client = discord.Client(
        intents=discord.Intents.none(),
    )

    tree = ClavigerCommandTree(
        client,
    )

    service = Mock(
        spec=CommandObservabilityService,
    )
    service.record_completion = AsyncMock()
    service.record_rejection = AsyncMock()
    service.record_failure = AsyncMock()

    tree._command_observability_service = service

    return client, tree, service


def _interaction(
    *,
    response_done: bool,
) -> Mock:
    """Create one deterministic interaction for command-tree tests."""

    interaction = Mock(
        spec=discord.Interaction,
    )

    interaction.response = Mock()
    interaction.response.is_done = Mock(
        return_value=response_done,
    )
    interaction.response.send_message = AsyncMock()

    interaction.followup = Mock()
    interaction.followup.send = AsyncMock()

    return interaction


async def test_tree_records_completed_command() -> None:
    """Forward discord.py's completion event into structured observability."""

    client, tree, service = _tree()
    interaction = _interaction(
        response_done=True,
    )

    await tree.record_completion(
        interaction,
    )

    service.record_completion.assert_awaited_once_with(
        interaction,
    )

    await client.close()


async def test_answered_check_failure_is_expected_rejection() -> None:
    """Suppress discord.py's default traceback for a rejection already explained."""

    client, tree, service = _tree()
    interaction = _interaction(
        response_done=True,
    )

    error = app_commands.CheckFailure(
        "normal rejection",
    )

    await tree.on_error(
        interaction,
        error,
    )

    service.record_rejection.assert_awaited_once_with(
        interaction,
        error,
    )
    service.record_failure.assert_not_awaited()
    interaction.followup.send.assert_not_awaited()

    await client.close()


async def test_unanswered_check_failure_remains_an_error() -> None:
    """Never hide a check failure that failed to explain itself to the user."""

    client, tree, service = _tree()
    interaction = _interaction(
        response_done=False,
    )

    error = app_commands.CheckFailure(
        "silent rejection",
    )

    await tree.on_error(
        interaction,
        error,
    )

    service.record_rejection.assert_not_awaited()
    service.record_failure.assert_awaited_once_with(
        interaction,
        error,
    )
    interaction.response.send_message.assert_awaited_once()

    await client.close()
