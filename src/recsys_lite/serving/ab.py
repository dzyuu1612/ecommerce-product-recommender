"""Deterministic, sticky A/B routing between the registry's champion and
an unpromoted candidate model -- the same "sticky user assignment" idea
the full-scale platform's progressive rollout uses, minus the Kubernetes
shadow/rollback machinery around it.
"""

from __future__ import annotations

import hashlib
from dataclasses import dataclass

from recsys_lite.model import ModelConfig, RankingModel


@dataclass
class RoutedModel:
    model: RankingModel
    config: ModelConfig
    version: str
    variant: str  # "champion" or "candidate"


class ABRouter:
    def __init__(
        self,
        champion: tuple[RankingModel, ModelConfig, str],
        candidate: tuple[RankingModel, ModelConfig, str] | None = None,
        candidate_weight_pct: int = 0,
    ):
        self._champion = champion
        self._candidate = candidate
        self.candidate_weight_pct = max(0, min(100, candidate_weight_pct))

    def route(self, user_id: int) -> RoutedModel:
        if self._candidate is None or self.candidate_weight_pct == 0:
            model, config, version = self._champion
            return RoutedModel(model, config, version, "champion")

        bucket = int(hashlib.md5(str(user_id).encode()).hexdigest(), 16) % 100
        if bucket < self.candidate_weight_pct:
            model, config, version = self._candidate
            return RoutedModel(model, config, version, "candidate")
        model, config, version = self._champion
        return RoutedModel(model, config, version, "champion")
