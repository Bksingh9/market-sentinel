from __future__ import annotations

import hashlib
import json
from pathlib import Path

import sklearn

from market_sentinel.model_training import MarketModelArtifact


class ModelStore:
    def __init__(self, root: Path):
        self.root = root
        self.root.mkdir(parents=True, exist_ok=True)

    def save(self, model: MarketModelArtifact) -> Path:
        validated = MarketModelArtifact.from_payload(model.to_payload())
        directory = self._lane_directory(validated.market, validated.symbol)
        directory.mkdir(parents=True, exist_ok=True)
        path = directory / f"{validated.version}.json"
        encoded = json.dumps(
            validated.to_payload(),
            sort_keys=True,
            separators=(",", ":"),
        ).encode("utf-8")
        checksum = hashlib.sha256(encoded).hexdigest()
        checksum_path = directory / f"{validated.version}.sha256"
        _write_immutable(path, encoded, "immutable model artifact differs")
        _write_immutable(
            checksum_path,
            checksum.encode("ascii"),
            "immutable model checksum differs",
        )
        return path

    def activate_for_paper(self, market: str, symbol: str, version: str) -> None:
        artifact = self.load(market, symbol, version)
        if not artifact.promoted_for_paper:
            raise ValueError("model is not promoted for paper")
        pointer = self._lane_directory(market, symbol) / "active-paper.txt"
        pointer.write_text(version, encoding="utf-8")

    def load(self, market: str, symbol: str, version: str) -> MarketModelArtifact:
        directory = self._lane_directory(market, symbol)
        path = directory / f"{version}.json"
        encoded = path.read_bytes()
        expected_checksum = (
            directory / f"{version}.sha256"
        ).read_text(encoding="ascii").strip()
        if hashlib.sha256(encoded).hexdigest() != expected_checksum:
            raise ValueError("model artifact checksum mismatch")
        artifact = MarketModelArtifact.from_payload(json.loads(encoded))
        if (artifact.market, artifact.symbol, artifact.version) != (
            market,
            symbol,
            version,
        ):
            raise ValueError("model artifact identity mismatch")
        return artifact

    def load_active(
        self,
        market: str,
        symbol: str,
        *,
        expected_schema: str,
        expected_dataset_checksum: str,
    ) -> MarketModelArtifact:
        directory = self._lane_directory(market, symbol)
        version = (directory / "active-paper.txt").read_text(
            encoding="utf-8"
        ).strip()
        artifact = self.load(market, symbol, version)
        if artifact.feature_schema != expected_schema:
            raise ValueError("active model feature schema mismatch")
        if artifact.dataset_checksum != expected_dataset_checksum:
            raise ValueError("active model dataset checksum mismatch")
        runtime_version = tuple(sklearn.__version__.split(".")[:2])
        artifact_version = tuple(artifact.sklearn_version.split(".")[:2])
        if artifact_version != runtime_version:
            raise ValueError("active model sklearn major/minor mismatch")
        return artifact

    def _lane_directory(self, market: str, symbol: str) -> Path:
        return self.root / market / symbol


def _write_immutable(path: Path, encoded: bytes, mismatch_message: str) -> None:
    try:
        with path.open("xb") as handle:
            handle.write(encoded)
    except FileExistsError:
        if path.read_bytes() != encoded:
            raise RuntimeError(mismatch_message) from None
