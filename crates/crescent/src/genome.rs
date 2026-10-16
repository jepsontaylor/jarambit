//! Crescent genotype: SWITCHBACK C.4 spline control-point offsets inside an aesthetic envelope,
//! plus a 3-D thickness-field / lattice / medial-axis feature layer. Not a stick figure: the
//! silhouette is ONE C2 spline (tip = only corner) + ring union with tangent neck fillets, and
//! every gene moves a smooth feature of that crescent. Cannot collapse to a stick figure either:
//! offsets are bounded per zone (mm), and the aesthetic floor (Hausdorff / curvature histogram /
//! straight-run vs C.4) rejects anything that drifts out of the C.4 family.
use jarambit_genotype::{q01, Rng, TiGrade};

pub const N_CP: usize = 40;
pub const NG: usize = 128;
/// Pre-P1 genome length (wave7..wave16 lattice layout); rows of this length load with the P1 layer OFF.
pub const NG_P0: usize = 117;
/// Legacy (wave6) genome length; rows of this length load with every internal-machining gene OFF.
pub const NG_LEGACY: usize = 90;
pub const DROP: usize = 40; pub const GRIP_DX: usize = 41; pub const RING_WALL: usize = 42; pub const RING_ID: usize = 43;
pub const NECK_FILLET: usize = 44; pub const T: usize = 45; pub const T_TIP: usize = 46; pub const TAPER_X0: usize = 47;
pub const EA_IN: usize = 48; pub const EA_SP: usize = 49;
pub const COMET_X0: usize = 50; pub const COMET_X1: usize = 51; pub const COMET_W0: usize = 52; pub const COMET_W1: usize = 53;
pub const COMET_BOW: usize = 54; pub const COMET_Y: usize = 55; pub const EYE: usize = 56; pub const CAIRN: usize = 57;
pub const DETENT: usize = 58; pub const WALL: usize = 59; pub const JIMP: usize = 60;
pub const SER_L: usize = 61; pub const SER_S: usize = 62; pub const SER_F: usize = 63; pub const SPINE_OFF: usize = 64;
pub const RELIEF_D: usize = 65; pub const RELIEF_W: usize = 66; pub const RELIEF_Q: usize = 67;
pub const LAT_D: usize = 68; pub const LAT_P: usize = 69; pub const LAT_F: usize = 70; pub const LAT_A: usize = 71;
pub const LAT_H: usize = 72; pub const LAT_B: usize = 73;
pub const FUL_D: usize = 74; pub const FUL_W: usize = 75; pub const FUL_S0: usize = 76; pub const FUL_S1: usize = 77;
pub const FLUTE: usize = 78; pub const TEX_MODE: usize = 79; pub const TEX_D: usize = 80; pub const TEX_P: usize = 81;
pub const TEX_A: usize = 82; pub const WRAP_X0: usize = 83; pub const WRAP_L: usize = 84;
pub const PAD_X: usize = 85; pub const PAD_Y: usize = 86; pub const PAD_W: usize = 87; pub const PAD_L: usize = 88;
/// Thickness left at the edge before the final sharpening (C.4: 0.5 mm). Tip-snap vs cutting knob.
pub const EDGE_TH: usize = 89;
// ---- internal machining layer (wave7+, exec/lattice) ----
/// Two-sided ISOGRID pockets (equilateral-triangle cells, full-thickness ribs, Ø2 mm end-mill corner
/// radius, flat floor clamped to the web floor), depth per side, cell height (pitch), rib width,
/// orientation, rim to outline / holes / grind lines, zone switches and a depth grade along x.
pub const ISO_D: usize = 90; pub const ISO_P: usize = 91; pub const ISO_RIB: usize = 92; pub const ISO_A: usize = 93;
pub const ISO_RIM: usize = 94; pub const ISO_ZB: usize = 95; pub const ISO_ZH: usize = 96; pub const ISO_XB: usize = 97; pub const ISO_GR: usize = 98;
/// PIERCED FULLER: n through-windows (curved stadium slots, Ø>=3 mm tool) on the blade medial line
/// inside the C.4 fuller band [s0, s1]; max width, slot length / pitch, width decay toward the tip.
pub const WIN_N: usize = 99; pub const WIN_S0: usize = 100; pub const WIN_S1: usize = 101; pub const WIN_W: usize = 102;
pub const WIN_FILL: usize = 103; pub const WIN_DECAY: usize = 104;
/// RING FLUTE: two-sided ball-nose groove on the finger-ring wall faces (depth/side, width fraction of
/// the wall, arc extent centred on the rear of the ring so it stays clear of the neck fillets).
pub const RFL_D: usize = 105; pub const RFL_W: usize = 106; pub const RFL_ARC: usize = 107;
/// Isogrid handle-zone start (fraction of x 18..74 kept solid next to the ring neck, where the lateral
/// moment peaks) and the guard / holder-land band switch (x 78..100; the >= 40 mm^2 full-thickness land
/// gate still applies: rib tops are the land).
pub const ISO_XH: usize = 108; pub const ISO_ZL: usize = 109;
/// PERFORATION LATTICE: affine-stretched hex lattice of elliptical THROUGH-holes (minor Ø 3-7 mm,
/// elongation along the lattice angle, rim/ligaments >= 3.2 mm to everything) in the guard / holder-land
/// band and/or the handle (start fraction keeps the ring neck solid). Through-holes keep Z/m = t/6 in
/// out-of-plane bending (face pockets lose Z at ~t/2 per removed volume), so they are SPG-neutral
/// outside stress concentrations and free mass inside low-stress zones.
pub const PERF_D: usize = 110; pub const PERF_GAP: usize = 111; pub const PERF_A: usize = 112; pub const PERF_E: usize = 113;
pub const PERF_ZL: usize = 114; pub const PERF_ZH: usize = 115; pub const PERF_XH: usize = 116;
// ---- D1 P1 continuous-rail layer (wave17+, exec/d1) ----
/// P1_ON (>= 0.5): continuous-rail architecture. Full-thickness (= local knot-field base) RAILS of width RAIL_W
/// from the outline and every hole rim, from the ring OD to the heel; full-thickness NECK out to r_od + NECK_L;
/// NO through-perforations / pierced-fuller windows / isogrid / dimple lattice / edge relief / comet flutes /
/// ring flute / machined texture (clamped OFF). Only SHALLOW face pockets (<= 0.6 mm/face, POCKET_D) with
/// >= R3 runouts (POCKET_R) inside the rails, outside the grinds, and only where the PARENT's 100 C SF map > 2
/// (JARAMBIT_P1_SFMAP). Thickness: K_N (3..5) centreline knots K0..K4 (mm, <= stock T) evenly spaced from the
/// ring centre to taper_x0, piecewise-linear, then the distal taper to t_tip.
pub const P1_ON: usize = 117; pub const RAIL_W: usize = 118; pub const NECK_L: usize = 119; pub const POCKET_D: usize = 120;
pub const POCKET_R: usize = 121; pub const K_N: usize = 122; pub const K0: usize = 123;
/// P1 caps.
pub const P1_POCKET_MAX: f64 = 0.6; pub const P1_RUNOUT_MIN: f64 = 3.0;
pub fn p1_env() -> bool { std::env::var("JARAMBIT_P1").map_or(false, |v| v == "1") }

