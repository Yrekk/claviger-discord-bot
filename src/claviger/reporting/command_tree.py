import logging

import discord
from discord import app_commands

from claviger.reporting.command_observability import CommandObservabilityService

logger = logging.getLogger(__name__)


class ClavigerCommandTree(app_commands.CommandTree):
    """Centralize application-command failure and completion observability.

    ``discord.py`` already exposes two stable lifecycle boundaries we care about:
    ``CommandTree.on_error`` for unhandled command errors and the client's
    ``on_app_command_completion`` event for commands that returned normally.
    Claviger uses this tree as the error boundary and lets ``ClavigerBot`` forward
    the completion event back here. This avoids command-by-command logging hooks.
    """

    def __init__(
        self,
        client: discord.Client,
    ) -> None:
        super().__init__(
            client,
        )

        # The client finishes composing repositories/reporting after the tree is
        # created. Resolve the service lazily on the first real command instead
        # of introducing a circular construction dependency in ClavigerBot.
        self._command_observability_service: CommandObservabilityService | None = None

    async def record_completion(
        self,
        interaction: discord.Interaction,
    ) -> None:
        """Record a completed command without turning reporting into a new failure."""

        try:
            await self._get_command_observability_service().record_completion(
                interaction,
            )

        except Exception:
            # Observability is intentionally best effort. A logging/reporting bug
            # must never change a command that already completed into a fake error.
            logger.exception(
                "Unable to record application-command completion."
            )

    async def on_error(
        self,
        interaction: discord.Interaction,
        error: app_commands.AppCommandError,
        /,
    ) -> None:
        """Separate expected rejections from unexpected command failures."""

        service = self._get_command_observability_service()

        if isinstance(
            error,
            app_commands.CheckFailure,
        ) and interaction.response.is_done():
            # A check that already answered the interaction performed a normal
            # rejection (for example ADMIN routing). discord.py represents that
            # False result as CheckFailure, but it is not an application error.
            try:
                await service.record_rejection(
                    interaction,
                    error,
                )

            except Exception:
                logger.exception(
                    "Unable to record expected application-command rejection."
                )

            return

        try:
            await service.record_failure(
                interaction,
                error,
            )

        except Exception:
            # Preserve the original failure even if observability itself breaks.
            underlying_error = CommandObservabilityService._unwrap_error(
                error,
            )

            logger.error(
                "Unhandled application-command error and reporting failure.",
                exc_info=(
                    type(underlying_error),
                    underlying_error,
                    underlying_error.__traceback__,
                ),
            )

        await self._send_unexpected_error_response(
            interaction,
        )

    def _get_command_observability_service(
        self,
    ) -> CommandObservabilityService:
        """Lazily bind observability to the fully composed Claviger runtime."""

        if self._command_observability_service is not None:
            return self._command_observability_service

        report_service = getattr(
            self.client,
            "report_service",
            None,
        )

        admin_configuration_repository = getattr(
            self.client,
            "guild_admin_configuration_repository",
            None,
        )

        if report_service is None or admin_configuration_repository is None:
            raise RuntimeError(
                "Command observability requires the completed Claviger runtime."
            )

        self._command_observability_service = CommandObservabilityService(
            report_service=report_service,
            admin_configuration_repository=admin_configuration_repository,
        )

        return self._command_observability_service

    @staticmethod
    async def _send_unexpected_error_response(
        interaction: discord.Interaction,
    ) -> None:
        """Give the user deterministic feedback for an uncaught command error."""

        message = (
            "Une erreur inattendue est survenue pendant l'exécution de la commande. "
            "L'incident a été journalisé."
        )

        try:
            if interaction.response.is_done():
                await interaction.followup.send(
                    message,
                    ephemeral=True,
                )
                return

            await interaction.response.send_message(
                message,
                ephemeral=True,
            )

        except discord.HTTPException:
            # The command failure is already recorded. Losing the Discord error
            # acknowledgement must not hide or replace the original traceback.
            logger.warning(
                "Unable to send application-command failure acknowledgement."
            )
