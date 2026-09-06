from collections.abc import Sequence

from claviger.models.catalog_sync_model import (
    CatalogStateUpdate,
    CatalogSyncEntry,
    CatalogSyncPlan,
    CatalogSyncWarning,
)
from claviger.models.role_channel_catalog_model import (
    RoleChannelCatalogEntry,
)
from claviger.models.role_channel_discovery_model import (
    DiscordChannelSnapshot,
    DiscordRoleSnapshot,
    GuildRoleChannelSnapshot,
)


class CatalogSyncPlanner:
    """Compare Discord state with one persisted role catalog."""

    def build_plan(
        self,
        current_entries: Sequence[RoleChannelCatalogEntry],
        snapshot: GuildRoleChannelSnapshot,
        *,
        prefix: str,
    ) -> CatalogSyncPlan:
        """Build a complete synchronization plan without writing data."""

        if not prefix:
            raise ValueError("Catalog role prefix cannot be empty.")

        roles_by_id = {role.role_id: role for role in snapshot.roles}

        channels_by_id = {channel.channel_id: channel for channel in snapshot.channels}

        current_by_role_id = {entry.role_id: entry for entry in current_entries}

        creates: list[CatalogSyncEntry] = []
        refreshes: list[CatalogSyncEntry] = []
        state_updates: list[CatalogStateUpdate] = []
        warnings: list[CatalogSyncWarning] = []

        for current in current_entries:
            role = roles_by_id.get(
                current.role_id,
            )

            if role is None:
                state_update = self._build_missing_role_state(
                    current,
                    channels_by_id,
                )

                if self._needs_state_update(
                    current,
                    state_update,
                ):
                    state_updates.append(
                        state_update,
                    )

                continue

            catalog_key = self._extract_catalog_key(
                role.role_name,
                prefix,
            )

            matches_policy = catalog_key is not None

            mapped_channel = self._resolve_unique_channel(
                role,
                channels_by_id,
            )

            mapping_valid = mapped_channel is not None

            if matches_policy and mapped_channel is not None:
                refresh = CatalogSyncEntry(
                    role_id=role.role_id,
                    role_name=role.role_name,
                    catalog_key=catalog_key,
                    channel_id=mapped_channel.channel_id,
                    channel_name=mapped_channel.channel_name,
                    role_manageable=role.role_manageable,
                )

                if self._needs_refresh(
                    current,
                    refresh,
                ):
                    refreshes.append(
                        refresh,
                    )

                continue

            historical_channel = channels_by_id.get(
                current.channel_id,
            )

            state_update = CatalogStateUpdate(
                role_id=current.role_id,
                role_name=role.role_name,
                catalog_key=(catalog_key if matches_policy else None),
                channel_name=(
                    historical_channel.channel_name
                    if historical_channel is not None
                    else None
                ),
                discord_present=True,
                role_manageable=role.role_manageable,
                channel_present=historical_channel is not None,
                mapping_valid=mapping_valid,
                matches_policy=matches_policy,
            )

            if self._needs_state_update(
                current,
                state_update,
            ):
                state_updates.append(
                    state_update,
                )

            if matches_policy and not mapping_valid:
                warnings.append(
                    self._build_mapping_warning(
                        role,
                    )
                )

        for role in snapshot.roles:
            if role.role_id in current_by_role_id:
                continue

            catalog_key = self._extract_catalog_key(
                role.role_name,
                prefix,
            )

            if catalog_key is None:
                continue

            mapped_channel = self._resolve_unique_channel(
                role,
                channels_by_id,
            )

            if mapped_channel is None:
                warnings.append(
                    self._build_mapping_warning(
                        role,
                    )
                )
                continue

            creates.append(
                CatalogSyncEntry(
                    role_id=role.role_id,
                    role_name=role.role_name,
                    catalog_key=catalog_key,
                    channel_id=mapped_channel.channel_id,
                    channel_name=mapped_channel.channel_name,
                    role_manageable=role.role_manageable,
                )
            )

        return CatalogSyncPlan(
            creates=tuple(creates),
            refreshes=tuple(refreshes),
            state_updates=tuple(state_updates),
            warnings=tuple(warnings),
        )

    @staticmethod
    def _extract_catalog_key(
        role_name: str,
        prefix: str,
    ) -> str | None:
        """Return the catalog key when a role matches the prefix."""

        if not role_name.startswith(prefix):
            return None

        catalog_key = role_name[len(prefix) :].strip()

        if not catalog_key:
            return None

        return catalog_key

    @staticmethod
    def _resolve_unique_channel(
        role: DiscordRoleSnapshot,
        channels_by_id: dict[
            int,
            DiscordChannelSnapshot,
        ],
    ) -> DiscordChannelSnapshot | None:
        """Resolve exactly one explicit Discord channel mapping."""

        if len(role.explicit_channel_ids) != 1:
            return None

        channel_id = role.explicit_channel_ids[0]

        channel = channels_by_id.get(
            channel_id,
        )

        if channel is None:
            raise RuntimeError(
                (
                    "Discord snapshot is inconsistent: "
                    f"role {role.role_id} references "
                    f"missing channel {channel_id}."
                )
            )

        return channel

    @staticmethod
    def _build_mapping_warning(
        role: DiscordRoleSnapshot,
    ) -> CatalogSyncWarning:
        """Describe a missing or ambiguous Discord channel mapping."""

        channel_count = len(
            role.explicit_channel_ids,
        )

        code = (
            "missing_channel_mapping"
            if channel_count == 0
            else "ambiguous_channel_mapping"
        )

        return CatalogSyncWarning(
            role_id=role.role_id,
            role_name=role.role_name,
            code=code,
            channel_count=channel_count,
        )

    @staticmethod
    def _build_missing_role_state(
        current: RoleChannelCatalogEntry,
        channels_by_id: dict[
            int,
            DiscordChannelSnapshot,
        ],
    ) -> CatalogStateUpdate:
        """Mark a persisted catalog role that disappeared from Discord."""

        historical_channel = channels_by_id.get(
            current.channel_id,
        )

        return CatalogStateUpdate(
            role_id=current.role_id,
            role_name=None,
            catalog_key=None,
            channel_name=(
                historical_channel.channel_name
                if historical_channel is not None
                else None
            ),
            discord_present=False,
            role_manageable=False,
            channel_present=historical_channel is not None,
            mapping_valid=False,
            matches_policy=False,
        )

    @staticmethod
    def _needs_refresh(
        current: RoleChannelCatalogEntry,
        refresh: CatalogSyncEntry,
    ) -> bool:
        """Return whether Discord-owned catalog data changed."""

        return (
            current.role_name != refresh.role_name
            or current.catalog_key != refresh.catalog_key
            or current.channel_id != refresh.channel_id
            or current.channel_name != refresh.channel_name
            or current.discord_present is not True
            or current.role_manageable != refresh.role_manageable
            or current.channel_present is not True
            or current.mapping_valid is not True
            or current.matches_policy is not True
        )

    @staticmethod
    def _needs_state_update(
        current: RoleChannelCatalogEntry,
        state: CatalogStateUpdate,
    ) -> bool:
        """Return whether observed synchronization state changed."""

        role_name_changed = (
            state.role_name is not None and current.role_name != state.role_name
        )

        catalog_key_changed = (
            state.catalog_key is not None and current.catalog_key != state.catalog_key
        )

        channel_name_changed = (
            state.channel_name is not None
            and current.channel_name != state.channel_name
        )

        return (
            role_name_changed
            or catalog_key_changed
            or channel_name_changed
            or current.discord_present != state.discord_present
            or current.role_manageable != state.role_manageable
            or current.channel_present != state.channel_present
            or current.mapping_valid != state.mapping_valid
            or current.matches_policy != state.matches_policy
        )
