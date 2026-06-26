from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime, time, timedelta
import math
import re
from typing import Iterable

import pandas as pd


_DATE_CLEAN_RE = re.compile(r"^\d{1,2}\.\d{1,2}\.\d{4}$")
_TIME_CLEAN_RE = re.compile(r"^\d{2}:\d{2}$")


@dataclass(frozen=True)
class Candidate:
    value: datetime
    reason: str
    raw_like: bool = False


def _safe_date(year: int, month: int, day: int) -> date | None:
    try:
        return date(year, month, day)
    except ValueError:
        return None


def _coerce_year(raw_year: str, prev: datetime | None) -> set[int]:
    raw_year = re.sub(r"\D", "", raw_year)
    years: set[int] = set()
    if len(raw_year) == 4:
        years.add(int(raw_year))
        if raw_year.startswith("20"):
            years.add(2025)
            years.add(2026)
    elif len(raw_year) == 3:
        if raw_year.startswith("20"):
            years.add(2025)
            years.add(2026)
        if prev is not None:
            years.add(prev.year)
    elif len(raw_year) == 2:
        years.add(2000 + int(raw_year))
    if prev is not None:
        years.add(prev.year)
    years.update({2025, 2026})
    return {y for y in years if 2020 <= y <= 2030}


def date_candidates(raw: object, prev: datetime | None = None) -> list[tuple[date, str]]:
    text = "" if pd.isna(raw) else str(raw).strip()
    out: dict[date, str] = {}

    groups = re.findall(r"\d+", text)
    if re.fullmatch(r"\d{8}", text):
        day, month, year = int(text[:2]), int(text[2:4]), int(text[4:])
        parsed = _safe_date(year, month, day)
        if parsed:
            out[parsed] = "date_compact"

    if len(groups) >= 3:
        day_text, month_text, year_text = groups[0], groups[1], groups[2]
        day = int(day_text[-2:]) if len(day_text) > 2 else int(day_text)
        month = int(month_text[-2:]) if len(month_text) > 2 else int(month_text)
        for year in _coerce_year(year_text, prev):
            parsed = _safe_date(year, month, day)
            if parsed:
                reason = "date_clean" if _DATE_CLEAN_RE.match(text) else "date_format"
                out.setdefault(parsed, reason)

    if len(groups) == 2 and prev is not None:
        # Handles values like ".07.2025" where the day is missing.
        first, second = groups
        if len(second) == 4 and 1 <= int(first) <= 12:
            month = int(first)
            for offset in range(-2, 3):
                candidate = prev.date() + timedelta(days=offset)
                if candidate.month == month:
                    out.setdefault(candidate, "date_context_missing_day")

    if prev is not None:
        for offset in range(-2, 4):
            out.setdefault(prev.date() + timedelta(days=offset), "date_context")

    return sorted(out.items(), key=lambda item: item[0])


def _valid_time(hour: int, minute: int) -> time | None:
    if 0 <= hour <= 23 and 0 <= minute <= 59:
        return time(hour, minute)
    return None


def _add_time(out: dict[time, str], hour: int, minute: int, reason: str) -> None:
    parsed = _valid_time(hour, minute)
    if parsed:
        out.setdefault(parsed, reason)


