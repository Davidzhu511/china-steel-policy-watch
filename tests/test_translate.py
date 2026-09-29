from steelwatch.translate import priority_signal, protect, restore, translate_pending


def test_regulatory_terms_and_figures_must_survive_translation():
    source = "EU ETS data due 6 October 2026; CBAM cost is 365 EUR/t."
    protected, values = protect(source)
    assert "EU ETS" not in protected
    assert "365" not in protected
    assert "365" in restore(protected, values)
    assert "EU ETS" in restore(protected, values)
    try:
        restore(protected.replace("ZXQ0XZ", ""), values)
    except ValueError:
        pass
    else:
        raise AssertionError("missing term must reject the machine translation")


def test_pending_translation_preserves_source_when_model_is_unavailable(tmp_path, monkeypatch):
    monkeypatch.setenv("STEELWATCH_MT_DIR", str(tmp_path))
    item = {"id": "one", "title_original": "CBAM verification", "translation_state": "pending"}
    result = translate_pending([item], {"offline_translation": True}, {})
    assert result["status"] == "unavailable"
    assert "machine_translation" not in item


def test_official_trade_review_cue_does_not_announce_legal_outcome():
    item = {
        "title_original": "Scheduling of final phase of antidumping investigation",
        "translation_state": "pending", "source": {"official": True},
    }
    signal = priority_signal(item)
    assert signal and "待核对" in signal["zh"]
    item["source"]["official"] = False
    assert priority_signal(item) is None


def test_machine_term_protection_avoids_false_stem_and_accreditation_meanings():
    source = "Rio Tinto and Shougang commission blast furnace carbon capture trial facility"
    protected, values = protect(source)
    assert "高炉" in restore(protected, values)
    assert "投运" in restore(protected, values)
    protected, values = protect("State-of-play CBAM accreditation")
    assert restore(protected, values) == "CBAM 核查机构认可进展"
