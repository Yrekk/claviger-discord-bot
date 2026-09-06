from dataclasses import dataclass

from claviger.models.adult_access_theme_model import AdultAccessTheme


@dataclass(frozen=True)
class AdultAccessQuestionnaire:
    """Represent the adult-access questionnaire state for one member."""

    themes: tuple[AdultAccessTheme, ...]
    selected_theme_keys: tuple[str, ...]
    include_ai: bool
