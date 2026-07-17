import unittest
from datetime import date

from market_sentinel.api_clients import HttpResponse
from market_sentinel.config import load_settings
from market_sentinel.historical_clients import (
    AlpacaHistoricalClient,
    GrowwHistoricalClient,
    sanitize_provider_error,
)


class RecordingHttp:
    def __init__(self, responses: list[HttpResponse]):
        self.responses = responses
        self.calls: list[tuple[str, dict[str, str], dict[str, str]]] = []

    def get_json(
        self,
        url: str,
        *,
        headers: dict[str, str],
        query: dict[str, str],
    ) -> HttpResponse:
        self.calls.append((url, headers, query))
        return self.responses.pop(0)


class FakeGrowwSDK:
    EXCHANGE_NSE = "NSE"
    SEGMENT_CASH = "CASH"
    CANDLE_INTERVAL_DAY = "1 day"

    def __init__(self):
        self.historical_calls: list[dict[str, str]] = []

    def get_instrument_by_exchange_and_trading_symbol(
        self,
        *,
        exchange: str,
        trading_symbol: str,
    ) -> dict[str, object]:
        return {
            "exchange": exchange,
            "trading_symbol": trading_symbol,
            "groww_symbol": f"NSE-{trading_symbol}",
            "segment": "CASH",
        }

    def get_historical_candles(self, **kwargs: str) -> dict[str, object]:
        self.historical_calls.append(kwargs)
        return {
            "candles": [
                [kwargs["start_time"][:10], 250, 255, 249, 254, 10000, None]
            ]
        }


class HistoricalClientsTest(unittest.TestCase):
    def test_alpaca_requests_adjusted_daily_bars_and_paginates(self):
        http = RecordingHttp(
            [
                HttpResponse(
                    200,
                    {
                        "bars": {
                            "SPY": [
                                {
                                    "t": "2026-07-15T04:00:00Z",
                                    "o": 100,
                                    "h": 102,
                                    "l": 99,
                                    "c": 101,
                                    "v": 10,
                                }
                            ]
                        },
                        "next_page_token": "next",
                    },
                ),
                HttpResponse(
                    200,
                    {
                        "bars": {
                            "SPY": [
                                {
                                    "t": "2026-07-16T04:00:00Z",
                                    "o": 101,
                                    "h": 103,
                                    "l": 100,
                                    "c": 102,
                                    "v": 11,
                                }
                            ]
                        }
                    },
                ),
            ]
        )
        download = AlpacaHistoricalClient(
            http,
            key_id="key",
            secret_key="secret",
        ).download(
            symbol="SPY",
            start=date(2026, 7, 15),
            end=date(2026, 7, 16),
            feed="iex",
        )
        self.assertEqual(download.page_count, 2)
        self.assertEqual(
            http.calls[0][0],
            "https://data.alpaca.markets/v2/stocks/bars",
        )
        self.assertEqual(http.calls[0][2]["adjustment"], "all")
        self.assertEqual(http.calls[1][2]["page_token"], "next")
        self.assertEqual(download.bars[0].trading_date, date(2026, 7, 15))

    def test_groww_resolves_nse_cash_symbol_and_uses_current_sdk_operation(self):
        sdk = FakeGrowwSDK()
        download = GrowwHistoricalClient(sdk).download(
            symbol="NIFTYBEES",
            start=date(2026, 7, 16),
            end=date(2026, 7, 16),
        )
        self.assertEqual(sdk.historical_calls[0]["exchange"], "NSE")
        self.assertEqual(sdk.historical_calls[0]["segment"], "CASH")
        self.assertEqual(
            sdk.historical_calls[0]["groww_symbol"],
            "NSE-NIFTYBEES",
        )
        self.assertEqual(sdk.historical_calls[0]["candle_interval"], "1 day")
        self.assertEqual(
            download.bars[0].adjustment_mode.value,
            "provider-unspecified",
        )

    def test_groww_splits_daily_history_into_supported_180_day_windows(self):
        sdk = FakeGrowwSDK()
        GrowwHistoricalClient(sdk).download(
            symbol="NIFTYBEES",
            start=date(2026, 1, 1),
            end=date(2026, 7, 16),
        )
        self.assertEqual(len(sdk.historical_calls), 2)

    def test_provider_error_redacts_market_specific_secrets(self):
        result = sanitize_provider_error(
            "key=ALPACA123 token=GROWW456",
            ("ALPACA123", "GROWW456"),
        )
        self.assertEqual(result, "key=[REDACTED] token=[REDACTED]")

    def test_alpaca_market_data_endpoint_fails_closed_to_official_host(self):
        settings = load_settings(
            {"ALPACA_MARKET_DATA_ENDPOINT": "https://attacker.example"}
        )
        self.assertEqual(
            settings.alpaca_market_data_endpoint,
            "https://data.alpaca.markets",
        )


if __name__ == "__main__":
    unittest.main()
