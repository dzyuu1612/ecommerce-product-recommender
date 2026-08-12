"""Sequence ranking model.

Conceptually: a candidate item attends over the user's recent behavior
history to produce a click/cart-likelihood score, in the spirit of
sequence-aware CTR models such as the Behavior Sequence Transformer
(Chen et al., 2019, https://arxiv.org/abs/1905.06874). The *idea* of
"append the target item to the sequence and let attention relate it to
history" is a well-known modeling pattern, not any one paper's code; the
implementation below is original and built entirely on PyTorch's
standard ``nn.TransformerEncoder`` primitive rather than any hand-rolled
attention math.
"""

from __future__ import annotations

from dataclasses import dataclass

import torch
from torch import Tensor, nn

from recsys_lite.constants import (
    NUM_BRANDS,
    NUM_EVENT_TYPES,
    NUM_PRICE_BUCKETS,
    PAD_IDX,
    SEQ_LEN,
)
from recsys_lite.constants import NUM_CATEGORIES as _NUM_CATEGORIES


@dataclass
class ModelConfig:
    item_num: int
    category_num: int = _NUM_CATEGORIES + 1
    brand_num: int = NUM_BRANDS + 1
    price_bucket_num: int = NUM_PRICE_BUCKETS + 1
    event_type_num: int = NUM_EVENT_TYPES
    embed_dim: int = 32
    n_heads: int = 4
    n_layers: int = 2
    ff_dim: int = 128
    dropout: float = 0.1
    seq_len: int = SEQ_LEN

    def to_dict(self) -> dict:
        return self.__dict__.copy()


class RankingModel(nn.Module):
    """Scores a candidate item against a user's recent behavior sequence."""

    def __init__(self, config: ModelConfig):
        super().__init__()
        self.config = config
        d = config.embed_dim

        self.item_emb = nn.Embedding(config.item_num + 1, d, padding_idx=PAD_IDX)
        self.category_emb = nn.Embedding(config.category_num, d, padding_idx=PAD_IDX)
        self.brand_emb = nn.Embedding(config.brand_num, d, padding_idx=PAD_IDX)
        self.price_emb = nn.Embedding(config.price_bucket_num, d, padding_idx=PAD_IDX)
        self.event_emb = nn.Embedding(config.event_type_num, d, padding_idx=PAD_IDX)
        # +1 extra position slot for the appended target/candidate token.
        self.pos_emb = nn.Embedding(config.seq_len + 1, d)

        self.input_norm = nn.LayerNorm(d)
        encoder_layer = nn.TransformerEncoderLayer(
            d_model=d,
            nhead=config.n_heads,
            dim_feedforward=config.ff_dim,
            dropout=config.dropout,
            batch_first=True,
            activation="gelu",
        )
        self.transformer = nn.TransformerEncoder(encoder_layer, num_layers=config.n_layers)

        self.head = nn.Sequential(
            nn.Linear(d, config.ff_dim),
            nn.GELU(),
            nn.Dropout(config.dropout),
            nn.Linear(config.ff_dim, 1),
        )

    def _history_embedding(self, batch: dict[str, Tensor]) -> tuple[Tensor, Tensor]:
        hist_item = batch["hist_item_id"]
        positions = torch.arange(hist_item.shape[1], device=hist_item.device).unsqueeze(0)
        emb = (
            self.item_emb(hist_item)
            + self.category_emb(batch["hist_category"])
            + self.brand_emb(batch["hist_brand"])
            + self.price_emb(batch["hist_price_bucket"])
            + self.event_emb(batch["hist_event_type"])
            + self.pos_emb(positions.expand_as(hist_item))
        )
        pad_mask = hist_item == PAD_IDX
        return emb, pad_mask

    def _target_embedding(self, batch: dict[str, Tensor], seq_len: int) -> Tensor:
        target_pos = torch.full(
            (batch["target_item_id"].shape[0],), seq_len, device=batch["target_item_id"].device
        )
        return (
            self.item_emb(batch["target_item_id"])
            + self.category_emb(batch["target_category"])
            + self.brand_emb(batch["target_brand"])
            + self.price_emb(batch["target_price_bucket"])
            + self.pos_emb(target_pos)
        )

    def forward(self, batch: dict[str, Tensor]) -> Tensor:
        """Returns raw logits, shape [batch]. Apply sigmoid for a probability."""
        hist_emb, hist_pad_mask = self._history_embedding(batch)
        target_emb = self._target_embedding(batch, hist_emb.shape[1]).unsqueeze(1)

        sequence = torch.cat([hist_emb, target_emb], dim=1)
        sequence = self.input_norm(sequence)

        target_pad_mask = torch.zeros(
            hist_pad_mask.shape[0], 1, dtype=torch.bool, device=hist_pad_mask.device
        )
        full_pad_mask = torch.cat([hist_pad_mask, target_pad_mask], dim=1)

        encoded = self.transformer(sequence, src_key_padding_mask=full_pad_mask)
        pooled = encoded[:, -1, :]  # representation at the appended target-token position
        return self.head(pooled).squeeze(-1)

    @torch.no_grad()
    def predict_proba(self, batch: dict[str, Tensor]) -> Tensor:
        self.eval()
        return torch.sigmoid(self.forward(batch))
