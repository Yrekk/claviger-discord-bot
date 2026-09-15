import traceback
from collections.abc import Mapping, Sequence
from typing import Any

import discord
from discord import app_commands
from discord.enums import AppCommandOptionType

from claviger.database.connection import DatabaseUnavailableError
from claviger.reporting.event import ReportEvent, ReportSeverity
from claviger.reporting.python_logger import PythonLoggingReporter
from claviger.reporting.service import ReportService
from claviger.repositories.guild_admin_configuration_repository import (
    GuildAdminConfigurationRepository,
)

_SUBCOMMAND_OPTION_TYPES = frozenset(
    {
        AppCommandOptionType.subcommand.value,
        AppCommandOptionType.subcommand_group.value,
    }
)


class CommandObservabilityService:
    """Record application-command activity without exposing command arguments.

    Command observability deliberately records command identity and execution
    context, not raw option values. Arguments may contain messages, prompts,
    secrets or other user content that does not belong in operational logs.

    Discord reporting is best effort. When a guild has no ADMIN configuration
    yet, command activity is still written to Python logging without generating
    a noisy reporter-unavailable warning for an expected bootstrap state.
    """

    def __init__(
        self,
        *,
        report_service: ReportService,
        admin_configuration_repository: GuildAdminConfigurationRepository,
        local_reporter: PythonLoggingReporter | None = None,
    ) -> None:
        self.report_service = report_service
        self.admin_configuration_repository = admin_configuration_repository
        self.local_reporter = local_reporter or PythonLoggingReporter()

    async def record_completion(
        self,
        interaction: discord.Interaction,
    ) -> None:
        """Record one command that returned without an unhandled exception."""

        command_path = self._resolve_command_path(
            interaction,
        )

        await self._emit(
            self._build_event(
                interaction=interaction,
                event_type="command.completed",
                severity=ReportSeverity.INFO,
                title="Commande traitée",
                summary=f"{command_path} a été traitée.",
                details=(
                    self._build_context_details(
                        interaction,
                        command_path=command_path,
                    )
                    + "\nRésultat : interaction terminée sans erreur non gérée."
                ),
            )
        )

    async def record_rejection(
        self,
        interaction: discord.Interaction,
        error: app_commands.CheckFailure,
    ) -> None:
        """Record an expected command rejection already explained to the user."""

        command_path = self._resolve_command_path(
            interaction,
        )

        await self._emit(
            self._build_event(
                interaction=interaction,
                event_type="command.rejected",
                severity=ReportSeverity.INFO,
                title="Commande refusée",
                summary=(
                    f"{command_path} a été refusée par un contrôle applicatif."
                ),
                details=(
                    self._build_context_details(
                        interaction,
                        command_path=command_path,
                    )
                    + (
                        "\nRésultat : refus attendu, réponse utilisateur déjà "
                        "envoyée."
                    )
                ),
            )
        )

    async def record_failure(
        self,
        interaction: discord.Interaction,
        error: app_commands.AppCommandError,
    ) -> None:
        """Record an unexpected application-command failure with its traceback."""

        command_path = self._resolve_command_path(
            interaction,
        )

        underlying_error = self._unwrap_error(
            error,
        )

        formatted_traceback = "".join(
            traceback.format_exception(
                type(underlying_error),
                underlying_error,
                underlying_error.__traceback__,
            )
        ).rstrip()

        details = self._build_context_details(
            interaction,
            command_path=command_path,
        )

        details += (
            "\nRésultat : erreur non gérée."
            f"\nErreur : {type(underlying_error).__name__}: {underlying_error}"
        )

        if formatted_traceback:
            details += f"\n\nTraceback:\n{formatted_traceback}"

        await self._emit(
            self._build_event(
                interaction=interaction,
                event_type="command.failed",
                severity=ReportSeverity.ERROR,
                title="Erreur de commande",
                summary=f"{command_path} a échoué avec une erreur non gérée.",
                details=details,
            )
        )

    async def _emit(
        self,
        event: ReportEvent,
    ) -> None:
        """Route to console always and Discord only when ADMIN routing exists."""

        guild_id = event.guild_id

        if guild_id is None:
            await self.local_reporter.report(
                event,
            )
            return

        try:
            configuration = await self.admin_configuration_repository.get(
                guild_id,
            )

        except DatabaseUnavailableError:
            # Database maintenance and first-run states are legitimate moments to
            # use recovery commands. Losing Discord reporting must not hide the
            # local audit trace or prevent the command itself from running.
            await self.local_reporter.report(
                event,
            )
            return

        if configuration is None:
            # An unconfigured guild cannot have report-activity yet. This is an
            # expected state, not a reporter failure worth warning about.
            await self.local_reporter.report(
                event,
            )
            return

        await self.report_service.emit(
            event,
        )

    @staticmethod
    def _build_event(
        *,
        interaction: discord.Interaction,
        event_type: str,
        severity: ReportSeverity,
        title: str,
        summary: str,
        details: str,
    ) -> ReportEvent:
        """Build one guild- and actor-scoped command observability event."""

        guild = interaction.guild
        user = interaction.user

        return ReportEvent(
            event_type=event_type,
            severity=severity,
            title=title,
            summary=summary,
            details=details,
            guild_id=(guild.id if guild is not None else None),
            guild_label=(guild.name if guild is not None else None),
            actor_id=user.id,
            actor_label=CommandObservabilityService._resolve_actor_label(
                user,
            ),
        )

    @staticmethod
    def _build_context_details(
        interaction: discord.Interaction,
        *,
        command_path: str,
    ) -> str:
        """Describe command context without serializing arguments or payload data."""

        channel = interaction.channel
        channel_id = interaction.channel_id

        channel_name = getattr(
            channel,
            "name",
            None,
        )

        channel_label = (
            f"#{channel_name}"
            if isinstance(channel_name, str) and channel_name
            else "salon inconnu"
        )

        return (
            f"Commande : {command_path}\n"
            f"Salon : {channel_label} (id={channel_id})"
        )

    @classmethod
    def _resolve_command_path(
        cls,
        interaction: discord.Interaction,
    ) -> str:
        """Resolve slash/group/subcommand names while intentionally ignoring values."""

        data = interaction.data

        if not isinstance(
            data,
            Mapping,
        ):
            return "/commande-inconnue"

        root_name = data.get(
            "name",
        )

        if not isinstance(
            root_name,
            str,
        ) or not root_name:
            return "/commande-inconnue"

        parts = [
            root_name,
        ]

        options = data.get(
            "options",
        )

        while isinstance(
            options,
            Sequence,
        ) and not isinstance(
            options,
            (str, bytes),
        ):
            nested_option = next(
                (
                    option
                    for option in options
                    if isinstance(
                        option,
                        Mapping,
                    )
                    and option.get("type") in _SUBCOMMAND_OPTION_TYPES
                ),
                None,
            )

            if nested_option is None:
                break

            nested_name = nested_option.get(
                "name",
            )

            if not isinstance(
                nested_name,
                str,
            ) or not nested_name:
                break

            parts.append(
                nested_name,
            )

            options = nested_option.get(
                "options",
            )

        return "/" + " ".join(
            parts,
        )

    @staticmethod
    def _resolve_actor_label(
        user: discord.abc.User,
    ) -> str | None:
        """Return the most useful human-readable actor label available."""

        display_name = getattr(
            user,
            "display_name",
            None,
        )

        if isinstance(
            display_name,
            str,
        ) and display_name:
            return display_name

        name = getattr(
            user,
            "name",
            None,
        )

        if isinstance(
            name,
            str,
        ) and name:
            return name

        return None

    @staticmethod
    def _unwrap_error(
        error: app_commands.AppCommandError,
    ) -> BaseException:
        """Expose the original callback exception when discord.py wrapped it."""

        if isinstance(
            error,
            app_commands.CommandInvokeError,
        ):
            return error.original

        return error
