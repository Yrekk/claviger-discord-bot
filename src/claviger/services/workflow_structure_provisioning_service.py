from dataclasses import dataclass

import discord

from claviger.models.resolved_workflow_configuration_model import (
    ResolvedWorkflowConfiguration,
)
from claviger.models.workflow_configuration_model import (
    WorkflowConfigurationSpec,
    WorkflowResourceSelection,
)
from claviger.models.workflow_structure_provisioning_model import (
    WorkflowStructureProvisioningResult,
)
from claviger.services.role_discovery import (
    RoleDiscoveryService,
    RoleHierarchy,
)

PROVISIONING_REASON = "Claviger workflow structure provisioning"


class WorkflowStructureProvisioningPermissionError(RuntimeError):
    """Raised when current Discord permissions no longer allow provisioning."""


class WorkflowStructureProvisioningResourceError(RuntimeError):
    """Raised when one reconciled Discord resource disappeared or changed."""


class WorkflowStructureProvisioningPartialError(RuntimeError):
    """Report successful Discord mutations that occurred before a later failure."""

    def __init__(
        self,
        message: str,
        *,
        created_category_id: int | None,
        created_channel_ids: tuple[int, ...],
        created_role_ids: tuple[int, ...],
        category_permissions_repaired: bool,
        repaired_channel_ids: tuple[int, ...],
    ) -> None:
        super().__init__(
            message,
        )

        self.created_category_id = created_category_id
        self.created_channel_ids = created_channel_ids
        self.created_role_ids = created_role_ids
        self.category_permissions_repaired = category_permissions_repaired
        self.repaired_channel_ids = repaired_channel_ids


@dataclass(frozen=True, slots=True)
class _WorkflowProvisioningPreflight:
    """Hold freshly resolved Discord resources before any mutation begins."""

    category: discord.CategoryChannel | None
    management_channel: discord.TextChannel | None
    execution_channel: discord.TextChannel | None

    primary_role: discord.Role | None
    ai_preference_role: discord.Role | None


