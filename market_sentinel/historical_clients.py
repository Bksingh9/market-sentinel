from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime, timedelta, timezone
from decimal import Decimal
import hashlib
import json
from typing import Any, Protocol

from market_sentinel.api_clients import HttpClient
from market_sentinel.historical_data import AdjustmentMode, CanonicalDailyBar


@dataclass(frozen=True)
class HistoricalDownload:
    bars: tuple[CanonicalDailyBar, ...]
    page_count: int
    source_query: dict[str, str]
    response_checksum: str


def sanitize_provider_error(message: str, secrets: tuple[str, ...]) -> str:
    sanitized = message
    for secret in secrets:
        if secret:
            sanitized = sanitized.replace(secret, "[REDACTED]")
    return sanitized


def _checksum(payloads: list[dict[str, Any]]) -> str:
    encoded = json.dumps(
        payloads,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


class AlpacaHistoricalClient:
    endpoint = "https://data.alpaca.markets/v2/stocks/bars"

    def __init__(self, http: HttpClient, *, key_id: str, secret_key: str):
        self.http = http
        self.headers = {
            "APCA-API-KEY-ID": key_id,
            "APCA-API-SECRET-KEY": secret_key,
        }

    def download(
        self,
        *,
        symbol: str,
        start: date,
        end: date,
        feed: str,
    ) -> HistoricalDownload:
        if start > end:
            raise ValueError("historical start must not follow end")
        query = {
            "symbols": symbol,
            "timeframe": "1Day",
            "start": start.isoformat(),
            "end": end.isoformat(),
            "sort": "asc",
            "adjustment": "all",
            "feed": feed,
        }
        pages: list[dict[str, Any]] = []
        raw_bars: list[dict[str, Any]] = []
        page_token: str | None = None
        while True:
            request_query = dict(query)
            if page_token is not None:
                request_query["page_token"] = page_token
            response = self.http.get_json(
                self.endpoint,
                headers=self.headers,
                query=request_query,
            )
            if response.status_code != 200:
                raise RuntimeError(
                    "Alpaca historical request failed with status "
                    f"{response.status_code}"
                )
            pages.append(response.payload)
            raw_bars.extend(response.payload.get("bars", {}).get(symbol, []))
            page_token_value = response.payload.get("next_page_token")
            page_token = str(page_token_value) if page_token_value else None
            if page_token is None:
                break
        checksum = _checksum(pages)
        retrieved_at = datetime.now(timezone.utc)
        bars = tuple(
            CanonicalDailyBar(
                provider="alpaca",
                provider_symbol=symbol,
                symbol=symbol,
                market="US",
                currency="USD",
                trading_date=date.fromisoformat(str(item["t"])[:10]),
                source_timezone="America/New_York",
                open=Decimal(str(item["o"])),
                high=Decimal(str(item["h"])),
                low=Decimal(str(item["l"])),
                close=Decimal(str(item["c"])),
                volume=int(item["v"]),
                adjustment_mode=AdjustmentMode.ALL,
                retrieved_at=retrieved_at,
                source_checksum=checksum,
            )
            for item in raw_bars
        )
        return HistoricalDownload(bars, len(pages), query, checksum)


class GrowwHistoricalSDK(Protocol):
    EXCHANGE_NSE: str
    SEGMENT_CASH: str
    CANDLE_INTERVAL_DAY: str

    def get_instrument_by_exchange_and_trading_symbol(
        self,
        *,
        exchange: str,
        trading_symbol: str,
    ) -> dict[str, object]:
        ...

    def get_historical_candles(
        self,
        *,
        exchange: str,
        segment: str,
        groww_symbol: str,
        start_time: str,
        end_time: str,
        candle_interval: str,
    ) -> dict[str, object]:
        ...


class GrowwHistoricalClient:
    def __init__(self, sdk: GrowwHistoricalSDK):
        self.sdk = sdk

    def download(
        self,
        *,
        symbol: str,
        start: date,
        end: date,
    ) -> HistoricalDownload:
        if start > end:
            raise ValueError("historical start must not follow end")
        instrument = self.sdk.get_instrument_by_exchange_and_trading_symbol(
            exchange=self.sdk.EXCHANGE_NSE,
            trading_symbol=symbol,
        )
        identity = (
            instrument.get("exchange"),
            instrument.get("segment"),
            instrument.get("trading_symbol"),
        )
        if identity != ("NSE", "CASH", symbol):
            raise ValueError(
                "Groww instrument must resolve to the requested NSE CASH symbol"
            )
        provider_symbol = str(instrument["groww_symbol"])
        if provider_symbol != f"NSE-{symbol}":
            raise ValueError("Groww instrument returned an unexpected Groww symbol")

        payloads: list[dict[str, Any]] = []
        cursor = start
        while cursor <= end:
            chunk_end = min(end, cursor + timedelta(days=179))
            payload = self.sdk.get_historical_candles(
                exchange=self.sdk.EXCHANGE_NSE,
                segment=self.sdk.SEGMENT_CASH,
                groww_symbol=provider_symbol,
                start_time=f"{cursor.isoformat()} 00:00:00",
                end_time=f"{chunk_end.isoformat()} 23:59:59",
                candle_interval=self.sdk.CANDLE_INTERVAL_DAY,
            )
            payloads.append(payload)
            cursor = chunk_end + timedelta(days=1)

        checksum = _checksum(payloads)
        retrieved_at = datetime.now(timezone.utc)
        candles = [
            item
            for payload in payloads
            for item in payload.get("candles", [])
        ]
        bars = tuple(
            CanonicalDailyBar(
                provider="groww",
                provider_symbol=provider_symbol,
                symbol=symbol,
                market="IN",
                currency="INR",
                trading_date=date.fromisoformat(str(item[0])[:10]),
                source_timezone="Asia/Kolkata",
                open=Decimal(str(item[1])),
                high=Decimal(str(item[2])),
                low=Decimal(str(item[3])),
                close=Decimal(str(item[4])),
                volume=int(item[5]),
                adjustment_mode=AdjustmentMode.PROVIDER_UNSPECIFIED,
                retrieved_at=retrieved_at,
                source_checksum=checksum,
            )
            for item in candles
        )
        query = {
            "exchange": "NSE",
            "segment": "CASH",
            "groww_symbol": provider_symbol,
            "interval": "1 day",
            "start": start.isoformat(),
            "end": end.isoformat(),
        }
        return HistoricalDownload(bars, len(payloads), query, checksum)
