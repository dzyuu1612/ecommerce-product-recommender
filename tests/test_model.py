import torch

from recsys_lite.constants import SEQ_LEN
from recsys_lite.model import ModelConfig, RankingModel


def _random_batch(batch_size: int, item_num: int, seq_len: int = SEQ_LEN) -> dict[str, torch.Tensor]:
    return {
        "hist_item_id": torch.randint(0, item_num + 1, (batch_size, seq_len)),
        "hist_event_type": torch.randint(0, 4, (batch_size, seq_len)),
        "hist_category": torch.randint(0, 5, (batch_size, seq_len)),
        "hist_brand": torch.randint(0, 5, (batch_size, seq_len)),
        "hist_price_bucket": torch.randint(0, 5, (batch_size, seq_len)),
        "target_item_id": torch.randint(1, item_num + 1, (batch_size,)),
        "target_category": torch.randint(1, 5, (batch_size,)),
        "target_brand": torch.randint(1, 5, (batch_size,)),
        "target_price_bucket": torch.randint(1, 5, (batch_size,)),
    }


def test_forward_returns_one_logit_per_row_with_no_nans():
    config = ModelConfig(item_num=100)
    model = RankingModel(config)
    batch = _random_batch(8, item_num=100)

    logits = model(batch)

    assert logits.shape == (8,)
    assert torch.isfinite(logits).all()


def test_cold_start_all_padded_history_does_not_crash_or_nan():
    """A brand-new user has zero interaction history: every hist_* slot is PAD_IDX (0)."""
    config = ModelConfig(item_num=100)
    model = RankingModel(config)
    batch = _random_batch(4, item_num=100)
    for key in ("hist_item_id", "hist_event_type", "hist_category", "hist_brand", "hist_price_bucket"):
        batch[key] = torch.zeros_like(batch[key])

    logits = model(batch)

    assert torch.isfinite(logits).all()


def test_predict_proba_is_bounded_between_zero_and_one():
    config = ModelConfig(item_num=50)
    model = RankingModel(config)
    batch = _random_batch(5, item_num=50)

    probs = model.predict_proba(batch)

    assert torch.all(probs >= 0.0) and torch.all(probs <= 1.0)


def test_different_target_items_yield_different_scores_for_same_history():
    """Sanity check that the target embedding actually influences the output
    (i.e. the model isn't accidentally ignoring the candidate item)."""
    config = ModelConfig(item_num=100, embed_dim=16)
    model = RankingModel(config)
    model.eval()
    batch = _random_batch(1, item_num=100)
    batch["target_item_id"] = torch.tensor([5])
    score_a = model.predict_proba(batch).item()
    batch["target_item_id"] = torch.tensor([42])
    score_b = model.predict_proba(batch).item()

    assert score_a != score_b
