"""T13 surface, film, topological, and hydrogen reservoir contracts (T13-01..07)."""
from typing import Sequence
from research.science_v1.common import ContractVerdict, ResearchContractError, require_disjoint_sets, require_finite


def check_process_vs_film(arms: Sequence[str], attribute_to_film_alone: bool) -> ContractVerdict:
    """T13-01: Thermal-only, gas-only, and full-process arms required to separate film from thermal softening."""
    needed = {"uncoated", "thermal_only", "gas_only", "full_process"}
    separated = needed.issubset(set(arms))
    if attribute_to_film_alone and not separated:
        raise ResearchContractError("film_vs_thermal_process_confounded")
    return ContractVerdict("T13-01-process_vs_film", "pass", "process_and_film_separated" if separated else "attributed_to_process_package")


def check_coupling_null(coupled_error: float, uncoupled_error: float, complexity_penalty: float, claim_coupling_supported: bool) -> ContractVerdict:
    """T13-02: Coupled surface-bulk model must beat uncoupled null beyond complexity penalty."""
    gain = require_finite("uncoupled", uncoupled_error) - require_finite("coupled", coupled_error)
    supported = gain > require_finite("penalty", complexity_penalty)
    if claim_coupling_supported and not supported:
        raise ResearchContractError("surface_bulk_coupling_not_supported_over_null")
    return ContractVerdict("T13-02-coupling_null", "pass", "coupling_supported" if supported else "uncoupled_null_retained", {"gain": gain})


def check_topology_average(mean_matched: bool, topology_differs: bool, holdout_passed: bool, claim_topology_predictive: bool) -> ContractVerdict:
    """T13-03: Topological descriptors must predict response when scalar averages are matched."""
    valid = mean_matched and topology_differs and holdout_passed
    if claim_topology_predictive and not valid:
        raise ResearchContractError("topology_not_separated_from_scalar_average")
    return ContractVerdict("T13-03-topology_average", "pass", "topology_beyond_average_verified" if valid else "average_sufficient")


def check_segmentation_bias( stable_across_thresholds: bool,lot_train: Sequence[str], lot_test: Sequence[str], claim_descriptor_robust: bool) -> ContractVerdict:
    """T13-04: Topological/grain descriptor must be stable across segmentation thresholds and disjoint lots."""
    require_disjoint_sets("segmentation_lot", lot_train, lot_test)
    if claim_descriptor_robust and not stable_across_thresholds:
        raise ResearchContractError("descriptor_sensitive_to_segmentation_threshold")
    return ContractVerdict("T13-04-segmentation_bias", "pass", "segmentation_invariant" if stable_across_thresholds else "threshold_sensitive")


def check_balance_reservoir(uptake: float, mobile: float, Reversible: float, deep_trap: float, residual: float, tol: float) -> ContractVerdict:
    """T13-05: Hydrogen/species mass balance across uptake, mobile, reversible, and deep traps must close within tolerance."""
    lhs = require_finite("uptake", uptake)
    rhs = (
        require_finite("mobile", mobile)
        + require_finite("reversible", Reversible)
        + require_finite("deep_trap", deep_trap)
        + require_finite("residual", residual)
    )
    imbalance = abs(lhs - rhs)
    if imbalance > require_finite("tol", tol):
        raise ResearchContractError("reservoir_mass_balance_violation")
    return ContractVerdict("T13-05-balance_reservoir", "pass", "reservoir_balance_closed", {"imbalance": imbalance})


def check_charge_not_loss(charged_ppm: float, mechanical_loss_pct: float, loss_threshold_pct: float, claim_embrittlement_reversed_without_mech_test: bool) -> ContractVerdict:
    """T13-06: High uptake without mechanical loss or desorption without mechanical test cannot be mislabeled."""
    if claim_embrittlement_reversed_without_mech_test:
        raise ResearchContractError("desorption_without_mechanical_recovery_test")
    embrittled = require_finite("loss", mechanical_loss_pct) >= require_finite("thresh", loss_threshold_pct)
    finding = "embrittlement_observed" if embrittled else "benign_trapping_no_mechanical_loss"
    return ContractVerdict("T13-06-charge_not_loss", "pass", finding, {"charged_ppm": charged_ppm})


def check_barrier_vs_structure(permeation_reduced: bool, microstructural_damage_present: bool, claim_net_protective_coating: bool) -> ContractVerdict:
    """T13-07: Permeation barrier that degrades underlying structure cannot be claimed net-protective."""
    if microstructural_damage_present and claim_net_protective_coating:
        raise ResearchContractError("barrier_with_structural_degradation_not_protective")
    return ContractVerdict(
        "T13-07-barrier_vs_structure",
        "pass",
        "net_protective_barrier" if (permeation_reduced and not microstructural_damage_present) else "barrier_tradeoff_flagged",
    )
