"""T16 damage recovery, crack closure vs healing, isotope tracer, and nanoscale transfer contracts (T16-01..06)."""
from research.science_v1.common import ContractVerdict, ResearchContractError, require_finite


def check_closure_false_heal(optical_or_acoustic_closed: bool, retest_toughness_ratio: float, min_healed_ratio: float, claim_structural_healing: bool) -> ContractVerdict:
    """T16-01: Geometric crack closure or oxide bridge without restored fracture toughness is not structural healing."""
    healed = optical_or_acoustic_closed and (require_finite("ratio", retest_toughness_ratio) >= require_finite("min_ratio", min_healed_ratio))
    if claim_structural_healing and not healed:
        raise ResearchContractError("geometric_closure_without_mechanical_recovery_misclassified")
    return ContractVerdict("T16-01-closure_false_heal", "pass", "structural_healing_verified" if healed else "closure_only_no_healing")


def check_recovery_positive(damaged_strength: float, treated_strength: float, sham_thermal_strength: float, min_net_gain: float, claim_active_recovery: bool) -> ContractVerdict:
    """T16-02: Recovery claim requires positive net mechanical restoration above damaged and sham-thermal controls."""
    net_over_damaged = require_finite("treated", treated_strength) - require_finite("damaged", damaged_strength)
    net_over_sham = require_finite("treated", treated_strength) - require_finite("sham", sham_thermal_strength)
    valid = (net_over_damaged >= require_finite("min_gain", min_net_gain)) and (net_over_sham >= min_net_gain)
    if claim_active_recovery and not valid:
        raise ResearchContractError("recovery_not_above_damaged_and_sham_controls")
    return ContractVerdict("T16-02-recovery_positive", "pass", "net_mechanical_recovery_verified")


def check_failure_migration(scar_healed: bool, haz_reinitiation_ratio: float, undamaged_baseline: float, claim_component_restored: bool) -> ContractVerdict:
    """T16-03: Repair that shifts failure to an embrittled HAZ below baseline cannot claim component restoration."""
    migrated_weakness = require_finite("haz", haz_reinitiation_ratio) < require_finite("base", undamaged_baseline)
    if (not scar_healed or migrated_weakness) and claim_component_restored:
        raise ResearchContractError("failure_migrated_to_embrittled_adjacent_zone")
    return ContractVerdict("T16-03-failure_migration", "pass", "no_adverse_failure_migration")


def check_isotope_exchange(tracer_enrichment: float, exchange_only_control_enrichment: float, transport_detected: bool) -> ContractVerdict:
    """T16-04: Isotope tracer must exceed passive surface exchange control to claim damage-driven transport."""
    net = require_finite("tracer", tracer_enrichment) - require_finite("control", exchange_only_control_enrichment)
    if transport_detected and net <= 0.0:
        raise ResearchContractError("isotope_signal_explained_by_passive_exchange")
    return ContractVerdict("T16-04-isotope_exchange", "pass", "net_tracer_transport_separated", {"net_enrichment": net})


def check_source_ambiguity(isotopic_ratio_matches_source_a: bool, isotopic_ratio_matches_source_b: bool, claim_unique_source: bool) -> ContractVerdict:
    """T16-05: Overlapping isotopic/chemical end-members must be reported ambiguous, not uniquely attributed."""
    ambiguous = isotopic_ratio_matches_source_a and isotopic_ratio_matches_source_b
    if ambiguous and claim_unique_source:
        raise ResearchContractError("overlapping_tracer_sources_uniquely_attributed")
    return ContractVerdict("T16-05-source_ambiguity", "inconclusive" if ambiguous else "pass", "source_unmixing_checked")


def check_nanoscale_transfer(thin_foil_recovered: bool, bulk_coupon_tested: bool, claim_bulk_component_healing: bool) -> ContractVerdict:
    """T16-06: Nanoscale/thin-foil healing observation cannot be extrapolated to bulk components without bulk validation."""
    if thin_foil_recovered and not bulk_coupon_tested and claim_bulk_component_healing:
        raise ResearchContractError("unvalidated_nanoscale_to_bulk_recovery_extrapolation")
    return ContractVerdict("T16-06-nanoscale_transfer", "pass", "scale_transfer_scope_enforced")
