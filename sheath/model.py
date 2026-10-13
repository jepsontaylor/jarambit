"""Pure-python analytic retention/draw models (no third-party deps; runs in CI).

Snap/detent axial force follows the Bayer/Covestro snap-fit guide:
    W  = P (mu + tan a)  / (1 - mu tan a)    (insertion, lead angle a)
    W' = P (mu + tan a') / (1 - mu tan a')   (separation, return angle a')
where P is the transverse force needed to deflect the flexing member by the undercut y (P = k_eff * y).
Ref: Covestro (Bayer MaterialScience) "Snap-Fit Joints for Plastics - A Design Guide", mating-force section.
"""
from dataclasses import dataclass, asdict
import math

G0 = 9.80665
SIGMA_PA12_MPA = 48.0    # EOS PA 2200 typical tensile strength (screening only)


def density_t_per_mm3(rho_kg_m3: float) -> float:
    """N-mm-s consistent density (tonne/mm^3). 930 kg/m^3 -> 9.30e-10 t/mm^3 (unit regression, dynamic solvers)."""
    return rho_kg_m3 * 1e-12


def legacy_holder_proxy(wall_mm: float, detent_mm: float, knife_t_mm: float = 6.0):
    """The crates/redteam holder proxy, reproduced UNCHANGED for documentation (never used for v1 scoring):
    F_ins = 6.6 wall^3 detent, F_draw = 0.55 F_ins, window 1.5-45 N, stack knife + 2 wall + 0.4 <= 9 mm.
    Returns (max wall allowed by the 9 mm rule, F_draw at that wall and 1.2 mm detent)."""
    wmax = (9.0 - 0.4 - knife_t_mm) / 2.0
    return wmax, 0.55 * 6.6 * min(wall_mm, wmax) ** 3 * detent_mm


def energy_proxy_tab_k(E_mpa: float, b: float, t: float, L: float) -> float:
    """Per-tab stiffness k = E b t^3 / (4 L^3) (== 3EI/L^3). +-10% thickness -> 0.729x..1.331x stiffness."""
    return E_mpa * b * t ** 3 / (4.0 * L ** 3)


@dataclass(frozen=True)
class Material:
    name: str
    E_mpa: float          # flexural/tensile modulus at 23 C
    rho_g_cm3: float
    mu_steel: float       # dry friction vs Ti/steel (guide value)
    eps_allow: float      # permissible short-term strain for repeated snap (guide value, assumption)
    E_temp: tuple         # (E(-20C)/E23, E(+60C)/E23) multipliers  [ASSUMPTION until DMA data]
    source: str


# Typical values. All marked as datasheet/guide values, not design allowables.
MATERIALS = {
    "PA12_MJF": Material("PA12_MJF", 1800.0, 1.01, 0.30, 0.04, (1.25, 0.70),
                         "HP 3D HP PA12 datasheet (tensile modulus ~1800 MPa, part density 1.01 g/cm3); mu: Covestro snap-fit guide Table 3 PA 0.25-0.30 (x1.5 vs self)"),
    "PA12_SLS": Material("PA12_SLS", 1650.0, 0.93, 0.30, 0.04, (1.25, 0.70),
                         "EOS PA 2200 typical: 930 kg/m3, tensile modulus 1650 MPa, tensile strength 48 MPa, elongation at break 18%. "
                         "18% is a single-pull break value, NOT a fatigue/repeated-snap strain limit; eps_allow here is a design ASSUMPTION"),
    "KYDEX100": Material("KYDEX100", 2340.0, 1.35, 0.40, 0.03, (1.15, 0.80),
                         "SEKISUI KYDEX 100 technical data (specific gravity 1.35; flexural modulus ~2.3 GPa - verify); mu assumption"),
}


def snap_axial(P_n: float, mu: float, angle_deg: float) -> float:
    """Axial force to ride over a ramp of the given angle with transverse force P (Bayer eq.). 90 deg -> locking (inf)."""
    t = math.tan(math.radians(angle_deg))
    den = 1.0 - mu * t
    if den <= 1e-9:
        return math.inf   # self-locking: friction angle + ramp angle >= 90 deg
    return P_n * (mu + t) / den


