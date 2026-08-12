"""Score a user's candidate pool with the ranking model and return top-K."""

from __future__ import annotations

import torch

from recsys_lite.dataset import pad_sequence
from recsys_lite.features import ItemFeature
from recsys_lite.model import RankingModel
from recsys_lite.online_store import UserSequence
from recsys_lite.serving.schemas import RecommendationItem


def score_candidates(
    model: RankingModel,
    user_sequence: UserSequence,
    candidate_item_ids: list[int],
    item_features: dict[int, ItemFeature],
    seq_len: int,
) -> list[float]:
    if not candidate_item_ids:
        return []

    hist_item = pad_sequence(user_sequence.hist_item_ids, seq_len)
    hist_event = pad_sequence(user_sequence.hist_event_type_ids, seq_len)
    hist_cat = pad_sequence(user_sequence.hist_category_ids, seq_len)
    hist_brand = pad_sequence(user_sequence.hist_brand_ids, seq_len)
    hist_price = pad_sequence(user_sequence.hist_price_bucket_ids, seq_len)
    n = len(candidate_item_ids)

    batch = {
        "hist_item_id": torch.tensor([hist_item] * n, dtype=torch.long),
        "hist_event_type": torch.tensor([hist_event] * n, dtype=torch.long),
        "hist_category": torch.tensor([hist_cat] * n, dtype=torch.long),
        "hist_brand": torch.tensor([hist_brand] * n, dtype=torch.long),
        "hist_price_bucket": torch.tensor([hist_price] * n, dtype=torch.long),
        "target_item_id": torch.tensor(candidate_item_ids, dtype=torch.long),
        "target_category": torch.tensor(
            [item_features[i].category_id for i in candidate_item_ids], dtype=torch.long
        ),
        "target_brand": torch.tensor(
            [item_features[i].brand_id for i in candidate_item_ids], dtype=torch.long
        ),
        "target_price_bucket": torch.tensor(
            [item_features[i].price_bucket for i in candidate_item_ids], dtype=torch.long
        ),
    }
    with torch.no_grad():
        model.eval()
        return torch.sigmoid(model(batch)).tolist()


def top_k(
    candidate_item_ids: list[int],
    scores: list[float],
    item_features: dict[int, ItemFeature],
    titles: dict[int, str],
    prices: dict[int, float],
    k: int,
) -> list[RecommendationItem]:
    ranked = sorted(zip(candidate_item_ids, scores), key=lambda pair: pair[1], reverse=True)[:k]
    items = []
    for item_id, score in ranked:
        feat = item_features.get(item_id)
        items.append(
            RecommendationItem(
                item_id=item_id,
                title=titles.get(item_id, f"Item {item_id}"),
                category_id=feat.category_id if feat else 0,
                brand_id=feat.brand_id if feat else 0,
                price=prices.get(item_id, 0.0),
                score=round(score, 4),
            )
        )
    return items
