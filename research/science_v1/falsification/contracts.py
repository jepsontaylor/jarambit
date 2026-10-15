"""T18 active falsification, non-identifiability, audit independence, budget, and authority boundary contracts (T18-01..07)."""
from typing import Sequence
from research.science_v1.common import ContractVerdict, ResearchContractError, require_disjoint_sets, require_finite


def check_mixed_none_models(candidate_menu: Sequence[str], force_single_winner_when_all_poor: bool) -> ContractVerdict:
    """T18-01: Model selection menu must include mixed-mechanism and none-of-the-above hypotheses."""
    needed = {"mixed_mechanism", "none_of_the_above"}
    has_open_world = needed.issubset(set(candidate_menu))
    if not has_open_world or force_single_winner_when_all_poor:
        raise ResearchContractError("closed_world_forced_winner_rejected")
    return ContractVerdict("T18-01-mixed_none_models", "pass", "mixed_and_none_hypotheses_admitted")


def check_nonidentifiable(fisher_min_eig: float, threshold: float, claim_parameters_identified: bool) -> ContractVerdict:
    """T18-02: Non-identifiable or collinear models under available observables must return inconclusive/unidentified."""
    identifiable = require_finite("eig", fisher_min_eig) >= require_finite("thresh", threshold)
    if not identifiable and claim_parameters_identified:
        raise ResearchContractError("nonidentifiable_model_claimed_unique")
    return ContractVerdict("T18-02-nonidentifiable", "pass" if identifiable else "inconclusive", "identifiability_checked")


def check_audit_independent(active_chosen_pts: Sequence[str], random_audit_pts: Sequence[str], audit_share: float, min_audit_share: float) -> ContractVerdict:
    """T18-03: Active experimental design requires a disjoint random/space-filling audit reserve."""
    require_disjoint_sets("active_vs_audit", active_chosen_pts, random_audit_pts)
    if require_finite("share", audit_share) < require_finite("min_share", min_audit_share):
        raise ResearchContractError("insufficient_independent_audit_allocation")
    return ContractVerdict("T18-03-audit_independent", "pass", "independent_audit_reserve_verified")


def check_budget_menu(planned_cost: float, budget_cap: float, destructive_count: int, max_destructive: int, feasible_setup: bool) -> ContractVerdict:
    """T18-04: Recommended falsification experiments must obey cost, destructive-coupon, and setup feasibility constraints."""
    valid = (
        feasible_setup
        and (require_finite("cost", planned_cost) <= require_finite("cap", budget_cap))
        and (destructive_count <= max_destructive)
    )
    if not valid:
        raise ResearchContractError("infeasible_or_over_budget_experiment_selected")
    return ContractVerdict("T18-04-budget_menu", "pass", "feasible_budget_compliant_plan")


def check_strategy_comparison(active_error: float, baseline_error: float, equal_total_cost: bool, audit_included_in_cost: bool, claim_active_superior: bool) -> ContractVerdict:
    """T18-05: Active learning must be compared against space-filling/random baselines at equal total budget including audit cost."""
    fair = equal_total_cost and audit_included_in_cost
    better = require_finite("active", active_error) < require_finite("base", baseline_error)
    if claim_active_superior and not (fair and better):
        raise ResearchContractError("unfair_or_inferior_active_strategy_claim")
    return ContractVerdict("T18-05-strategy_comparison", "pass", "equal_budget_strategy_comparison_valid")


def check_failed_acquisition(experiment_aborted_or_censored: bool, impute_as_confirming_observation: bool) -> ContractVerdict:
    """T18-06: Failed, aborted, or censored experimental acquisition must be logged as missing/censored, never imputed as confirmation."""
    if experiment_aborted_or_censored and impute_as_confirming_observation:
        raise ResearchContractError("failed_acquisition_imputed_as_confirmation")
    return ContractVerdict("T18-06-failed_acquisition", "pass", "failed_acquisition_recorded_explicitly")


def check_authority_boundary(proposes_destructive_or_safety_action: bool, human_signoff_present: bool, auto_execute: bool) -> ContractVerdict:
    """T18-07: Active planner is advisory only and cannot auto-execute destructive or safety-critical actions without human sign-off."""
    if proposes_destructive_or_safety_action and auto_execute and not human_signoff_present:
        raise ResearchContractError("autonomous_safety_or_destructive_authority_violation")
    return ContractVerdict("T18-07-authority_boundary", "pass", "advisory_authority_boundary_enforced")
