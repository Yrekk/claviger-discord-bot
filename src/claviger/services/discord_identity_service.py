"""Compatibility import for the canonical Discord identity service."""

from claviger.services.runtime.discord_identity_service import (
    DiscordIdentityService,
    InvalidApplicationCommandNameError,
    normalize_application_command_name,
)

__all__ = [
    "DiscordIdentityService",
    "InvalidApplicationCommandNameError",
    "normalize_application_command_name",
]