pub const NAMES: [&str; NG - N_CP] = ["blade_drop_deg", "grip_dx", "ring_wall", "ring_id", "neck_fillet", "t_stock", "t_tip", "taper_x0",
    "edge_angle_in", "edge_angle_sp", "comet_x0", "comet_x1", "comet_w0", "comet_w1", "comet_bow", "comet_y", "eye_scale", "cairn_d",
    "nub_engage", "holder_wall", "jimp_scale", "serr_large_d", "serr_small_d", "serr_fine_d", "spine_sharp_offset",
    "relief_d", "relief_w", "relief_q", "lattice_d", "lattice_pitch", "lattice_frac", "lattice_angle", "lattice_handle", "lattice_blade",
    "fuller_d", "fuller_w", "fuller_s0", "fuller_s1", "flute_d", "texture_mode", "texture_d", "texture_pitch", "texture_angle",
    "wrap_x0", "wrap_len", "pad_x", "pad_y", "pad_w", "pad_l", "edge_t",
    "iso_d", "iso_pitch", "iso_rib", "iso_angle", "iso_rim", "iso_blade", "iso_handle", "iso_blade_extent", "iso_grade",
    "win_n", "win_s0", "win_s1", "win_w", "win_fill", "win_decay", "rflute_d", "rflute_w", "rflute_arc", "iso_handle_start", "iso_land", "perf_d", "perf_gap", "perf_angle", "perf_elong", "perf_land", "perf_handle", "perf_handle_start",
    "p1_on", "rail_w", "neck_l", "pocket_d", "pocket_r", "k_n", "k0", "k1", "k2", "k3", "k4"];

