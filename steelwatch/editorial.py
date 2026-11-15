"""Small immutable editorial batches and observable, bounded review queues."""
from __future__ import annotations

import hashlib
import json
import re
from datetime import timedelta
from pathlib import Path
from typing import Any

from .util import atomic_json_write, canonical_url, now_iso, parse_datetime, title_similarity


def source_key(row: dict) -> tuple[str, str]:
    return canonical_url(row["url"]), row.get("match_published_date", row["published_date"])


def load_batches(config_dir: Path, config: dict) -> None:
    """Keep legacy history; newer, independently reviewable batches override one version."""
    maps = {kind: {source_key(row): row for row in config.get(kind, [])}
            for kind in ("editorial", "triage", "translations")}
    for path in sorted((config_dir / "reviews").glob("*.json")):
        batch = json.loads(path.read_text(encoding="utf-8"))
        validate_batch(batch, str(path))
        for kind, rows in maps.items():
            for row in batch.get(kind, []):
                rows[source_key(row)] = row
    config.update({kind: list(rows.values()) for kind, rows in maps.items()})


def validate_batch(batch: dict, label: str = "batch") -> None:
    if not isinstance(batch, dict) or batch.get("schema_version") != 1:
        raise ValueError(f"{label}: expected batch schema_version=1")
    if set(batch) - {"schema_version", "created_at", "note", "editorial", "triage", "translations"}:
        raise ValueError(f"{label}: unsupported batch fields")
    for kind in ("editorial", "triage", "translations"):
        rows = batch.get(kind, [])
        if not isinstance(rows, list):
            raise ValueError(f"{label}: {kind} must be a list")
        seen = set()
        for row in rows:
            if not isinstance(row, dict) or not all(row.get(k) for k in ("url", "published_date")):
                raise ValueError(f"{label}: source URL and date required")
            if not re.fullmatch(r"\d{4}-\d{2}-\d{2}", row["published_date"]):
                raise ValueError(f"{label}: invalid publication date")
            key = source_key(row)
            if key in seen:
                raise ValueError(f"{label}: duplicate source version in {kind}")
            seen.add(key)
            required = {
                "editorial": ("title_zh", "title_en", "summary_zh", "summary_en",
                              "impact_zh", "impact_en", "reviewed_at", "evidence_url", "coverage"),
                "triage": ("decision", "reason_zh", "attempted_at", "coverage"),
                "translations": ("title_zh", "title_original", "translated_at"),
            }[kind]
            if not all(row.get(k) for k in required):
                raise ValueError(f"{label}: incomplete {kind} entry")
            if kind == "translations" and not re.search(r"[\u3400-\u9fff]", row["title_zh"]):
                raise ValueError(f"{label}: Chinese translation required")
            if kind == "triage":
                if row["decision"] not in {"blocked", "excluded", "duplicate"}:
                    raise ValueError(f"{label}: invalid disposition")
                if row["decision"] == "duplicate" and not row.get("duplicate_of"):
                    raise ValueError(f"{label}: duplicate_of must link a verified primary record")


def apply_translations(items: list[dict], config: dict) -> None:
    rows = {source_key(row): row for row in config.get("translations", [])}
    for item in items:
        row = rows.get((canonical_url(item["url"]), item["published_at"][:10]))
        item.pop("source_translation", None)
        if row and row["title_original"] == item.get("title_original"):
            item["source_translation"] = {
                "title_zh": row["title_zh"], "translated_at": row["translated_at"],
                "method": "editor_translation", "coverage": "标题翻译，不代表全文核验",
            }
            # An excerpt translation is only reusable against that exact excerpt.
            if row.get("source_excerpt") == item.get("source_excerpt") and row.get("excerpt_zh"):
                item["source_translation"]["excerpt_zh"] = row["excerpt_zh"]


def has_chinese_title(item: dict) -> bool:
    if item.get("translation_state") == "complete":
        return True
    return any(re.search(r"[\u3400-\u9fff]", str(value or "")) for value in (
        item.get("source_translation", {}).get("title_zh"),
        item.get("machine_translation", {}).get("title_zh"),
        item.get("review_title_zh"), item.get("title_original"),
    ))


