from __future__ import annotations

from typing import Any

from market_sentinel.api_clients import HttpClient, UrllibHttpClient
from market_sentinel.config import Settings


class AlertReject(RuntimeError):
    pass


class TwilioAlertAdapter:
    def __init__(self, settings: Settings, *, http_client: HttpClient | None = None):
        self.settings = settings
        self.http_client = http_client or UrllibHttpClient()

    def send(self, message: str) -> dict[str, Any]:
        if not self.settings.twilio_alerts_enabled:
            return {"status": "disabled"}
        missing = [
            name
            for name, value in {
                "TWILIO_ACCOUNT_SID": self.settings.twilio_account_sid,
                "TWILIO_AUTH_TOKEN": self.settings.twilio_auth_token,
                "TWILIO_FROM": self.settings.twilio_from,
                "TWILIO_TO": self.settings.twilio_to,
            }.items()
            if not value
        ]
        if missing:
            raise AlertReject(f"missing Twilio settings: {', '.join(missing)}")
        url = f"https://api.twilio.com/2010-04-01/Accounts/{self.settings.twilio_account_sid}/Messages.json"
        response = self.http_client.post_form(
            url,
            data={
                "From": self.settings.twilio_from or "",
                "To": self.settings.twilio_to or "",
                "Body": message,
            },
            auth=(self.settings.twilio_account_sid or "", self.settings.twilio_auth_token or ""),
        )
        if response.status_code >= 400:
            raise AlertReject(f"Twilio alert rejected with HTTP {response.status_code}")
        return response.payload
