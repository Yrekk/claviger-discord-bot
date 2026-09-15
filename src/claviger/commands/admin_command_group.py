import logging
from collections.abc import Awaitable, Callable

import discord
from discord import app_commands

from claviger.models.admin_configuration_inspection_model import (
    AdminConfigurationInspectionResult,
)

logger = logging.getLogger(__name__)

RECOVERY_COMMAND_NAMES = frozenset(
    {
        "database",
        "restart",
        "config-server",
    }
)

AdminRoutingInspector = Callable[
    [discord.Guild],
    Awaitable[AdminConfigurationInspectionResult],
]


class GuildAdminCommandGroup(app_commands.Group):
    """Route ADMIN commands through the guild's current ADMIN configuration."""

    def __init__(
        self,
        *,
        name: str,
        description: str,
        routing_inspector: AdminRoutingInspector | None = None,
    ) -> None:
        super().__init__(
            name=name,
            description=description,
        )

        self.routing_inspector = routing_inspector

    def add_command(
        self,
        command: app_commands.Command | app_commands.Group,
        /,
        *,
        override: bool = False,
    ) -> None:
        """Register a child and propagate the ADMIN guard to nested commands."""

        super().add_command(
            command,
            override=override,
        )

        # discord.py calls only the immediate parent group's interaction_check
        # for nested commands. Descendant checks deliberately bridge that gap so
        # every /{bot} <group> <command> path still reaches this central guard.
        if isinstance(
            command,
            app_commands.Group,
        ):
            self._attach_descendant_routing_checks(
                command,
            )

    def _attach_descendant_routing_checks(
        self,
        group: app_commands.Group,
    ) -> None:
        """Attach the central ADMIN guard to every invokable descendant command."""

        for child in group.commands:
            if isinstance(
                child,
                app_commands.Group,
            ):
                self._attach_descendant_routing_checks(
                    child,
                )
                continue

            child.add_check(
                self._check_descendant_interaction,
            )

    async def _check_descendant_interaction(
        self,
        interaction: discord.Interaction,
    ) -> bool:
        """Delegate nested command checks to the root ADMIN routing guard."""

        return await self.interaction_check(
            interaction,
        )

    async def interaction_check(
        self,
        interaction: discord.Interaction,
    ) -> bool:
        """Restrict healthy ADMIN routing and expose recovery paths only on drift."""

        if interaction.guild is None:
            await interaction.response.send_message(
                "Cette commande doit être utilisée sur un serveur.",
                ephemeral=True,
            )
            return False

        root_child_name = self._resolve_root_child_name(
            interaction,
        )

        inspection = await self._inspect_routing(
            interaction.guild,
        )

        if inspection is not None and inspection.is_routing_ready:
            command_channel_id = inspection.command_channel_id

            if command_channel_id is None:
                logger.error(
                    "ADMIN routing inspection reported ready without command channel "
                    "for guild %s.",
                    interaction.guild.id,
                )
                return False

            if interaction.channel_id == command_channel_id:
                return True

            await interaction.response.send_message(
                (
                    "Cette commande administrative doit être utilisée dans "
                    f"<#{command_channel_id}>."
                ),
                ephemeral=True,
            )
            return False

        if root_child_name in RECOVERY_COMMAND_NAMES:
            return True

        await interaction.response.send_message(
            (
                "La configuration ADMIN de ce serveur est absente, incomplète "
                "ou ne correspond plus à Discord. "
                f"Utilise `/{self.name} config-server` pour la réparer."
            ),
            ephemeral=True,
        )

        return False

    async def _inspect_routing(
        self,
        guild: discord.Guild,
    ) -> AdminConfigurationInspectionResult | None:
        """Return fresh ADMIN routing state or fall back to recovery mode safely."""

        if self.routing_inspector is None:
            return None

        try:
            return await self.routing_inspector(
                guild,
            )

        except Exception:
            # Routing inspection is a safety boundary. An unexpected DB or
            # Discord read failure must never leave normal ADMIN commands open.
            # Recovery commands stay reachable so the owner can diagnose/repair.
            logger.exception(
                "Unable to inspect ADMIN routing for guild %s.",
                guild.id,
            )
            return None

    def _resolve_root_child_name(
        self,
        interaction: discord.Interaction,
    ) -> str | None:
        """Resolve the first command directly below this ADMIN root group."""

        root_child = interaction.command

        while (
            root_child is not None and getattr(root_child, "parent", None) is not self
        ):
            root_child = getattr(
                root_child,
                "parent",
                None,
            )

        if root_child is None:
            return None

        return getattr(
            root_child,
            "name",
            None,
        )