class WorkflowStructureProvisioningService:
    """Provision one reconciled workflow without destructive replacement."""

    def __init__(
        self,
        *,
        role_discovery_service: RoleDiscoveryService,
    ) -> None:
        self.role_discovery_service = role_discovery_service

    async def provision(
        self,
        *,
        guild: discord.Guild,
        configuration: WorkflowConfigurationSpec,
    ) -> WorkflowStructureProvisioningResult:
        """Resolve, create and repair Discord resources for one workflow."""

        if configuration.guild_id != guild.id:
            raise ValueError("Workflow configuration belongs to another Discord guild.")

        bot_member = self._require_bot_member(
            guild,
        )

        # Reconciliation may have happened several interactions earlier.
        # Preflight rechecks current Discord state before the first mutation.
        preflight = await self._preflight(
            guild=guild,
            bot_member=bot_member,
            configuration=configuration,
        )

        created_category_id: int | None = None
        created_channel_ids: list[int] = []
        created_role_ids: list[int] = []

        category_permissions_repaired = False
        repaired_channel_ids: list[int] = []

        try:
            category = preflight.category

            if configuration.category.mode == "create":
                category = await guild.create_category(
                    self._require_creation_name(
                        configuration.category,
                        resource_label="workflow category",
                    ),
                    reason=PROVISIONING_REASON,
                )

                created_category_id = category.id

            if category is None:
                raise WorkflowStructureProvisioningResourceError(
                    "Workflow category could not be resolved."
                )

            if configuration.category.mode == "existing":
                category_permissions_repaired = (
                    await self._ensure_bot_category_visibility(
                        category=category,
                        bot_member=bot_member,
                    )
                )

            management_channel = preflight.management_channel

            if configuration.management_channel.mode == "create":
                management_channel = await guild.create_text_channel(
                    self._require_creation_name(
                        configuration.management_channel,
                        resource_label="management channel",
                    ),
                    category=category,
                    overwrites=self._build_management_overwrites(
                        guild=guild,
                        bot_member=bot_member,
                    ),
                    reason=PROVISIONING_REASON,
                )

                created_channel_ids.append(
                    management_channel.id,
                )

            if management_channel is None:
                raise WorkflowStructureProvisioningResourceError(
                    "Workflow management channel could not be resolved."
                )

            if configuration.management_channel.mode == "existing":
                if await self._repair_management_channel(
                    guild=guild,
                    channel=management_channel,
                    bot_member=bot_member,
                ):
                    repaired_channel_ids.append(
                        management_channel.id,
                    )

            execution_channel = preflight.execution_channel

            if configuration.execution_channel.mode == "create":
                execution_channel = await guild.create_text_channel(
                    self._require_creation_name(
                        configuration.execution_channel,
                        resource_label="execution channel",
                    ),
                    category=category,
                    overwrites=self._build_execution_overwrites(
                        bot_member=bot_member,
                    ),
                    reason=PROVISIONING_REASON,
                )

                created_channel_ids.append(
                    execution_channel.id,
                )

            if execution_channel is None:
                raise WorkflowStructureProvisioningResourceError(
                    "Workflow execution channel could not be resolved."
                )

            if configuration.execution_channel.mode == "existing":
                if await self._ensure_bot_channel_access(
                    channel=execution_channel,
                    bot_member=bot_member,
                ):
                    repaired_channel_ids.append(
                        execution_channel.id,
                    )

            primary_role = preflight.primary_role

            if configuration.primary_role.mode == "create":
                primary_role = await self._create_role(
                    guild=guild,
                    selection=configuration.primary_role,
                    resource_label="primary role",
                )

                created_role_ids.append(
                    primary_role.id,
                )

            if primary_role is None:
                raise WorkflowStructureProvisioningResourceError(
                    "Workflow primary role could not be resolved."
                )

            ai_preference_role = preflight.ai_preference_role

            if (
                configuration.ai_enabled
                and configuration.ai_preference_role is not None
                and configuration.ai_preference_role.mode == "create"
            ):
                ai_preference_role = await self._create_role(
                    guild=guild,
                    selection=configuration.ai_preference_role,
                    resource_label="AI preference role",
                )

                created_role_ids.append(
                    ai_preference_role.id,
                )

            if configuration.ai_enabled and ai_preference_role is None:
                raise WorkflowStructureProvisioningResourceError(
                    "AI-enabled workflow has no resolved AI preference role."
                )

            resolved_configuration = ResolvedWorkflowConfiguration(
                guild_id=configuration.guild_id,
                workflow_key=configuration.workflow_key,
                title=configuration.title,
                description=configuration.description,
                command_name=configuration.command_name,
                command_description=configuration.command_description,
                category_id=category.id,
                management_channel_id=management_channel.id,
                execution_channel_id=execution_channel.id,
                primary_role_id=primary_role.id,
                questionnaire_role_prefix=(configuration.questionnaire_role_prefix),
                ai_preference_role_id=(
                    ai_preference_role.id if ai_preference_role is not None else None
                ),
            )

            return WorkflowStructureProvisioningResult(
                guild_id=guild.id,
                configuration=resolved_configuration,
                created_category_id=created_category_id,
                created_channel_ids=tuple(
                    created_channel_ids,
                ),
                created_role_ids=tuple(
                    created_role_ids,
                ),
                category_permissions_repaired=(category_permissions_repaired),
                repaired_channel_ids=tuple(
                    repaired_channel_ids,
                ),
            )

        except Exception as error:
            # Discord provisioning is not transactional. If anything succeeded
            # before a later failure, preserve those identities for reporting
            # instead of pretending that nothing changed.
            if (
                created_category_id is not None
                or created_channel_ids
                or created_role_ids
                or category_permissions_repaired
                or repaired_channel_ids
            ):
                raise WorkflowStructureProvisioningPartialError(
                    "Workflow provisioning stopped after partial Discord mutation.",
                    created_category_id=created_category_id,
                    created_channel_ids=tuple(
                        created_channel_ids,
                    ),
                    created_role_ids=tuple(
                        created_role_ids,
                    ),
                    category_permissions_repaired=(category_permissions_repaired),
                    repaired_channel_ids=tuple(
                        repaired_channel_ids,
                    ),
                ) from error

            raise

    async def _preflight(
        self,
        *,
        guild: discord.Guild,
        bot_member: discord.Member,
        configuration: WorkflowConfigurationSpec,
    ) -> _WorkflowProvisioningPreflight:
        """Revalidate Discord identities and permissions before mutation."""

        category = self._preflight_category(
            guild=guild,
            bot_member=bot_member,
            selection=configuration.category,
        )

        management_channel = self._preflight_channel(
            guild=guild,
            bot_member=bot_member,
            selection=configuration.management_channel,
            category=category,
            category_selection=configuration.category,
            resource_label="management channel",
            require_private_writes=True,
        )

        execution_channel = self._preflight_channel(
            guild=guild,
            bot_member=bot_member,
            selection=configuration.execution_channel,
            category=category,
            category_selection=configuration.category,
            resource_label="execution channel",
            require_private_writes=False,
        )

        if configuration.ai_enabled and configuration.ai_preference_role is None:
            raise WorkflowStructureProvisioningResourceError(
                "AI-enabled workflow requires a reconciled AI preference role."
            )

        if (
            not configuration.ai_enabled
            and configuration.ai_preference_role is not None
        ):
            raise WorkflowStructureProvisioningResourceError(
                "AI-disabled workflow cannot provision an AI preference role."
            )

        role_hierarchy = await self._load_role_hierarchy_if_needed(
            guild=guild,
            configuration=configuration,
        )

        primary_role = self._preflight_role(
            guild=guild,
            bot_member=bot_member,
            selection=configuration.primary_role,
            hierarchy=role_hierarchy,
            resource_label="primary role",
        )

        ai_preference_role = None

        if configuration.ai_preference_role is not None:
            ai_preference_role = self._preflight_role(
                guild=guild,
                bot_member=bot_member,
                selection=configuration.ai_preference_role,
                hierarchy=role_hierarchy,
                resource_label="AI preference role",
            )

        return _WorkflowProvisioningPreflight(
            category=category,
            management_channel=management_channel,
            execution_channel=execution_channel,
            primary_role=primary_role,
            ai_preference_role=ai_preference_role,
        )

    def _preflight_category(
        self,
        *,
        guild: discord.Guild,
        bot_member: discord.Member,
        selection: WorkflowResourceSelection,
    ) -> discord.CategoryChannel | None:
        """Resolve or authorize creation of the selected workflow category."""

        if selection.mode == "create":
            self._require_manage_channels(
                bot_member,
            )

            return None

        category_id = self._require_existing_id(
            selection,
            resource_label="workflow category",
        )

        category = self._find_category(
            guild,
            category_id=category_id,
        )

        if category is None:
            raise WorkflowStructureProvisioningResourceError(
                "Reconciled workflow category no longer exists."
            )

        if not category.permissions_for(
            bot_member,
        ).view_channel:
            self._require_manage_channels(
                bot_member,
            )

        return category

    def _preflight_channel(
        self,
        *,
        guild: discord.Guild,
        bot_member: discord.Member,
        selection: WorkflowResourceSelection,
        category: discord.CategoryChannel | None,
        category_selection: WorkflowResourceSelection,
        resource_label: str,
        require_private_writes: bool,
    ) -> discord.TextChannel | None:
        """Resolve or authorize creation of one workflow text channel."""

        if selection.mode == "create":
            self._require_manage_channels(
                bot_member,
            )

            return None

        if category_selection.mode == "create":
            raise WorkflowStructureProvisioningResourceError(
                f"Existing {resource_label} cannot be attached to "
                "a not-yet-created category."
            )

        if category is None:
            raise WorkflowStructureProvisioningResourceError(
                "Existing workflow channel requires an existing category."
            )

        channel_id = self._require_existing_id(
            selection,
            resource_label=resource_label,
        )

        channel = self._find_text_channel(
            guild,
            channel_id=channel_id,
        )

        if channel is None:
            raise WorkflowStructureProvisioningResourceError(
                f"Reconciled {resource_label} no longer exists."
            )

        if channel.category_id != category.id:
            raise WorkflowStructureProvisioningResourceError(
                f"Reconciled {resource_label} moved outside "
                "the selected workflow category."
            )

        bot_permissions = channel.permissions_for(
            bot_member,
        )

        requires_repair = (
            not bot_permissions.view_channel or not bot_permissions.send_messages
        )

        if require_private_writes:
            everyone_permissions = channel.permissions_for(
                guild.default_role,
            )

            requires_repair = requires_repair or everyone_permissions.send_messages

        if requires_repair:
            self._require_manage_channels(
                bot_member,
            )

        return channel

    def _preflight_role(
        self,
        *,
        guild: discord.Guild,
        bot_member: discord.Member,
        selection: WorkflowResourceSelection,
        hierarchy: RoleHierarchy | None,
        resource_label: str,
    ) -> discord.Role | None:
        """Resolve or authorize creation of one workflow role."""

        if selection.mode == "create":
            self._require_manage_roles(
                bot_member,
            )

            return None

        if hierarchy is None:
            raise WorkflowStructureProvisioningResourceError(
                f"Unable to revalidate existing {resource_label}."
            )

        role_id = self._require_existing_id(
            selection,
            resource_label=resource_label,
        )

        role = next(
            (
                candidate
                for candidate in hierarchy.manageable_roles
                if candidate.id == role_id
            ),
            None,
        )

        if role is None:
            raise WorkflowStructureProvisioningResourceError(
                f"Reconciled {resource_label} is no longer manageable."
            )

        return role

    async def _load_role_hierarchy_if_needed(
        self,
        *,
        guild: discord.Guild,
        configuration: WorkflowConfigurationSpec,
    ) -> RoleHierarchy | None:
        """Load hierarchy once when at least one existing role needs revalidation."""

        selections = [
            configuration.primary_role,
        ]

        if configuration.ai_preference_role is not None:
            selections.append(
                configuration.ai_preference_role,
            )

        if not any(selection.mode == "existing" for selection in selections):
            return None

        return await self.role_discovery_service.get_hierarchy(
            guild,
        )

    async def _create_role(
        self,
        *,
        guild: discord.Guild,
        selection: WorkflowResourceSelection,
        resource_label: str,
    ) -> discord.Role:
        """Create one inert workflow role with no elevated Discord permissions."""

        return await guild.create_role(
            name=self._require_creation_name(
                selection,
                resource_label=resource_label,
            ),
            permissions=discord.Permissions.none(),
            hoist=False,
            mentionable=False,
            reason=PROVISIONING_REASON,
        )

    async def _ensure_bot_category_visibility(
        self,
        *,
        category: discord.CategoryChannel,
        bot_member: discord.Member,
    ) -> bool:
        """Restore only the bot visibility required for an existing category."""

        if category.permissions_for(
            bot_member,
        ).view_channel:
            return False

        overwrite = category.overwrites_for(
            bot_member,
        )

        overwrite.view_channel = True

        await category.set_permissions(
            bot_member,
            overwrite=overwrite,
            reason=PROVISIONING_REASON,
        )

        return True

    async def _repair_management_channel(
        self,
        *,
        guild: discord.Guild,
        channel: discord.TextChannel,
        bot_member: discord.Member,
    ) -> bool:
        """Reserve management-channel writes for admins and Claviger."""

        changed = False

        everyone_permissions = channel.permissions_for(
            guild.default_role,
        )

        if everyone_permissions.send_messages:
            overwrite = channel.overwrites_for(
                guild.default_role,
            )

            overwrite.send_messages = False

            await channel.set_permissions(
                guild.default_role,
                overwrite=overwrite,
                reason=PROVISIONING_REASON,
            )

            changed = True

        return (
            await self._ensure_bot_channel_access(
                channel=channel,
                bot_member=bot_member,
            )
            or changed
        )

    async def _ensure_bot_channel_access(
        self,
        *,
        channel: discord.TextChannel,
        bot_member: discord.Member,
    ) -> bool:
        """Restore the bot visibility and write access required by a workflow."""

        permissions = channel.permissions_for(
            bot_member,
        )

        if permissions.view_channel and permissions.send_messages:
            return False

        overwrite = channel.overwrites_for(
            bot_member,
        )

        overwrite.view_channel = True
        overwrite.send_messages = True

        await channel.set_permissions(
            bot_member,
            overwrite=overwrite,
            reason=PROVISIONING_REASON,
        )

        return True

    @staticmethod
    def _build_management_overwrites(
        *,
        guild: discord.Guild,
        bot_member: discord.Member,
    ) -> dict[
        discord.Role | discord.Member,
        discord.PermissionOverwrite,
    ]:
        """Build minimal management-channel overwrites."""

        return {
            # Visibility continues to inherit from the selected category.
            # Only ordinary member writes are denied here.
            guild.default_role: discord.PermissionOverwrite(
                send_messages=False,
            ),
            bot_member: discord.PermissionOverwrite(
                view_channel=True,
                send_messages=True,
            ),
        }

    @staticmethod
    def _build_execution_overwrites(
        *,
        bot_member: discord.Member,
    ) -> dict[
        discord.Role | discord.Member,
        discord.PermissionOverwrite,
    ]:
        """Keep member permissions inherited while guaranteeing bot access."""

        return {
            bot_member: discord.PermissionOverwrite(
                view_channel=True,
                send_messages=True,
            ),
        }

    @staticmethod
    def _find_category(
        guild: discord.Guild,
        *,
        category_id: int,
    ) -> discord.CategoryChannel | None:
        """Resolve one current Discord category by stable identity."""

        return next(
            (
                channel
                for channel in guild.channels
                if isinstance(
                    channel,
                    discord.CategoryChannel,
                )
                and channel.id == category_id
            ),
            None,
        )

    @staticmethod
    def _find_text_channel(
        guild: discord.Guild,
        *,
        channel_id: int,
    ) -> discord.TextChannel | None:
        """Resolve one current Discord text channel by stable identity."""

        return next(
            (
                channel
                for channel in guild.channels
                if isinstance(
                    channel,
                    discord.TextChannel,
                )
                and channel.id == channel_id
            ),
            None,
        )

    @staticmethod
    def _require_bot_member(
        guild: discord.Guild,
    ) -> discord.Member:
        """Return Claviger's guild member or fail closed."""

        bot_member = guild.me

        if bot_member is None:
            raise RuntimeError("Claviger could not resolve its own guild member.")

        return bot_member

    @staticmethod
    def _require_manage_channels(
        bot_member: discord.Member,
    ) -> None:
        """Require current Manage Channels permission before channel mutation."""

        if bot_member.guild_permissions.manage_channels:
            return

        raise WorkflowStructureProvisioningPermissionError(
            "Claviger requires Manage Channels for workflow provisioning."
        )

    @staticmethod
    def _require_manage_roles(
        bot_member: discord.Member,
    ) -> None:
        """Require current Manage Roles permission before role creation."""

        if bot_member.guild_permissions.manage_roles:
            return

        raise WorkflowStructureProvisioningPermissionError(
            "Claviger requires Manage Roles for workflow role creation."
        )

    @staticmethod
    def _require_existing_id(
        selection: WorkflowResourceSelection,
        *,
        resource_label: str,
    ) -> int:
        """Return one validated existing Discord identity."""

        if (
            selection.mode != "existing"
            or selection.resource_id is None
            or selection.resource_id <= 0
        ):
            raise WorkflowStructureProvisioningResourceError(
                f"Invalid existing {resource_label} identity."
            )

        return selection.resource_id

    @staticmethod
    def _require_creation_name(
        selection: WorkflowResourceSelection,
        *,
        resource_label: str,
    ) -> str:
        """Return one validated Discord creation name."""

        if (
            selection.mode != "create"
            or selection.name is None
            or not selection.name.strip()
        ):
            raise WorkflowStructureProvisioningResourceError(
                f"Invalid creation name for {resource_label}."
            )

        return selection.name.strip()
