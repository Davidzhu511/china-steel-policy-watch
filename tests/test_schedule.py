from datetime import datetime
from zoneinfo import ZoneInfo

from steelwatch.schedule import should_run


def test_schedule_gate_handles_berlin_summer_and_winter_time():
    summer = datetime(2026, 7, 21, 8, tzinfo=ZoneInfo("Europe/Berlin"))
    winter = datetime(2026, 12, 21, 8, tzinfo=ZoneInfo("Europe/Berlin"))
    assert should_run("schedule", "50 5 * * *", summer)
    assert not should_run("schedule", "50 6 * * *", summer)
    assert should_run("schedule", "50 6 * * *", winter)
    assert not should_run("schedule", "50 5 * * *", winter)
    assert should_run("schedule", "50 11 * * *", summer)
    assert not should_run("schedule", "50 12 * * *", summer)
    assert should_run("schedule", "50 12 * * *", winter)
    assert not should_run("schedule", "50 11 * * *", winter)
    assert should_run("schedule", "50 17 * * *", summer)
    assert not should_run("schedule", "50 18 * * *", summer)
    assert should_run("schedule", "50 18 * * *", winter)
    assert not should_run("schedule", "50 17 * * *", winter)
    assert should_run("schedule", "10 8,15,21 * * *", summer)
    assert should_run("schedule", "10 8,15,21 * * *", winter)
    assert should_run("workflow_dispatch", "", summer)
    assert should_run("push", "", summer)
