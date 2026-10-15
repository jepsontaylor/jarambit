"""Measurement binding, reduction, support, and interpretation.

count is an instrument axis, not an observation unit. Alias N is not newton.
A censored nondetection stays null. A measured zero stays a value.
Declared alternatives are tested by exact fractions, with no solver.
"""
import math
from fractions import Fraction

from assurance.laboratory.history import history_prefix, parse_utc
from assurance.laboratory.records import _digest, schema_refusal

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


def _unable(reason, **extra):
    payload = {
        "diagnostic": "unable_to_determine",
        "finding": "inconclusive",
        "outcome": "refused",
        "reason": reason,
    }
    payload.update(extra)
    return payload


def _number(value):
    if type(value) is bool or type(value) not in (int, float) or not math.isfinite(value):
        return None
    return Fraction(str(value)) if type(value) is float else Fraction(value)


def _value_reason(value):
    if type(value) is bool or type(value) not in (int, float):
        return "non_numeric_value"
    if not math.isfinite(value):
        return "non_finite_value"
    return None


def bind_observation(measurement, history, raw_bytes_sha256=None):
    """Bind one observation to the history prefix, caller raw bytes, calibration, and unit.

    The digest stored on the measurement is not the caller's presented raw
    identity. A missing caller argument stays unavailable. Every accepted
    binding reports the completed prefix event ids, including a censored
    result, a measured zero, and a screened component mapping.
    """
    if type(measurement) is not dict:
        return _refuse("measurement_not_an_object")
    unit = measurement.get("unit")
    if unit not in S01_UNITS:
        return _refuse("unknown_unit")
    value = measurement.get("value")
    if value is not None:
        value_reason = _value_reason(value)
        if value_reason is not None:
            return _refuse(value_reason)
    prefix = history_prefix(history, measurement.get("time_utc"))
    if prefix.get("outcome") == "refused":
        return prefix
    claimed = list(measurement.get("history_prefix_events") or [])
    if prefix["event_ids"] != claimed:
        return _refuse("history_prefix_mismatch")
    if prefix.get("active_event_ids"):
        return _refuse("measurement_during_active_exposure")
    if not _digest(measurement.get("raw_sha256")):
        return _refuse("raw_identity_unavailable")
    if raw_bytes_sha256 is not None and raw_bytes_sha256 != measurement.get("raw_sha256"):
        return _refuse("raw_acquisition_mismatch")
    calibration = measurement.get("calibration") or {}
    if type(calibration) is not dict:
        return _refuse("calibration_malformed")
    when, when_reason = parse_utc(measurement.get("time_utc"))
    opened, open_reason = parse_utc(calibration.get("valid_from_utc"))
    closed, close_reason = parse_utc(calibration.get("valid_to_utc"))
    if when_reason or open_reason or close_reason:
        return _refuse(when_reason or open_reason or close_reason)
    if when < opened or when > closed:
        return _refuse("calibration_not_valid_at_acquisition")
    censoring = measurement.get("censoring")
    if censoring is not None and value is not None:
        return _refuse("censored_value_not_null")
    screened = None
    if "components" in measurement:
        screened = _bind_components(measurement)
        if screened.get("outcome") != "accepted":
            return screened
    if raw_bytes_sha256 is None:
        return _refuse("raw_identity_unavailable")
    for record, filename in (
        (measurement, "measurement_intervention.v1.json"),
        (history, "exposure_history.v1.json"),
    ):
        reason = schema_refusal(record, filename)
        if reason is not None:
            return _refuse(reason)
    if screened is not None:
        accepted = dict(screened)
        accepted["history_prefix_events"] = list(prefix["event_ids"])
        return accepted
    if censoring is not None:
        return {
            "censoring": censoring.get("type"),
            "history_prefix_events": list(prefix["event_ids"]),
            "limit": censoring.get("limit"),
            "outcome": "accepted",
            "value": None,
        }
    if value == 0 or value == 0.0:
        return {
            "censoring": None,
            "history_prefix_events": list(prefix["event_ids"]),
            "outcome": "accepted",
            "value": 0.0,
        }
    return {
        "available": True,
        "history_prefix_events": list(prefix["event_ids"]),
        "outcome": "accepted",
    }


