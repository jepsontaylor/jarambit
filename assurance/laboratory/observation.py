"""Measurement binding, reduction, support, and interpretation.

count is an instrument axis, not an observation unit. Alias N is not newton.
A censored nondetection stays null. A measured zero stays a value.
Declared alternatives are tested by exact fractions, with no solver.
"""
from fractions import Fraction

from assurance.laboratory.history import history_prefix, parse_utc

S01_UNITS = (
    "dimensionless",
    "gram",
    "millimetre",
    "newton",
    "newton_millimetre",
    "newton_per_gram",
    "megapascal",
    "second",
    "celsius",
)


def _refuse(reason, **extra):
    payload = {"outcome": "refused", "reason": reason}
    payload.update(extra)
    return payload


def _fraction(value):
    if type(value) is float:
        return Fraction(str(value))
    return Fraction(value)


def bind_observation(measurement, history, raw_bytes_sha256=None):
    """Bind one observation to the history prefix, raw bytes, calibration, and unit."""
    unit = measurement.get("unit")
    if unit not in S01_UNITS:
        return _refuse("unknown_unit")
    prefix = history_prefix(history, measurement.get("time_utc"))
    if prefix.get("outcome") == "refused":
        return prefix
    claimed = list(measurement.get("history_prefix_events") or [])
    if prefix["event_ids"] != claimed:
        return _refuse("history_prefix_mismatch")
    if raw_bytes_sha256 is not None and raw_bytes_sha256 != measurement.get("raw_sha256"):
        return _refuse("raw_acquisition_mismatch")
    calibration = measurement.get("calibration") or {}
    when, when_reason = parse_utc(measurement.get("time_utc"))
    opened, open_reason = parse_utc(calibration.get("valid_from_utc"))
    closed, close_reason = parse_utc(calibration.get("valid_to_utc"))
    if when_reason or open_reason or close_reason:
        return _refuse(when_reason or open_reason or close_reason)
    if when < opened or when > closed:
        return _refuse("calibration_not_valid_at_acquisition")
    censoring = measurement.get("censoring")
    if censoring is not None and measurement.get("value") is not None:
        return _refuse("censored_value_not_null")
    if "components" in measurement:
        roles = measurement.get("component_roles") or {}
        unknown = []
        for name, value in measurement["components"].items():
            if type(value) is dict and "unknown" in value:
                unknown.append(name)
                continue
            if (value == 0 or value == 0.0) and roles.get(name) == "measured":
                return _refuse("inferred_component_labeled_measured")
        return {"components_unknown": unknown, "outcome": "accepted"}
    if censoring is not None:
        return {
            "censoring": censoring.get("type"),
            "limit": censoring.get("limit"),
            "outcome": "accepted",
            "value": None,
        }
    if measurement.get("value") == 0 or measurement.get("value") == 0.0:
        return {"censoring": None, "outcome": "accepted", "value": 0.0}
    if raw_bytes_sha256 is not None:
        return {"available": True, "outcome": "accepted"}
    return {"history_prefix_events": prefix["event_ids"], "outcome": "accepted"}


def reduce_trace(trace):
    """Exact gain*(raw-baseline-drift*t). Missing samples stay null."""
    if trace.get("unit_out") not in S01_UNITS:
        return _refuse("unknown_unit")
    gain = _fraction(trace["gain_n_per_count"])
    baseline = _fraction(trace["baseline_counts"])
    drift = _fraction(trace["drift_counts_per_s"])
    values = []
    missing = 0
    for sample in trace["samples"]:
        time_s, raw = sample
        if raw is None:
            values.append(None)
            missing += 1
            continue
        reduced = gain * (_fraction(raw) - baseline - drift * _fraction(time_s))
        values.append(float(reduced))
    return {
        "outcome": "accepted",
        "reduction": {
            "failure_observed": trace.get("termination") == "failure",
            "n_missing": missing,
            "n_samples": len(trace["samples"]),
            "termination": trace.get("termination"),
            "values_n": values,
        },
    }


def validate_reduction(summary, trace):
    """Recompute the trace. Omission and runout relabel are separate refusals."""
    fresh = reduce_trace(trace)
    if fresh.get("outcome") != "accepted":
        return fresh
    expected = fresh["reduction"]
    summary_values = list(summary.get("values_n") or [])
    expected_missing = any(value is None for value in expected["values_n"])
    summary_missing = any(value is None for value in summary_values)
    if summary.get("termination") != expected["termination"] and expected_missing and summary_missing:
        return _refuse("runout_relabeled_failure")
    if expected_missing and not summary_missing and summary.get("termination") == "runout_censored":
        return _refuse("reduction_omits_missing")
    if summary.get("termination") != trace.get("termination"):
        return _refuse("runout_relabeled_failure")
    return _refuse("reduction_mismatch")


def validate_observation_support(observation, claim):
    """Unit, frame, and support are separate. Equal numbers do not match support."""
    frame = claim.get("frame")
    observed_frame = observation.get("frame") or {}
    if frame is not None and frame.get("handedness") != observed_frame.get("handedness"):
        return _refuse("frame_handedness_mismatch")
    support = claim.get("support")
    observed_support = observation.get("support") or {}
    if support is not None:
        for key in ("kind", "reference_state", "size_mm"):
            if support.get(key) != observed_support.get(key):
                return _refuse("support_or_reference_mismatch")
    if "unit" in claim and claim.get("unit") != observation.get("unit"):
        return _refuse("frame_handedness_mismatch")
    scope = claim.get("scope")
    kind = observed_support.get("kind")
    if scope == "local_organization" and kind == "bulk":
        return _refuse("scope_exceeds_support")
    if scope == "bulk_composition" and kind != "bulk":
        return _refuse("scope_exceeds_support")
    return {"outcome": "accepted"}


def validate_intervention(intervention, claim):
    """A preparation that can introduce a species blocks an intrinsic claim for it."""
    species = claim.get("species")
    introduced = intervention.get("may_introduce") or []
    if claim.get("scope") == "intrinsic" and species in introduced:
        return _refuse("preparation_induced_not_intrinsic")
    return {"outcome": "accepted"}


def _row_image(row, alternative):
    if len(row) != len(alternative):
        return None
    total = Fraction(0)
    for term, coefficient in zip(row, alternative):
        total += _fraction(term) * _fraction(coefficient)
    return total


def interpret(observations=None, claim=None, operator_rows=None, observed=None, alternatives=None):
    """No empty set is healthy. Declared rows either identify one alternative or refuse."""
    if operator_rows is not None or alternatives is not None:
        target = [_fraction(value) for value in (observed or [])]
        matched = []
        for alternative in alternatives or []:
            image = [_row_image(row, alternative) for row in (operator_rows or [])]
            if None in image:
                continue
            if image == target:
                matched.append(list(alternative))
        if len(matched) == 1:
            return {"identified": matched, "outcome": "accepted"}
        return {
            "alternatives": [list(alternative) for alternative in (alternatives or [])],
            "finding": "inconclusive",
            "outcome": "refused",
            "reason": "not_identified",
        }
    if not observations:
        return {
            "diagnostic": "unable_to_determine",
            "finding": "inconclusive",
            "outcome": "refused",
            "reason": "absent_measurement_cannot_be_healthy",
        }
    return {"finding": "supported_within_scope", "outcome": "accepted"}