def time_candidates(raw: object) -> list[tuple[time, str]]:
    text = "" if pd.isna(raw) else str(raw).strip()
    out: dict[time, str] = {}
    if not text:
        return []

    cleaned = text.replace(".", ":").replace("-", ":").replace("?", ":").replace("&", ":")
    groups = re.findall(r"\d+", cleaned)

    if ":" in cleaned and len(groups) >= 2:
        hour_text, minute_text = groups[0], groups[1]
        raw_hour = int(hour_text[:2]) if len(hour_text) >= 2 else int(hour_text)
        raw_minute = int(minute_text[:2]) if len(minute_text) >= 2 else int(minute_text)
        clean_value = bool(_TIME_CLEAN_RE.match(text) and _valid_time(raw_hour, raw_minute))
        hour_values = {int(hour_text[:2]) if len(hour_text) >= 2 else int(hour_text)}
        if len(hour_text) == 1:
            base = int(hour_text)
            hour_values.update(h for h in (base + 10, base + 20) if h <= 23)
        if len(hour_text) >= 3:
            hour_values.add(int(hour_text[-2:]))
            hour_values.add(int(hour_text[0] + hour_text[-1]))

        minute_values: set[int] = set()
        if len(minute_text) == 1:
            m = int(minute_text)
            minute_values.add(m)
            minute_values.update(range(m * 10, min(m * 10 + 10, 60)))
        else:
            minute = int(minute_text[:2])
            minute_values.add(minute)
            if minute >= 60:
                last_digit = minute % 10
                minute_values.update(tens * 10 + last_digit for tens in range(6))

        for hour in hour_values:
            for minute in minute_values:
                reason = "time_clean" if clean_value else "time_format"
                if raw_hour > 23 or raw_minute > 59:
                    reason = "time_value"
                _add_time(out, hour, minute, reason)
                if minute >= 60:
                    _add_time(out, hour + 1, minute - 60, "time_overflow")

    digits = "".join(groups)
    if digits:
        if text.startswith("!") and len(digits) >= 3:
            # Common keyboard slip: ! instead of 1, e.g. "!6050" near 16:05.
            _add_time(out, int("1" + digits[0]), int(digits[1:3]), "time_keyboard_slip")
        if len(digits) == 4:
            hour, minute = int(digits[:2]), int(digits[2:])
            _add_time(out, hour, minute, "time_compact")
            if hour > 23:
                _add_time(out, int(digits[0]), int(digits[1:3]), "time_compact_shift")
        elif len(digits) == 3:
            _add_time(out, int(digits[0]), int(digits[1:]), "time_compact")
            _add_time(out, int(digits[:2]), int(digits[2]) * 10, "time_compact")
            _add_time(out, int(digits[:2]), int(digits[2]), "time_compact")
        elif len(digits) == 2:
            minute = int(digits)
            for hour in range(24):
                _add_time(out, hour, minute, "time_context_hour")

    expanded: list[tuple[time, str]] = []
    for t, reason in sorted(out.items(), key=lambda item: item[0]):
        expanded.append((t, reason))
    return expanded


def _strict_datetime(raw_date: object, raw_time: object) -> datetime | None:
    date_text = "" if pd.isna(raw_date) else str(raw_date).strip()
    time_text = "" if pd.isna(raw_time) else str(raw_time).strip()
    if not (_DATE_CLEAN_RE.match(date_text) and _TIME_CLEAN_RE.match(time_text)):
        return None
    try:
        return datetime.strptime(f"{date_text} {time_text}", "%d.%m.%Y %H:%M")
    except ValueError:
        return None


def _score_candidate(candidate: datetime, prev: datetime | None, next_anchor: datetime | None, raw_like: bool) -> float:
    score = 0.0 if raw_like else 12.0
    if prev is not None:
        delta_min = (candidate - prev).total_seconds() / 60
        if not raw_like and delta_min == 0:
            score += 5
        if delta_min < 0:
            score += 100_000 + abs(delta_min)
        elif delta_min <= 12 * 60:
            score += delta_min * 0.03
        elif delta_min <= 48 * 60:
            score += 30 + delta_min * 0.04
        elif delta_min <= 10 * 24 * 60:
            score += 300 + delta_min * 0.02
        else:
            score += 10_000 + math.log1p(delta_min)
    if next_anchor is not None:
        delta_min = (next_anchor - candidate).total_seconds() / 60
        if delta_min < 0:
            score += 100_000 + abs(delta_min)
        elif delta_min <= 12 * 60:
            score += delta_min * 0.02
        elif delta_min <= 48 * 60:
            score += 20 + delta_min * 0.03
        elif delta_min <= 10 * 24 * 60:
            score += 250 + delta_min * 0.015
        else:
            score += 5_000 + math.log1p(delta_min)
    return score


def _next_clean_anchors(df: pd.DataFrame, date_col: str, time_col: str) -> list[datetime | None]:
    anchors = [_strict_datetime(d, t) for d, t in zip(df[date_col], df[time_col], strict=False)]
    next_anchors: list[datetime | None] = [None] * len(anchors)
    upcoming: datetime | None = None
    for idx in range(len(anchors) - 1, -1, -1):
        next_anchors[idx] = upcoming
        if anchors[idx] is not None:
            upcoming = anchors[idx]
    return next_anchors


