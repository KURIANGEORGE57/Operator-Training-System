"""Placeholder plant model definitions for future detailed simulations."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, Any


@dataclass
class BasePlantModel:
    """Minimal base class describing a process plant model.

    This scaffold provides a consistent interface for future detailed
    dynamic models.  For now it simply stores manipulated variable values
    and can be expanded as richer physics are implemented.
    """

    name: str = "baseline"
    metadata: Dict[str, Any] | None = None

    def describe(self) -> Dict[str, Any]:
        """Return a description of the model configuration."""
        return {
            "name": self.name,
            "metadata": self.metadata or {},
        }
