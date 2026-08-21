import discord
from discord import app_commands

from claviger.services.role_manager import RoleManager


def create_role_test_group(
    role_manager: RoleManager,
    role_id: int,
) -> app_commands.Group:
    """Create the temporary role integration-test command group."""

    group = app_commands.Group(
        name="role-test",
        description="Commandes temporaires de test pour la gestion des rôles.",
    )

    @group.command(
        name="add",
        description="Attribue le rôle de test à l'utilisateur.",
    )
    async def add_role(interaction: discord.Interaction) -> None:
        if interaction.guild is None:
            await interaction.response.send_message(
                "Cette commande doit être utilisée sur un serveur.",
                ephemeral=True,
            )
            return

        if interaction.user.id != interaction.guild.owner_id:
            await interaction.response.send_message(
                "Cette commande de test est réservée au propriétaire du serveur.",
                ephemeral=True,
            )
            return

        if not isinstance(interaction.user, discord.Member):
            await interaction.response.send_message(
                "Impossible de récupérer ton profil membre.",
                ephemeral=True,
            )
            return

        role = interaction.guild.get_role(role_id)

        if role is None:
            await interaction.response.send_message(
                "Le rôle de test configuré est introuvable.",
                ephemeral=True,
            )
            return

        changed = await role_manager.add_role(
            interaction.user,
            role,
            reason="Claviger role integration test",
        )

        if changed:
            message = f"Rôle **{role.name}** attribué."
        else:
            message = f"Tu possèdes déjà le rôle **{role.name}**."

        await interaction.response.send_message(
            message,
            ephemeral=True,
        )

    @group.command(
        name="remove",
        description="Retire le rôle de test à l'utilisateur.",
    )
    async def remove_role(interaction: discord.Interaction) -> None:
        if interaction.guild is None:
            await interaction.response.send_message(
                "Cette commande doit être utilisée sur un serveur.",
                ephemeral=True,
            )
            return

        if interaction.user.id != interaction.guild.owner_id:
            await interaction.response.send_message(
                "Cette commande de test est réservée au propriétaire du serveur.",
                ephemeral=True,
            )
            return

        if not isinstance(interaction.user, discord.Member):
            await interaction.response.send_message(
                "Impossible de récupérer ton profil membre.",
                ephemeral=True,
            )
            return

        role = interaction.guild.get_role(role_id)

        if role is None:
            await interaction.response.send_message(
                "Le rôle de test configuré est introuvable.",
                ephemeral=True,
            )
            return

        changed = await role_manager.remove_role(
            interaction.user,
            role,
            reason="Claviger role integration test",
        )

        if changed:
            message = f"Rôle **{role.name}** retiré."
        else:
            message = f"Tu ne possèdes déjà plus le rôle **{role.name}**."

        await interaction.response.send_message(
            message,
            ephemeral=True,
        )

    return group