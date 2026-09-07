from dataclasses import dataclass

import discord

MAX_CHECKBOX_OPTIONS = 10
MAX_OPTION_LABEL_LENGTH = 100
MAX_OPTION_VALUE_LENGTH = 100
MAX_OPTION_DESCRIPTION_LENGTH = 100


@dataclass(
    frozen=True,
    slots=True,
)
class CatalogSelectionOption:
    """One selectable catalog entry displayed in a modal."""

    key: str
    label: str
    description: str | None = None
    emoji: str | None = None
    selected: bool = False


def _truncate_text(
    text: str,
    *,
    max_length: int,
) -> str:
    """Truncate text while preserving room for an ellipsis."""

    if len(text) <= max_length:
        return text

    return f"{text[: max_length - 3]}..."


def _build_option_label(
    option: CatalogSelectionOption,
) -> str:
    """Build the user-facing checkbox label."""

    if option.emoji:
        label = f"{option.emoji} {option.label}"
    else:
        label = option.label

    return _truncate_text(
        label,
        max_length=MAX_OPTION_LABEL_LENGTH,
    )


def _build_option_description(
    option: CatalogSelectionOption,
) -> str | None:
    """Build the optional user-facing checkbox description."""

    if not option.description:
        return None

    return _truncate_text(
        option.description,
        max_length=MAX_OPTION_DESCRIPTION_LENGTH,
    )


class CatalogSelectionModal(
    discord.ui.Modal,
):
    """Generic modal for selecting entries from a Claviger catalog."""

    def __init__(
        self,
        *,
        title: str,
        actor_id: int,
        group_label: str,
        group_description: str,
        options: tuple[CatalogSelectionOption, ...],
        checkbox_custom_id: str,
        timeout: float = 600,
    ) -> None:
        if not options:
            raise ValueError("A catalog selection modal requires at least one option.")

        if len(options) > MAX_CHECKBOX_OPTIONS:
            raise ValueError(
                (
                    "Discord CheckboxGroup supports at most "
                    f"{MAX_CHECKBOX_OPTIONS} options."
                )
            )

        for option in options:
            if len(option.key) > MAX_OPTION_VALUE_LENGTH:
                raise ValueError(
                    (
                        "Catalog selection option keys must not exceed "
                        f"{MAX_OPTION_VALUE_LENGTH} characters."
                    )
                )

        super().__init__(
            title=title,
            timeout=timeout,
        )

        self.actor_id = actor_id
        self.catalog_options = options

        checkbox_options = [
            discord.CheckboxGroupOption(
                label=_build_option_label(option),
                value=option.key,
                description=_build_option_description(
                    option,
                ),
                default=option.selected,
            )
            for option in options
        ]

        self.selection_group = discord.ui.CheckboxGroup(
            custom_id=checkbox_custom_id,
            options=checkbox_options,
            required=False,
            min_values=0,
            max_values=len(checkbox_options),
        )

        self.add_item(
            discord.ui.Label(
                text=group_label,
                description=group_description,
                component=self.selection_group,
            )
        )

    @property
    def selected_keys(self) -> tuple[str, ...]:
        """Return the keys selected when the modal is submitted."""

        return tuple(
            self.selection_group.values,
        )

    async def interaction_check(
        self,
        interaction: discord.Interaction,
    ) -> bool:
        """Ensure only the modal owner can submit it."""

        if interaction.user.id == self.actor_id:
            return True

        await interaction.response.send_message(
            "Ce questionnaire appartient à un autre utilisateur.",
            ephemeral=True,
        )

        return False
