from __future__ import annotations

from enum import Enum
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from models import ScoredPost
    from scorers import Scorer


def _percentileofscore(scores: list[float], score: float) -> float:
    """Returns the percentile rank of `score` within `scores` (0–100)."""
    if not scores:
        return 0.0
    return sum(1 for s in scores if s <= score) / len(scores) * 100


class Threshold(Enum):
    LAX = 90
    NORMAL = 95
    STRICT = 98

    def get_name(self):
        return self.name.lower()

    def posts_meeting_criteria(
        self, posts: list[ScoredPost], scorer: Scorer
    ) -> list[ScoredPost]:
        """Returns ScoredPosts that meet this Threshold with the given Scorer."""
        if not posts:
            return []
        scores = {p: p.get_score(scorer) for p in posts}
        all_scores = list(scores.values())
        return [
            p for p in posts if _percentileofscore(all_scores, scores[p]) >= self.value
        ]


def get_thresholds():
    """Returns a dictionary mapping lowercase threshold names to values."""
    return {i.get_name(): i.value for i in Threshold}


def get_threshold_from_name(name: str) -> Threshold:
    """Returns Threshold for a given named string."""
    return Threshold[name.upper()]
