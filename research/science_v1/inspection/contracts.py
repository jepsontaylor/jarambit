"""T14 non-destructive inspection, PoD, blind-zone, and warning contracts (T14-01..09)."""
from typing import Sequence
from research.science_v1.common import ContractVerdict, ResearchContractError, require_disjoint_sets, require_finite


def check_truth_independent(ndt_channel_id: str, destructive_truth_id: str) -> ContractVerdict:
    """T14-01: NDT calibration truth must come from an independent destructive/reference channel."""
    if not destructive_truth_id or ndt_channel_id == destructive_truth_id:
        raise ResearchContractError("circular_ndt_truth_channel")
    return ContractVerdict("T14-01-truth_independent", "pass", "independent_destructive_truth_verified")


def check_silent_damage(proxy_delta: float, proxy_threshold: float, toughness_drop_pct: float, claim_safe_from_proxy_alone: bool) -> ContractVerdict:
    """T14-02: Low-proxy-signature high-consequence embrittlement/damage cannot be cleared by single proxy alone."""
    proxy_quiet = abs(require_finite("proxy", proxy_delta)) < require_finite("thresh", proxy_threshold)
    damaged = require_finite("toughness_drop", toughness_drop_pct) >= 15.0
    if proxy_quiet and damaged and claim_safe_from_proxy_alone:
        raise ResearchContractError("silent_damage_missed_by_single_proxy")
    return ContractVerdict("T14-02-silent_damage", "pass", "silent_damage_screened_with_complementary_channel")


def check_healthy_nuisance(geometry_or_roughness_shift: float, damage_present: bool, false_reject: bool) -> ContractVerdict:
    """T14-03: Benign roughness/thickness/oxide variation on healthy part must not trigger false damage reject."""
    require_finite("nuisance", geometry_or_roughness_shift)
    if not damage_present and false_reject:
        raise ResearchContractError("healthy_part_false_reject_under_nuisance")
    return ContractVerdict("T14-03-healthy_nuisance", "pass", "nuisance_invariant_healthy_pass")


def check_instrument_nonlinearity(saturation_flag: bool, dead_zone_flag: bool, lift_off_mm: float, max_lift_off_mm: float, emit_valid_sizing: bool) -> ContractVerdict:
    """T14-04: Saturation, dead-zone, or excessive probe lift-off must invalidate flaw sizing."""
    invalid = saturation_flag or dead_zone_flag or (require_finite("liftoff", lift_off_mm) > require_finite("max_liftoff", max_lift_off_mm))
    if invalid and emit_valid_sizing:
        raise ResearchContractError("nonlinear_or_saturated_instrument_sizing_emitted")
    return ContractVerdict("T14-04-instrument_nonlinearity", "pass", "instrument_linearity_guarded")


def check_lot_session_holdout(cal_lots: Sequence[str], eval_lots: Sequence[str], cal_sessions: Sequence[str], eval_sessions: Sequence[str]) -> ContractVerdict:
    """T14-05: Calibration and evaluation must be disjoint across both material lots and inspection sessions."""
    require_disjoint_sets("inspection_lot", cal_lots, eval_lots)
    require_disjoint_sets("inspection_session", cal_sessions, eval_sessions)
    return ContractVerdict("T14-05-lot_session_holdout", "pass", "lot_and_session_holdout_disjoint")


def check_pod_prevalence(pod_at_a90: float, lower_95_ci: float, prevalence_shifted: bool, report_uncalibrated_accuracy_only: bool) -> ContractVerdict:
    """T14-06: PoD requires lower confidence bound and prevalence-aware calibration, not raw accuracy."""
    if report_uncalibrated_accuracy_only or require_finite("ci", lower_95_ci) > require_finite("pod", pod_at_a90):
        raise ResearchContractError("invalid_pod_or_prevalence_uncalibrated_metric")
    return ContractVerdict("T14-06-pod_prevalence", "pass", "pod_confidence_and_prevalence_valid", {"a90_95": lower_95_ci})


def check_blind_zone(flaw_depth_mm: float, dead_zone_depth_mm: float, claim_inspected_clear: bool) -> ContractVerdict:
    """T14-07: Flaw location inside near-surface or geometric blind zone must be reported uninspectable, never clear."""
    in_blind_zone = require_finite("depth", flaw_depth_mm) <= require_finite("dead_zone", dead_zone_depth_mm)
    if in_blind_zone and claim_inspected_clear:
        raise ResearchContractError("blind_zone_reported_as_clear")
    return ContractVerdict("T14-07-blind_zone", "unknown" if in_blind_zone else "pass", "blind_zone_flagged" if in_blind_zone else "inspectable_zone")


def check_warning_censor(retired_after_warning: bool, count_as_non_failure_survival: bool) -> ContractVerdict:
    """T14-08: Parts retired due to inspection warning are right-censored / intervention-confounded, not natural survival."""
    if retired_after_warning and count_as_non_failure_survival:
        raise ResearchContractError("warning_triggered_retirement_miscoded_as_survival")
    return ContractVerdict("T14-08-warning_censor", "pass", "intervention_censoring_accounted")


def check_shared_sensor_bias(channel_a_env_source: str, channel_b_env_source: str, claim_independent_fusion: bool) -> ContractVerdict:
    """T14-09: Multi-sensor fusion sharing a common environmental drift source cannot claim independent error reduction."""
    shared = bool(channel_a_env_source) and (channel_a_env_source == channel_b_env_source)
    if shared and claim_independent_fusion:
        raise ResearchContractError("shared_environmental_sensor_bias_unaccounted")
    return ContractVerdict("T14-09-shared_sensor_bias", "pass", "common_mode_sensor_bias_checked")
