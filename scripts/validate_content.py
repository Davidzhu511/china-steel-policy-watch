"""Validate legacy uniqueness and additive batches before editorial auto-merge."""
from pathlib import Path

from steelwatch.config import load_config
from steelwatch.util import load_json


def main() -> None:
    root = Path(__file__).resolve().parents[1]
    for kind in ("editorial", "triage"):
        rows = load_json(root / "config" / f"{kind}.json", [])
        keys = [(row.get("url"), row.get("published_date")) for row in rows]
        if any(not all(key) for key in keys) or len(keys) != len(set(keys)):
            raise ValueError(f"{kind}: source versions missing or duplicated")
    config = load_config(root / "config" / "sources.json")
    reviewed = {row["url"] for row in config["editorial"]}
    # Only enforce the stronger contract on new batches; legacy diagnostics remain visible.
    for path in (root / "config" / "reviews").glob("*.json"):
        for row in load_json(path, {}).get("triage", []):
            if row["decision"] == "duplicate" and row["duplicate_of"] not in reviewed:
                raise ValueError(f"{path}: duplicate target has no reviewed record")
    print("Editorial batches, exact source versions and duplicate references validated")


if __name__ == "__main__":
    main()
