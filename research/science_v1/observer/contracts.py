"""T12 observer perturbation, instrument drift, and preparation transfer contracts (T12-01..05)."""
from typing import Sequence
from research.science_v1.common import ContractVerdict, ResearchContractError, require_finite


def check_observation_arms(arms: Sequence[str], handling_matched: bool, claim_zero_observer_effect: bool) -> ContractVerdict:
    """T12-01: Frequent, sparse, endpoint-only, prep, and sham arms required to identify observer effect."""
    needed = {"frequent", "sparse", "endpoint_only", "prep", "sham"}
    complete = needed.issubset(set(arms)) and handling_matched
    if claim_zero_observer_effect and not complete:
        raise ResearchContractError("observer_schedule_or_prep_unidentifiable")
    return ContractVerdict("T12-01-observation_arms", "pass", "observer_arms_identifiable" if complete else "causal_claim_incomplete")


def check_created_erased(endpoint_only_mean: float, frequent_beam_mean: float, claim_universal_artifact_or_real: str) -> ContractVerdict:
    """T12-02: Distinguish scoped observer-induced creation/erasure without universalizing."""
    delta = require_finite("frequent", frequent_beam_mean) - require_finite("endpoint", endpoint_only_mean)
    if claim_universal_artifact_or_real == "universal":
        raise ResearchContractError("universal_observer_label_rejected")
    finding = "observer_perturbed_signal" if abs(delta) > 0.1 else "observer_neutral_within_scope"
    return ContractVerdict("T12-02-created_erased", "pass", finding, {"delta": delta})


def check_drift_only(raw_signal_shift: float, reference_channel_shift: float, tol: float, diagnose_damage: bool) -> ContractVerdict:
    """T12-03: Nuisance instrument drift tracked by reference channel is not diagnosed as material damage."""
    corrected = abs(require_finite("raw", raw_signal_shift) - require_finite("ref", reference_channel_shift))
    if corrected <= tol and diagnose_damage:
        raise ResearchContractError("instrument_drift_misdiagnosed_as_damage")
    return ContractVerdict("T12-03-drift_only", "pass", "drift_compensated_no_damage", {"corrected_shift": corrected})


def check_true_nuisance(signal_shift: float, nuisance_value: float, validated_max_nuisance: float, claim_definitive_status: bool) -> ContractVerdict:
    """T12-04: True change detected inside validated nuisance bounds; outside bounds is unknown."""
    in_bounds = abs(require_finite("nuisance", nuisance_value)) <= require_finite("max_nuisance", validated_max_nuisance)
    if not in_bounds and claim_definitive_status:
        raise ResearchContractError("out_of_range_nuisance_must_be_unknown")
    return ContractVerdict(
        "T12-04-true_nuisance",
        "pass" if in_bounds else "unknown",
        "detected_in_scope" if in_bounds else "outside_validated_nuisance_range",
        {"signal_shift": signal_shift},
    )


def check_prep_transfer(source_alloy: str, target_alloy: str, target_qualified: bool) -> ContractVerdict:
    """T12-05: Material-specific surface/section preparation study cannot transfer across alloys without qualification."""
    if source_alloy != target_alloy and not target_qualified:
        raise ResearchContractError("unqualified_prep_alloy_transfer_rejected")
    return ContractVerdict("T12-05-prep_transfer", "pass", "prep_scope_valid")
