"""Placeholder plant model definitions for future detailed simulations."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, Any


@dataclass
class BasePlantModel:
    """Minimal base class describing a process plant model."""

    name: str = "baseline"
    metadata: Dict[str, Any] | None = None

    def describe(self) -> Dict[str, Any]:
        return {"name": self.name, "metadata": self.metadata or {}}
