from __future__ import annotations

import shutil
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

from .collectors import (
    EcHaveYourSayCollector,
    EurLexCollector,
    FederalRegisterCollector,
    GdeltCollector,
    GovUkCollector,
)
from .enrich import GitHubModelsEnricher
from .fetch import fetch_page_excerpt
from .models import RawItem, SourceResult
from .render import render_outputs
from .util import (
    atomic_json_write,
    canonical_url,
    is_rule_relevant,
    load_json,
    now_iso,
    parse_datetime,
    title_similarity,
)


COLLECTOR_TYPES = {
    "ec_have_your_say": EcHaveYourSayCollector,
    "eurlex": EurLexCollector,
    "federal_register": FederalRegisterCollector,
    "govuk": GovUkCollector,
    "gdelt": GdeltCollector,
}
IMPORTANCE_SCORE = {"重大": 4, "高": 3, "中": 2, "低": 1}
SOURCE_SCORE = {"official-law": 3, "official-notice": 2, "news": 1}


def _collect(config: dict[str, Any]) -> list[SourceResult]:
    collectors = []
    for source_id, source_config in config.get("sources", {}).items():
        if not source_config.get("enabled", True) or source_id not in COLLECTOR_TYPES:
            continue
        collectors.append(COLLECTOR_TYPES[source_id](source_config, config))
    results: list[SourceResult] = []
    with ThreadPoolExecutor(max_workers=min(6, max(1, len(collectors)))) as executor:
        futures = {executor.submit(collector.run): collector for collector in collectors}
        for future in as_completed(futures):
            results.append(future.result())
    return sorted(results, key=lambda result: result.source_id)


def _raw_preference(item: RawItem) -> tuple[int, datetime]:
    return SOURCE_SCORE.get(item.source_kind, 0), parse_datetime(item.published_at)


def _deduplicate(items: list[RawItem]) -> list[RawItem]:
    by_id: dict[str, RawItem] = {}
    for item in items:
        current = by_id.get(item.id)
        if current is None or _raw_preference(item) > _raw_preference(current):
            by_id[item.id] = item
    ordered = sorted(by_id.values(), key=_raw_preference, reverse=True)
    kept: list[RawItem] = []
    for candidate in ordered:
        duplicate_index = None
        for index, existing in enumerate(kept):
            day_gap = abs((parse_datetime(candidate.published_at) - parse_datetime(existing.published_at)).days)
            if day_gap <= 5 and title_similarity(candidate.title, existing.title) >= 0.86:
                duplicate_index = index
                break
        if duplicate_index is None:
            kept.append(candidate)
        elif _raw_preference(candidate) > _raw_preference(kept[duplicate_index]):
            kept[duplicate_index] = candidate
    return kept


def _hydrate_excerpts(items: list[RawItem], settings: dict[str, Any]) -> list[str]:
    if not settings.get("fetch_page_descriptions", True):
        return []
    warnings: list[str] = []
    timeout = min(30, int(settings.get("request_timeout_seconds", 25)))

    def fetch(item: RawItem) -> tuple[str, str]:
        if item.excerpt and len(item.excerpt) >= 320:
            return item.id, item.excerpt
        try:
            value = fetch_page_excerpt(
                item.url,
                official=item.source_kind != "news",
                timeout=timeout,
            )
            return item.id, value or item.excerpt
        except Exception as exc:
            return item.id, f"__ERROR__{type(exc).__name__}: {str(exc)[:120]}"

    with ThreadPoolExecutor(max_workers=6) as executor:
        futures = {executor.submit(fetch, item): item for item in items}
        for future in as_completed(futures):
            item = futures[future]
            identifier, value = future.result()
            if value.startswith("__ERROR__"):
                warnings.append(f"正文摘录 {item.source_name}: {value.removeprefix('__ERROR__')}")
            elif identifier == item.id:
                item.excerpt = value
    return warnings


def _build_item(raw: RawItem, analysis: dict[str, Any], timestamp: str) -> dict[str, Any]:
    official = bool(raw.metadata.get("official")) or raw.source_kind != "news"
    item = {
        "id": raw.id,
        "title_zh": analysis["title_zh"],
        "title_en": analysis.get("title_en") or raw.title,
        "title_original": raw.title,
        "summary_zh": analysis["summary_zh"],
        "summary_en": analysis.get("summary_en", ""),
        "impact_zh": analysis["impact_zh"],
        "impact_en": analysis.get("impact_en", ""),
        "url": canonical_url(raw.url),
        "published_at": raw.published_at,
        "source": {
            "id": raw.source_id,
            "name": raw.source_name,
            "kind": raw.source_kind,
            "official": official,
        },
        "country": analysis.get("country") or raw.country,
        "region": analysis.get("region") or raw.region,
        "category": analysis["category"],
        "status": analysis["status"],
        "importance": analysis["importance"],
        "products": analysis.get("products", []),
        "products_en": analysis.get("products_en", []),
        "tags": analysis.get("tags", []),
        "tags_en": analysis.get("tags_en", []),
        "language": raw.language,
        "image_url": raw.image_url,
        "confidence": analysis.get("confidence", 0.5),
        "translation_state": analysis.get("translation_state", "complete"),
        "first_seen": timestamp,
        "last_seen": timestamp,
    }
    consultation = raw.metadata.get("consultation")
    if isinstance(consultation, dict) and consultation:
        item["consultation"] = {
            key: str(consultation[key])
            for key in ("status", "stage", "opens_at", "closes_at")
            if consultation.get(key)
        }
    return item