/// Finished-thickness floor from 6.35 mm (1/4 in) Ti plate; ceiling = JARAMBIT_T_MAX (<= 6.0).
pub const T_MIN: f64 = 5.3;
pub const PLATE_MM: f64 = 6.35;
pub fn t_max() -> f64 {
    static TM: std::sync::OnceLock<f64> = std::sync::OnceLock::new();
    *TM.get_or_init(|| std::env::var("JARAMBIT_T_MAX").ok().and_then(|v| v.parse::<f64>().ok()).map(|t| t.clamp(T_MIN, 6.0)).unwrap_or(6.0))
}

/// Aesthetic envelope: max normal offset (mm) of each C.4 spline control point.
/// 0 = pinned (tip corner; the four points hidden inside the ring disk).
pub fn cp_delta(i: usize) -> f64 {
    match i { 0 | 39 | 19..=22 => 0.0, 1..=7 => 3.0, 8 => 2.0, 9..=13 => 3.5, 14..=18 => 3.0, 23..=27 => 3.0, 28 | 29 => 2.0, 30..=35 => 3.5, 36..=38 => 2.5, _ => 0.0 }
}

/// Internal-machining genes with every feature OFF (C.4 / legacy wave6 genomes).
pub const MACHINING_OFF: [f64; NG - NG_LEGACY] = [0.0, 10.0, 2.0, 0.0, 3.0, 0.0, 0.0, 0.6, 0.0, 0.0, 0.2, 0.75, 6.0, 0.6, 0.7, 0.0, 0.5, 200.0, 0.3, 0.0, 0.0, 4.0, 0.0, 1.0, 0.0, 0.0, 0.3,
    // P1 layer OFF (knots are overwritten with the stock T by clamp when P1 is off)
    0.0, 3.0, 8.0, 0.0, 4.0, 3.0, 6.0, 6.0, 6.0, 6.0, 6.0];

