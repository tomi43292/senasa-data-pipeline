from dataclasses import dataclass

@dataclass(frozen=True)
class SyncRequestDTO:
    incremental: bool = False