def choose_datetime(
    raw_date: object,
    raw_time: object,
    prev: datetime | None = None,
    next_anchor: datetime | None = None,
) -> tuple[datetime | None, str, str]:
    raw_dt = _strict_datetime(raw_date, raw_time)

    if raw_dt is not None:
        if prev is None:
            return raw_dt, "valid", "valid"
        prev_delta_min = (raw_dt - prev).total_seconds() / 60
        next_delta_min = None
        if next_anchor is not None:
            next_delta_min = (next_anchor - raw_dt).total_seconds() / 60

        # Clean timestamps should remain clean when they agree with at least
        # one local anchor. This prevents early outliers from dragging a valid
        # series backward, while still allowing isolated copy/paste errors
        # like a single October row typed as December to be context-repaired.
        one_week = 7 * 24 * 60
        agrees_with_prev = 0 <= prev_delta_min <= one_week
        agrees_with_next = next_delta_min is not None and 0 <= next_delta_min <= one_week
        if agrees_with_prev or agrees_with_next:
            return raw_dt, "valid", "valid"

    candidates: list[Candidate] = []
    for d, d_reason in date_candidates(raw_date, prev):
        for t, t_reason in time_candidates(raw_time):
            value = datetime.combine(d, t)
            raw_like = raw_dt == value
            reason = "valid" if raw_like else ",".join(sorted({d_reason, t_reason}))
            candidates.append(Candidate(value=value, reason=reason, raw_like=raw_like))

    if not candidates:
        return None, "unrecoverable", "no_valid_datetime_candidate"

    best = min(candidates, key=lambda c: _score_candidate(c.value, prev, next_anchor, c.raw_like))
    if raw_dt is not None and best.value == raw_dt:
        return best.value, "valid", "valid"
    return best.value, "repaired", best.reason


def interpolate_unresolved(values: list[datetime | None]) -> list[datetime | None]:
    out = values[:]
    for idx, value in enumerate(out):
        if value is not None:
            continue
        prev_idx = next((j for j in range(idx - 1, -1, -1) if out[j] is not None), None)
        next_idx = next((j for j in range(idx + 1, len(out)) if out[j] is not None), None)
        if prev_idx is None or next_idx is None:
            continue
        prev_value = out[prev_idx]
        next_value = out[next_idx]
        if prev_value is None or next_value is None or next_value < prev_value:
            continue
        fraction = (idx - prev_idx) / (next_idx - prev_idx)
        out[idx] = prev_value + (next_value - prev_value) * fraction
    return out


def repair_dataframe(df: pd.DataFrame, date_col: str = "date", time_col: str = "time") -> pd.DataFrame:
    out = df.copy()
    next_anchors = _next_clean_anchors(out, date_col, time_col)

    repaired: list[datetime | None] = []
    statuses: list[str] = []
    reasons: list[str] = []
    prev: datetime | None = None
    for idx, row in out.iterrows():
        value, status, reason = choose_datetime(row[date_col], row[time_col], prev=prev, next_anchor=next_anchors[idx])
        repaired.append(value)
        statuses.append(status)
        reasons.append(reason)
        if value is not None:
            prev = value

    interpolated = interpolate_unresolved(repaired)
    for idx, (before, after) in enumerate(zip(repaired, interpolated, strict=False)):
        if before is None and after is not None:
            statuses[idx] = "repaired"
            reasons[idx] = "interpolated_from_neighbors"

    out["original_date"] = out[date_col]
    out["original_time"] = out[time_col]
    out["repaired_datetime"] = pd.to_datetime(interpolated)
    out["repaired_date"] = out["repaired_datetime"].dt.strftime("%d.%m.%Y")
    out["repaired_time"] = out["repaired_datetime"].dt.strftime("%H:%M")
    out["repair_status"] = statuses
    out["repair_reason"] = reasons
    out.loc[out["repaired_datetime"].isna(), "repair_status"] = "unrecoverable"
    out["raw_row_index"] = range(len(out))
    out["sort_order_after_repair"] = out["repaired_datetime"].rank(method="first", na_option="bottom").astype(int)
    out["raw_out_of_order_after_repair"] = out["sort_order_after_repair"] != (out["raw_row_index"] + 1)
    return out


def status_summary(statuses: Iterable[str]) -> dict[str, int]:
    return pd.Series(list(statuses)).value_counts().sort_index().astype(int).to_dict()
