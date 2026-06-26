from __future__ import annotations

import pandas as pd

from sensor_fusion.timestamp_repair import repair_dataframe


def _repair(rows):
    return repair_dataframe(pd.DataFrame(rows), "date", "time")


def test_one_digit_hour_can_be_contextual_evening_hour():
    out = _repair(
        [
            {"date": "01.05.2025", "time": "23:04"},
            {"date": "01.05.2025", "time": "3:06"},
            {"date": "01.05.2025", "time": "23:22"},
        ]
    )
    assert out.loc[1, "repaired_time"] == "23:06"
    assert out.loc[1, "repair_status"] == "repaired"


def test_date_carryover_across_midnight_is_context_repaired():
    out = _repair(
        [
            {"date": "08.05.2025", "time": "23:56"},
            {"date": "08.05.2026", "time": "00:02"},
            {"date": "08.05.2027", "time": "00:05"},
            {"date": "09.05.2025", "time": "07:24"},
        ]
    )
    assert out.loc[1, "repaired_date"] == "09.05.2025"
    assert out.loc[2, "repaired_date"] == "09.05.2025"


def test_month_typo_uses_neighbor_context():
    out = _repair(
        [
            {"date": "20.10.2025", "time": "14:53"},
            {"date": "20.12.2025", "time": "14:54"},
            {"date": "20.10.2025", "time": "14:59"},
        ]
    )
    assert out.loc[1, "repaired_date"] == "20.10.2025"


def test_missing_day_and_compact_time_are_repaired():
    out = _repair(
        [
            {"date": "08.07.2025", "time": "14:43"},
            {"date": ".07.2025", "time": "1445"},
            {"date": "08.07.2025", "time": "14:46"},
        ]
    )
    assert out.loc[1, "repaired_date"] == "08.07.2025"
    assert out.loc[1, "repaired_time"] == "14:45"

