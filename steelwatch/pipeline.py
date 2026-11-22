from __future__ import annotations

import hashlib
import json
import re
import shutil
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

from .collectors import (
    EcHaveYourSayCollector,
    EcWatchPagesCollector,
    EurLexCollector,
    FederalRegisterCollector,
    GdeltCollector,
    GovUkCollector,
    RssCollector,
)
from .enrich import GitHubModelsEnricher, _fallback
from .editorial import (
    apply_translations,
    has_chinese_title,
    is_active_item,
    source_key,
    update_retry_schedule,
    write_review_outputs,
)
from .fetch import fetch_official_observations, fetch_page_excerpt, is_access_block_text
from .models import RawItem, SourceResult
from .render import render_outputs
from .translate import priority_signal, translate_pending
from .util import (
    atomic_json_write,
    canonical_url,
    is_rule_relevant,
    load_json,
    now_iso,
    parse_datetime,
    title_similarity,
    trim_text,
)


COLLECTOR_TYPES = {
    "ec_have_your_say": EcHaveYourSayCollector,
    "ec_watch_pages": EcWatchPagesCollector,
    "eurlex": EurLexCollector,
    "federal_register": FederalRegisterCollector,
    "govuk": GovUkCollector,
    "gdelt": GdeltCollector,
    "rss": RssCollector,
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


def _check_official_documents(
    items: list[RawItem], previous_by_id: dict, settings: dict[str, Any], timestamp: str,
) -> list[str]:
    limit = max(0, min(24, int(settings.get("max_official_revision_checks_per_run", 0))))
    if not limit:
        return []
    eligible = [item for item in items if item.metadata.get("official")
                and item.source_kind != "news" and item.source_id != "ec_have_your_say"]
    eligible.sort(key=lambda item: (
        previous_by_id.get(item.id, {}).get("source_revision_checked_at", ""),
        -parse_datetime(item.published_at).timestamp(),
    ))
    warnings: list[str] = []
    with ThreadPoolExecutor(max_workers=6) as executor:
        futures = {executor.submit(fetch_official_observations, item.url, timeout=12): item
                   for item in eligible[:limit]}
        for future in as_completed(futures):
            item = futures[future]
            item.metadata["source_revision_checked_at"] = timestamp
            try:
                item.metadata["document_observations"] = future.result()
            except Exception as exc:
                warnings.append(f"官方版本检查 {item.source_name}: {type(exc).__name__}: {str(exc)[:100]}")
    return warnings


def _source_observation(raw: RawItem) -> dict[str, str]:
    if raw.source_kind == "news":
        return {}
    values = {"title": raw.title, "excerpt": raw.excerpt}
    if consultation := raw.metadata.get("consultation"):
        values["consultation"] = json.dumps(consultation, sort_keys=True)
    observed = dict(raw.metadata.get("document_observations", {}))
    for key, value in values.items():
        normalized = " ".join(value.split())
        if normalized and not is_access_block_text(normalized):
            observed[f"{raw.source_id}:{key}"] = hashlib.sha256(normalized.encode()).hexdigest()
    return observed


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
        "source_published_date": raw.published_at[:10],
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
        "source_excerpt": trim_text(raw.excerpt, 1000 if official else 450),
    }
    consultation = raw.metadata.get("consultation")
    if isinstance(consultation, dict) and consultation:
        item["consultation"] = {
            key: str(consultation[key])
            for key in ("status", "stage", "opens_at", "closes_at")
            if consultation.get(key)
        }
    return item


def _restore_observed_dates(items: list[dict], reviews: list[dict]) -> None:
    """Recover the feed date on records whose displayed date was editorially corrected."""
    observations = {
        (canonical_url(row["url"]), row["published_date"], row.get("source_revision"),
         row.get("reviewed_at")): row["match_published_date"]
        for row in reviews
        if row.get("match_published_date") and row["match_published_date"] != row["published_date"]
    }
    if not observations:
        return
    for item in items:
        if item.get("review_method") != "source_checked":
            continue
        url, day, _ = source_key(item)
        displayed = item["published_at"][:10]
        if day != displayed:
            continue
        key = url, displayed, item.get("source_revision"), item.get("reviewed_at")
        if observed := observations.get(key):
            item["source_published_date"] = observed


