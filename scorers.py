from __future__ import annotations

import importlib
import inspect
import math
from abc import ABC, abstractmethod
from math import sqrt
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from models import ScoredPost


def _gmean(*values: float) -> float:
    """Geometric mean of one or more positive values."""
    return math.exp(sum(math.log(v) for v in values) / len(values))


class Weight(ABC):
    @classmethod
    @abstractmethod
    def weight(cls, scored_post: ScoredPost):
        pass


class UniformWeight(Weight):
    @classmethod
    def weight(cls, scored_post: ScoredPost) -> float:
        return 1.0


class InverseFollowerWeight(Weight):
    @classmethod
    def weight(cls, scored_post: ScoredPost) -> float:
        followers = scored_post.info["account"]["followers_count"]
        if followers == 0:
            return 1.0
        return 1.0 / sqrt(followers)


class Scorer(ABC):
    @classmethod
    @abstractmethod
    def score(cls, scored_post: ScoredPost) -> float:
        pass

    @classmethod
    def get_name(cls):
        return cls.__name__.replace("Scorer", "")


class SimpleScorer(UniformWeight, Scorer):
    @classmethod
    def score(cls, scored_post: ScoredPost) -> float:
        reblogs = scored_post.info["reblogs_count"]
        favs = scored_post.info["favourites_count"]
        if reblogs or favs:
            metric_average = _gmean(reblogs + 1, favs + 1)
        else:
            metric_average = 0.0
        return metric_average * super().weight(scored_post)


class SimpleWeightedScorer(InverseFollowerWeight, SimpleScorer):
    @classmethod
    def score(cls, scored_post: ScoredPost) -> float:
        return super().score(scored_post) * super().weight(scored_post)


class ExtendedSimpleScorer(UniformWeight, Scorer):
    @classmethod
    def score(cls, scored_post: ScoredPost) -> float:
        reblogs = scored_post.info["reblogs_count"]
        favs = scored_post.info["favourites_count"]
        replies = scored_post.info["replies_count"]
        if reblogs or favs or replies:
            metric_average = _gmean(reblogs + 1, favs + 1, replies + 1)
        else:
            metric_average = 0.0
        return metric_average * super().weight(scored_post)


class ExtendedSimpleWeightedScorer(InverseFollowerWeight, ExtendedSimpleScorer):
    @classmethod
    def score(cls, scored_post: ScoredPost) -> float:
        return super().score(scored_post) * super().weight(scored_post)


class FriendBoostScorer(InverseFollowerWeight, Scorer):
    """Weights posts by how many of your follows boosted them (network_boost_count).

    Falls back to global reblogs/favs for posts that no follow explicitly boosted.
    Also applies a controversy penalty when replies outnumber favourites+reblogs.
    """

    def __init__(
        self,
        affinity_accounts: set[str] | None = None,
        list_accounts: set[str] | None = None,
        controversy_penalty: float = 0.5,
    ):
        self.affinity_accounts: set[str] = affinity_accounts or set()
        self.list_accounts: set[str] = list_accounts or set()
        self.controversy_penalty: float = controversy_penalty

    def score(self, scored_post: ScoredPost) -> float:
        reblogs = scored_post.info["reblogs_count"]
        favs = scored_post.info["favourites_count"]
        replies = scored_post.info["replies_count"]
        network_boosts = scored_post.network_boost_count

        # Use network boost count as primary signal; fall back to global if zero
        effective_reblogs = network_boosts if network_boosts > 0 else reblogs

        if effective_reblogs or favs:
            base_score = _gmean(effective_reblogs + 1, favs + 1)
        else:
            base_score = 0.0

        base_score *= self.weight(scored_post)

        # Controversy penalty: dampen posts where replies exceed engagement
        engagement = favs + reblogs
        if replies > engagement:
            ratio = engagement / max(1, replies)
            # penalty=0 → no effect; penalty=1 → full ratio dampening
            multiplier = 1.0 - self.controversy_penalty * (1.0 - ratio)
            base_score *= multiplier

        return base_score

    @classmethod
    def weight(cls, scored_post: ScoredPost) -> float:
        return InverseFollowerWeight.weight(scored_post)

    @classmethod
    def get_name(cls):
        return cls.__name__.replace("Scorer", "")


class FriendWeightedScorer(FriendBoostScorer):
    """Extends FriendBoostScorer with a social-affinity multiplier.

    Posts from accounts you've recently favourited receive a 1.5× boost.
    Posts from accounts in your lists receive a 1.3× boost.
    Both bonuses stack multiplicatively.
    """

    AFFINITY_MULTIPLIER = 1.5
    LIST_MULTIPLIER = 1.3

    def score(self, scored_post: ScoredPost) -> float:
        base = super().score(scored_post)
        account_id = str(scored_post.info["account"]["id"])

        multiplier = 1.0
        if account_id in self.affinity_accounts:
            multiplier *= self.AFFINITY_MULTIPLIER
        if account_id in self.list_accounts:
            multiplier *= self.LIST_MULTIPLIER

        return base * multiplier


def get_scorers():
    all_classes = inspect.getmembers(importlib.import_module(__name__), inspect.isclass)
    scorers = [c for c in all_classes if c[1] is not Scorer and issubclass(c[1], Scorer)]
    return {scorer[1].get_name(): scorer[1] for scorer in scorers}
