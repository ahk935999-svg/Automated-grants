from dataclasses import dataclass
from typing import Protocol

@dataclass(frozen=True)
class SubmissionResult:
    status: str
    external_id: str | None = None
    message: str = ""

class PortalAdapter(Protocol):
    name: str

    def can_handle(self,url: str) -> bool:
        ...

    def prepare(self,application: dict) -> dict:
        ...

    def submit(self,application: dict) -> SubmissionResult:
        ...
