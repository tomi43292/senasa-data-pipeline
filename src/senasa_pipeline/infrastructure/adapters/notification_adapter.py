from typing import Any


class SimpleNotificationAdapter:
    def notify(self, event: str, payload: dict[str, Any]) -> None:
        print(f"[{event}] {payload}")
