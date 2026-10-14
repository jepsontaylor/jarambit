"""Chronological exposure history. Clocks stay segmented and UTC-only."""
import math
import re
from datetime import datetime

from assurance.laboratory.records import schema_refusal
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
    An impossible calendar date is a typed refusal, not an exception.
    """
    if type(text) is not str:
        return None, "timestamp_without_utc_offset"
    try:
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
    except ValueError:
        return None, "timestamp_not_a_calendar_date"


def _stamp(text):
    parsed, reason = parse_utc(text)
    if reason is not None:
        raise _Stamp(reason)
    return parsed


class _Stamp(Exception):
    def __init__(self, reason):
        self.reason = reason


def _nonnegative_finite(value):
    if type(value) is bool or type(value) not in (int, float):
        return False
    if not math.isfinite(value) or value < 0:
        return False
    return True


def history_prefix(history, at_utc):
    """Completed events end strictly before at_utc.

    An event that contains at_utc stays active. Callers must not treat the
    completed prefix as the whole history while one of those events is open.
    """
    if type(history) is not dict:
        return _refuse("history_not_an_object")
    at, reason = parse_utc(at_utc)
    if reason is not None:
        return _refuse(reason)
    events = history.get("events") or []
    if type(events) is not list:
        return _refuse("history_malformed")
    event_ids = []
    active_ids = []
    for event in events:
        if type(event) is not dict:
            return _refuse("history_malformed")
        start, start_reason = parse_utc(event.get("start_utc"))
        end, end_reason = parse_utc(event.get("end_utc"))
        if start_reason is not None:
            return _refuse(start_reason)
        if end_reason is not None:
            return _refuse(end_reason)
        if start <= at < end:
            active_ids.append(event.get("id"))
        elif end < at:
            event_ids.append(event.get("id"))
    return {
        "active_event_ids": active_ids,
        "event_ids": event_ids,
        "scientific_hash": scientific_hash(event_ids),
    }


def _overlaps(left, right):
    return left[0] < right[1] and right[0] < left[1]


def _gap_is_recorded(earlier, later, gap_start, gap_end):
    for event in (earlier, later):
        for gap in event.get("missing_intervals") or []:
            if type(gap) is not dict:
                continue
            start, start_reason = parse_utc(gap.get("start_utc"))
            end, end_reason = parse_utc(gap.get("end_utc"))
            if start_reason or end_reason:
                continue
            if start <= gap_start and gap_end <= end:
                return True
    return False


def validate_history(history):
    """Accept explicit UTC segments. Never invent a continuous elapsed time."""
    if type(history) is not dict:
        return _refuse("history_not_an_object")
    try:
        intervals = []
        parsed_events = []
        missing_recorded = False
        events = history.get("events") or []
        segments = history.get("segments") or []
        if type(events) is not list or type(segments) is not list:
            return _refuse("history_malformed")
        segment_ids = []
        origins = []
        for segment in segments:
            if type(segment) is not dict:
                return _refuse("history_malformed")
            identity = segment.get("id")
            if type(identity) is not str or not identity or identity in segment_ids:
                return _refuse("segment_reference_unknown")
            if segment.get("clock") != "monotonic":
                return _refuse("incoherent_clock_reset")
            origins.append(_stamp(segment.get("origin_utc")))
            if "uncertainty_s" not in segment:
                return _refuse("segment_uncertainty_missing")
            if not _nonnegative_finite(segment.get("uncertainty_s")):
                return _refuse("segment_uncertainty_invalid")
            segment_ids.append(identity)
        for index in range(1, len(origins)):
            if origins[index] <= origins[index - 1]:
                return _refuse("incoherent_clock_reset")
        for event in events:
            if type(event) is not dict:
                return _refuse("history_malformed")
            if event.get("segment") not in segment_ids:
                return _refuse("segment_reference_unknown")
            start = _stamp(event.get("start_utc"))
            end = _stamp(event.get("end_utc"))
            if end < start:
                return _refuse("impossible_interval_order")
            for gap in event.get("missing_intervals") or []:
                if type(gap) is not dict:
                    return _refuse("history_malformed")
                gap_start = _stamp(gap.get("start_utc"))
                gap_end = _stamp(gap.get("end_utc"))
                if gap_end < gap_start:
                    return _refuse("impossible_interval_order")
                missing_recorded = True
            intervals.append((start, end))
            parsed_events.append((event, start, end))
        by_segment = {}
        for event, start, end in parsed_events:
            by_segment.setdefault(event.get("segment"), []).append((start, end, event))
        for rows in by_segment.values():
            rows.sort(key=lambda row: (row[0], row[1], str(row[2].get("id"))))
            for earlier, later in zip(rows, rows[1:]):
                if later[0] > earlier[1] and not _gap_is_recorded(
                    earlier[2], later[2], earlier[1], later[0]
                ):
                    return _refuse("uncovered_gap")
    except _Stamp as error:
        return _refuse(error.reason)
    schema_reason = schema_refusal(history, "exposure_history.v1.json")
    if schema_reason is not None:
        return _refuse(schema_reason)
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
