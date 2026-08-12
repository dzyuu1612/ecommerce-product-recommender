from recsys_lite.constants import PAD_IDX
from recsys_lite.dataset import RankingDataset, pad_sequence, temporal_split
from recsys_lite.features import TrainingExample


def _example(ts: int, hist_len: int = 3) -> TrainingExample:
    return TrainingExample(
        user_id=1,
        ts=ts,
        hist_item_ids=list(range(1, hist_len + 1)),
        hist_event_type_ids=[1] * hist_len,
        hist_category_ids=[1] * hist_len,
        hist_brand_ids=[1] * hist_len,
        hist_price_bucket_ids=[1] * hist_len,
        target_item_id=99,
        target_category_id=1,
        target_brand_id=1,
        target_price_bucket=1,
        label=1,
    )


def test_pad_sequence_pads_short_sequences_with_pad_idx():
    assert pad_sequence([1, 2, 3], 5) == [1, 2, 3, PAD_IDX, PAD_IDX]


def test_pad_sequence_truncates_to_the_most_recent_entries():
    assert pad_sequence([1, 2, 3, 4, 5], 3) == [3, 4, 5]


def test_temporal_split_never_lets_a_later_event_land_in_an_earlier_split():
    examples = [_example(ts) for ts in range(100)]
    train, val, test = temporal_split(examples, val_frac=0.2, test_frac=0.2)

    assert len(train) + len(val) + len(test) == len(examples)
    assert max(e.ts for e in train) < min(e.ts for e in val)
    assert max(e.ts for e in val) < min(e.ts for e in test)


def test_ranking_dataset_produces_fixed_shape_tensors():
    ds = RankingDataset([_example(1, hist_len=3), _example(2, hist_len=30)], seq_len=10)
    row_short, row_long = ds[0], ds[1]

    assert row_short["hist_item_id"].shape == (10,)
    assert row_long["hist_item_id"].shape == (10,)
    assert row_short["label"].item() == 1.0
