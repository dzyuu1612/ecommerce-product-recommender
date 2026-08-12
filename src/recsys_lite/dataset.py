"""Torch Dataset, padding, and the temporal train/val/test split.

Splitting by time (not randomly) is the same discipline the full-scale
platform's SplitService applies: a sequence model must never be validated
on an interaction that happened before events in its own training set, or
the reported metrics are optimistic nonsense.
"""

from __future__ import annotations

import json
from pathlib import Path

import torch
from torch.utils.data import Dataset

from recsys_lite.constants import PAD_IDX, SEQ_LEN
from recsys_lite.features import TrainingExample


def pad_sequence(seq: list[int], seq_len: int) -> list[int]:
    if len(seq) >= seq_len:
        return seq[-seq_len:]
    return seq + [PAD_IDX] * (seq_len - len(seq))


def load_examples(path: Path | str) -> list[TrainingExample]:
    examples = []
    with open(path, encoding="utf-8") as fh:
        for line in fh:
            row = json.loads(line)
            examples.append(TrainingExample(**row))
    return examples


def temporal_split(
    examples: list[TrainingExample], val_frac: float = 0.15, test_frac: float = 0.15
) -> tuple[list[TrainingExample], list[TrainingExample], list[TrainingExample]]:
    """Split by timestamp cutoffs so validation/test rows always occur after training rows."""
    ordered = sorted(examples, key=lambda e: e.ts)
    n = len(ordered)
    n_test = int(n * test_frac)
    n_val = int(n * val_frac)
    n_train = n - n_val - n_test
    return ordered[:n_train], ordered[n_train:n_train + n_val], ordered[n_train + n_val:]


class RankingDataset(Dataset):
    def __init__(self, examples: list[TrainingExample], seq_len: int = SEQ_LEN):
        self.examples = examples
        self.seq_len = seq_len

    def __len__(self) -> int:
        return len(self.examples)

    def __getitem__(self, idx: int) -> dict[str, torch.Tensor]:
        ex = self.examples[idx]
        seq_len = self.seq_len
        return {
            "hist_item_id": torch.tensor(pad_sequence(ex.hist_item_ids, seq_len), dtype=torch.long),
            "hist_event_type": torch.tensor(pad_sequence(ex.hist_event_type_ids, seq_len), dtype=torch.long),
            "hist_category": torch.tensor(pad_sequence(ex.hist_category_ids, seq_len), dtype=torch.long),
            "hist_brand": torch.tensor(pad_sequence(ex.hist_brand_ids, seq_len), dtype=torch.long),
            "hist_price_bucket": torch.tensor(pad_sequence(ex.hist_price_bucket_ids, seq_len), dtype=torch.long),
            "target_item_id": torch.tensor(ex.target_item_id, dtype=torch.long),
            "target_category": torch.tensor(ex.target_category_id, dtype=torch.long),
            "target_brand": torch.tensor(ex.target_brand_id, dtype=torch.long),
            "target_price_bucket": torch.tensor(ex.target_price_bucket, dtype=torch.long),
            "label": torch.tensor(float(ex.label), dtype=torch.float32),
        }
