"""T17 atomistic/MLIP domain validity, transition barrier, ensemble bias, and timescale contracts (T17-01..06)."""
from typing import Sequence
from research.science_v1.common import ContractVerdict, ResearchContractError, require_disjoint_sets, require_finite


def check_model_domain(defect_motif_in_training_domain: bool, uncertainty_metric: float, max_uncertainty: float, accept_prediction: bool) -> ContractVerdict:
    """T17-01: Out-of-domain defect motif or high epistemic uncertainty must reject atomistic prediction."""
    in_domain = defect_motif_in_training_domain and (require_finite("unc", uncertainty_metric) <= require_finite("max_unc", max_uncertainty))
    if not in_domain and accept_prediction:
        raise ResearchContractError("out_of_domain_atomistic_extrapolation")
    return ContractVerdict("T17-01-model_domain", "pass" if in_domain else "unknown", "domain_gate_enforced")


def check_transition_error(equilibrium_mae_mev: float, saddle_barrier_error_mev: float, max_barrier_error_mev: float, claim_kinetics_accurate: bool) -> ContractVerdict:
    """T17-02: Low equilibrium energy error cannot certify kinetics when saddle/transition barrier error is high."""
    require_finite("eq_mae", equilibrium_mae_mev)
    accurate = require_finite("barrier_err", saddle_barrier_error_mev) <= require_finite("max_err", max_barrier_error_mev)
    if claim_kinetics_accurate and not accurate:
        raise ResearchContractError("high_saddle_barrier_error_masked_by_equilibrium_mae")
    return ContractVerdict("T17-02-transition_error", "pass", "transition_state_barrier_verified")


def check_ensemble_shared_bias(dft_functional_family_count: int, dft_reference_offset_mev: float, tol_mev: float, claim_true_error_bounded_by_spread: bool) -> ContractVerdict:
    """T17-03: Committee spread of MLIPs trained on the same biased DFT functional does not bound true physical error."""
    biased = (dft_functional_family_count <= 1) and (abs(require_finite("offset", dft_reference_offset_mev)) > require_finite("tol", tol_mev))
    if biased and claim_true_error_bounded_by_spread:
        raise ResearchContractError("shared_dft_systematic_bias_ignored_by_ensemble_spread")
    return ContractVerdict("T17-03-ensemble_shared_bias", "pass", "systematic_reference_bias_accounted")


def check_rate_sensitivity(md_strain_rate_s_inv: float, lab_strain_rate_s_inv: float, rate_sensitivity_exponent: float, claim_direct_rate_equivalence: bool) -> ContractVerdict:
    """T17-04: High-strain-rate MD mechanism cannot be equated directly to quasi-static lab rate when rate-sensitive."""
    ratio = require_finite("md_rate", md_strain_rate_s_inv) / max(require_finite("lab_rate", lab_strain_rate_s_inv), 1e-30)
    if ratio > 1e3 and require_finite("m", rate_sensitivity_exponent) > 0.01 and claim_direct_rate_equivalence:
        raise ResearchContractError("unbridged_strain_rate_gap_in_atomistic_claim")
    return ContractVerdict("T17-04-rate_sensitivity", "pass", "strain_rate_scaling_qualified")


def check_time_bridge(harmonic_tst_valid: bool, anharmonic_or_correlated_events: bool, claim_long_time_kinetics_certified: bool) -> ContractVerdict:
    """T17-05: Timescale bridge assuming uncorrelated harmonic TST must fail closed under anharmonic/correlated events."""
    if (not harmonic_tst_valid or anharmonic_or_correlated_events) and claim_long_time_kinetics_certified:
        raise ResearchContractError("invalid_harmonic_tst_timescale_bridge")
    return ContractVerdict("T17-05-time_bridge", "pass", "timescale_bridge_assumptions_verified")


def check_holdout_reference(train_structures: Sequence[str], holdout_defect_paths: Sequence[str]) -> ContractVerdict:
    """T17-06: Ab-initio benchmark validation must use held-out defect reaction pathways disjoint from training structures."""
    require_disjoint_sets("atomistic_holdout", train_structures, holdout_defect_paths)
    return ContractVerdict("T17-06-holdout_reference", "pass", "ab_initio_pathway_holdout_disjoint")