def _sort_key(item: dict[str, Any]) -> tuple[int, int, datetime]:
    source = item.get("source", {})
    return (
        IMPORTANCE_SCORE.get(item.get("importance", "低"), 0),
        SOURCE_SCORE.get(source.get("kind", "news"), 0),
        parse_datetime(item.get("published_at")),
    )


def run_update(config: dict[str, Any], data_dir: Path, docs_dir: Path) -> dict[str, Any]:
    timestamp = now_iso()
    settings = config.get("settings", {})
    history_path = data_dir / "items.json"
    previous_payload = load_json(history_path, {"items": []})
    previous_items = previous_payload.get("items", []) if isinstance(previous_payload, dict) else []
    previous_by_id = {item.get("id"): item for item in previous_items if item.get("id")}

    source_results = _collect(config)
    raw_items = [item for result in source_results if result.ok for item in result.items]
    keywords = config.get("keywords", {})
    raw_items = [
        item
        for item in raw_items
        if item.metadata.get("scope_relevant")
        or is_rule_relevant(item.title, item.excerpt, keywords)
    ]
    raw_items = _deduplicate(raw_items)
    raw_by_id = {item.id: item for item in raw_items}
    observed_ids = {item.id for item in raw_items}
    observed_existing_ids = set(observed_ids & previous_by_id.keys())
    candidates: list[RawItem] = []
    previous_values = list(previous_by_id.values())
    for raw in raw_items:
        previous = previous_by_id.get(raw.id)
        if previous:
            if previous.get("translation_state") != "complete":
                candidates.append(raw)
            continue
        near_duplicate = next(
            (
                item
                for item in previous_values
                if abs(
                    (
                        parse_datetime(raw.published_at)
                        - parse_datetime(item.get("published_at"))
                    ).days
                )
                <= 5
                and title_similarity(raw.title, item.get("title_original", "")) >= 0.9
            ),
            None,
        )
        if near_duplicate:
            observed_existing_ids.add(near_duplicate["id"])
            continue
        candidates.append(raw)
    candidates.sort(key=lambda item: parse_datetime(item.published_at), reverse=True)
    max_new = int(settings.get("max_new_items_per_run", 48))
    candidates = candidates[:max_new]

    warnings = _hydrate_excerpts(candidates, settings)
    enricher = GitHubModelsEnricher(settings)
    analyses, model_warnings = enricher.enrich(candidates)
    warnings.extend(model_warnings)
    analysis_by_id = {analysis["id"]: analysis for analysis in analyses}

    english_fields = ("title_en", "summary_en", "impact_en")
    backfill_limit = max(0, min(48, int(settings.get("english_backfill_per_run", 24))))
    backfill_candidates = [
        item
        for item in previous_values
        if not all(item.get(field) for field in english_fields)
    ][:backfill_limit]
    english_updates, english_warnings = enricher.backfill_english(backfill_candidates)
    warnings.extend(english_warnings)

    combined = dict(previous_by_id)
    for identifier in observed_existing_ids:
        updated = {**previous_by_id[identifier], "last_seen": timestamp}
        raw = raw_by_id.get(identifier)
        consultation = raw.metadata.get("consultation") if raw else None
        if isinstance(consultation, dict) and consultation:
            updated["consultation"] = {
                key: str(consultation[key])
                for key in ("status", "stage", "opens_at", "closes_at")
                if consultation.get(key)
            }
        combined[identifier] = updated
    for identifier, update in english_updates.items():
        if identifier in combined:
            combined[identifier] = {**combined[identifier], **update}
    for raw in candidates:
        analysis = analysis_by_id.get(raw.id)
        if not analysis or not analysis.get("relevant", True):
            if raw.id in previous_by_id and previous_by_id[raw.id].get("translation_state") != "complete":
                combined.pop(raw.id, None)
            continue
        built = _build_item(raw, analysis, timestamp)
        if raw.id in previous_by_id:
            built["first_seen"] = previous_by_id[raw.id].get("first_seen", timestamp)
        combined[raw.id] = built

    retention = int(settings.get("retention_days", 730))
    cutoff = datetime.now(UTC) - timedelta(days=retention)
    retained = [
        item
        for item in combined.values()
        if parse_datetime(item.get("published_at") or item.get("first_seen")) >= cutoff
    ]
    retained.sort(key=_sort_key, reverse=True)
    payload = {
        "schema_version": 1,
        "generated_at": timestamp,
        "disclaimer": "机器翻译与摘要仅供业务筛查，不构成法律意见；正式要求以原文及主管机关解释为准。",
        "items": retained,
    }
    atomic_json_write(history_path, payload)

    successful_sources = sum(1 for result in source_results if result.ok)
    status = {
        "generated_at": timestamp,
        "run_ok": successful_sources > 0,
        "model": enricher.model,
        "translation_available": enricher.available,
        "new_items": sum(1 for item in retained if item.get("first_seen") == timestamp),
        "total_items": len(retained),
        "source_success": successful_sources,
        "source_total": len(source_results),
        "sources": [result.status_dict() for result in source_results],
        "warnings": warnings[:24],
    }
    atomic_json_write(data_dir / "status.json", status)
    render_outputs(data_dir, docs_dir)
    return status


def render_existing(data_dir: Path, docs_dir: Path) -> None:
    render_outputs(data_dir, docs_dir)


def copy_seed_if_missing(seed_dir: Path, data_dir: Path) -> None:
    data_dir.mkdir(parents=True, exist_ok=True)
    for filename in ("items.json", "status.json"):
        source = seed_dir / filename
        target = data_dir / filename
        if source.exists() and not target.exists():
            shutil.copy2(source, target)
