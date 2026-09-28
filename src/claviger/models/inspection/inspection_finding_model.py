from dataclasses import dataclass, field
from types import MappingProxyType
from typing import Mapping

InspectionDetailValue = str | int | float | bool | None


@dataclass(frozen=True, slots=True)
class InspectionFinding:
    """Stable machine-readable inspection evidence.

    Human-readable wording belongs to presentation adapters. Details are
    intentionally limited to transport-safe primitive values so the same
    contract can later cross the Nexus API boundary without parsing prose.
    """

    code: str
    details: Mapping[str, InspectionDetailValue] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if not self.code.strip():
            raise ValueError("Inspection finding code must not be empty.")

        copied_details = dict(self.details)

        for key, value in copied_details.items():
            if not key.strip():
                raise ValueError("Inspection finding detail keys must not be empty.")

            if value is not None and not isinstance(
                value,
                (str, int, float, bool),
            ):
                raise TypeError(
                    f"Unsupported inspection finding detail type for {key!r}."
                )

        object.__setattr__(
            self,
            "details",
            MappingProxyType(copied_details),
        )
