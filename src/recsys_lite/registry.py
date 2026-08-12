"""A lightweight, file-backed model registry.

Stands in for MLflow's tracking server + model registry: every trained
model is saved under a version directory with its config and metrics, and
`registry.json` tracks which version is the serving "champion" versus an
unpromoted "candidate" -- the same champion/candidate distinction the
full-scale platform's progressive rollout is built around, just without
the Kubernetes deployment machinery behind it.
"""

from __future__ import annotations

import json
import time
from dataclasses import asdict
from pathlib import Path

import torch

from recsys_lite.model import ModelConfig, RankingModel

DEFAULT_REGISTRY_DIR = Path(__file__).resolve().parents[2] / "models"


class ModelRegistry:
    def __init__(self, root: Path | str = DEFAULT_REGISTRY_DIR):
        self.root = Path(root)
        self.root.mkdir(parents=True, exist_ok=True)
        self.index_path = self.root / "registry.json"
        if not self.index_path.exists():
            self._write_index({"champion": None, "versions": {}})

    def _read_index(self) -> dict:
        return json.loads(self.index_path.read_text())

    def _write_index(self, index: dict) -> None:
        self.index_path.write_text(json.dumps(index, indent=2))

    def register(
        self,
        model: RankingModel,
        config: ModelConfig,
        metrics: dict,
        dataset_hash: str | None = None,
    ) -> str:
        index = self._read_index()
        version = f"v{len(index['versions']) + 1}"
        version_dir = self.root / version
        version_dir.mkdir(parents=True, exist_ok=True)

        torch.save(model.state_dict(), version_dir / "model.pt")
        (version_dir / "config.json").write_text(json.dumps(asdict(config), indent=2))

        index["versions"][version] = {
            "created_at": time.time(),
            "metrics": metrics,
            "dataset_hash": dataset_hash,
        }
        self._write_index(index)
        return version

    def promote(self, version: str) -> None:
        index = self._read_index()
        if version not in index["versions"]:
            raise ValueError(f"unknown model version: {version}")
        index["champion"] = version
        self._write_index(index)

    def champion_version(self) -> str | None:
        return self._read_index().get("champion")

    def list_versions(self) -> dict:
        return self._read_index()["versions"]

    def load(self, version: str) -> tuple[RankingModel, ModelConfig]:
        version_dir = self.root / version
        config_dict = json.loads((version_dir / "config.json").read_text())
        config = ModelConfig(**config_dict)
        model = RankingModel(config)
        model.load_state_dict(torch.load(version_dir / "model.pt", map_location="cpu"))
        model.eval()
        return model, config

    def load_champion(self) -> tuple[RankingModel, ModelConfig, str]:
        version = self.champion_version()
        if version is None:
            raise RuntimeError(
                "no champion model registered yet -- run `python -m recsys_lite.train` first"
            )
        model, config = self.load(version)
        return model, config, version