def _apply_editorial(items: list[dict[str, Any]], config: dict[str, Any]) -> None:
    """Apply source-checked briefs only to the exact dated source revision reviewed."""
    records = config.get("editorial", [])
    _restore_observed_dates(items, records)
    # Older collectors overwrote a URL's reviewed edition when its feed date changed.
    # Restore only explicitly referenced, saved reviews; never review the newer edition.
    versions = {source_key(item) for item in items}
    targets = {canonical_url(row["duplicate_of"]) for row in config.get("triage", [])
               if row.get("decision") == "duplicate" and row.get("duplicate_of")
               and source_key(row) in versions}
    for review in records:
        url, day, revision = source_key(review)
        if (url not in targets or (url, day, revision) in versions
                or (url, review["published_date"], revision) in versions
                or not review.get("evidence_url") or not review.get("coverage")):
            continue
        template = next((item for item in items if canonical_url(item["url"]) == url), None)
        if template is None:
            continue
        restored = {**template, "id": template["id"] + "-review-" + day + revision,
                    "published_at": day + "T00:00:00Z", "source_published_date": day,
                    "source_excerpt": "",
                    "title_original": review.get("title_en") or review["title_zh"],
                    "restored_from_editorial": True}
        restored.pop("machine_translation", None)
        if revision:
            restored["source_revision"] = revision
        else:
            restored.pop("source_revision", None)
        items.append(restored)
        versions.add((url, day, revision))
    reviews = {source_key(row): row for row in records}
    fields = {
        "title_zh", "title_en", "summary_zh", "summary_en", "impact_zh", "impact_en",
        "category", "status", "importance", "tags", "tags_en", "follow_up",
        "evidence_url", "coverage",
    }
    for item in items:
        review = reviews.get(source_key(item))
        if not review:
            continue
        if observed := review.get("match_published_date"):
            item["source_published_date"] = observed
            item["published_at"] = review["published_date"] + "T00:00:00Z"
        item.update({key: review[key] for key in fields if key in review})
        item.update(translation_state="complete", review_method="source_checked",
                    reviewed_at=review["reviewed_at"])


def _apply_triage(items: list[dict[str, Any]], config: dict[str, Any]) -> None:
    """Persist exact-version dispositions without treating blocked sources as reviews."""
    rows = {source_key(row): row for row in config.get("triage", [])}
    by_url = {canonical_url(item["url"]): item for item in sorted(
        items, key=lambda row: (row.get("review_method") == "source_checked",
                                is_active_item(row), row["published_at"]))}
    for item in items:
        for alias in item.get("related_sources", []):
            by_url.setdefault(canonical_url(alias["url"]), item)
    for item in items:
        for key in ("review_disposition", "review_note_zh", "review_note_en",
                    "review_attempted_at", "duplicate_of", "review_title_zh",
                    "review_evidence_url", "review_coverage", "retry_after", "retry_policy"):
            item.pop(key, None)
        row = rows.get(source_key(item))
        if not row or item.get("review_method") == "source_checked":
            continue
        decision = row.get("decision")
        if decision not in {"duplicate", "excluded", "blocked"}:
            continue
        target = by_url.get(canonical_url(row.get("duplicate_of", "")))
        if decision == "duplicate" and (not target or target is item
                or target.get("review_method") != "source_checked"):
            decision = "blocked"
        item.update(review_disposition=decision, review_note_zh=row.get("reason_zh", ""),
                    review_note_en=row.get("reason_en", ""),
                    review_attempted_at=row.get("attempted_at", ""))
        if decision == "blocked" and row.get("title_zh"):
            item["review_title_zh"] = row["title_zh"]
        if decision == "blocked":
            for key in ("retry_after", "retry_policy"):
                if row.get(key):
                    item[key] = row[key]
            for key in ("evidence_url", "coverage"):
                if row.get(key):
                    item[f"review_{key}"] = row[key]
        if decision == "duplicate":
            item["duplicate_of"] = target["url"]
            links = target.setdefault("related_sources", [])
            if not any(link["url"] == item["url"] for link in links):
                links.append({"name": item.get("source", {}).get("name", ""), "url": item["url"]})



