"""Chronological exposure history. Clocks stay segmented and UTC-only."""
import re
from datetime import datetime

from assurance.testing.contracts import scientific_hash

_UTC_Z = re.compile(r"^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}Z$")
_UTC_OFFSET = re.compile(
    r"^(\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2})([+-]\d{2}:\d{2})$"
)


def _refuse(reason):
    return {"outcome": "refused", "reason": reason}


def parse_utc(text):
    """Return a naive UTC datetime, or a refusal reason.

    Z is the fixtured UTC form. +00:00 is the only other UTC offset.
    """
    if type(text) is not str:
        return None, "timestamp_without_utc_offset"
    if text.endswith("Z"):
        if _UTC_Z.fullmatch(text) is None:
            return None, "timestamp_without_utc_offset"
        return datetime.strptime(text[:-1], "%Y-%m-%dT%H:%M:%S"), None
    matched = _UTC_OFFSET.fullmatch(text)
    if matched is None:
        return None, "timestamp_without_utc_offset"
    if matched.group(2) != "+00:00":
        return None, "timestamp_offset_not_utc"
    return datetime.strptime(matched.group(1), "%Y-%m-%dT%H:%M:%S"), None


def _stamp(text):
    parsed, reason = parse_utc(text)
    if reason is not None:
        raise _Stamp(reason)
    return parsed


class _Stamp(Exception):
    def __init__(self, reason):
        self.reason = reason


def history_prefix(history, at_utc):
    """Event ids whose end is strictly before at_utc, plus their hash."""
    at, reason = parse_utc(at_utc)
    if reason is not None:
        return _refuse(reason)
    event_ids = []
    for event in history.get("events") or []:
        end, end_reason = parse_utc(event.get("end_utc"))
        if end_reason is not None:
            return _refuse(end_reason)
        if end < at:
            event_ids.append(event["id"])
    return {
        "event_ids": event_ids,
        "scientific_hash": scientific_hash(event_ids),
    }


def _overlaps(left, right):
    return left[0] < right[1] and right[0] < left[1]


def validate_history(history):
    """Accept explicit UTC segments. Never invent a continuous elapsed time."""
    try:
        intervals = []
        missing_recorded = False
        for event in history.get("events") or []:
            start = _stamp(event.get("start_utc"))
            end = _stamp(event.get("end_utc"))
            if end < start:
                return _refuse("impossible_interval_order")
            for gap in event.get("missing_intervals") or []:
                gap_start = _stamp(gap.get("start_utc"))
                gap_end = _stamp(gap.get("end_utc"))
                if gap_end < gap_start:
                    return _refuse("impossible_interval_order")
                missing_recorded = True
            for origin in ():
                _stamp(origin)
            intervals.append((start, end))
        for segment in history.get("segments") or []:
            _stamp(segment.get("origin_utc"))
            if "uncertainty_s" not in segment:
                return _refuse("segment_uncertainty_missing")
    except _Stamp as error:
        return _refuse(error.reason)
    overlap_recorded = any(
        _overlaps(intervals[index], intervals[other])
        for index in range(len(intervals))
        for other in range(index + 1, len(intervals))
    )
    result = {
        "continuous_elapsed": None,
        "outcome": "accepted",
        "segments": [segment["id"] for segment in history.get("segments") or []],
    }
    if missing_recorded:
        result["missing_intervals_recorded"] = True
    if overlap_recorded:
        result["overlap_recorded"] = True
    return result
