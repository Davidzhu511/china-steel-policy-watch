from __future__ import annotations

import time
from abc import ABC, abstractmethod
from typing import Any

import requests

from ..models import RawItem, SourceResult


USER_AGENT = (
    "ChinaSteelPolicyWatch/0.1 "
    "(+https://github.com/Davidzhu511/china-steel-policy-watch; public-interest monitor)"
)


class Collector(ABC):
    source_id: str

    def __init__(self, source_config: dict[str, Any], app_config: dict[str, Any]) -> None:
        self.config = source_config
        self.app_config = app_config
        self.source_name = source_config.get("name", self.source_id)
        timeout = app_config.get("settings", {}).get("request_timeout_seconds", 25)
        self.timeout = int(timeout)
        self.session = requests.Session()
        self.session.headers.update(
            {
                "User-Agent": USER_AGENT,
                "Accept-Language": "en-US,en;q=0.9",
                "Accept": "application/json,text/html,application/xhtml+xml;q=0.9,*/*;q=0.6",
            }
        )

    @abstractmethod
    def collect(self) -> list[RawItem]:
        raise NotImplementedError

    def run(self) -> SourceResult:
        start = time.monotonic()
        try:
            items = self.collect()
            return SourceResult(
                source_id=self.source_id,
                source_name=self.source_name,
                ok=True,
                items=items,
                duration_ms=int((time.monotonic() - start) * 1000),
            )
        except Exception as exc:  # Each source is isolated by design.
            return SourceResult(
                source_id=self.source_id,
                source_name=self.source_name,
                ok=False,
                error=f"{type(exc).__name__}: {str(exc)[:280]}",
                duration_ms=int((time.monotonic() - start) * 1000),
            )
