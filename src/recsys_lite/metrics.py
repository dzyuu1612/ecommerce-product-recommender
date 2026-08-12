"""Ranking metrics: ROC-AUC, NDCG@K, HitRate@K.

Small, dependency-free (numpy only) implementations so the training and
evaluation CLIs don't need scikit-learn just to compute an AUC.
"""

from __future__ import annotations

from collections import defaultdict
from typing import Hashable, Sequence

import numpy as np


def roc_auc(labels: Sequence[int], scores: Sequence[float]) -> float:
    """Rank-based AUC: P(score(positive) > score(random negative))."""
    labels = np.asarray(labels, dtype=np.float64)
    scores = np.asarray(scores, dtype=np.float64)
    n_pos = labels.sum()
    n_neg = len(labels) - n_pos
    if n_pos == 0 or n_neg == 0:
        return float("nan")
    order = np.argsort(scores, kind="mergesort")
    ranks = np.empty_like(order, dtype=np.float64)
    ranks[order] = np.arange(1, len(scores) + 1)
    # average tied ranks
    _, inverse, counts = np.unique(scores, return_inverse=True, return_counts=True)
    sum_ranks_per_value = np.zeros(len(counts))
    np.add.at(sum_ranks_per_value, inverse, ranks)
    ranks = (sum_ranks_per_value / counts)[inverse]

    sum_pos_ranks = ranks[labels == 1].sum()
    auc = (sum_pos_ranks - n_pos * (n_pos + 1) / 2) / (n_pos * n_neg)
    return float(auc)


def dcg_at_k(relevances: Sequence[float], k: int) -> float:
    relevances = np.asarray(relevances, dtype=np.float64)[:k]
    if relevances.size == 0:
        return 0.0
    discounts = np.log2(np.arange(2, relevances.size + 2))
    return float((relevances / discounts).sum())


def ndcg_at_k(labels_ranked_by_score: Sequence[int], k: int) -> float:
    """`labels_ranked_by_score` must already be sorted by descending model score."""
    dcg = dcg_at_k(labels_ranked_by_score, k)
    ideal = dcg_at_k(sorted(labels_ranked_by_score, reverse=True), k)
    return dcg / ideal if ideal > 0 else 0.0


def hit_rate_at_k(labels_ranked_by_score: Sequence[int], k: int) -> float:
    return 1.0 if any(labels_ranked_by_score[:k]) else 0.0


def evaluate_grouped(
    group_keys: Sequence[Hashable],
    labels: Sequence[int],
    scores: Sequence[float],
    k: int = 5,
) -> dict[str, float]:
    """Group (label, score) pairs by `group_keys` (one group per ranking context:
    a user + point-in-time = one positive target plus its sampled negatives),
    then average NDCG@k and HitRate@k across groups. AUC is computed globally.
    """
    grouped: dict[Hashable, list[tuple[float, int]]] = defaultdict(list)
    for key, label, score in zip(group_keys, labels, scores):
        grouped[key].append((score, label))

    ndcgs, hit_rates = [], []
    for rows in grouped.values():
        rows.sort(key=lambda r: r[0], reverse=True)
        ranked_labels = [label for _, label in rows]
        ndcgs.append(ndcg_at_k(ranked_labels, k))
        hit_rates.append(hit_rate_at_k(ranked_labels, k))

    return {
        "auc": roc_auc(labels, scores),
        f"ndcg@{k}": float(np.mean(ndcgs)) if ndcgs else float("nan"),
        f"hit_rate@{k}": float(np.mean(hit_rates)) if hit_rates else float("nan"),
        "n_groups": len(grouped),
    }
