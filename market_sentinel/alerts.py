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
        required = {
            "TWILIO_ACCOUNT_SID": self.settings.twilio_account_sid,
            "TWILIO_AUTH_TOKEN": self.settings.twilio_auth_token,
            "TWILIO_TO": self.settings.twilio_to,
        }
        if not self.settings.twilio_messaging_service_sid:
            required["TWILIO_FROM"] = self.settings.twilio_from
        missing = [name for name, value in required.items() if not value]
        if missing:
            raise AlertReject(f"missing Twilio settings: {', '.join(missing)}")
        url = f"https://api.twilio.com/2010-04-01/Accounts/{self.settings.twilio_account_sid}/Messages.json"
        data = {
            "To": self.settings.twilio_to or "",
            "Body": message,
        }
        if self.settings.twilio_messaging_service_sid:
            data["MessagingServiceSid"] = self.settings.twilio_messaging_service_sid
        else:
            data["From"] = self.settings.twilio_from or ""
        if self.settings.twilio_status_callback_url:
            data["StatusCallback"] = self.settings.twilio_status_callback_url
        response = self.http_client.post_form(
            url,
            data=data,
            auth=(self.settings.twilio_account_sid or "", self.settings.twilio_auth_token or ""),
        )
        if response.status_code >= 400:
            raise AlertReject(f"Twilio alert rejected with HTTP {response.status_code}")
        return response.payload
