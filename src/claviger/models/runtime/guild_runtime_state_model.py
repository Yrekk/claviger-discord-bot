from dataclasses import dataclass

from claviger.models.runtime.discord_guild_identity_model import (
    DiscordGuildIdentity,
)
from claviger.models.runtime.guild_configuration_readiness_model import (
    GuildConfigurationReadiness,
)


@dataclass(frozen=True, slots=True)
class GuildRuntimeState:
    """Describe the configured runtime state of one Discord guild.

    The state is deliberately guild-scoped. Application-wide concerns such as
    Discord application identity and database lifecycle state must remain
    outside this model so several guilds can safely share one application
    runtime and one database.

    Attributes:
        identity:
            Discord identity resolved specifically for this guild.

        readiness:
            Persisted ADMIN configuration readiness for this guild. ``None``
            means readiness was intentionally not inspected, typically because
            the application database was not operational.

        command_tree_signature:
            Deterministic signature of the local application-command tree built
            for this guild.
    """

    identity: DiscordGuildIdentity
    readiness: GuildConfigurationReadiness | None
    command_tree_signature: str