pub fn bounds() -> Vec<(f64, f64)> {
    let mut b: Vec<(f64, f64)> = (0..N_CP).map(|i| (-cp_delta(i), cp_delta(i))).collect();
    b.extend_from_slice(&[(-4.0, 4.0), (-0.4, 10.0), (4.5, 7.0), (24.9, 25.9), (8.0, 18.0), (T_MIN, t_max()), (2.6, 4.5), (115.0, 150.0),
        (14.0, 22.0), (14.0, 22.0), (22.0, 30.0), (56.0, 70.0), (7.0, 12.0), (3.5, 6.0), (0.0, 4.0), (0.5, 4.0), (0.0, 1.25), (4.0, 7.0),
        (0.4, 1.2), (1.2, 2.0), (0.8, 1.2), (1.0, 1.5), (0.4, 0.8), (0.5, 0.9), (0.0, 45.0),
        (0.0, 1.2), (2.0, 8.0), (1.0, 3.0), (0.0, 1.5), (4.0, 9.0), (0.4, 0.8), (0.0, 60.0), (0.0, 1.0), (0.0, 1.0),
        (0.0, 1.2), (2.0, 5.0), (0.05, 0.4), (0.5, 0.9), (0.0, 1.0), (0.0, 1.0), (0.15, 0.4), (1.5, 3.0), (-45.0, 45.0),
        (16.0, 26.0), (45.0, 60.0), (70.0, 80.0), (-5.0, 3.0), (6.0, 9.0), (12.0, 16.0), (0.5, 0.9),
        (0.0, 1.6), (7.0, 16.0), (1.4, 3.0), (-30.0, 30.0), (2.0, 5.0), (0.0, 1.0), (0.0, 1.0), (0.0, 1.0), (-0.8, 0.8),
        (0.0, 7.99), (0.05, 0.5), (0.5, 0.92), (3.0, 10.0), (0.45, 0.8), (0.4, 1.0), (0.0, 2.0), (0.3, 0.7), (120.0, 260.0), (0.0, 0.8), (0.0, 1.0), (0.0, 7.0), (3.2, 8.0), (-40.0, 40.0), (1.0, 2.4), (0.0, 1.0), (0.0, 1.0), (0.0, 0.9),
        (0.0, 1.0), (3.0, 7.0), (4.0, 12.0), (0.0, P1_POCKET_MAX), (P1_RUNOUT_MIN, 6.0), (3.0, 5.99), (T_MIN, 6.0), (T_MIN, 6.0), (T_MIN, 6.0), (T_MIN, 6.0), (T_MIN, 6.0)]);
    assert_eq!(b.len(), NG);
    b
}

#[derive(Clone, Debug, PartialEq)]
pub struct Genome { pub v: Vec<f64>, pub mat: TiGrade }

