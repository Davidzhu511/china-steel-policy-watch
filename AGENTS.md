# Collection and analysis responsibilities

GitHub Actions owns collection, deduplication, history, tests, merge and publication. ChatGPT owns source verification, translation and business interpretation. Do not turn a daily editorial task into an infrastructure audit.

Read README.md. Prefer data/review_queue.json. In schema v2, items are actionable and blocked_items are deferred; pending_count includes both. An empty actionable list with blocked items is valid. Do not revisit the same blocked source version without new evidence or a user request. Never treat a deferred item as verified.

For routine analysis, process at most five high-value items, match source URL and publication date, preserve existing entries, and submit one editorial/ PR changing only config/editorial.json and config/triage.json. Check for existing matching PRs to prevent duplicate submissions. GitHub owns subsequent CI, automatic merge and publishing; do not poll or re-run the pipeline as part of the daily analysis. Report submitted content honestly without claiming it is already live.

Keep collection timestamps distinct from editorial timestamps. Scheduled jobs may arrive late; a normal DST skip is not a deployment failure. Use valid older data with its date rather than blocking analysis on same-day collection. Do not emit recurring technical status tables. Report business developments and only actionable, persistent blockers.

Engineering changes still require appropriate tests and a PR. Preserve source evidence, tests and publication verification. Never bypass CI or infer legal facts from titles.
