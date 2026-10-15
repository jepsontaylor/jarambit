"""T11 path/history dependence, dual clocks, and competing risks contracts (T11-01..07)."""
from typing import Dict, Sequence
from research.science_v1.common import ContractVerdict, ResearchContractError, require_finite


def check_sequence_controls(arms_present: Sequence[str], clocks_matched: bool, intermediate_observed: bool) -> ContractVerdict:
    """T11-01: A->B, B->A, A, B, unexposed, sham with matched total clocks and intermediate observations."""
    required = {"A_then_B", "B_then_A", "A_only", "B_only", "unexposed", "sham"}
    if not required.issubset(set(arms_present)) or not clocks_matched or not intermediate_observed:
        raise ResearchContractError("incomplete_sequence_control_design")
    return ContractVerdict("T11-01-sequence_controls", "pass", "sequence_order_isolated")


def check_order_null(ab_outcomes: Sequence[float], ba_outcomes: Sequence[float], tol: float, force_history_term: bool) -> ContractVerdict:
    """T11-02: Additive order-independent outcomes accept the null without forcing an interaction term."""
    diff = abs(sum(ab_outcomes) / len(ab_outcomes) - sum(ba_outcomes) / len(ba_outcomes))
    if diff <= tol and force_history_term:
        raise ResearchContractError("forced_history_interaction_on_commutative_null")
    return ContractVerdict("T11-02-order_null", "pass", "commutative_null_accepted", {"order_diff": diff})


def check_order_positive(ab_outcomes: Sequence[float], ba_outcomes: Sequence[float], min_effect: float, preregistered: bool) -> ContractVerdict:
    """T11-03: Non-commutative state transition detects order effect under preregistered analysis."""
    if not preregistered:
        raise ResearchContractError("post_hoc_order_claim_rejected")
    diff = abs(sum(ab_outcomes) / len(ab_outcomes) - sum(ba_outcomes) / len(ba_outcomes))
    if diff < min_effect:
        raise ResearchContractError("order_effect_below_preregistered_threshold")
    return ContractVerdict("T11-03-order_positive", "pass", "noncommutative_order_effect_detected", {"order_diff": diff})


def check_cycle_time_clock(cycles_equal: bool, elapsed_time_equal: bool, temp_rise_equal: bool, claim_pure_cycle_effect: bool) -> ContractVerdict:
    """T11-04: Equal cycles with unequal time/heating cannot claim pure cycle-count causality."""
    if claim_pure_cycle_effect and (not elapsed_time_equal or not temp_rise_equal):
        raise ResearchContractError("cycle_time_thermal_clock_confounded")
    return ContractVerdict("T11-04-cycle_time_clock", "pass", "dual_clock_control_verified")


def check_hold_redistribution(local_relaxation_observed: bool, assume_local_state_frozen: bool) -> ContractVerdict:
    """T11-05: Unobserved local state during external hold cannot be assumed invariant."""
    if not local_relaxation_observed and assume_local_state_frozen:
        raise ResearchContractError("unobserved_hold_assumed_invariant")
    finding = "local_relaxation_measured" if local_relaxation_observed else "local_hold_evolution_unknown"
    return ContractVerdict("T11-05-hold_redistribution", "pass", finding)


def check_acceleration_mode(service_mode: str, accelerated_mode: str, claim_service_years: bool) -> ContractVerdict:
    """T11-06: Accelerated condition that switches failure mechanism cannot claim service-year equivalence."""
    if service_mode != accelerated_mode and claim_service_years:
        raise ResearchContractError("accelerated_mechanism_shift_nontransferable")
    return ContractVerdict("T11-06-acceleration_mode", "pass", "mechanism_preserved" if service_mode == accelerated_mode else "nontransferable_mode_shift_flagged")


def check_competing_censor(mode_counts: Dict[str, int], right_censored: int, interval_censored: int, reported_total: int) -> ContractVerdict:
    """T11-07: Multiple failure modes and censored units retain full denominator and mode-specific counts."""
    full_n = sum(mode_counts.values()) + right_censored + interval_censored
    if reported_total != full_n or right_censored < 0 or interval_censored < 0:
        raise ResearchContractError("censored_or_competing_units_dropped_from_denominator")
    require_finite("full_n", float(full_n))
    return ContractVerdict("T11-07-competing_censor", "pass", "competing_risks_denominator_retained", {"n_total": full_n})
