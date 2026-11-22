from __future__ import annotations

import argparse
import json
from pathlib import Path

from .config import load_config, project_root
from .pipeline import (
    publish_editorial,
    refresh_review_queue,
    render_existing,
    run_update,
    translate_existing,
)


def parser() -> argparse.ArgumentParser:
    value = argparse.ArgumentParser(description="China steel policy watch")
    value.add_argument(
        "command", nargs="?",
        choices=("update", "render", "publish-editorial", "translate", "refresh-review-queue"),
        default="update",
    )
    value.add_argument("--config", type=Path, default=None)
    value.add_argument("--data-dir", type=Path, default=project_root() / "data")
    value.add_argument("--docs-dir", type=Path, default=project_root() / "docs")
    return value


def main() -> None:
    args = parser().parse_args()
    config = load_config(args.config)
    if args.command == "update":
        status = run_update(config, args.data_dir, args.docs_dir)
        print(json.dumps(status, ensure_ascii=False, indent=2))
    elif args.command == "translate":
        print(json.dumps(translate_existing(config, args.data_dir, args.docs_dir), ensure_ascii=False))
    elif args.command == "publish-editorial":
        publish_editorial(config, args.data_dir, args.docs_dir)
        print("Published reviewed content from existing collection")
    elif args.command == "refresh-review-queue":
        changed = refresh_review_queue(args.data_dir, args.docs_dir)
        print("Review retry queue refreshed" if changed else "Review retry queue is current")
    else:
        render_existing(args.data_dir, args.docs_dir)
        print(f"Rendered dashboard data into {args.docs_dir}")
