from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class CatalogSynchronizationSummary:
    """Summarize one explicit ADMIN catalog synchronization."""

    catalog_key: str
    display_name: str
    role_prefix: str

    entry_count: int | None
    incomplete_metadata_count: int | None
    error: str | None = None

    @property
    def succeeded(self) -> bool:
        """Return whether this catalog completed synchronization."""

        return self.error is None


@dataclass(frozen=True, slots=True)
class CatalogMetadataCandidate:
    """Describe one logical entry requiring human questionnaire metadata."""

    catalog_key: str
    catalog_display_name: str
    entry_key: str

    label: str | None
    description: str | None
    emoji: str | None

    target_role_names: tuple[str, ...]
    target_channel_names: tuple[str, ...]