def _build_review_queue(items: list[dict[str, Any]], timestamp: str) -> dict[str, Any]:
    """Small, versioned backlog for ChatGPT when full history exceeds connector limits."""
    pending = [
        item for item in items
        if item.get("review_method") != "source_checked"
        and is_active_item(item)
    ]
    pending.sort(
        key=lambda item: (
            bool(item.get("priority_signal")),
            IMPORTANCE_SCORE.get(item.get("importance", "低"), 0),
            SOURCE_SCORE.get(item.get("source", {}).get("kind", "news"), 0),
            parse_datetime(item.get("first_seen") or item.get("published_at")),
        ),
        reverse=True,
    )
    fields = (
        "id", "url", "published_at", "title_original", "first_seen", "last_seen",
        "source", "category", "importance", "priority_signal", "translation_state",
        "review_disposition", "review_note_zh", "review_evidence_url",
        "review_coverage", "consultation", "source_revision",
    )
    rows = []
    for item in pending:
        row = {key: item[key] for key in fields if key in item}
        row["published_date"] = source_key(item)[1]
        row["source_excerpt"] = trim_text(item.get("source_excerpt", ""), 600)
        rows.append(row)
    return {
        "schema_version": 2,
        "generated_at": timestamp,
        "pending_count": len(rows),
        "actionable_count": sum(row.get("review_disposition") != "blocked" for row in rows),
        "blocked_count": sum(row.get("review_disposition") == "blocked" for row in rows),
        "items": [row for row in rows if row.get("review_disposition") != "blocked"],
        "blocked_items": [row for row in rows if row.get("review_disposition") == "blocked"],
    }


def _review_counts(items: list[dict[str, Any]]) -> dict[str, int]:
    active = [item for item in items if is_active_item(item)]
    return {
        "active_items": len(active), "archived_items": len(items) - len(active),
        "verified_items": sum(item.get("review_method") == "source_checked" for item in active),
        "pending_analysis": sum(item.get("review_method") != "source_checked" for item in active),
        "pending_translation": sum(not has_chinese_title(item) for item in active),
        "blocked_items": sum(item.get("review_disposition") == "blocked" for item in active),
    }