impl Genome {
    /// SWITCHBACK Rev C.4 at `t` mm finished stock: zero offsets, C.4 holes/flutes/serrations,
    /// spine sharpening moved aft so its arc fits the 4.0 in edge cap, bare-flat 3-D layer.
    pub fn c4_seed(t: f64) -> Self {
        let mut v = vec![0.0; N_CP];
        v.extend_from_slice(&[0.0, 0.0, 6.3, 25.4, 15.0, t, 3.0, 130.0, 16.0, 16.0, 25.0, 66.0, 11.0, 5.2, 2.3, 2.3, 1.0, 6.0,
            0.6, 1.3, 1.0, 1.38, 0.7, 0.75, 24.0, 0.0, 4.0, 2.0, 0.0, 6.0, 0.6, 0.0, 0.0, 0.0, 0.0, 3.0, 0.15, 0.7, 0.6,
            0.0, 0.25, 2.0, 30.0, 20.0, 52.0, 75.0, -1.0, 6.5, 12.0, 0.5]);
        v.extend_from_slice(&MACHINING_OFF);
        let mut g = Genome { v, mat: TiGrade::Ti6Al4V }; g.clamp(); g
    }
    /// SWITCHBACK Rev C.5 seed: same genome as C.4 (C.5 changes only the jimping, which the
    /// phenotype now draws as R0.8 / uniform 0.45 mm at jimp_scale 1.0).
    pub fn c5_seed(t: f64) -> Self { Self::c4_seed(t) }
    /// SWITCHBACK Rev C.6 seed: same genome as C.5 (the ring-face groove is drawn by the phenotype
    /// from the ring wall genes: rims 1.6 mm to bore and OD, 0.6 mm per face).
    pub fn c6_seed(t: f64) -> Self { Self::c4_seed(t) }
    pub fn get(&self, i: usize) -> f64 { self.v[i] }
    pub fn clamp(&mut self) {
        let b = bounds();
        for (x, (lo, hi)) in self.v.iter_mut().zip(&b) { *x = if x.is_finite() { x.clamp(*lo, *hi) } else { *lo }; }
        self.v[T] = q01(self.v[T]).clamp(T_MIN, t_max());
        self.v[T_TIP] = self.v[T_TIP].min(self.v[T] - 0.5);
        // holder stack: t + 2 wall + 2 x 0.2 clearance <= 9.0 mm
        self.v[WALL] = self.v[WALL].min((9.0 - self.v[T] - 0.4) / 2.0).max(1.2);
        // nub engagement <= t/4 (it seats in the cairn hole)
        self.v[DETENT] = self.v[DETENT].min(self.v[T] / 4.0);
        if self.v[FUL_S1] < self.v[FUL_S0] + 0.15 { self.v[FUL_S1] = (self.v[FUL_S0] + 0.15).min(0.9); }
        if self.v[COMET_X1] < self.v[COMET_X0] + 28.0 { self.v[COMET_X1] = self.v[COMET_X0] + 28.0; }
        if self.v[WIN_S1] < self.v[WIN_S0] + 0.2 { self.v[WIN_S1] = (self.v[WIN_S0] + 0.2).min(0.92); }
        if p1_env() { self.v[P1_ON] = 1.0; }
        if self.p1() {
            // continuous-rail architecture: every through-feature / deep face-pocket family OFF
            for i in [ISO_D, ISO_ZB, ISO_ZH, ISO_ZL, WIN_N, RFL_D, PERF_D, PERF_ZL, PERF_ZH, LAT_D, LAT_H, LAT_B, RELIEF_D, FLUTE, TEX_MODE] { self.v[i] = 0.0; }
            self.v[FUL_D] = self.v[FUL_D].min(P1_POCKET_MAX);
            self.v[POCKET_D] = self.v[POCKET_D].clamp(0.0, P1_POCKET_MAX); self.v[POCKET_R] = self.v[POCKET_R].max(P1_RUNOUT_MIN);
            for k in 0..5 { self.v[K0 + k] = self.v[K0 + k].clamp(T_MIN, self.v[T]); }
            // the stock is the thickest knot (finished from 6.35 plate; 0.1 mm stock rule applies to T)
            let kn = self.k_n(); let kmax = (0..kn).map(|k| self.v[K0 + k]).fold(T_MIN, f64::max);
            if kmax < self.v[T] - 1e-9 { let s = self.v[T] - kmax; for k in 0..kn { self.v[K0 + k] = (self.v[K0 + k] + s).min(self.v[T]); } }
        } else { for k in 0..5 { self.v[K0 + k] = self.v[T]; } }
    }
    pub fn p1(&self) -> bool { self.v.len() > P1_ON && self.v[P1_ON] >= 0.5 }
    pub fn k_n(&self) -> usize { (self.v[K_N].floor() as usize).clamp(3, 5) }
    /// P1 knot thickness at x (ring centre = 0 .. taper_x0 + dx), piecewise-linear; stock T when P1 is off.
    pub fn knot_t(&self, x: f64, tx0: f64) -> f64 {
        if !self.p1() { return self.v[T]; }
        let kn = self.k_n(); let u = (x / tx0.max(1.0)).clamp(0.0, 1.0) * (kn - 1) as f64;
        let i = (u.floor() as usize).min(kn - 2); let f = u - i as f64;
        self.v[K0 + i] * (1.0 - f) + self.v[K0 + i + 1] * f
    }
    /// Thinnest knot (P1) — the joint thin+hot factor uses this, conservatively; stock T otherwise.
    pub fn t_joint(&self) -> f64 { if !self.p1() { return self.v[T]; } (0..self.k_n()).map(|k| self.v[K0 + k]).fold(f64::MAX, f64::min) }
    pub fn random_in_envelope(r: &mut Rng) -> Self {
        let b = bounds();
        let mut g = Genome { v: b.iter().map(|(lo, hi)| r.range(*lo, *hi)).collect(), mat: if r.f64() < 0.8 { TiGrade::Ti6Al4V } else { TiGrade::Ti3Al2_5V } };
        // smooth the silhouette offsets (a random walk per zone, not white noise)
        let raw = g.v[..N_CP].to_vec();
        for i in 0..N_CP { if cp_delta(i) == 0.0 { g.v[i] = 0.0; continue; }
            let (a, c) = (raw[(i + N_CP - 1) % N_CP], raw[(i + 1) % N_CP]); g.v[i] = (0.25 * a + 0.5 * raw[i] + 0.25 * c).clamp(-cp_delta(i), cp_delta(i)); }
        g.clamp(); g
    }

