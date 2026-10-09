from __future__ import annotations

import html
import hashlib
import json
import re
from email.utils import format_datetime
from pathlib import Path

from .util import atomic_json_write, load_json, now_iso, parse_datetime, trim_text


def _rss(items: list[dict], generated_at: str) -> str:
    rows = []
    for item in items[:50]:
        checked = item.get("translation_state") == "complete" or (
            not item.get("translation_state") and bool(item.get("summary_zh"))
        )
        machine = item.get("machine_translation") or {}
        title = html.escape(
            (item.get("title_zh") if checked else machine.get("title_zh"))
            or item.get("title_original") or ""
        )
        link = html.escape(item.get("url") or "", quote=True)
        guid = html.escape(item.get("id") or link)
        if checked:
            description = html.escape(
                f"{item.get('summary_zh', '')} 影响：{item.get('impact_zh', '')}"
            )
        elif machine.get("excerpt_zh"):
            description = html.escape(f"机器译文，业务影响待核对：{machine['excerpt_zh']}")
        else:
            description = "中文解读待补充，请核对原文。"
        pub_date = html.escape(
            format_datetime(parse_datetime(item.get("published_at") or generated_at), usegmt=True)
        )
        rows.append(
            f"<item><title>{title}</title><link>{link}</link><guid>{guid}</guid>"
            f"<description>{description}</description><pubDate>{pub_date}</pubDate></item>"
        )
    return (
        '<?xml version="1.0" encoding="UTF-8"?>\n'
        '<rss version="2.0"><channel><title>中国钢铁全球政策情报</title>'
        '<link>https://davidzhu511.github.io/china-steel-policy-watch/</link>'
        '<description>中国钢铁法规、贸易救济与行业动态中文摘要</description>'
        f"<lastBuildDate>"
        f"{html.escape(format_datetime(parse_datetime(generated_at), usegmt=True))}"
        f"</lastBuildDate>"
        f"{''.join(rows)}</channel></rss>\n"
    )


def render_outputs(data_dir: Path, docs_dir: Path) -> None:
    docs_data = docs_dir / "data"
    docs_data.mkdir(parents=True, exist_ok=True)
    items_payload = load_json(data_dir / "items.json", {"items": [], "generated_at": now_iso()})
    status_payload = load_json(data_dir / "status.json", {"generated_at": now_iso()})
    atomic_json_write(docs_data / "items.json", items_payload)
    atomic_json_write(docs_data / "status.json", status_payload)
    recent_items = sorted(
        [item for item in items_payload.get("items", [])
         if item.get("review_disposition") not in {"excluded", "duplicate"}],
        key=lambda item: parse_datetime(item.get("published_at") or item.get("first_seen")),
        reverse=True,
    )
    latest = {
        "generated_at": items_payload.get("generated_at"),
        "items": recent_items[:50],
    }
    atomic_json_write(docs_data / "latest.json", latest)
    (docs_dir / "feed.xml").write_text(
        _rss(recent_items, items_payload.get("generated_at") or now_iso()),
        encoding="utf-8",
    )
    (docs_dir / ".nojekyll").touch()
    index_path = docs_dir / "index.html"
    if index_path.exists():
        index = index_path.read_text(encoding="utf-8")
        for name in ("app.js", "styles.css"):
            asset = docs_dir / name
            if asset.exists():
                version = hashlib.sha256(asset.read_bytes()).hexdigest()[:12]
                index = re.sub(
                    rf"\./{re.escape(name)}(?:\?v=[^\"']*)?(?=[\"'])",
                    f"./{name}?v={version}", index,
                )
        index_path.write_text(index, encoding="utf-8")


def dashboard_summary(data_dir: Path) -> str:
    payload = load_json(data_dir / "items.json", {"items": []})
    items = payload.get("items", [])
    top = sorted(
        items,
        key=lambda item: ({"重大": 4, "高": 3, "中": 2, "低": 1}.get(item.get("importance"), 0)),
        reverse=True,
    )[:3]
    titles = "；".join(trim_text(item.get("title_zh", ""), 45) for item in top)
    return json.dumps({"total": len(items), "top": titles}, ensure_ascii=False)
