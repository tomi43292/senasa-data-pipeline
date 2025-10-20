from typing import Any, Protocol


class INotificationPort(Protocol):
    def notify(self, event: str, payload: dict[str, Any]) -> None: ...
