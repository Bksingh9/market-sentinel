from __future__ import annotations

import json
from pathlib import Path

from market_sentinel.model_training import LinearModel


class ModelStore:
    def __init__(self, root: Path):
        self.root = root
        self.root.mkdir(parents=True, exist_ok=True)
        self.active_path = self.root / "active_model.txt"

    def save(self, model: LinearModel) -> Path:
        path = self.root / f"{model.version}.json"
        path.write_text(json.dumps(model.to_payload(), indent=2, sort_keys=True), encoding="utf-8")
        return path

    def activate(self, version: str) -> None:
        path = self.root / f"{version}.json"
        if not path.exists():
            raise FileNotFoundError(path)
        self.active_path.write_text(version, encoding="utf-8")

    def load(self, version: str) -> LinearModel:
        payload = json.loads((self.root / f"{version}.json").read_text(encoding="utf-8"))
        return LinearModel.from_payload(payload)

    def load_active(self) -> LinearModel:
        version = self.active_path.read_text(encoding="utf-8").strip()
        return self.load(version)
