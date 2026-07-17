from __future__ import annotations

from dataclasses import asdict, dataclass
from datetime import date, datetime
from decimal import Decimal
import hashlib
import json
from pathlib import Path

from market_sentinel.historical_data import (
    AdjustmentMode,
    CanonicalDailyBar,
    DatasetManifest,
)


@dataclass(frozen=True)
class StoredDataset:
    manifest: DatasetManifest
    manifest_path: Path
    bars_path: Path


class DatasetStore:
    def __init__(self, root: Path):
        self.root = root

    def write(
        self,
        bars: tuple[CanonicalDailyBar, ...],
        *,
        requested_start: date,
        requested_end: date,
        interval: str,
        page_count: int,
        feed: str | None,
        reconciliation_record_id: str | None = None,
    ) -> StoredDataset:
        if not bars:
            raise ValueError("cannot persist an empty dataset")
        lines = b"".join(
            json.dumps(
                item.to_payload(),
                sort_keys=True,
                separators=(",", ":"),
            ).encode("utf-8")
            + b"\n"
            for item in bars
        )
        dataset_id = hashlib.sha256(lines).hexdigest()
        directory = self.root / bars[0].market / bars[0].symbol / dataset_id
        directory.mkdir(parents=True, exist_ok=True)
        bars_path = directory / "bars.jsonl"
        _write_immutable(bars_path, lines, "content-addressed dataset collision")

        manifest = DatasetManifest(
            dataset_id=dataset_id,
            provider=bars[0].provider,
            provider_symbol=bars[0].provider_symbol,
            symbol=bars[0].symbol,
            market=bars[0].market,
            currency=bars[0].currency,
            interval=interval,
            adjustment_mode=bars[0].adjustment_mode,
            requested_start=requested_start,
            requested_end=requested_end,
            first_trading_date=bars[0].trading_date,
            last_trading_date=bars[-1].trading_date,
            retrieved_at=bars[0].retrieved_at,
            response_page_count=page_count,
            requested_feed=feed,
            source_checksum=bars[0].source_checksum,
            row_count=len(bars),
            reconciliation_record_id=reconciliation_record_id,
        )
        manifest_path = directory / "manifest.json"
        payload = asdict(manifest)
        payload = {
            key: value.value
            if isinstance(value, AdjustmentMode)
            else value.isoformat()
            if isinstance(value, (date, datetime))
            else value
            for key, value in payload.items()
        }
        encoded = json.dumps(payload, indent=2, sort_keys=True).encode("utf-8")
        _write_immutable(
            manifest_path,
            encoded,
            "immutable dataset manifest differs",
        )
        return StoredDataset(manifest, manifest_path, bars_path)

    def load(
        self,
        market: str,
        symbol: str,
        dataset_id: str,
    ) -> tuple[DatasetManifest, tuple[CanonicalDailyBar, ...]]:
        directory = self.root / market / symbol / dataset_id
        lines = (directory / "bars.jsonl").read_bytes()
        if hashlib.sha256(lines).hexdigest() != dataset_id:
            raise ValueError("dataset checksum mismatch")
        payload = json.loads(
            (directory / "manifest.json").read_text(encoding="utf-8")
        )
        if (
            payload["dataset_id"] != dataset_id
            or payload["market"] != market
            or payload["symbol"] != symbol
        ):
            raise ValueError("dataset manifest identity mismatch")
        manifest = _manifest_from_payload(payload)
        bars = tuple(
            _bar_from_payload(json.loads(line))
            for line in lines.splitlines()
            if line
        )
        if len(bars) != manifest.row_count:
            raise ValueError("dataset manifest row count mismatch")
        return manifest, bars


def _write_immutable(path: Path, encoded: bytes, mismatch_message: str) -> None:
    try:
        with path.open("xb") as handle:
            handle.write(encoded)
    except FileExistsError:
        if path.read_bytes() != encoded:
            raise RuntimeError(mismatch_message) from None


def _manifest_from_payload(payload: dict[str, object]) -> DatasetManifest:
    return DatasetManifest(
        dataset_id=str(payload["dataset_id"]),
        provider=str(payload["provider"]),
        provider_symbol=str(payload["provider_symbol"]),
        symbol=str(payload["symbol"]),
        market=str(payload["market"]),
        currency=str(payload["currency"]),
        interval=str(payload["interval"]),
        adjustment_mode=AdjustmentMode(str(payload["adjustment_mode"])),
        requested_start=date.fromisoformat(str(payload["requested_start"])),
        requested_end=date.fromisoformat(str(payload["requested_end"])),
        first_trading_date=date.fromisoformat(str(payload["first_trading_date"])),
        last_trading_date=date.fromisoformat(str(payload["last_trading_date"])),
        retrieved_at=datetime.fromisoformat(str(payload["retrieved_at"])),
        response_page_count=int(payload["response_page_count"]),
        requested_feed=None
        if payload["requested_feed"] is None
        else str(payload["requested_feed"]),
        source_checksum=str(payload["source_checksum"]),
        row_count=int(payload["row_count"]),
        reconciliation_record_id=None
        if payload["reconciliation_record_id"] is None
        else str(payload["reconciliation_record_id"]),
    )


def _bar_from_payload(payload: dict[str, object]) -> CanonicalDailyBar:
    return CanonicalDailyBar(
        provider=str(payload["provider"]),
        provider_symbol=str(payload["provider_symbol"]),
        symbol=str(payload["symbol"]),
        market=str(payload["market"]),
        currency=str(payload["currency"]),
        trading_date=date.fromisoformat(str(payload["trading_date"])),
        source_timezone=str(payload["source_timezone"]),
        open=Decimal(str(payload["open"])),
        high=Decimal(str(payload["high"])),
        low=Decimal(str(payload["low"])),
        close=Decimal(str(payload["close"])),
        volume=int(payload["volume"]),
        adjustment_mode=AdjustmentMode(str(payload["adjustment_mode"])),
        retrieved_at=datetime.fromisoformat(str(payload["retrieved_at"])),
        source_checksum=str(payload["source_checksum"]),
    )
