"""T09 internal state sufficiency and irreversibility contracts (T09-01..06)."""
from typing import Dict, List, Sequence
from research.science_v1.common import ContractVerdict, ResearchContractError, require_disjoint_sets, require_finite


def check_latent_collision(
    summaries: Sequence[float],
    branch_labels: Sequence[str],
    heldout_futures: Sequence[float],
    min_branch_gap: float = 0.5,
) -> ContractVerdict:
    """T09-01: Identical summaries with divergent heldout futures detect omitted latent state."""
    if len(summaries) != len(branch_labels) or len(summaries) != len(heldout_futures) or len(summaries) < 2:
        raise ResearchContractError("invalid_latent_collision_inputs")
    if max(summaries) - min(summaries) > 1e-9:
        raise ResearchContractError("summaries_not_matched")
    by_branch: Dict[str, List[float]] = {}
    for b, f in zip(branch_labels, heldout_futures):
        by_branch.setdefault(b, []).append(require_finite("future", f))
    if len(by_branch) < 2:
        raise ResearchContractError("single_branch_cannot_test_collision")
    means = [sum(v) / len(v) for v in by_branch.values()]
    gap = max(means) - min(means)
    if gap < min_branch_gap:
        raise ResearchContractError("omitted_state_not_detected")
    return ContractVerdict("T09-01-latent_collision", "pass", "omitted_latent_state_detected", {"branch_gap": gap})


def check_sufficient_null(branch_a: Sequence[float], branch_b: Sequence[float], threshold: float, claim_hidden_state: bool) -> ContractVerdict:
    """T09-02: When summary is sufficient and future gap is within noise, reject forced hidden-state discovery."""
    ma = sum(branch_a) / len(branch_a)
    mb = sum(branch_b) / len(branch_b)
    gap = abs(ma - mb)
    if gap <= threshold and claim_hidden_state:
        raise ResearchContractError("forced_hidden_state_discovery_on_null")
    return ContractVerdict("T09-02-sufficient_null", "pass", "scoped_null_accepted", {"gap": gap, "threshold": threshold})


def check_matching_bias(matched_after_outcome: bool, survivor_filtered: bool) -> ContractVerdict:
    """T09-03: Post-history matching or survivor filtering chosen after outcomes is rejected."""
    if matched_after_outcome or survivor_filtered:
        raise ResearchContractError("post_outcome_matching_or_survivor_bias_confounded")
    return ContractVerdict("T09-03-matching_bias", "pass", "pre_outcome_protocol_valid")


def check_early_irreversible(residual_plastic_strain: float, noise_floor: float, claim_crack_or_lifetime: bool) -> ContractVerdict:
    """T09-04: Measured early slip/irreversibility is kept distinct from crack initiation or lifetime claims."""
    eps_p = require_finite("residual_plastic_strain", residual_plastic_strain)
    floor = require_finite("noise_floor", noise_floor)
    if claim_crack_or_lifetime:
        raise ResearchContractError("early_slip_cannot_claim_crack_or_service_lifetime")
    finding = "early_irreversible_slip_detected" if eps_p > floor else "reversible_within_noise"
    return ContractVerdict("T09-04-early_irreversible", "pass", finding, {"residual_plastic_strain": eps_p})


def check_lot_confirmation(pilot_lots: Sequence[str], confirm_lots: Sequence[str], grains_counted_as_lots: bool) -> ContractVerdict:
    """T09-05: Pilot calibration lots cannot be reused in confirmatory holdout; grains are not independent lots."""
    if grains_counted_as_lots:
        raise ResearchContractError("grains_counted_as_independent_lots")
    require_disjoint_sets("pilot_confirm_lot", pilot_lots, confirm_lots)
    return ContractVerdict("T09-05-lot_confirmation", "pass", "disjoint_lot_holdout_verified", {"n_confirm_lots": len(set(confirm_lots))})


def check_low_power_null(n_specimens: int, ci_half_width: float, max_equiv_bound: float, claim_universal_sufficiency: bool) -> ContractVerdict:
    """T09-06: Few independent specimens with wide CI must report inconclusive, never universal sufficiency."""
    if (n_specimens < 5 or ci_half_width > max_equiv_bound) and claim_universal_sufficiency:
        raise ResearchContractError("underpowered_study_cannot_claim_universal_sufficiency")
    status = "inconclusive" if (n_specimens < 5 or ci_half_width > max_equiv_bound) else "pass"
    return ContractVerdict("T09-06-low_power_null", status, "inconclusive_wide_interval", {"n_specimens": n_specimens, "ci_half_width": ci_half_width})
