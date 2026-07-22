from __future__ import annotations

import os

from steelwatch.schedule import should_run


event_name = os.environ.get("GITHUB_EVENT_NAME", "")
schedule = os.environ.get("GITHUB_EVENT_SCHEDULE", "")
print(f"run={'true' if should_run(event_name, schedule) else 'false'}")
