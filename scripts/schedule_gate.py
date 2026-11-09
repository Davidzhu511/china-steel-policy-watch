from __future__ import annotations

import os

from steelwatch.schedule import should_run


event_name = os.environ.get("GITHUB_EVENT_NAME", "")
schedule = os.environ.get("GITHUB_EVENT_SCHEDULE", "")
run = should_run(event_name, schedule)
print(f"run={'true' if run else 'false'}")
reason = "执行采集或内容发布" if run else "正常跳过：此UTC候选时段不适用于当前冬夏令时；不是采集或部署失败"
if os.environ.get("GITHUB_STEP_SUMMARY"):
    with open(os.environ["GITHUB_STEP_SUMMARY"], "a", encoding="utf-8") as summary:
        summary.write(f"### 运行决定\n{reason}\n")