def _bind_components(measurement):
    """Unknown stays unknown. A measured label needs a complete raw binding.

    A partial measured label on one numeric sibling is an unprovenanced fill
    at every value, including zero. A complete measured labeling bound to the
    observation raw digest keeps a measured zero as a value.
    """
    components = measurement.get("components")
    roles = measurement.get("component_roles") or {}
    if type(components) is not dict or type(roles) is not dict:
        return _refuse("components_malformed")
    unknown = []
    numeric = []
    for name, component in components.items():
        if type(name) is not str:
            return _refuse("components_malformed")
        if type(component) is dict:
            if (
                set(component) == {"unknown"}
                and type(component.get("unknown")) is str
                and component["unknown"]
            ):
                unknown.append(name)
                continue
            return _refuse("components_malformed")
        reason = _value_reason(component)
        if reason is not None:
            return _refuse(reason)
        numeric.append(name)
    labeled = [name for name in numeric if roles.get(name) == "measured"]
    if labeled and (
        len(labeled) != len(numeric) or not _digest(measurement.get("raw_sha256"))
    ):
        return _refuse("inferred_component_labeled_measured")
    return {"components_unknown": unknown, "outcome": "accepted"}


def _trace_number(value):
    number = _number(value)
    if number is None:
        return None, "non_numeric_value"
    return number, None


def reduce_trace(trace):
    """Exact gain*(raw-baseline-drift*t). Missing samples stay null."""
    if type(trace) is not dict:
        return _refuse("trace_not_an_object")
    if trace.get("unit_out") not in S01_UNITS:
        return _refuse("unknown_unit")
    gain, gain_reason = _trace_number(trace.get("gain_n_per_count"))
    baseline, baseline_reason = _trace_number(trace.get("baseline_counts"))
    drift, drift_reason = _trace_number(trace.get("drift_counts_per_s"))
    if gain_reason or baseline_reason or drift_reason:
        return _refuse(gain_reason or baseline_reason or drift_reason)
    samples = trace.get("samples")
    if type(samples) is not list:
        return _refuse("trace_malformed")
    values = []
    missing = 0
    for sample in samples:
        if type(sample) is not list or len(sample) != 2:
            return _refuse("trace_malformed")
        time_s, raw = sample
        if raw is None:
            values.append(None)
            missing += 1
            continue
        time_number, time_reason = _trace_number(time_s)
        raw_number, raw_reason = _trace_number(raw)
        if time_reason or raw_reason:
            return _refuse(time_reason or raw_reason)
        values.append(float(gain * (raw_number - baseline - drift * time_number)))
    return {
        "outcome": "accepted",
        "reduction": {
            "failure_observed": trace.get("termination") == "failure",
            "n_missing": missing,
            "n_samples": len(samples),
            "termination": trace.get("termination"),
            "values_n": values,
        },
    }


def validate_reduction(summary, trace):
    """Compare a supplied summary with the independent reduction of the trace.

    Healthy and adverse inputs use this function. Omission and runout relabel
    keep their reasons. Any other disagreement is reduction_mismatch. An exact
    match is accepted, so a reject-all implementation fails the healthy path.
    """
    if type(summary) is not dict:
        return _refuse("summary_not_an_object")
    fresh = reduce_trace(trace)
    if fresh.get("outcome") != "accepted":
        return fresh
    expected = fresh["reduction"]
    summary_values = list(summary.get("values_n") or [])
    expected_values = list(expected["values_n"])
    if any(value is None for value in expected_values) and not any(
        value is None for value in summary_values
    ):
        return _refuse("reduction_omits_missing")
    if summary_values != expected_values:
        return _refuse("reduction_mismatch")
    if summary.get("termination") != expected["termination"]:
        return _refuse("runout_relabeled_failure")
    for key in ("failure_observed", "n_missing", "n_samples"):
        if summary.get(key) != expected[key]:
            return _refuse("reduction_mismatch")
    return {"outcome": "accepted", "reduction": expected}