def cantilever_k(E_mpa: float, b_mm: float, h_mm: float, L_mm: float) -> float:
    """Tip stiffness of a rectangular cantilever, N/mm: 3EI/L^3."""
    return 3.0 * E_mpa * (b_mm * h_mm ** 3 / 12.0) / L_mm ** 3


def clamped_circ_plate_k(E_mpa: float, h_mm: float, a_mm: float, nu: float = 0.38) -> float:
    """Centre-load stiffness of a clamped circular plate (Roark/Timoshenko): w = P a^2 / (16 pi D)."""
    D = E_mpa * h_mm ** 3 / (12.0 * (1 - nu ** 2))
    return 16.0 * math.pi * D / a_mm ** 2


def tab_k(E_mpa: float, b_mm: float, h_mm: float, L_mm: float, nu: float = 0.38, plate: bool = True) -> float:
    """Click-tab (U-slot cantilever cut in the side panel) tip stiffness; plate=True uses D = E/(1-nu^2) (wide tab)."""
    return cantilever_k(E_mpa / (1 - nu ** 2) if plate else E_mpa, b_mm, h_mm, L_mm)


def tab_strain(h_mm: float, L_mm: float, y_mm: float) -> float:
    """Root strain of a uniform cantilever at tip deflection y: eps = 1.5 h y / L^2 (Covestro guide Table 1, type 1)."""
    return 1.5 * h_mm * y_mm / L_mm ** 2


def series(*k):
    return 1.0 / sum(1.0 / x for x in k)


@dataclass
class DetentResult:
    k_eff_n_mm: float
    P_n: float
    insert_n: float
    draw_n: float
    strain_est: float


def detent_forces(k_eff: float, undercut_mm: float, mu: float, a_in_deg: float, a_out_deg: float,
                  preload_friction_n: float = 0.0, strain_per_mm: float = 0.0) -> DetentResult:
    P = k_eff * undercut_mm
    return DetentResult(k_eff, P,
                        snap_axial(P, mu, a_in_deg) + preload_friction_n,
                        snap_axial(P, mu, a_out_deg) + preload_friction_n,
                        strain_per_mm * undercut_mm)


# ---------------------------------------------------------------- target window (see plan §5)
@dataclass(frozen=True)
class DrawWindow:
    lo_new: float = 28.0      # N, new sheath, 23 C, dry  (v1.1, plan §5)
    target: float = 35.0
    hi_new: float = 45.0
    lo_life: float = 20.0     # N, any conditioned state (-10..+50 C, wet/grit, 5000 cycles, 168 h 50 C dwell)
    hi_life: float = 55.0
    insert_max: float = 50.0


WINDOW = DrawWindow()


def window_score(f: float, w: DrawWindow = WINDOW) -> float:
    """Two-sided desirability in [0,1]: 1 at target, linear to 0.5 at the new-sheath limits, 0 at life limits."""
    if not math.isfinite(f):
        return 0.0
    if f <= w.lo_life or f >= w.hi_life:
        return 0.0
    if f < w.target:
        return 0.5 + 0.5 * (f - w.lo_new) / (w.target - w.lo_new) if f >= w.lo_new else 0.5 * (f - w.lo_life) / (w.lo_new - w.lo_life)
    return 0.5 + 0.5 * (w.hi_new - f) / (w.hi_new - w.target) if f <= w.hi_new else 0.5 * (w.hi_life - f) / (w.hi_life - w.hi_new)


def inertial_sf(draw_n: float, knife_g: float, accel_g: float) -> float:
    """Quasi-static unseat safety factor along the draw axis (detent fn >> excitation)."""
    return draw_n / (knife_g * 1e-3 * G0 * accel_g)