    /// Mutation operators that stay INSIDE the aesthetic envelope.
    /// 0 gaussian per-gene, 1 smooth silhouette bump (low-frequency offset field over the spline),
    /// 2 thickness-field op (taper/relief/medial-axis section), 3 lattice op, 4 fuller/flute op.
    pub fn mutate(&self, r: &mut Rng, sigma: f64) -> Self {
        let b = bounds();
        let mut g = self.clone();
        let op = (r.f64() * 6.0) as usize;
        let span = |i: usize| b[i].1 - b[i].0;
        let jig = |g: &mut Genome, i: usize, r: &mut Rng, s: f64| { g.v[i] += r.normal() * s * span(i); };
        let fine = sigma < 0.025;
        let sil_s = if fine { sigma * 0.1 } else { sigma };
        match op {
            0 => { for i in 0..NG { if (!fine || i != T) && r.f64() < 0.15 { jig(&mut g, i, r, if i < N_CP { sil_s } else { sigma }); } } }
            1 => { let c = r.range(0.0, N_CP as f64); let w = r.range(1.5, 5.0); let a = r.normal() * sil_s * 6.0;
                   for i in 0..N_CP { let d = (i as f64 - c).abs().min(N_CP as f64 - (i as f64 - c).abs());
                       g.v[i] += a * (-(d / w).powi(2)).exp() * (cp_delta(i) / 3.5); }
                   if !fine && r.f64() < 0.3 { jig(&mut g, DROP, r, sigma); } if !fine && r.f64() < 0.3 { jig(&mut g, GRIP_DX, r, sigma); } }
            2 => { for i in [T, T_TIP, TAPER_X0, RELIEF_D, RELIEF_W, RELIEF_Q, EA_IN, EA_SP, RING_WALL, EDGE_TH] { if (!fine || i != T) && r.f64() < 0.5 { jig(&mut g, i, r, sigma * 1.5); } }
                   if g.p1() { for i in [K0, K0 + 1, K0 + 2, K0 + 3, K0 + 4, K_N] { if r.f64() < 0.5 { jig(&mut g, i, r, sigma * 1.5); } } } }
            5 if g.p1() => { for i in [RAIL_W, NECK_L, POCKET_D, POCKET_R, K_N, K0, K0 + 1, K0 + 2, K0 + 3, K0 + 4, T, FUL_D, RING_WALL, NECK_FILLET] { if (!fine || i != T) && r.f64() < 0.4 { jig(&mut g, i, r, sigma * 1.5); } } }
            3 => { for i in [LAT_D, LAT_P, LAT_F, LAT_A] { if r.f64() < 0.6 { jig(&mut g, i, r, sigma * 1.5); } }
                   if !fine { if r.f64() < 0.2 { g.v[LAT_H] = 1.0 - g.v[LAT_H]; } if r.f64() < 0.2 { g.v[LAT_B] = 1.0 - g.v[LAT_B]; } } }
            5 => { for i in [ISO_D, ISO_P, ISO_RIB, ISO_A, ISO_RIM, ISO_XB, ISO_XH, ISO_GR, WIN_S0, WIN_S1, WIN_W, WIN_FILL, WIN_DECAY, RFL_D, RFL_W, RFL_ARC, PERF_D, PERF_GAP, PERF_A, PERF_E, PERF_XH, T] { if (!fine || i != T) && r.f64() < 0.4 { jig(&mut g, i, r, sigma * 1.5); } }
                   if !fine {
                       for z in [ISO_ZB, ISO_ZH, ISO_ZL, PERF_ZL, PERF_ZH] { if r.f64() < 0.12 { g.v[z] = 1.0 - g.v[z]; } }
                       if r.f64() < 0.25 { g.v[WIN_N] += if r.f64() < 0.5 { -1.0 } else { 1.0 }; }
                   } }
            _ => { for i in [FUL_D, FUL_W, FUL_S0, FUL_S1, FLUTE, TEX_MODE, TEX_D, TEX_P, TEX_A, COMET_W0, COMET_W1, COMET_BOW, EYE, CAIRN] { if (!fine || i != TEX_MODE) && r.f64() < 0.4 { jig(&mut g, i, r, sigma * 1.5); } } }
        }
        if !fine && r.f64() < 0.03 { g.mat = if g.mat == TiGrade::Ti6Al4V { TiGrade::Ti3Al2_5V } else { TiGrade::Ti6Al4V }; }
        g.clamp(); g
    }
    pub fn crossover(&self, o: &Self, r: &mut Rng) -> Self {
        // block crossover: silhouette block, then each named gene independently
        let take_sil = r.f64() < 0.5;
        let v = (0..NG).map(|i| if i < N_CP { if take_sil { self.v[i] } else { o.v[i] } } else if r.f64() < 0.5 { self.v[i] } else { o.v[i] }).collect();
        let mut g = Genome { v, mat: if r.f64() < 0.5 { self.mat } else { o.mat } }; g.clamp(); g
    }
    pub fn csv_header() -> String {
        let mut h: Vec<String> = (0..N_CP).map(|i| format!("cp{i:02}")).collect();
        h.extend(NAMES.iter().map(|s| s.to_string())); h.push("material".into()); h.join(",")
    }
    pub fn csv_row(&self) -> String {
        // D1: full round-trip precision (Rust shortest repr). {:.4} made on-disk genomes differ from the certified
        // in-memory design (wave13_c01 re-certifies 12 % lower from its CSV).
        let mut s: Vec<String> = self.v.iter().map(|x| format!("{x}")).collect(); s.push(self.mat.name().into()); s.join(",")
    }
    pub fn from_csv(fields: &[&str]) -> Option<Self> {
        // material column = first field naming a Ti grade; genes before it. Older layouts (90 genes = wave6,
        // 110 = wave7) are padded with the remaining internal-machining genes OFF.
        let n = fields.iter().position(|f| f.trim().starts_with("Ti"))?;
        if n < NG_LEGACY || n > NG { return None; }
        // pre-P1 rows (<= 117 genes) get the P1 layer OFF; knots follow the stock via clamp()
        let mut v: Vec<f64> = fields[..n].iter().map(|s| s.trim().parse().ok()).collect::<Option<Vec<f64>>>()?;
        v.extend_from_slice(&MACHINING_OFF[n - NG_LEGACY..]);
        Some(Genome { v, mat: if fields[n].contains("3Al") { TiGrade::Ti3Al2_5V } else { TiGrade::Ti6Al4V } })
    }
    /// Activate the internal-machining layer at random (seeding operator for the lattice lane).
    pub fn machining_kick(&self, r: &mut Rng) -> Self {
        let b = bounds(); let mut g = self.clone();
        if g.p1() { // P1: re-draw the rail / neck / pocket / knot layer instead of through-machining
            for i in [RAIL_W, NECK_L, POCKET_D, POCKET_R, K_N, K0, K0 + 1, K0 + 2, K0 + 3, K0 + 4] { g.v[i] = r.range(b[i].0, b[i].1); }
            if r.f64() < 0.5 { g.v[T] = r.range(T_MIN, t_max()); }
            g.clamp(); return g; }
        for i in [ISO_D, ISO_P, ISO_RIB, ISO_A, ISO_RIM, ISO_XB, ISO_XH, ISO_GR, WIN_S0, WIN_S1, WIN_W, WIN_FILL, WIN_DECAY, RFL_D, RFL_W, RFL_ARC, PERF_D, PERF_GAP, PERF_A, PERF_E, PERF_XH] { g.v[i] = r.range(b[i].0, b[i].1); }
        for z in [ISO_ZB, ISO_ZH, ISO_ZL, PERF_ZL, PERF_ZH] { g.v[z] = if r.f64() < 0.5 { 1.0 } else { 0.0 }; }
        g.v[WIN_N] = (r.f64() * 8.0).floor().min(7.0);
        if r.f64() < 0.5 { g.v[T] = r.range(T_MIN, t_max()); }
        g.clamp(); g
    }
}
