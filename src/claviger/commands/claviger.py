import discord
from discord import app_commands

from claviger.services.role_discovery import RoleDiscoveryService


def create_claviger_group(
    role_discovery_service: RoleDiscoveryService,
) -> app_commands.Group:
    """Create Claviger's administrative command group."""

    claviger_group = app_commands.Group(
        name="claviger",
        description="Commandes d'administration de Claviger.",
    )

    roles_group = app_commands.Group(
        name="roles",
        description="Analyse et gestion des rôles Discord.",
    )

    @roles_group.command(
        name="scan",
        description="Analyse la hiérarchie actuelle des rôles du serveur.",
    )
    async def scan_roles(
        interaction: discord.Interaction,
    ) -> None:
        if interaction.guild is None:
            await interaction.response.send_message(
                "Cette commande doit être utilisée sur un serveur.",
                ephemeral=True,
            )
            return

        if interaction.user.id != interaction.guild.owner_id:
            await interaction.response.send_message(
                "Cette commande est réservée au propriétaire du serveur.",
                ephemeral=True,
            )
            return

        await interaction.response.defer(
            ephemeral=True,
        )

        try:
            hierarchy = await role_discovery_service.get_hierarchy(
                interaction.guild,
            )
        except RuntimeError as error:
            await interaction.followup.send(
                f"Impossible d'analyser les rôles : {error}",
                ephemeral=True,
            )
            return

        lines = [
            f"**Rôle de Claviger :** {hierarchy.bot_role.name}",
            "",
            f"**Rôles au-dessus ({len(hierarchy.trusted_roles)})**",
        ]

        if hierarchy.trusted_roles:
            lines.extend(
                f"- {role.name} (position {role.position})"
                for role in hierarchy.trusted_roles
            )
        else:
            lines.append("- Aucun")

        lines.extend(
            [
                "",
                f"**Rôles en dessous ({len(hierarchy.manageable_roles)})**",
            ]
        )

        if hierarchy.manageable_roles:
            lines.extend(
                f"- {role.name} (position {role.position})"
                for role in hierarchy.manageable_roles
            )
        else:
            lines.append("- Aucun")

        await interaction.followup.send(
            "\n".join(lines),
            ephemeral=True,
        )

    claviger_group.add_command(
        roles_group,
    )

    return claviger_group