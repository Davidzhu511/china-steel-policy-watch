from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any


@dataclass(slots=True)
class RawItem:
    id: str
    title: str
    url: str
    published_at: str
    source_id: str
    source_name: str
    source_kind: str
    region: str = "全球"
    country: str = "全球"
    excerpt: str = ""
    language: str = "en"
    image_url: str = ""
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(slots=True)
class SourceResult:
    source_id: str
    source_name: str
    ok: bool
    items: list[RawItem] = field(default_factory=list)
    error: str = ""
    duration_ms: int = 0

    def status_dict(self) -> dict[str, Any]:
        return {
            "id": self.source_id,
            "name": self.source_name,
            "ok": self.ok,
            "count": len(self.items),
            "error": self.error,
            "duration_ms": self.duration_ms,
        }