def add_review_context(queue: dict, items: list[dict], timestamp: str) -> dict:
    """Retry a small due slice; never conflate source translations with verification."""
    clock = parse_datetime(timestamp)
    verified = [item for item in items if item.get("review_method") == "source_checked"]
    by_id = {item.get("id"): item for item in items}
    for row in queue["items"] + queue["blocked_items"]:
        item = by_id[row.get("id")]
        row["needs_translation"] = not has_chinese_title(item)
        row["title_zh"] = (item.get("source_translation", {}).get("title_zh")
                           or item.get("machine_translation", {}).get("title_zh")
                           or item.get("review_title_zh") or item.get("title_zh"))
        row["review_attempted_at"] = item.get("review_attempted_at", "")
        row["evidence_fingerprint"] = hashlib.sha256(
            (row.get("title_original", "") + "\n" + row.get("source_excerpt", "")).encode()
        ).hexdigest()[:16]
        related = sorted(verified, key=lambda other: title_similarity(
            row.get("title_original", ""), other.get("title_original", "")), reverse=True)
        row["related_reviews"] = [
            {key: other.get(key) for key in ("url", "published_at", "title_zh", "evidence_url")}
            for other in related[:2] if title_similarity(
                row.get("title_original", ""), other.get("title_original", "")) >= 0.4
        ]
        if row.get("review_disposition") == "blocked":
            delay = 3 if row.get("source", {}).get("official") else 7
            attempted = row["review_attempted_at"] or row.get("first_seen") or timestamp
            row["retry_after"] = item.get("retry_after") or (
                parse_datetime(attempted) + timedelta(days=delay)).isoformat()
            row["retry_policy"] = item.get("retry_policy", "scheduled")
    due = [row for row in queue["blocked_items"] if row["retry_policy"] != "manual"
           and parse_datetime(row["retry_after"]) <= clock]
    due.sort(key=lambda row: (not row.get("source", {}).get("official"), row["retry_after"]))
    queue["retry_items"] = due[:4]
    queue["retry_due_count"] = len(due)
    # Fingerprint excludes observation timestamps, so empty/repeated runs are cheap.
    identity = [(row["url"], row["published_date"], row["evidence_fingerprint"],
                 row.get("review_attempted_at")) for row in queue["items"] + queue["retry_items"]]
    queue["work_fingerprint"] = hashlib.sha256(json.dumps(identity).encode()).hexdigest()[:20]
    return queue


def write_review_outputs(data_dir: Path, queue: dict, items: list[dict]) -> dict[str, Any]:
    now = now_iso()
    add_review_context(queue, items, now)
    active = [item for item in items if item.get("review_disposition") not in {"excluded", "duplicate"}]
    untranslated = [item for item in active if not has_chinese_title(item)]
    actionable_ids = {row["id"] for row in queue["items"]}
    ages = [(parse_datetime(now) - parse_datetime(item.get("first_seen") or item["published_at"])
             ).total_seconds() / 3600 for item in active if item.get("id") in actionable_ids]
    metrics = {
        "actionable_count": queue["actionable_count"], "blocked_count": queue["blocked_count"],
        "retry_due_count": queue["retry_due_count"],
        "pending_translation": len(untranslated),
        "pending_machine_translation": sum(item.get("language", "en") in {"en", "eng", ""}
                                           for item in untranslated),
        "chinese_title_coverage": round(100 * (len(active) - len(untranslated)) / max(1, len(active)), 1),
        "oldest_actionable_hours": round(max(ages, default=0), 1),
    }
    atomic_json_write(data_dir / "review_queue.json", queue)
    atomic_json_write(data_dir / "review_manifest.json", {
        "schema_version": 1, "generated_at": queue["generated_at"], "updated_at": now,
        "work_fingerprint": queue["work_fingerprint"], **metrics,
        "queue_path": "data/review_queue.json", "batch_path": "config/reviews/",
    })
    return metrics
