from dataclasses import dataclass
from typing import Literal

AdminChannelType = Literal[
    "text",
    "forum",
]


@dataclass(frozen=True, slots=True)
class AdminChannelCandidate:
    """Describe one Discord channel discovered inside an admin category."""

    channel_id: int
    channel_name: str
    channel_type: AdminChannelType

    everyone_can_view: bool

    bot_can_view: bool
    bot_can_send: bool

    @property
    def is_private(self) -> bool:
        """Return whether @everyone cannot view this channel."""

        return not self.everyone_can_view

    @property
    def bot_usable(self) -> bool:
        """Return whether Claviger can use this channel."""

        return self.bot_can_view and self.bot_can_send


@dataclass(frozen=True, slots=True)
class AdminCategoryCandidate:
    """Describe one Discord category that could host administration."""

    category_id: int
    category_name: str

    everyone_can_view: bool
    bot_can_view: bool

    has_public_child: bool

    channels: tuple[AdminChannelCandidate, ...]

    @property
    def text_channels(
        self,
    ) -> tuple[AdminChannelCandidate, ...]:
        """Return discovered text channels."""

        return tuple(
            channel for channel in self.channels if channel.channel_type == "text"
        )

    @property
    def forum_channels(
        self,
    ) -> tuple[AdminChannelCandidate, ...]:
        """Return discovered forum channels."""

        return tuple(
            channel for channel in self.channels if channel.channel_type == "forum"
        )

    @property
    def usable_text_channels(
        self,
    ) -> tuple[AdminChannelCandidate, ...]:
        """Return text channels Claviger can currently use."""

        return tuple(channel for channel in self.text_channels if channel.bot_usable)

    @property
    def usable_forum_channels(
        self,
    ) -> tuple[AdminChannelCandidate, ...]:
        """Return forum channels Claviger can currently use."""

        return tuple(channel for channel in self.forum_channels if channel.bot_usable)

    @property
    def is_private(self) -> bool:
        """Return whether the category and all children hide from @everyone."""

        return not self.everyone_can_view and not self.has_public_child

    @property
    def has_required_shape(self) -> bool:
        """Return whether the category contains the minimum admin structure."""

        return len(self.text_channels) >= 1 and len(self.forum_channels) >= 2

    @property
    def has_required_usable_shape(self) -> bool:
        """Return whether Claviger can use enough channels for administration."""

        return (
            len(self.usable_text_channels) >= 1 and len(self.usable_forum_channels) >= 2
        )

    @property
    def is_structurally_ready(self) -> bool:
        """Return whether this category could host a complete admin config."""

        return (
            self.is_private
            and self.bot_can_view
            and self.has_required_shape
            and self.has_required_usable_shape
        )


@dataclass(frozen=True, slots=True)
class AdminStructureDiscoveryResult:
    """Describe every administrative category candidate found in a guild."""

    categories: tuple[AdminCategoryCandidate, ...]

    @property
    def has_candidates(self) -> bool:
        """Return whether at least one admin category was discovered."""

        return bool(self.categories)

    @property
    def is_ambiguous(self) -> bool:
        """Return whether several admin categories require human choice."""

        return len(self.categories) > 1

    @property
    def single_candidate(
        self,
    ) -> AdminCategoryCandidate | None:
        """Return the unique candidate when discovery is unambiguous."""

        if len(self.categories) != 1:
            return None

        return self.categories[0]
