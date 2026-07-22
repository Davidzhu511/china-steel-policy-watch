from steelwatch.util import canonical_url, is_rule_relevant, stable_id, title_similarity


KEYWORDS = {
    "china": ["china", "chinese"],
    "materials": ["steel", "hot-rolled"],
    "global_steel_policy": ["union steel market", "steel safeguard"],
    "universal_policy": ["carbon border adjustment mechanism", "cbam"],
    "exclude": ["pittsburgh steelers"],
}


def test_canonical_url_removes_tracking_and_fragment():
    value = canonical_url("HTTPS://www.Example.com/a/?utm_source=x&keep=1#section")
    assert value == "https://example.com/a?keep=1"
    assert stable_id(value) == stable_id("https://example.com/a?keep=1")


def test_relevance_accepts_china_and_universal_steel_rules():
    assert is_rule_relevant("Anti-dumping review of Chinese hot-rolled steel", "", KEYWORDS)
    assert is_rule_relevant("New quota for the Union steel market", "", KEYWORDS)
    assert is_rule_relevant("CBAM certificate surrender rules", "", KEYWORDS)
    assert not is_rule_relevant("Pittsburgh Steelers sign a player", "", KEYWORDS)
    assert not is_rule_relevant("China issues a software regulation", "", KEYWORDS)


def test_title_similarity_detects_reordered_near_duplicates():
    left = "China opens anti-dumping investigation into hot-rolled steel"
    right = "Anti-dumping investigation opened into hot rolled steel from China"
    assert title_similarity(left, right) > 0.7
