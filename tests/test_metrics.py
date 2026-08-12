import math

from recsys_lite.metrics import dcg_at_k, evaluate_grouped, hit_rate_at_k, ndcg_at_k, roc_auc


def test_roc_auc_is_one_for_perfect_separation():
    labels = [0, 0, 0, 1, 1, 1]
    scores = [0.1, 0.2, 0.3, 0.8, 0.9, 0.95]
    assert roc_auc(labels, scores) == 1.0


def test_roc_auc_is_zero_for_perfectly_inverted_scores():
    labels = [0, 0, 0, 1, 1, 1]
    scores = [0.9, 0.8, 0.7, 0.1, 0.2, 0.3]
    assert roc_auc(labels, scores) == 0.0


def test_roc_auc_is_one_half_for_ties_between_classes():
    labels = [0, 1]
    scores = [0.5, 0.5]
    assert roc_auc(labels, scores) == 0.5


def test_dcg_at_k_matches_hand_computed_value():
    # rel = [1, 0, 1] -> 1/log2(2) + 0/log2(3) + 1/log2(4) = 1 + 0 + 0.5
    assert math.isclose(dcg_at_k([1, 0, 1], k=3), 1.5)


def test_ndcg_at_k_is_one_for_an_already_ideal_ranking():
    assert ndcg_at_k([1, 1, 0, 0], k=4) == 1.0


def test_ndcg_at_k_is_less_than_one_when_the_positive_is_not_first():
    assert 0 < ndcg_at_k([0, 1, 0], k=3) < 1.0


def test_hit_rate_at_k_detects_a_hit_within_the_cutoff():
    assert hit_rate_at_k([0, 0, 1, 0], k=3) == 1.0
    assert hit_rate_at_k([0, 0, 1, 0], k=2) == 0.0


def test_evaluate_grouped_averages_per_group_correctly():
    # group A: positive ranked first (perfect); group B: positive ranked last (worst)
    group_keys = ["A", "A", "B", "B"]
    labels = [1, 0, 0, 1]
    scores = [0.9, 0.1, 0.9, 0.1]

    result = evaluate_grouped(group_keys, labels, scores, k=2)

    assert result["n_groups"] == 2
    assert result["hit_rate@2"] == 1.0  # both groups contain the positive within top-2
    assert result["ndcg@2"] < 1.0  # group B's ranking is imperfect, pulling the average down
