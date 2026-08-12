"""Training CLI: load point-in-time examples, temporal split, train the
ranking model, evaluate with AUC/NDCG@K/HitRate@K, and register the result
in the local model registry -- auto-promoting it to champion the first
time, or whenever it beats the current champion's validation NDCG@5.
"""

from __future__ import annotations

import argparse
import time

import torch
from torch import nn
from torch.utils.data import DataLoader

from recsys_lite import db, metrics
from recsys_lite.dataset import RankingDataset, load_examples, temporal_split
from recsys_lite.features import DEFAULT_FEATURES_PATH, TrainingExample
from recsys_lite.model import ModelConfig, RankingModel
from recsys_lite.registry import DEFAULT_REGISTRY_DIR, ModelRegistry


def _infer_item_num(examples_db_path) -> int:
    conn = db.connect(examples_db_path)
    try:
        row = conn.execute("SELECT MAX(item_id) AS max_id FROM products").fetchone()
        return int(row["max_id"])
    finally:
        conn.close()


@torch.no_grad()
def _score_examples(model: RankingModel, examples: list[TrainingExample], batch_size: int = 512) -> list[float]:
    model.eval()
    loader = DataLoader(RankingDataset(examples), batch_size=batch_size, shuffle=False)
    scores: list[float] = []
    for batch in loader:
        batch.pop("label")
        scores.extend(torch.sigmoid(model(batch)).tolist())
    return scores


def _evaluate(model: RankingModel, examples: list[TrainingExample], k: int = 5) -> dict:
    scores = _score_examples(model, examples)
    labels = [e.label for e in examples]
    keys = [(e.user_id, e.ts) for e in examples]
    return metrics.evaluate_grouped(keys, labels, scores, k=k)


def train_model(
    examples_path=DEFAULT_FEATURES_PATH,
    db_path=db.DEFAULT_DB_PATH,
    registry_dir=DEFAULT_REGISTRY_DIR,
    epochs: int = 6,
    batch_size: int = 256,
    lr: float = 1e-3,
    embed_dim: int = 32,
    seed: int = 13,
    eval_k: int = 5,
) -> dict:
    torch.manual_seed(seed)
    examples = load_examples(examples_path)
    if not examples:
        raise RuntimeError(f"no training examples at {examples_path} -- run features.py first")

    train_ex, val_ex, test_ex = temporal_split(examples)
    item_num = _infer_item_num(db_path)

    config = ModelConfig(item_num=item_num, embed_dim=embed_dim)
    model = RankingModel(config)
    optimizer = torch.optim.Adam(model.parameters(), lr=lr)
    loss_fn = nn.BCEWithLogitsLoss()
    train_loader = DataLoader(RankingDataset(train_ex), batch_size=batch_size, shuffle=True)

    best_ndcg = -1.0
    best_state = None
    history = []

    for epoch in range(1, epochs + 1):
        model.train()
        total_loss, n_rows = 0.0, 0
        for batch in train_loader:
            optimizer.zero_grad()
            labels = batch.pop("label")
            logits = model(batch)
            loss = loss_fn(logits, labels)
            loss.backward()
            optimizer.step()
            total_loss += loss.item() * labels.shape[0]
            n_rows += labels.shape[0]

        val_metrics = _evaluate(model, val_ex, k=eval_k)
        history.append({"epoch": epoch, "train_loss": total_loss / n_rows, **val_metrics})
        print(
            f"epoch {epoch}/{epochs}  loss={total_loss / n_rows:.4f}  "
            f"val_auc={val_metrics['auc']:.4f}  val_ndcg@{eval_k}={val_metrics[f'ndcg@{eval_k}']:.4f}"
        )

        if val_metrics[f"ndcg@{eval_k}"] > best_ndcg:
            best_ndcg = val_metrics[f"ndcg@{eval_k}"]
            best_state = {k: v.clone() for k, v in model.state_dict().items()}

    if best_state is not None:
        model.load_state_dict(best_state)

    test_metrics = _evaluate(model, test_ex, k=eval_k)
    print(f"test_auc={test_metrics['auc']:.4f}  test_ndcg@{eval_k}={test_metrics[f'ndcg@{eval_k}']:.4f}")

    registry = ModelRegistry(registry_dir)
    version = registry.register(
        model,
        config,
        metrics={"val": {"best_ndcg": best_ndcg, "eval_k": eval_k}, "test": test_metrics, "history": history},
    )

    current_champion = registry.champion_version()
    should_promote = current_champion is None
    if current_champion is not None:
        champion_metrics = registry.list_versions()[current_champion]["metrics"]
        champion_ndcg = champion_metrics.get("val", {}).get("best_ndcg", -1.0)
        should_promote = best_ndcg >= champion_ndcg

    if should_promote:
        registry.promote(version)
        print(f"promoted {version} to champion (val_ndcg@{eval_k}={best_ndcg:.4f})")
    else:
        print(f"{version} registered as candidate; champion {current_champion} was not beaten")

    return {"version": version, "promoted": should_promote, "test_metrics": test_metrics, "val_ndcg": best_ndcg}


def main() -> None:
    parser = argparse.ArgumentParser(description="Train the ranking model.")
    parser.add_argument("--examples-path", type=str, default=str(DEFAULT_FEATURES_PATH))
    parser.add_argument("--db-path", type=str, default=str(db.DEFAULT_DB_PATH))
    parser.add_argument("--registry-dir", type=str, default=str(DEFAULT_REGISTRY_DIR))
    parser.add_argument("--epochs", type=int, default=6)
    parser.add_argument("--batch-size", type=int, default=256)
    parser.add_argument("--lr", type=float, default=1e-3)
    parser.add_argument("--embed-dim", type=int, default=32)
    parser.add_argument("--seed", type=int, default=13)
    args = parser.parse_args()

    started = time.time()
    result = train_model(
        examples_path=args.examples_path,
        db_path=args.db_path,
        registry_dir=args.registry_dir,
        epochs=args.epochs,
        batch_size=args.batch_size,
        lr=args.lr,
        embed_dim=args.embed_dim,
        seed=args.seed,
    )
    print(f"done in {time.time() - started:.1f}s -> {result}")


if __name__ == "__main__":
    main()
