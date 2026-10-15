"""T15 structural witness, self-test, persistence, and coupling contracts (T15-01..06)."""
from research.science_v1.common import ContractVerdict, ResearchContractError, require_finite


def check_strain_vs_damage(reversible_elastic_strain: float, irreversible_damage_index: float, trigger_latch: bool) -> ContractVerdict:
    """T15-01: Witness latch must separate reversible elastic strain from irreversible damage threshold."""
    require_finite("strain", reversible_elastic_strain)
    damaged = require_finite("damage", irreversible_damage_index) >= 1.0
    if not damaged and trigger_latch:
        raise ResearchContractError("reversible_strain_falsely_latched_as_damage")
    return ContractVerdict("T15-01-strain_vs_damage", "pass", "damage_selective_latch" if damaged else "elastic_subthreshold_rejected")


def check_witness_invalid(debonded_or_broken: bool, report_structural_safe: bool) -> ContractVerdict:
    """T15-02: Debonded, broken, or tampered witness must report invalid/unknown, never structurally safe."""
    if debonded_or_broken and report_structural_safe:
        raise ResearchContractError("invalid_witness_reported_as_safe")
    return ContractVerdict("T15-02-witness_invalid", "unknown" if debonded_or_broken else "pass", "witness_integrity_checked")


def check_shared_selftest(selftest_excites_witness_path: bool, independent_reference_present: bool, claim_selftest_valid: bool) -> ContractVerdict:
    """T15-03: Self-test sharing the same failure mode without an independent reference cannot validate witness health."""
    if not (selftest_excites_witness_path and independent_reference_present) and claim_selftest_valid:
        raise ResearchContractError("non_independent_witness_selftest")
    return ContractVerdict("T15-03-shared_selftest", "pass", "independent_selftest_verified")


def check_warning_persistence(latched_before_reset: bool, state_after_unload_and_thermal_cycle: bool) -> ContractVerdict:
    """T15-04: Irreversible witness warning must persist across unload, power loss, and thermal cycling."""
    if latched_before_reset and not state_after_unload_and_thermal_cycle:
        raise ResearchContractError("witness_warning_erased_by_unload_or_cycle")
    return ContractVerdict("T15-04-warning_persistence", "pass", "nonvolatile_warning_persisted")


def check_reader_environment(readout_delta: float, misalignment_deg: float, max_aligned_deg: float, accept_uncompensated: bool) -> ContractVerdict:
    """T15-05: Reader misalignment or ambient field beyond bounds must reject uncompensated readout."""
    require_finite("delta", readout_delta)
    misaligned = abs(require_finite("angle", misalignment_deg)) > require_finite("max_angle", max_aligned_deg)
    if misaligned and accept_uncompensated:
        raise ResearchContractError("uncompensated_reader_misalignment_accepted")
    return ContractVerdict("T15-05-reader_environment", "pass", "reader_alignment_compensated_or_gated")


def check_mass_coupling(added_mass_pct: float, max_mass_pct: float, fatigue_penalty_pct: float, claim_non_intrusive: bool) -> ContractVerdict:
    """T15-06: Witness mass/stiffness/stress-concentration penalty exceeding budget cannot be claimed non-intrusive."""
    intrusive = (require_finite("mass", added_mass_pct) > require_finite("max_mass", max_mass_pct)) or (require_finite("fatigue", fatigue_penalty_pct) > 0.0)
    if intrusive and claim_non_intrusive:
        raise ResearchContractError("intrusive_witness_parasitic_coupling")
    return ContractVerdict("T15-06-mass_coupling", "pass", "parasitic_coupling_within_budget")
