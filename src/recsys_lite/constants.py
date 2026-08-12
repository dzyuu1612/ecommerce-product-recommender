"""Shared cardinalities and vocab used by the generator, feature builder, and model.

Every embedding table in the model is sized from these constants, so the
generator can never produce an id the model wasn't built to embed.
"""

from __future__ import annotations

PAD_IDX = 0

# Category/brand ids are generated in [1, N]; id 0 is reserved for padding.
NUM_CATEGORIES = 24
NUM_BRANDS = 120
NUM_PRICE_BUCKETS = 10
NUM_EVENT_TYPES = 4  # 0=pad, 1=view, 2=cart, 3=purchase
SEQ_LEN = 20  # max behavior-history length fed to the model

EVENT_VIEW = 1
EVENT_CART = 2
EVENT_PURCHASE = 3
EVENT_NAMES = {EVENT_VIEW: "view", EVENT_CART: "cart", EVENT_PURCHASE: "purchase"}
EVENT_IDS = {name: idx for idx, name in EVENT_NAMES.items()}

PRICE_MIN = 5.0
PRICE_MAX = 500.0
