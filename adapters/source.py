from typing import Protocol

class SourceAdapter(Protocol):
    name: str

    def discover(self) -> tuple[list[dict],list[dict]]:
        ...
