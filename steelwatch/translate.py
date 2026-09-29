"""Offline source translation, deliberately separate from policy analysis."""
from __future__ import annotations

import hashlib
import os
import re
import time
from pathlib import Path
from typing import Any

from .util import now_iso, trim_text

MODEL = "Helsinki-NLP/opus-mt-en-zh"
REVISION = "408d9bc410a388e1d9aef112a2daba955b945255"
GLOSSARY = {
    "cold rolled stainless steel sheets and coils": "冷轧不锈钢板卷",
    "prestressed concrete steel wire strand": "预应力混凝土用钢绞线",
    "non-refillable steel cylinders": "不可重复充装钢瓶",
    "steel grating": "钢格板", "brake drums": "制动鼓",
    "EU ETS suspension": "暂停 EU ETS", "EU-bound offers": "输欧报价",
    "steel site": "钢铁生产基地", "mills": "钢厂", "launches": "推出",
    "wire rod products": "盘条产品", "wire rod": "盘条",
    "cold-rolled": "冷轧", "cold rolled": "冷轧",
    "expiry review": "期满复审", "sunset review": "日落复审",
    "steel mills": "钢厂", "steel suppliers": "钢材供应商",
    "state-of-play CBAM accreditation": "CBAM 核查机构认可进展",
    "boltless steel shelving units": "无螺栓钢制货架",
    "non-grain-oriented electrical steel": "无取向电工钢",
    "grain-oriented electrical steel": "取向电工钢",
    "blast furnace": "高炉", "carbon-capture": "碳捕集", "carbon capture": "碳捕集",
    "tin mill products": "镀锡板类产品（Tin Mill Products）",
    "carbon border adjustment mechanism": "碳边境调节机制",
    "tariff-rate quotas": "关税配额", "tariff-rate quota": "关税配额",
    "accreditation": "认可", "accredited": "获认可的",
    "verification": "核查", "verifiers": "核查机构",
    "countervailing duty": "反补贴税", "antidumping duty": "反倾销税",
    "anti-dumping duty": "反倾销税", "safeguard measures": "保障措施",
    "hot-rolled steel": "热轧钢", "cold-rolled steel": "冷轧钢",
    "galvanized steel": "镀锌钢", "galvanised steel": "镀锌钢",
    "stainless steel": "不锈钢", "Rio Tinto": "力拓", "Shougang": "首钢",
    "CBAM": "CBAM", "EU ETS": "EU ETS", "UK ETS": "UK ETS",
}
TERM_PATTERN = re.compile(
    r"\bcommissions?\b(?=\s+(?:blast furnace|carbon[- ]capture|pilot|trial|steel))|\b(?:"
    + "|".join(re.escape(k) for k in sorted(GLOSSARY, key=len, reverse=True))
    + r")\b|\b\d+(?:[.,/-]\d+)*(?:%)?", re.I,
)
TERM_VALUES = {k.casefold(): v for k, v in GLOSSARY.items()}


def protect(text: str) -> tuple[str, dict[str, str]]:
    values: dict[str, str] = {}

    def replace(match: re.Match) -> str:
        marker = f"ZXQ{len(values)}XZ"
        lowered = match[0].casefold()
        if lowered in {"commission", "commissions"}:
            values[marker] = "投运" if "facility" in text.lower() else "启动"
        else:
            values[marker] = TERM_VALUES.get(lowered, match[0])
        return marker

    return TERM_PATTERN.sub(replace, text), values


def restore(text: str, values: dict[str, str]) -> str:
    # Reject dropped/duplicated terms or figures rather than publishing altered facts.
    for marker, value in values.items():
        if text.count(marker) != 1:
            raise ValueError("translation did not preserve a protected term or number")
        text = text.replace(marker, value)
    if re.search(r"ZXQ\d+XZ", text):
        raise ValueError("unresolved translation marker")
    return text.strip()


def fingerprint(item: dict[str, Any]) -> str:
    value = f"{REVISION}:v4:{item.get('title_original', '')}\n{item.get('source_excerpt', '')}"
    return hashlib.sha256(value.encode()).hexdigest()


