from unittest.mock import AsyncMock, Mock

import discord
import pytest

from claviger.reporting.command_observability import CommandObservabilityService
from claviger.reporting.command_tree import ClavigerCommandTree

pytestmark = pytest.mark.asyncio


def _tree() -> tuple[discord.Client, ClavigerCommandTree, Mock]:
    """Create a command tree with deterministic observability."""

    client = discord.Client(intents=discord.Intents.none())
    tree = ClavigerCommandTree(client)
    service = Mock(spec=CommandObservabilityService)
    service.record_completion = AsyncMock()
    service.record_rejection = AsyncMock()
    service.record_failure = AsyncMock()
    tree._command_observability_service = service
    return client, tree, service


async def test_deferred_action_runs_only_after_observability() -> None:
    """Execute lifecycle work only after the command completion was recorded."""

    client, tree, service = _tree()
    events: list[str] = []

    async def record_completion(interaction) -> None:
        events.append("observability")

    async def deferred_action() -> None:
        events.append("deferred")

    service.record_completion.side_effect = record_completion
    callback = AsyncMock(side_effect=deferred_action)
    interaction = Mock(spec=discord.Interaction)
    interaction.token = "restart-token"

    tree.defer_until_completion("restart-token", callback)
    await tree.record_completion(interaction)

    assert events == ["observability", "deferred"]
    callback.assert_awaited_once_with()

    await client.close()


async def test_deferred_action_is_bound_to_exact_interaction_token() -> None:
    """Never execute one command's deferred action for another completion event."""

    client, tree, _ = _tree()
    callback = AsyncMock()
    other = Mock(spec=discord.Interaction)
    other.token = "other-token"
    matching = Mock(spec=discord.Interaction)
    matching.token = "restart-token"

    tree.defer_until_completion("restart-token", callback)

    await tree.record_completion(other)
    callback.assert_not_awaited()

    await tree.record_completion(matching)
    callback.assert_awaited_once_with()

    await client.close()
