"""T10 grain/local neighborhood topology and chemical organization contracts (T10-01..05)."""
from typing import Sequence, Tuple
from research.science_v1.common import ContractVerdict, ResearchContractError


def check_same_marginals_graph(
    node_values: Sequence[int],
    edges_a: Sequence[Tuple[int, int]],
    edges_b: Sequence[Tuple[int, int]],
    histogram_only: bool = False,
) -> ContractVerdict:
    """T10-01: Graphs with identical node-value & degree marginals but different assortativity/connectivity are distinguished."""
    if histogram_only:
        raise ResearchContractError("histogram_baseline_misses_graph_connectivity")
    deg_a = [0] * len(node_values)
    deg_b = [0] * len(node_values)
    for u, v in edges_a:
        deg_a[u] += 1
        deg_a[v] += 1
    for u, v in edges_b:
        deg_b[u] += 1
        deg_b[v] += 1
    if sorted(deg_a) != sorted(deg_b):
        raise ResearchContractError("degree_marginals_differ")
    same_type_a = sum(1 for u, v in edges_a if node_values[u] == node_values[v])
    same_type_b = sum(1 for u, v in edges_b if node_values[u] == node_values[v])
    if same_type_a == same_type_b:
        raise ResearchContractError("topology_contrast_failed")
    return ContractVerdict(
        "T10-01-same_marginals_graph",
        "pass",
        "topology_contrast_distinguished",
        {"homophily_a": same_type_a, "homophily_b": same_type_b},
    )


def check_physical_rotation(edge_lengths_orig: Sequence[float], edge_lengths_rot: Sequence[float], frame_dependent_feature_used: bool) -> ContractVerdict:
    """T10-02: Physically rotated graph produces invariant relational features; raw coordinate frame feature rejected."""
    if frame_dependent_feature_used:
        raise ResearchContractError("non_invariant_coordinate_feature_rejected")
    if len(edge_lengths_orig) != len(edge_lengths_rot) or max(abs(a - b) for a, b in zip(edge_lengths_orig, edge_lengths_rot)) > 1e-9:
        raise ResearchContractError("rotation_invariance_broken")
    return ContractVerdict("T10-02-physical_rotation", "pass", "rotation_invariant_feature_verified")


def check_shuffle_control(orig_degrees: Sequence[int], shuffled_degrees: Sequence[int], claim_manufactured_specimen: bool) -> ContractVerdict:
    """T10-03: Degree-preserving edge shuffle is admitted as an analysis control, never a manufactured specimen."""
    if claim_manufactured_specimen:
        raise ResearchContractError("shuffled_graph_is_not_manufactured_material")
    if list(orig_degrees) != list(shuffled_degrees):
        raise ResearchContractError("shuffle_violated_named_marginals")
    return ContractVerdict("T10-03-shuffle_control", "pass", "marginal_preserving_null_control")


def check_resolution_boundary(interior_grains: int, boundary_truncated_grains: int, drop_boundary_uncertainty: bool) -> ContractVerdict:
    """T10-04: ROI-truncated neighborhoods and registration uncertainty must remain visible."""
    if drop_boundary_uncertainty and boundary_truncated_grains > 0:
        raise ResearchContractError("roi_boundary_truncation_hidden")
    return ContractVerdict(
        "T10-04-resolution_boundary",
        "pass",
        "boundary_uncertainty_retained",
        {"interior_grains": interior_grains, "boundary_truncated_grains": boundary_truncated_grains},
    )


def check_chemistry_organization(bulk_cert_only: bool, direct_sro_measurement: bool, claim_short_range_order: bool) -> ContractVerdict:
    """T10-05: Bulk chemistry certificate alone cannot support local short-range order (SRO) claims."""
    if claim_short_range_order and bulk_cert_only and not direct_sro_measurement:
        raise ResearchContractError("sro_inferred_from_bulk_certificate_alone")
    finding = "measured_local_order" if direct_sro_measurement else "bulk_composition_only_local_order_unknown"
    return ContractVerdict("T10-05-chemistry_organization", "pass", finding)