def _deduplicate_history(items: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Collapse identical syndicated headlines while retaining all original links."""
    ordered = sorted(items, key=lambda row: (
        row.get("review_method") == "source_checked",
        row.get("translation_state") == "complete",
        row.get("source", {}).get("name", "").lower() == "reuters",
    ), reverse=True)
    kept: list[dict[str, Any]] = []
    for item in ordered:
        if item.get("source", {}).get("kind") != "news":
            kept.append(item)
            continue
        title = item.get("title_original", "")
        source_name = item.get("source", {}).get("name", "")
        title = title.removesuffix(f" - {source_name}").removesuffix(" - News and Statistics")
        item["title_original"] = title
        duplicate = next((row for row in kept if (
            row.get("source", {}).get("kind") == "news"
            and row.get("title_original", "").casefold() == title.casefold()
            and (canonical_url(row["url"]) != canonical_url(item["url"])
                 or row["published_at"][:10] == item["published_at"][:10])
            and abs((parse_datetime(row["published_at"]) - parse_datetime(item["published_at"])).days) <= 2
        )), None)
        if duplicate:
            duplicate["first_seen"] = min(duplicate["first_seen"], item["first_seen"])
            links = duplicate.setdefault("related_sources", [])
            if not any(link["url"] == item["url"] for link in links):
                links.append({"name": source_name, "url": item["url"]})
        else:
            kept.append(item)
    return kept


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
    _restore_observed_dates(previous_items, config.get("editorial", []))
    previous_status = load_json(data_dir / "status.json", {})
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
    revision_warnings = _check_official_documents(raw_items, previous_by_id, settings, timestamp)
    source_observations = {item.id: _source_observation(item) for item in raw_items}
    same_day_revisions: dict[str, str] = {}
    candidates: list[RawItem] = []
    previous_values = list(previous_by_id.values())
    for raw in raw_items:
        previous = previous_by_id.get(raw.id)
        if previous:
            previous_day = source_key(previous)[1]
            if raw.published_at[:10] != previous_day:
                candidates.append(raw)
                continue
            prior = previous.get("source_observation", {})
            observed = source_observations[raw.id]
            if any(key in prior and prior[key] != value for key, value in observed.items()):
                identity = [previous.get("source_revision"), observed]
                digest = hashlib.sha256(json.dumps(identity, sort_keys=True).encode()).hexdigest()
                same_day_revisions[raw.id] = digest[:16]
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
    # Discovery must not queue behind a repeatedly failing translation job.
    candidates.sort(key=lambda item: (item.id not in previous_by_id,
                                     parse_datetime(item.published_at)), reverse=True)
    max_new = max(1, int(settings.get("max_new_items_per_run", 120)))
    candidates = candidates[:max_new]

    warnings = [warning for result in source_results for warning in result.warnings]
    warnings.extend(revision_warnings)
    # Collect source excerpts independently of the optional analysis provider.
    # Official HTML pages often contain the only useful facts behind a short feed title.
    excerpt_limit = max(0, min(24, int(settings.get("max_source_excerpts_per_run", 12))))
    official_excerpt_candidates = sorted(
        (
            item for item in candidates
            if item.source_kind != "news" and len(item.excerpt) < 160
            and "federalregister.gov" not in item.url.lower()
        ),
        key=lambda item: parse_datetime(item.published_at), reverse=True,
    )[:excerpt_limit]
    if official_excerpt_candidates:
        warnings.extend(_hydrate_excerpts(official_excerpt_candidates, settings))
    enricher = GitHubModelsEnricher(settings)
    model_limit = max(0, int(settings.get("max_model_items_per_run", 12)))
    model_candidates = sorted(candidates, key=_raw_preference, reverse=True)[:model_limit]
    if enricher.available:
        remaining_model_candidates = [
            item for item in model_candidates if item not in official_excerpt_candidates
        ]
        warnings.extend(_hydrate_excerpts(remaining_model_candidates, settings))
    analyses, model_warnings = enricher.enrich(model_candidates)
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
        if (raw is not None and identifier not in same_day_revisions
                and raw.published_at[:10] == source_key(updated)[1]):
            observation = source_observations[identifier]
            if observation:
                updated["source_observation"] = {
                    **updated.get("source_observation", {}), **observation,
                }
            if checked_at := raw.metadata.get("source_revision_checked_at"):
                updated["source_revision_checked_at"] = checked_at
            consultation = raw.metadata.get("consultation")
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
        analysis = analysis_by_id.get(raw.id, _fallback(raw))
        if not analysis.get("relevant", True):
            if raw.id in previous_by_id and previous_by_id[raw.id].get("translation_state") != "complete":
                combined.pop(raw.id, None)
            continue
        built = _build_item(raw, analysis, timestamp)
        observation = source_observations[raw.id]
        if observation:
            built["source_observation"] = observation
        if checked_at := raw.metadata.get("source_revision_checked_at"):
            built["source_revision_checked_at"] = checked_at
        old = previous_by_id.get(raw.id)
        if old is not None:
            _, old_day, old_revision = source_key(old)
            if revision := same_day_revisions.get(raw.id):
                built["source_revision"] = revision
                built["source_observation"] = {**old["source_observation"], **observation}
                version_id = f"{raw.id}-{old_day}-{old_revision or 'original'}"
                combined[version_id] = {**old, "id": version_id, "superseded_at": timestamp}
            else:
                if old_day != raw.published_at[:10]:
                    suffix = f"-{old_revision}" if old_revision else ""
                    version_id = f"{raw.id}-{old_day}{suffix}"
                    combined[version_id] = {**old, "id": version_id}
                built["first_seen"] = old.get("first_seen", timestamp)
        combined[raw.id] = built

    retention = int(settings.get("retention_days", 730))
    cutoff = datetime.now(UTC) - timedelta(days=retention)
    retained = [
        item
        for item in combined.values()
        if parse_datetime(item.get("published_at") or item.get("first_seen")) >= cutoff
        and (
            item.get("translation_state") == "complete"
            or item.get("superseded_at")
            or any(canonical_url(row["url"]) == canonical_url(item["url"])
                   and row["published_date"] == item["published_at"][:10]
                   for row in config.get("triage", []))
            or not re.search(
                r"\b(?:alumini?um|fertili[sz]ers?|cement|hydrogen|airlines?|aviation|"
                r"aircraft|overvalued|undervalued|stock holds)\b",
                item.get("title_original", ""), re.I,
            )
            or is_rule_relevant(
                item.get("title_original", ""), item.get("source_excerpt", ""), keywords
            )
        )
    ]
    for item in retained:
        if is_access_block_text(item.get("source_excerpt", "")):
            item["source_excerpt"] = ""
            item.pop("machine_translation", None)
    _apply_editorial(retained, config)
    _apply_triage(retained, config)
    apply_translations(retained, config)
    retained = _deduplicate_history(retained)
    active = [item for item in retained if is_active_item(item)]
    # Collection publishes immediately; the separate translation workflow does CPU work.
    translation = {"status": "queued" if settings.get("offline_translation") else "disabled",
                   "translated": 0, "warnings": []}
    warnings.extend(translation["warnings"])
    for item in retained:
        item.pop("priority_signal", None)
        signal = priority_signal(item)
        if signal:
            item["priority_signal"] = signal
    retained.sort(key=_sort_key, reverse=True)
    payload = {
        "schema_version": 1,
        "generated_at": timestamp,
        "disclaimer": "机器翻译与摘要仅供业务筛查，不构成法律意见；正式要求以原文及主管机关解释为准。",
        "items": retained,
    }
    atomic_json_write(history_path, payload)
    review_metrics = write_review_outputs(
        data_dir, _build_review_queue(retained, timestamp), retained)

    successful_sources = sum(1 for result in source_results if result.ok)
    previous_sources = {row["id"]: row for row in previous_status.get("sources", [])}
    source_statuses = []
    for result in source_results:
        row = result.status_dict()
        old = previous_sources.get(row["id"], {})
        row["last_success_at"] = timestamp if result.ok else (
            old.get("last_success_at") or (previous_status.get("generated_at") if old.get("ok") else None)
        )
        row["last_observed_at"] = max((
            item.get("last_seen", "") for item in retained
            if item.get("source", {}).get("id") == row["id"]
        ), default="")
        row["consecutive_failures"] = 0 if result.ok else old.get("consecutive_failures", 0) + 1
        source_statuses.append(row)
    status = {
        "generated_at": timestamp,
        "run_ok": successful_sources > 0,
        "model": enricher.model,
        "translation_available": enricher.available and not model_warnings,
        "analysis_status": "unconfigured" if not enricher.available else (
            "degraded" if model_warnings else "available"
        ),
        **_review_counts(retained),
        **review_metrics,
        "offline_translation": translation,
        "machine_translated_items": sum(
            bool(item.get("machine_translation")) and item.get("review_method") != "source_checked"
            for item in active
        ),
        "collected_items": len(raw_items),
        "processed_items": len(candidates),
        "deferred_items": max(0, len(raw_items) - len(observed_existing_ids) - len(candidates)),
        "new_items": sum(1 for item in retained if item.get("first_seen") == timestamp),
        "total_items": len(retained),
        "source_success": successful_sources,
        "source_total": len(source_results),
        "sources": source_statuses,
        "warnings": warnings[:24],
    }
    atomic_json_write(data_dir / "status.json", status)
    render_outputs(data_dir, docs_dir)
    return status


def publish_editorial(config: dict[str, Any], data_dir: Path, docs_dir: Path) -> None:
    """Apply reviewed content without network collection or changing collection timestamps."""
    payload = load_json(data_dir / "items.json", {})
    status = load_json(data_dir / "status.json", {})
    if not payload.get("generated_at") or not status.get("generated_at"):
        raise ValueError("Editorial publication requires an existing collected snapshot")
    items = payload["items"]
    _apply_editorial(items, config)
    _apply_triage(items, config)
    apply_translations(items, config)
    items.sort(key=_sort_key, reverse=True)
    status.update(_review_counts(items))
    status["editorial_updated_at"] = now_iso()
    atomic_json_write(data_dir / "items.json", payload)
    status.update(write_review_outputs(
        data_dir, _build_review_queue(items, status["generated_at"]), items))
    status["machine_translated_items"] = sum(
        bool(item.get("machine_translation")) and item.get("review_method") != "source_checked"
        for item in items if is_active_item(item))
    atomic_json_write(data_dir / "status.json", status)
    render_outputs(data_dir, docs_dir)


def refresh_review_queue(data_dir: Path, docs_dir: Path) -> bool:
    """Advance retry eligibility using the clock and the saved collection only."""
    status = load_json(data_dir / "status.json", {})
    queue = load_json(data_dir / "review_queue.json", {})
    manifest = load_json(data_dir / "review_manifest.json", {})
    generation = status.get("generated_at")
    if not generation:
        raise ValueError("Review retry refresh requires an existing collected snapshot")
    if (generation != queue.get("generated_at") or generation != manifest.get("generated_at")
            or any("evidence_fingerprint" not in row
                   for row in queue.get("items", []) + queue.get("blocked_items", []))):
        payload = load_json(data_dir / "items.json", {})
        if payload.get("generated_at") != generation:
            raise ValueError("Cannot refresh review queue from mismatched collection versions")
        items = payload["items"]
        status.update(write_review_outputs(data_dir, _build_review_queue(items, generation), items))
    else:
        stamp = now_iso()
        update_retry_schedule(queue, stamp)
        changes = {key: queue[key] for key in ("retry_due_count", "next_retry_at")}
        manifest_changes = {**changes, "work_fingerprint": queue["work_fingerprint"]}
        if (all(manifest.get(key) == value and key in manifest
                for key, value in manifest_changes.items())
                and all(status.get(key) == value and key in status
                        for key, value in changes.items())):
            return False
        atomic_json_write(data_dir / "review_queue.json", queue)
        atomic_json_write(data_dir / "review_manifest.json", {
            **manifest, **manifest_changes, "updated_at": stamp,
        })
        status.update(changes)
    atomic_json_write(data_dir / "status.json", status)
    render_outputs(data_dir, docs_dir)
    return True


def translate_existing(config: dict[str, Any], data_dir: Path, docs_dir: Path) -> dict[str, Any]:
    """Translate the latest saved snapshot without fetching or promoting source evidence."""
    payload = load_json(data_dir / "items.json", {})
    if not payload.get("generated_at"):
        raise ValueError("Translation requires a collected snapshot")
    items = payload["items"]
    apply_translations(items, config)
    active = [item for item in items if is_active_item(item)]
    result = translate_pending(active, config.get("settings", {}), {})
    result["attempted_at"] = now_iso()
    if result["status"] in {"partial", "unavailable"}:
        result["retry_after"] = (datetime.now(UTC) + timedelta(hours=6)).isoformat()
    atomic_json_write(data_dir / "items.json", payload)
    status = load_json(data_dir / "status.json", {})
    status["offline_translation"] = result
    status["translation_updated_at"] = now_iso()
    atomic_json_write(data_dir / "status.json", status)
    editorial_timestamp = status.get("editorial_updated_at")
    publish_editorial(config, data_dir, docs_dir)
    # Translation is not a new source review.
    status = load_json(data_dir / "status.json", {})
    if editorial_timestamp:
        status["editorial_updated_at"] = editorial_timestamp
    else:
        status.pop("editorial_updated_at", None)
    atomic_json_write(data_dir / "status.json", status)
    render_outputs(data_dir, docs_dir)
    return result


def render_existing(data_dir: Path, docs_dir: Path) -> None:
    render_outputs(data_dir, docs_dir)


def copy_seed_if_missing(seed_dir: Path, data_dir: Path) -> None:
    data_dir.mkdir(parents=True, exist_ok=True)
    for filename in ("items.json", "status.json"):
        source = seed_dir / filename
        target = data_dir / filename
        if source.exists() and not target.exists():
            shutil.copy2(source, target)
