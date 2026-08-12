from recsys_lite import db
from recsys_lite.constants import EVENT_CART, EVENT_VIEW
from recsys_lite.features import build_training_examples


def _seed_simple_catalog_and_events(conn):
    conn.executemany(
        "INSERT INTO products (item_id, title, category_id, brand_id, price, price_bucket) VALUES (?,?,?,?,?,?)",
        [
            (1, "A", 1, 1, 10.0, 1),
            (2, "B", 1, 2, 20.0, 2),
            (3, "C", 2, 1, 30.0, 3),
            (4, "D", 2, 2, 40.0, 4),
            (5, "E", 3, 3, 50.0, 5),
        ],
    )
    conn.execute("INSERT INTO users (user_id) VALUES (1)")
    # user 1: view item 1 at t=100, view item 2 at t=110, cart item 2 at t=120
    conn.executemany(
        "INSERT INTO events (user_id, item_id, event_type, ts) VALUES (?, ?, ?, ?)",
        [
            (1, 1, EVENT_VIEW, 100),
            (1, 2, EVENT_VIEW, 110),
            (1, 2, EVENT_CART, 120),
        ],
    )
    conn.commit()


def test_training_example_history_never_includes_the_triggering_event_or_future_events(tmp_path):
    conn = db.reset_db(tmp_path / "f.db")
    _seed_simple_catalog_and_events(conn)

    examples = build_training_examples(conn, seq_len=10, negatives_per_positive=2, min_history=1)
    positives = [e for e in examples if e.label == 1]

    assert len(positives) == 1
    positive = positives[0]
    assert positive.target_item_id == 2
    assert positive.ts == 120
    # history must contain only the two prior views (item 1 @100, item 2 @110), not the cart event itself
    assert positive.hist_item_ids == [1, 2]
    assert positive.hist_event_type_ids == [EVENT_VIEW, EVENT_VIEW]


def test_negative_examples_never_reuse_the_positive_or_history_items(tmp_path):
    conn = db.reset_db(tmp_path / "f2.db")
    _seed_simple_catalog_and_events(conn)

    examples = build_training_examples(conn, seq_len=10, negatives_per_positive=2, min_history=1)
    negatives = [e for e in examples if e.label == 0]

    assert len(negatives) == 2
    for neg in negatives:
        assert neg.target_item_id not in {1, 2}  # 1 and 2 are the user's history/positive
        assert neg.hist_item_ids == [1, 2]  # negatives share the same context as their positive


def test_hard_negative_fraction_one_only_draws_same_category_negatives(tmp_path):
    conn = db.reset_db(tmp_path / "f4.db")
    conn.executemany(
        "INSERT INTO products (item_id, title, category_id, brand_id, price, price_bucket) VALUES (?,?,?,?,?,?)",
        [
            (1, "A", 1, 1, 10.0, 1),
            (2, "B", 1, 2, 20.0, 2),  # positive target, category 1
            (6, "F", 1, 3, 15.0, 1),  # another category-1 item available as a hard negative
            (3, "C", 2, 1, 30.0, 3),
            (4, "D", 2, 2, 40.0, 4),
            (5, "E", 3, 3, 50.0, 5),
        ],
    )
    conn.execute("INSERT INTO users (user_id) VALUES (1)")
    conn.executemany(
        "INSERT INTO events (user_id, item_id, event_type, ts) VALUES (?, ?, ?, ?)",
        [(1, 1, EVENT_VIEW, 100), (1, 2, EVENT_CART, 120)],
    )
    conn.commit()

    examples = build_training_examples(
        conn, seq_len=10, negatives_per_positive=1, min_history=1, hard_negative_fraction=1.0
    )
    negatives = [e for e in examples if e.label == 0]

    assert len(negatives) == 1
    assert negatives[0].target_item_id == 6
    assert negatives[0].target_category_id == 1  # same category as the positive (item 2)


def test_min_history_filters_out_a_users_very_first_interaction(tmp_path):
    conn = db.reset_db(tmp_path / "f3.db")
    conn.executemany(
        "INSERT INTO products (item_id, title, category_id, brand_id, price, price_bucket) VALUES (?,?,?,?,?,?)",
        [(1, "A", 1, 1, 10.0, 1)],
    )
    conn.execute("INSERT INTO users (user_id) VALUES (1)")
    conn.execute(
        "INSERT INTO events (user_id, item_id, event_type, ts) VALUES (1, 1, ?, 100)", (EVENT_CART,)
    )
    conn.commit()

    examples = build_training_examples(conn, seq_len=10, negatives_per_positive=2, min_history=1)
    assert examples == []  # a cart with zero prior history produces no example
