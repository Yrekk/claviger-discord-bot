from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class GuildConfigurationMetrics:
    """Summarize enabled declarative configuration persisted for one guild."""

    workflow_count: int
    catalog_count: int
    context_count: int
