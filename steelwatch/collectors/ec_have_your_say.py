from __future__ import annotations

import re
import unicodedata
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import UTC, datetime, timedelta
from typing import Any

from ..models import RawItem
from ..util import canonical_url, contains_any, iso_datetime, parse_datetime, stable_id
from .base import Collector


class EcHaveYourSayCollector(Collector):
    """Collect European Commission initiatives before they reach the Official Journal."""

    source_id = "ec_have_your_say"
    api_base = "https://ec.europa.eu/info/law/better-regulation/brpapi"
    initiative_base = (
        "https://ec.europa.eu/info/law/better-regulation/have-your-say/initiatives"
    )

    def __init__(self, source_config: dict[str, Any], app_config: dict[str, Any]) -> None:
        super().__init__(source_config, app_config)
        # This endpoint intermittently stalls while streaming deflate responses over HTTP/1.1.
        self.session.headers.update({"Accept": "application/json", "Accept-Encoding": "identity"})

    @staticmethod
    def _initiative_url(initiative_id: int, title: str) -> str:
        ascii_title = unicodedata.normalize("NFKD", title).encode("ascii", "ignore").decode()
        slug = re.sub(r"[^A-Za-z0-9]+", "-", ascii_title).strip("-")
        slug = slug or "initiative"
        return f"{EcHaveYourSayCollector.initiative_base}/{initiative_id}-{slug}_en"

    @staticmethod
    def _feedback_window(record: dict[str, Any]) -> dict[str, str]:
        statuses = [
            status
            for status in (record.get("currentStatuses") or [])
            if isinstance(status, dict)
        ]
        if not statuses:
            return {}
        rank = {"OPEN": 4, "UPCOMING": 3, "CLOSED": 2, "DISABLED": 1}
        selected = max(
            statuses,
            key=lambda status: (
                rank.get(str(status.get("receivingFeedbackStatus") or "").upper(), 0),
                parse_datetime(status["feedbackEndDate"])
                if status.get("feedbackEndDate")
                else datetime.min.replace(tzinfo=UTC),
            ),
        )
        output = {
            "status": str(selected.get("receivingFeedbackStatus") or "").upper(),
            "stage": str(selected.get("frontEndStage") or ""),
        }
        if selected.get("feedbackStartDate"):
            output["opens_at"] = iso_datetime(selected["feedbackStartDate"])
        if selected.get("feedbackEndDate"):
            output["closes_at"] = iso_datetime(selected["feedbackEndDate"])
        return {key: value for key, value in output.items() if value}

    @staticmethod
    def _published_at(record: dict[str, Any], detail: dict[str, Any]) -> str:
        now = datetime.now(UTC)
        candidates: list[datetime] = []
        for value in (detail.get("publishedDate"), detail.get("createdDate")):
            if value:
                candidates.append(parse_datetime(value))
        for publication in detail.get("publications") or []:
            if isinstance(publication, dict) and publication.get("publishedDate"):
                candidates.append(parse_datetime(publication["publishedDate"]))
        for status in record.get("currentStatuses") or []:
            if isinstance(status, dict) and status.get("feedbackStartDate"):
                candidates.append(parse_datetime(status["feedbackStartDate"]))
        past_or_present = [value for value in candidates if value <= now]
        return iso_datetime(max(past_or_present or candidates or [now]))

    @staticmethod
    def _excerpt(
        detail: dict[str, Any], record: dict[str, Any], consultation: dict[str, str]
    ) -> str:
        parts = [str(detail.get("dossierSummary") or "").strip()]
        topics = ", ".join(
            str(topic.get("label") or "")
            for topic in (detail.get("topics") or record.get("topics") or [])
            if isinstance(topic, dict) and topic.get("label")
        )
        act_type = detail.get("foreseenActType") or record.get("foreseenActType")
        reference = detail.get("reference") or record.get("reference")
        if consultation.get("status"):
            parts.append(f"Feedback status: {consultation['status']}.")
        if consultation.get("opens_at") or consultation.get("closes_at"):
            parts.append(
                "Feedback period: "
                f"{consultation.get('opens_at', 'not stated')} to "
                f"{consultation.get('closes_at', 'not stated')}."
            )
        if topics:
            parts.append(f"Topics: {topics}.")
        if act_type:
            parts.append(f"Type of act: {act_type}.")
        if reference:
            parts.append(f"Reference: {reference}.")
        return " ".join(part for part in parts if part)

    def _search(self, query: str) -> list[dict[str, Any]]:
        records: list[dict[str, Any]] = []
        max_pages = max(1, min(10, int(self.config.get("max_pages_per_query", 3))))
        for page in range(max_pages):
            last_error: Exception | None = None
            payload: dict[str, Any] = {}
            for _attempt in range(2):
                try:
                    response = self.session.get(
                        f"{self.api_base}/searchInitiatives",
                        params={
                            "text": query,
                            "page": page,
                            "size": 20,
                            "language": "en",
                        },
                        timeout=self.timeout,
                    )
                    response.raise_for_status()
                    body = response.json()
                    payload = body.get("initiativeResultDtoPage") or {}
                    last_error = None
                    break
                except Exception as exc:
                    last_error = exc
            if last_error is not None:
                raise last_error
            records.extend(payload.get("content") or [])
            if payload.get("last", True) or page + 1 >= int(payload.get("totalPages") or 1):
                break
        return records

    def _detail(self, initiative_id: int) -> dict[str, Any]:
        try:
            response = self.session.get(
                f"{self.api_base}/groupInitiatives/{initiative_id}", timeout=self.timeout
            )
            response.raise_for_status()
            payload = response.json()
            return payload if isinstance(payload, dict) else {}
        except Exception:
            # A single malformed initiative must not hide the rest of the official source.
            return {}

    def collect(self) -> list[RawItem]:
        lookback = int(self.config.get("lookback_days", 730))
        cutoff = datetime.now(UTC) - timedelta(days=lookback)
        keywords = self.app_config.get("keywords", {})
        match_terms = self.config.get(
            "match_terms",
            ["steel", "stainless steel", "ferroalloy", "ferrosilicon", "steel scrap"],
        )
        search_records: dict[int, dict[str, Any]] = {}
        successful_queries = 0
        last_search_error: Exception | None = None
        for query in self.config.get("queries", ["steel", "CBAM"]):
            try:
                records = self._search(str(query))
                successful_queries += 1
            except Exception as exc:
                last_search_error = exc
                continue
            for record in records:
                try:
                    initiative_id = int(float(record.get("id")))
                except (TypeError, ValueError):
                    continue
                search_records[initiative_id] = record
        if successful_queries == 0 and last_search_error is not None:
            raise last_search_error

        details: dict[int, dict[str, Any]] = {}
        worker_count = max(1, min(6, int(self.config.get("detail_workers", 4))))
        with ThreadPoolExecutor(max_workers=worker_count) as executor:
            futures = {
                executor.submit(self._detail, initiative_id): initiative_id
                for initiative_id in search_records
            }
            for future in as_completed(futures):
                details[futures[future]] = future.result()

        found: dict[str, RawItem] = {}
        for initiative_id, record in search_records.items():
            detail = details.get(initiative_id, {})
            title = str(detail.get("shortTitle") or record.get("shortTitle") or "").strip()
            if not title:
                continue
            consultation = self._feedback_window(record)
            excerpt = self._excerpt(detail, record, consultation)
            haystack = f"{title} {excerpt}"
            if not (
                contains_any(haystack, match_terms)
                or contains_any(haystack, keywords.get("universal_policy", []))
            ):
                continue
            published_at = self._published_at(record, detail)
            if parse_datetime(published_at) < cutoff:
                continue
            target = canonical_url(self._initiative_url(initiative_id, title))
            identifier = stable_id(f"{self.initiative_base}/{initiative_id}")
            topics = [
                str(topic.get("label") or "")
                for topic in (detail.get("topics") or record.get("topics") or [])
                if isinstance(topic, dict) and topic.get("label")
            ]
            found[identifier] = RawItem(
                id=identifier,
                title=title,
                url=target,
                published_at=published_at,
                source_id=self.source_id,
                source_name=self.source_name,
                source_kind="official-notice",
                region="欧洲",
                country="欧盟",
                excerpt=excerpt,
                language="en",
                metadata={
                    "official": True,
                    "scope_relevant": True,
                    "initiative_id": initiative_id,
                    "reference": detail.get("reference") or record.get("reference") or "",
                    "act_type": detail.get("foreseenActType")
                    or record.get("foreseenActType")
                    or "",
                    "topics": topics,
                    "consultation": consultation,
                },
            )
        return list(found.values())