class LocalTranslator:
    def __init__(self, model_dir: Path) -> None:
        import torch
        from transformers import MarianMTModel, MarianTokenizer

        torch.set_num_threads(2)
        self.torch = torch
        self.tokenizer = MarianTokenizer.from_pretrained(model_dir, local_files_only=True)
        self.model = MarianMTModel.from_pretrained(model_dir, local_files_only=True).eval()

    def translate(self, texts: list[str]) -> list[str]:
        protected = [protect(text) for text in texts]
        # A short official heading sometimes consists solely of one fixed term.
        # Sending the placeholder through Marian can produce stray words.
        direct = [values.get(source) if source in values else None for source, values in protected]
        tokens = self.tokenizer(
            [">>cmn_Hans<< " + text for text, _ in protected],
            return_tensors="pt", padding=True, truncation=False,
        )
        if tokens["input_ids"].shape[1] > 480:
            raise ValueError("source exceeds translation input limit")
        with self.torch.inference_mode():
            output = self.model.generate(**tokens, num_beams=3, max_new_tokens=384)
        decoded = self.tokenizer.batch_decode(output, skip_special_tokens=True)
        return [exact if exact is not None else restore(text, values)
                for text, (_, values), exact in zip(decoded, protected, direct)]


def translate_pending(
    items: list[dict[str, Any]], settings: dict[str, Any], previous: dict[str, dict],
) -> dict[str, Any]:
    result: dict[str, Any] = {"status": "disabled", "translated": 0, "warnings": []}
    if not settings.get("offline_translation", False):
        return result
    pending = []
    for item in items:
        if item.get("translation_state") == "complete":
            continue
        if item.get("language", "").startswith("zh"):
            item.pop("machine_translation", None)
            continue
        cached = item.get("machine_translation") or previous.get(item["id"], {}).get(
            "machine_translation", {}
        )
        if cached.get("fingerprint") == fingerprint(item):
            item["machine_translation"] = cached
            continue
        item.pop("machine_translation", None)
        pending.append(item)
    pending.sort(key=lambda item: item.get("published_at", ""), reverse=True)
    model_dir = Path(os.environ.get("STEELWATCH_MT_DIR", ".cache/opus-en-zh"))
    if not (model_dir / "ready.json").is_file():
        result["status"] = "unavailable"
        result["warnings"].append("离线翻译模型未就绪；原文收录继续。")
        return result
    result["status"] = "available"
    if not pending:
        return result
    try:
        translator = LocalTranslator(model_dir)
    except Exception as exc:
        result.update(status="unavailable", warnings=[f"离线翻译加载失败：{type(exc).__name__}"])
        return result
    started = time.monotonic()
    limit = max(1, min(200, int(settings.get("max_offline_translations_per_run", 100))))
    budget = max(10, min(300, int(settings.get("offline_translation_seconds", 180))))
    failures = 0
    for item in pending[:limit]:
        if time.monotonic() - started >= budget:
            result["status"] = "partial"
            break
        title = trim_text(item.get("title_original", ""), 350)
        excerpt = trim_text(item.get("source_excerpt", ""), 450)
        texts = [title, excerpt] if excerpt and excerpt != title else [title]
        try:
            if item.get("language", "en") not in {"en", "eng", ""}:
                continue
            translated = translator.translate(texts)
            if not re.search(r"[\u3400-\u9fff]", translated[0]) and len(title) > 10:
                raise ValueError("translated headline lacks Chinese text")
            item["machine_translation"] = {
                "title_zh": translated[0],
                "excerpt_zh": translated[1] if len(translated) > 1 else "",
                "fingerprint": fingerprint(item), "model": MODEL,
                "revision": REVISION, "translated_at": now_iso(),
            }
            result["translated"] += 1
        except Exception:
            failures += 1
            result["status"] = "partial"
    if failures:
        result["warnings"].append(f"{failures} 条译文未通过完整性检查，保留原文待重试。")
    result["remaining"] = sum(
        item.get("translation_state") != "complete" and not item.get("machine_translation")
        and not item.get("language", "").startswith("zh")
        for item in items
    )
    if result["remaining"]:
        result["status"] = "partial"
    return result


def priority_signal(item: dict[str, Any]) -> dict[str, str] | None:
    """Explain rule-based review cues without declaring a new legal obligation."""
    if item.get("translation_state") == "complete" or not item.get("source", {}).get("official"):
        return None
    title = item.get("title_original", "").lower()
    if re.search(r"anti[- ]?dumping|countervailing|safeguard|tariff.rate quota", title):
        return {"zh": "贸易救济程序 · 待核对", "en": "Trade-remedy procedure · review needed"}
    if "cbam" in title and re.search(r"verif|accredit|registration|implementing regulation", title):
        return {"zh": "CBAM 执行信息 · 待核对", "en": "CBAM implementation · review needed"}
    if item.get("consultation", {}).get("status") == "OPEN":
        return {"zh": "公开征求意见中", "en": "Consultation open"}
    return None