# Load cases for retention (plan §5.2). accel in g along the draw axis.
RETENTION_CASES = {
    "inverted_static": 1.0,
    "running_sacral_peak": 5.13,   # elite female runners 14 km/h, sacral S2 peak 5.13 g (MSSE abstract 10.1249/01.mss.0001057684.78716.32)
    "fall_waist_peak": 4.5,        # waist IMU, forward fall 4.5+-0.5 g (backward 4.1, side 4.4), Lee et al. PMC4101685 (mattress)
    "jump_waist_peak": 7.5,        # same study, jumping ADL 7.5 g
    "design_shock": 15.0,          # = 2 x jump (hard ground, trail drop-offs): ASSUMPTION closed by M6 sheath IMU
}
# Upper side (one-handed draw through the ring): index fingertip on a thin ring 59.5 +- 21.4 N (females, MVC;
# Int. J. Ind. Ergon. 2010, doi S0169814110001137) -> 5th pct ~24 N; index proximal phalanx flexion 110.7 +- 9.0 N
# (Clin. Biomech., "Multi-directional strength and force envelope of the index finger", S0268-0033(03)00178-5).


def catch_profiles():
    """Snap-only vs snap+positive-catch, ranked on one-handed emergency draw time (plan §5.6).
    Time deltas from duty-holster studies: Level II (one extra release) 1.84 s vs Level I 1.71 s draw-and-fire (+0.13 s,
    HPTC 2018); open-top ~1.49 s; combined (integrated) release motions make the cost negligible (Lewinski et al. 2015)."""
    return [
        {"id": "pull_only", "locked_proof_n": None, "draw_n": "28-45", "snag_protection_n": "= draw (~35)", "extra_action": 0,
         "draw_time_penalty_s": 0.0, "notes": "fastest; snag along draw path >~45 N releases"},
        {"id": "snap+ring_actuated_catch", "locked_proof_n": 150, "draw_n": "15-35 after unlock", "snag_protection_n": 150,
         "extra_action": "integrated (finger entering ring depresses catch tongue)", "draw_time_penalty_s": "~0-0.05 (ASSUMPTION; Lewinski integrated release)",
         "notes": "recommended once M5 confirms time penalty; adds ~2-3 g"},
        {"id": "snap+thumb_break_catch", "locked_proof_n": 150, "draw_n": "15-35 after unlock", "snag_protection_n": 150,
         "extra_action": 1, "draw_time_penalty_s": 0.13, "notes": "separate thumb action (Level-II-like)"},
    ]


def fitness(m: dict, w: DrawWindow = WINDOW) -> dict:
    """Feasible-first, then minimise mass (+ cost proxy). No weighted compensation: a failed containment / strength /
    retention gate can never be bought back by low mass. score in (0,1] only when every hard gate passes."""
    gates = []
    if m.get("path_feasible") is not True: gates.append("path_infeasible")
    if m.get("uncovered_sharp_mm", 0) > 0.0: gates.append("sharp_edge_outside_sheath")
    if m.get("edge_mouth_depth_mm", 99) < 6.0: gates.append("edge_mouth_depth<6mm")
    if m.get("min_edge_clearance_mm", -1) < 0.3: gates.append("edge_clearance<0.3mm")
    if m.get("rim_min_mm", 0) < 2.0: gates.append("edge_rim<2mm")
    if m.get("tip_reserve_mm", 99) < 1.0: gates.append("tip_reserve<1mm")
    if m.get("insert_n", math.inf) > w.insert_max: gates.append("insert>max")
    if m.get("strain_est", 1) > m.get("eps_allow", 0.04): gates.append("detent_strain>allow")
    if m.get("p_in_life_window", 0) < 0.95: gates.append("MC_life_window<95%")
    if m.get("p_in_new_window", 0) < 0.80: gates.append("MC_new_window<80%")
    for k in m.get("strength_fail", []): gates.append("strength:" + k)
    mass = m.get("mass_g", 1e9)
    score = 1.0 / (1.0 + mass / 30.0 + m.get("cost_proxy", 0.0))
    return {"feasible": not gates, "score": score if not gates else 0.0, "gates": gates, "mass_g": mass,
            "s_draw": window_score(m.get("draw_n", math.nan), w)}