def validate_observation_support(observation, claim):
    """Unit, frame, and support are separate. Equal numbers do not match support."""
    if type(observation) is not dict or type(claim) is not dict:
        return _refuse("support_record_malformed")
    frame = claim.get("frame")
    observed_frame = observation.get("frame") or {}
    if frame is not None:
        if type(frame) is not dict or type(observed_frame) is not dict:
            return _refuse("frame_axes_mismatch")
        if frame.get("handedness") != observed_frame.get("handedness"):
            return _refuse("frame_handedness_mismatch")
        if frame.get("axes") != observed_frame.get("axes"):
            return _refuse("frame_axes_mismatch")
        if frame.get("id") != observed_frame.get("id"):
            return _refuse("frame_axes_mismatch")
        if "roi" in frame and frame.get("roi") != observed_frame.get("roi"):
            return _refuse("frame_roi_mismatch")
    if "unit" in claim and claim.get("unit") != observation.get("unit"):
        return _refuse("unit_mismatch")
    support = claim.get("support")
    observed_support = observation.get("support") or {}
    if support is not None:
        if type(support) is not dict or type(observed_support) is not dict:
            return _refuse("support_or_reference_mismatch")
        for key in ("kind", "reference_state", "size_mm"):
            if support.get(key) != observed_support.get(key):
                return _refuse("support_or_reference_mismatch")
    scope = claim.get("scope")
    kind = observed_support.get("kind") if type(observed_support) is dict else None
    if scope == "local_organization" and kind in (None, "", "unknown", "bulk"):
        if kind in (None, "", "unknown"):
            return _unable("scope_exceeds_support")
        return _refuse("scope_exceeds_support")
    if scope == "bulk_composition" and kind != "bulk":
        return _refuse("scope_exceeds_support")
    reason = schema_refusal(observation, "measurement_intervention.v1.json")
    if reason is not None:
        return _refuse(reason)
    return {"outcome": "accepted"}


def validate_intervention(intervention, claim):
    """A preparation that can introduce a species blocks an intrinsic claim for it.

    An intrinsic claim needs an explicit may_introduce list. A missing list is
    undeclared, not evidence that the preparation introduces nothing.
    """
    if type(intervention) is not dict or type(claim) is not dict:
        return _refuse("intervention_not_an_object")
    if claim.get("scope") == "intrinsic":
        introduced = intervention.get("may_introduce")
        if "may_introduce" not in intervention or type(introduced) is not list:
            return _unable("preparation_undeclared")
        if claim.get("species") in introduced:
            return _refuse("preparation_induced_not_intrinsic")
    reason = schema_refusal(intervention, "measurement_intervention.v1.json")
    if reason is not None:
        return _refuse(reason)
    return {"outcome": "accepted"}


def _row_image(row, alternative):
    if len(row) != len(alternative):
        return None
    total = Fraction(0)
    for term, coefficient in zip(row, alternative):
        term_number = _number(term)
        coefficient_number = _number(coefficient)
        if term_number is None or coefficient_number is None:
            return None
        total += term_number * coefficient_number
    return total


def interpret(
    observations=None,
    claim=None,
    operator_rows=None,
    observed=None,
    alternatives=None,
    history=None,
    raw_bytes_by_id=None,
):
    """No empty set is healthy. Support needs observations that actually bind.

    History and presented raw identities come only from the explicit arguments.
    Fields on the claim are subject assertions, not caller evidence. A
    calibration id or a stored digest is not that context.
    """
    if operator_rows is not None or alternatives is not None:
        rows = list(operator_rows or [])
        choices = list(alternatives or [])
        if not rows or not choices:
            return _unable("not_identified")
        width = len(rows[0])
        if width == 0 or any(type(row) is not list or len(row) != width for row in rows):
            return _unable("alternative_dimension_mismatch", alternatives=choices)
        if any(type(alternative) is not list or len(alternative) != width for alternative in choices):
            return _unable("alternative_dimension_mismatch", alternatives=choices)
        if type(observed) is not list or len(observed) != len(rows):
            return _unable("not_identified", alternatives=choices)
        target = []
        for value in observed:
            number = _number(value)
            if number is None:
                return _unable("non_numeric_value", alternatives=choices)
            target.append(number)
        matched = []
        for alternative in choices:
            image = [_row_image(row, alternative) for row in rows]
            if None in image:
                return _unable("non_numeric_value", alternatives=choices)
            if image == target:
                matched.append(list(alternative))
        if len(matched) == 1:
            return {"identified": matched, "outcome": "accepted"}
        return {
            "alternatives": [list(alternative) for alternative in choices],
            "finding": "inconclusive",
            "outcome": "refused",
            "reason": "not_identified",
        }
    if not observations:
        return _unable("absent_measurement_cannot_be_healthy")
    if type(observations) is not list or type(claim) is not dict or not claim:
        return _unable("invalid_observation_cannot_support")
    bound_history = history
    bound_raw = raw_bytes_by_id if type(raw_bytes_by_id) is dict else None
    for observation in observations:
        presented = None
        if type(observation) is dict and bound_raw is not None:
            presented = bound_raw.get(observation.get("id"))
        bound = bind_observation(observation, bound_history, presented)
        if bound.get("outcome") != "accepted":
            return _unable(bound.get("reason", "invalid_observation_cannot_support"))
    return {"finding": "supported_within_scope", "outcome": "accepted"}
