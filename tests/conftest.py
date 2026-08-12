import importlib
import sys

import pytest

from recsys_lite import features, generator, train


@pytest.fixture(scope="session")
def serving_env(tmp_path_factory):
    """Generate a tiny dataset, train a tiny model, and point the serving app
    at it via env vars -- exercising the exact same code path a real deploy
    uses, just at a size that runs in under a few seconds.
    """
    workdir = tmp_path_factory.mktemp("serving_env")
    db_path = workdir / "recsys_lite.db"
    features_path = workdir / "training_examples.jsonl"
    registry_dir = workdir / "models"

    generator.generate_all(db_path=db_path, n_items=60, n_users=60, seed=1, days_back=14)

    import sqlite3

    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    examples = features.build_training_examples(conn, negatives_per_positive=2, min_history=1)
    conn.close()
    features.write_jsonl(examples, features_path)

    train.train_model(
        examples_path=features_path,
        db_path=db_path,
        registry_dir=registry_dir,
        epochs=1,
        batch_size=64,
        embed_dim=8,
    )

    import os

    os.environ["RECSYS_LITE_DB_PATH"] = str(db_path)
    os.environ["RECSYS_LITE_REGISTRY_DIR"] = str(registry_dir)

    for name in list(sys.modules):
        if name.startswith("recsys_lite.serving"):
            del sys.modules[name]

    app_module = importlib.import_module("recsys_lite.serving.app")
    return app_module
