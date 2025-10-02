"""Minimal scenario scaffold for future expansion."""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict, Any


@dataclass
class Scenario:
    """Describe an operator training scenario."""

    name: str
    description: str
    initial_conditions: Dict[str, float] = field(default_factory=dict)
    faults: Dict[str, Any] = field(default_factory=dict)
