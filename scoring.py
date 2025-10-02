"""Basic scoring utilities for the operator training system."""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import List

import numpy as np


@dataclass
class ScoreTracker:
    """Keep track of the operator's performance metrics."""

    history: List[float] = field(default_factory=list)

    def update(self, deviation: np.ndarray) -> float:
        """Append a new score based on the deviation vector."""
        score = float(np.exp(-np.linalg.norm(deviation)))
        self.history.append(score)
        return score

    @property
    def average(self) -> float:
        """Return the running average score."""
        if not self.history:
            return 0.0
        return float(np.mean(self.history))
