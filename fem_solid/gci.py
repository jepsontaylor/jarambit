"""Checked relative GCI arithmetic; three points do not establish asymptotic validity."""
from dataclasses import asdict, dataclass
from enum import Enum
import math
from assurance.testing.contracts import ContractError, digest, finite, unique_ids

METHOD = 'relative_gci.v2'


class FitStatus(str, Enum):
    VALID = 'admissible_estimate'
    INVALID = 'invalid_input'
    UNRESOLVED = 'unresolved'
    PRECISION = 'precision_limited'
    OSCILLATORY = 'oscillatory'
    NONPOSITIVE = 'nonpositive_order'
    UNSUPPORTED = 'unsupported_sequence'


@dataclass(frozen=True)
class MeshRef:
    id: str
    revision: str
    sha256: str


@dataclass(frozen=True)
class Observable:
    id: str
    units: str
    region: str
    projection: str
    metric: str


@dataclass(frozen=True)
class Level:
    mesh: MeshRef
    h: float
    observable: Observable
    refinement: str = 'uniform_h'


@dataclass(frozen=True)
class Estimate:
    fit_status: FitStatus
    reason: str
    p: float | None = None
    f_ext: float | None = None
    gci_fine: float | None = None
    monotone: bool = False
    sequence_valid: bool = False
    observable_valid: bool = False
    method_id: str = METHOD
    asymptotic_validation: str = 'not_established'
    levels: tuple[Level, ...] = ()

    @property
    def relative_error_available(self):
        try:
            p, extrapolated, error = map(finite, (self.p, self.f_ext, self.gci_fine))
            return self.method_id == METHOD and self.fit_status == FitStatus.VALID and self.monotone is True and p > 0 and error >= 0
        except (ContractError, OverflowError):
            return False

    @property
    def admitted(self):
        if not (self.relative_error_available and self.sequence_valid is True and self.observable_valid is True):
            return False
        try: return validate_sequence(self.levels, finite(self.levels[1].h)/finite(self.levels[0].h)) is None
        except (AttributeError, IndexError, TypeError, ContractError, OverflowError, ZeroDivisionError): return False

    def to_dict(self):
        return {**asdict(self), 'fit_status': self.fit_status.value,
                'relative_error_available': self.relative_error_available, 'admitted': self.admitted}


def validate_sequence(levels, r):
    """Only uniform-h is implemented; layer counts do not define an effective r."""
    if type(levels) not in (tuple, list) or len(levels) != 3 or not all(isinstance(x, Level) for x in levels):
        return 'three_ordered_levels_required'
    try:
        if finite(r) <= 1: return 'invalid_refinement_ratio'
        if not all(isinstance(x.mesh, MeshRef) and isinstance(x.observable, Observable) for x in levels):
            return 'invalid_mesh_or_observable'
        unique_ids(x.mesh.id for x in levels)
        for x in levels:
            unique_ids([x.mesh.revision]); digest(x.mesh.sha256)
            for field in asdict(x.observable).values(): unique_ids([field])
        if len({x.mesh.sha256 for x in levels}) != 3: return 'duplicate_mesh_content'
        h = [finite(x.h) for x in levels]
        if not 0 < h[0] < h[1] < h[2]: return 'invalid_level_order'
        if any(x.refinement != 'uniform_h' for x in levels): return 'unsupported_refinement'
        if h[1]/h[0] != r or h[2]/h[1] != r: return 'nonuniform_refinement'
        if any(x.observable != levels[0].observable for x in levels[1:]): return 'observable_mismatch'
    except (ContractError, OverflowError, ZeroDivisionError):
        return 'invalid_mesh_sequence'
    return None


def compute_gci(f1, f2, f3, r, fs=1.25, *, levels=None):
    """f1 finest, f2 middle, f3 coarse. Missing metadata gives arithmetic only, no admission."""
    def result(status, reason, **fields):
        return Estimate(status, reason, sequence_valid=levels is not None,
                        observable_valid=levels is not None, levels=tuple(levels) if levels is not None else (), **fields)
    try:
        f1, f2, f3, r, fs = map(finite, (f1, f2, f3, r, fs))
    except (ContractError, OverflowError):
        return Estimate(FitStatus.INVALID, 'nonfinite_or_invalid_scalar')
    if r <= 1 or fs <= 0: return Estimate(FitStatus.INVALID, 'invalid_ratio_or_safety_factor')
    if levels is not None:
        reason = validate_sequence(levels, r)
        if reason: return Estimate(FitStatus.UNSUPPORTED, reason)
    e21, e32 = f2-f1, f3-f2
    if not math.isfinite(e21) or not math.isfinite(e32):
        return result(FitStatus.INVALID, 'nonfinite_difference')
    if e21 == 0 and e32 == 0: return result(FitStatus.UNRESOLVED, 'all_levels_equal')
    if e21 == 0: return result(FitStatus.UNRESOLVED, 'fine_pair_plateau')
    if e32 == 0: return result(FitStatus.UNRESOLVED, 'coarse_pair_plateau')
    for a, b, difference in [(f1, f2, e21), (f2, f3, e32)]:
        if abs(difference) <= 16*max(math.ulp(a), math.ulp(b)):
            return result(FitStatus.PRECISION, 'pair_at_precision_floor')
    if f1 == 0: return result(FitStatus.UNRESOLVED, 'zero_reference_quantity')
    if (e21 < 0) != (e32 < 0): return result(FitStatus.OSCILLATORY, 'oscillatory_sequence')
    quotient = abs(e32/e21)
    if not math.isfinite(quotient) or quotient == 0:
        return result(FitStatus.INVALID, 'unrepresentable_difference_ratio')
    p = math.log(quotient)/math.log(r)
    if not math.isfinite(p): return result(FitStatus.INVALID, 'nonfinite_observed_order')
    if p <= 0: return result(FitStatus.NONPOSITIVE, 'nonpositive_observed_order', p=p, monotone=True)
    try:
        denominator = math.expm1(p*math.log(r))
        if not math.isfinite(denominator) or denominator <= 0:
            return result(FitStatus.UNRESOLVED, 'invalid_extrapolation_denominator', p=p, monotone=True)
        extrapolated = f1-e21/denominator
        error = fs*abs(e21/f1)/denominator
    except (OverflowError, ZeroDivisionError):
        return result(FitStatus.UNRESOLVED, 'unrepresentable_error_estimate', p=p, monotone=True)
    if not math.isfinite(extrapolated) or not math.isfinite(error) or error < 0:
        return result(FitStatus.UNRESOLVED, 'unrepresentable_error_estimate', p=p, monotone=True)
    if error == 0: return result(FitStatus.PRECISION, 'relative_error_underflow', p=p, monotone=True)
    return result(FitStatus.VALID, 'arithmetic_only' if levels is None else 'checked_relative_estimate',
                  p=p, f_ext=extrapolated, gci_fine=error, monotone=True)


def gci(f1, f2, f3, r, fs=1.25):
    """Versioned historical call adapter; never qualifying unbound scalar triples."""
    return {**compute_gci(f1, f2, f3, r, fs).to_dict(), 'adapter': 'historical_gci_call.v1'}
