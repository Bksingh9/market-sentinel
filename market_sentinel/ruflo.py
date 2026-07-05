from __future__ import annotations


class RUFLOAgent:
    def checklist_status(self) -> dict[str, object]:
        return {
            "can_place_orders": False,
            "role": "coordination-only",
            "checks": [
                "dependency license review",
                "Groww permissions and India algo obligations",
                "Alpaca account and endpoint separation",
                "Twilio alert delivery and consent setup",
                "four-week paper gate",
            ],
        }
