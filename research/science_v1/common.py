"""Shared typed contracts and claim-limit guards for Science v1 (T08..T18)."""
from dataclasses import dataclass, field
import math
from typing import Any, Dict, Sequence


CLAIM_LIMIT = "No new physical validation from synthetic or metadata-only execution"


class ResearchContractError(ValueError):
    """Raised when a scientific protocol, scope, holdout, or physical boundary is violated."""


@dataclass(frozen=True)
class ContractVerdict:
    case_id: str
    status: str
    finding: str
    detail: Dict[str, Any] = field(default_factory=dict)
    claim_limit: str = CLAIM_LIMIT

    def __post_init__(self) -> None:
        if self.claim_limit != CLAIM_LIMIT:
            raise ResearchContractError("claim_limit_tampered")
        if self.status not in ("pass", "unknown", "inconclusive"):
            raise ResearchContractError(f"invalid_verdict_status:{self.status}")


def require_finite(name: str, value: float) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(float(value)):
        raise ResearchContractError(f"nonfinite_{name}")
    return float(value)


def require_disjoint_sets(name: str, a: Sequence[Any], b: Sequence[Any]) -> None:
    overlap = set(a) & set(b)
    if overlap:
        raise ResearchContractError(f"{name}_leakage:{sorted(overlap)}")
