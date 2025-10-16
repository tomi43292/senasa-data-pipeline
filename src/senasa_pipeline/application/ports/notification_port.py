from typing import Protocol, Any

class INotificationPort(Protocol):
    def notify(self, event: str, payload: dict[str, Any]) -> None: ...
