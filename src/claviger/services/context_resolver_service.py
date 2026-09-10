import discord

from claviger.models.resolved_context_model import ResolvedContext
from claviger.models.workflow_definition_model import (
    WorkflowContextBinding,
    WorkflowDefinition,
)
from claviger.services.role_manageability_service import (
    is_role_manageable,
)


class ContextResolutionError(RuntimeError):
    """Base error raised while resolving workflow context state."""


class ContextGuildMismatchError(ContextResolutionError):
    """Raised when context configuration belongs to another guild."""


class ContextRoleNotFoundError(ContextResolutionError):
    """Raised when the Discord role backing a context no longer exists."""


class UnsupportedContextValueTypeError(ContextResolutionError):
    """Raised when the runtime cannot resolve a configured context value type."""


class ContextResolverService:
    """Resolve declarative workflow contexts against current Discord state."""

    def resolve(
        self,
        binding: WorkflowContextBinding,
        member: discord.Member,
    ) -> ResolvedContext:
        """Resolve one context binding for a Discord member."""

        context = binding.context
        guild = member.guild

        if context.guild_id != guild.id:
            raise ContextGuildMismatchError(
                "Context "
                f"{context.context_key!r} belongs to guild "
                f"{context.guild_id}, not guild {guild.id}."
            )

        if context.value_type != "boolean":
            raise UnsupportedContextValueTypeError(
                "Context "
                f"{context.context_key!r} uses unsupported value type "
                f"{context.value_type!r}."
            )

        role = guild.get_role(
            context.role_id,
        )

        if role is None:
            raise ContextRoleNotFoundError(
                "Context "
                f"{context.context_key!r} references missing Discord role "
                f"{context.role_id}."
            )

        current_value = any(
            member_role.id == context.role_id for member_role in member.roles
        )

        bot_member = guild.me

        role_manageable = bot_member is not None and is_role_manageable(
            role,
            bot_member,
        )

        return ResolvedContext(
            binding=binding,
            current_value=current_value,
            role_manageable=role_manageable,
        )

    def resolve_workflow(
        self,
        workflow: WorkflowDefinition,
        member: discord.Member,
    ) -> tuple[ResolvedContext, ...]:
        """Resolve every context belonging to one workflow."""

        if workflow.guild_id != member.guild.id:
            raise ContextGuildMismatchError(
                "Workflow "
                f"{workflow.workflow_key!r} belongs to guild "
                f"{workflow.guild_id}, not guild {member.guild.id}."
            )

        return tuple(
            self.resolve(
                binding,
                member,
            )
            for binding in workflow.contexts
        )
