from dataclasses import dataclass

from claviger.models.role_channel_catalog_model import (
    RoleChannelCatalogEntry,
)


@dataclass(frozen=True, slots=True)
class MemberInterestQuestionnaire:
    """Describe the member interests available to one Discord member."""

    interests: tuple[RoleChannelCatalogEntry, ...]
    selected_interest_keys: tuple[str, ...]
