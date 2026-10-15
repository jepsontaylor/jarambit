"""T08 multimodal microstructure registration and bounded ingest contracts."""
import math
from typing import Dict, List, Sequence, Tuple
from research.science_v1.common import ContractVerdict, ResearchContractError, require_finite

MAX_APPROVED_BYTES = 5 * 1024 ** 3  # 5 GiB hard cap


def check_bounded_download(archive_bytes: int, expanded_bytes: int, cap_bytes: int = MAX_APPROVED_BYTES) -> ContractVerdict:
    """T08-01: Archive expanded size/file access must not exceed 5 GB approved cap."""
    if archive_bytes <= 0 or expanded_bytes <= 0 or archive_bytes > cap_bytes or expanded_bytes > cap_bytes:
        raise ResearchContractError("archive_exceeds_5gb_cap_unavailable_full_reproduction")
    return ContractVerdict(
        "T08-01-bounded_download",
        "pass",
        "within_approved_cap",
        {"archive_bytes": archive_bytes, "expanded_bytes": expanded_bytes, "cap_bytes": cap_bytes},
    )


def check_units_metadata(meta: Dict[str, str], expected_doi: str, expected_version: str) -> ContractVerdict:
    """T08-02: Ambiguous units or DOI/version/license mismatch stops physical comparison."""
    units = meta.get("length_unit")
    if units not in ("um", "mm", "nm"):
        raise ResearchContractError("ambiguous_or_missing_units")
    if meta.get("doi") != expected_doi or meta.get("version") != expected_version:
        raise ResearchContractError("doi_or_version_mismatch")
    if not meta.get("license"):
        raise ResearchContractError("missing_license")
    return ContractVerdict("T08-02-units_metadata", "pass", "metadata_resolved", dict(meta))


def check_registration_truth(
    src_pts: Sequence[Tuple[float, float]],
    dst_pts: Sequence[Tuple[float, float]],
    src_grain_ids: Sequence[int],
    dst_grain_ids: Sequence[int],
    tol: float = 1e-6,
) -> ContractVerdict:
    """T08-03: Proper rigid 2D transform accepted; reflection (det < 0) or grain-ID mismatch rejected."""
    if len(src_pts) < 3 or len(src_pts) != len(dst_pts):
        raise ResearchContractError("insufficient_registration_points")
    if list(src_grain_ids) != list(dst_grain_ids):
        raise ResearchContractError("wrong_grain_mapping")
    sx = sum(p[0] for p in src_pts) / len(src_pts)
    sy = sum(p[1] for p in src_pts) / len(src_pts)
    dx = sum(p[0] for p in dst_pts) / len(dst_pts)
    dy = sum(p[1] for p in dst_pts) / len(dst_pts)
    sxx = sum((p[0] - sx) * (q[0] - dx) for p, q in zip(src_pts, dst_pts))
    sxy = sum((p[0] - sx) * (q[1] - dy) for p, q in zip(src_pts, dst_pts))
    syx = sum((p[1] - sy) * (q[0] - dx) for p, q in zip(src_pts, dst_pts))
    syy = sum((p[1] - sy) * (q[1] - dy) for p, q in zip(src_pts, dst_pts))
    det_h = sxx * syy - sxy * syx
    if det_h <= 0.0:
        raise ResearchContractError("mirrored_improper_registration_rejected")
    theta = math.atan2(sxy - syx, sxx + syy)
    c, s = math.cos(theta), math.sin(theta)
    max_err = 0.0
    for (x, y), (qx, qy) in zip(src_pts, dst_pts):
        rx = c * (x - sx) - s * (y - sy) + dx
        ry = s * (x - sx) + c * (y - sy) + dy
        max_err = max(max_err, math.hypot(rx - qx, ry - qy))
    if max_err > tol:
        raise ResearchContractError(f"registration_residual_exceeded:{max_err:.3e}")
    return ContractVerdict("T08-03-registration_truth", "pass", "proper_rigid_transform_verified", {"theta_rad": theta, "max_err": max_err})


def check_orientation_symmetry(angle_a: float, unit_a: str, angle_b: float, unit_b: str, symmetry_fold: int = 6) -> ContractVerdict:
    """T08-04: Hexagonal/cubic symmetry-equivalent orientations accepted; unit convention mismatch rejected."""
    if unit_a != unit_b or unit_a not in ("rad", "deg"):
        raise ResearchContractError("orientation_unit_convention_mismatch")
    a = require_finite("angle_a", angle_a)
    b = require_finite("angle_b", angle_b)
    period = (2.0 * math.pi if unit_a == "rad" else 360.0) / symmetry_fold
    diff = abs((a - b) % period)
    diff = min(diff, abs(period - diff))
    if diff > 1e-6:
        raise ResearchContractError("non_equivalent_orientation")
    return ContractVerdict("T08-04-orientation_symmetry", "pass", "symmetry_equivalent", {"residual": diff})


def check_matched_slip_missing(modalities_present: Sequence[str], claim_full_slip_reproduction: bool) -> ContractVerdict:
    """T08-05: EBSD/DCT subset without matched DIC/slip gives importer-only receipt, never full slip reproduction."""
    has_dic = "DIC" in modalities_present and "slip_bands" in modalities_present
    if claim_full_slip_reproduction and not has_dic:
        raise ResearchContractError("matched_slip_missing_cannot_claim_full_reproduction")
    finding = "full_slip_reproduction" if has_dic else "importer_only_receipt"
    return ContractVerdict("T08-05-matched_slip_missing", "pass", finding, {"modalities": list(modalities_present)})


def check_group_acquisition(specimen_to_grains: Dict[str, List[int]], unobserved_grains: Sequence[int], claim_independent_specimens: int) -> ContractVerdict:
    """T08-06: Repeated acquisitions/unobserved grains from one specimen retain specimen grouping and coverage."""
    actual_specimens = len(specimen_to_grains)
    if claim_independent_specimens != actual_specimens:
        raise ResearchContractError("specimen_count_inflated_by_grain_count")
    observed = sum(len(g) for g in specimen_to_grains.values())
    total = observed + len(unobserved_grains)
    coverage = observed / max(total, 1)
    return ContractVerdict(
        "T08-06-group_acquisition",
        "pass",
        "specimen_grouped_with_coverage",
        {"n_specimens": actual_specimens, "observed_grains": observed, "unobserved_grains": len(unobserved_grains), "coverage": coverage},
    )
