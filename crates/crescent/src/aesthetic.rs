//! Aesthetic floor vs SWITCHBACK Rev C.4 (HARD) + aesthetic score (soft multiplier).
//! Floor: continuous crescent (no straight stem; convex spine, concave hawkbill), smooth blends
//! (min concave radius), thumb seat + guard lobe present, Hausdorff and curvature-histogram
//! distance to C.4 within bounds, lightening only in C.4 zones, textured / cord-wrap grip,
//! flat brand pad. A design failing any of these is NOT an aesthetic passer and gets no novelty.
use crate::c4_ref as c4;
use crate::genome::*;
use crate::geom::*;
use crate::pheno::*;

pub const HAUSDORFF_MAX_MM: f64 = 6.0;
pub const EMD_MAX: f64 = 0.06;
pub const STRAIGHT_R_MM: f64 = 250.0;   // |kappa| < 1/250 counts as "straight"
pub const STRAIGHT_SLACK_MM: f64 = 8.0; // allowed over the C.4 longest straight run
pub const MIN_BLEND_R_MM: f64 = 2.0;
pub const HIST_BINS: usize = 32;

#[derive(Clone, Debug, Default)]
pub struct Aes {
    pub hausdorff: f64, pub emd: f64, pub straight_mm: f64, pub min_concave_r: f64,
    pub spine_convex: f64, pub inside_concave: f64, pub seat_depth: f64, pub lobe_prom: f64, pub hook_drop: f64,
    pub score: f64, pub pass: bool, pub fails: Vec<String>,
}

pub struct RefStats { pub hist: Vec<f64>, pub straight: f64, pub min_r: f64, pub c4_dense: Vec<P2>, pub spine_convex: f64, pub inside_concave: f64 }

/// Crescent-continuity tolerance: convex-spine / concave-hawkbill sample fractions may drop at most
/// this much below C.4's own value (C.4 spine has a short inflection just past the thumb crest).
pub const CONTINUITY_SLACK: f64 = 0.03;

fn tip_excluded(q: P2, tip: P2) -> bool { dist(q, tip) < 5.0 }

/// (curvature histogram, longest straight run, min concave radius) on the macro silhouette.
pub fn shape_stats(macro_outline: &[P2], tip: P2) -> (Vec<f64>, f64, f64) {
    let r = resample_closed(macro_outline, 0.5);
    let k = curvature_closed(&r, 4);
    let mut hist = vec![0.0f64; HIST_BINS]; let mut tot = 0.0f64;
    let mut run = 0.0f64; let mut best = 0.0f64; let mut minr = f64::INFINITY;
    for (i, &kk) in k.iter().enumerate() {
        if tip_excluded(r[i], tip) { run = 0.0; continue; }
        let u = kk.signum() * (1.0 + 50.0 * kk.abs()).ln();
        let b = (((u + 4.0) / 8.0) * HIST_BINS as f64).floor().clamp(0.0, (HIST_BINS - 1) as f64) as usize;
        hist[b] += 0.5; tot += 0.5;
        if kk.abs() < 1.0 / STRAIGHT_R_MM { run += 0.5; best = best.max(run); } else { run = 0.0; }
        if kk < 0.0 { minr = minr.min(1.0 / kk.abs()); }
    }
    for h in hist.iter_mut() { *h /= tot.max(1e-9); }
    (hist, best, minr)
}

pub fn emd(a: &[f64], b: &[f64]) -> f64 {
    let (mut ca, mut cb, mut d) = (0.0, 0.0, 0.0);
    for i in 0..a.len() { ca += a[i]; cb += b[i]; d += (ca - cb).abs(); }
    d / a.len() as f64
}

pub fn reference() -> &'static RefStats {
    static R: std::sync::OnceLock<RefStats> = std::sync::OnceLock::new();
    R.get_or_init(|| {
        let p = build(&Genome::c4_seed(5.7));
        let (hist, straight, min_r) = shape_stats(&p.macro_outline, p.tip);
        let (sc, ic) = continuity(&p);
        RefStats { hist, straight, min_r, c4_dense: densify(&c4::EXTERIOR, 0.25, true), spine_convex: sc, inside_concave: ic }
    })
}

/// Fraction of samples on curve range [a, b) (0.1 mm spline samples) with signed curvature
/// sign `want` (+1 convex, -1 concave) or near-straight.
fn sign_frac(c: &[P2], a: usize, b: usize, want: f64, orient: f64) -> f64 {
    let k = 20; let mut ok = 0usize; let mut n = 0usize;
    for i in (a + k..b.saturating_sub(k)).step_by(5) {
        let (p, q, r) = (c[i - k], c[i], c[i + k]);
        let cr = orient * cross(sub(q, p), sub(r, q)); let den = dist(p, q) * dist(q, r) * dist(p, r);
        let kap = if den < 1e-12 { 0.0 } else { 2.0 * cr / den };
        n += 1; if kap * want >= -1.0 / 400.0 { ok += 1; }
    }
    if n == 0 { 1.0 } else { ok as f64 / n as f64 }
}

/// (convex fraction of the sharpened-spine run, concave fraction of the hawkbill run).
pub fn continuity(p: &Pheno) -> (f64, f64) {
    let c = &p.curve; let ci = &p.cidx; let orient = signed_area(&c[..c.len() - 1]).signum();
    (sign_frac(c, ci[30], c.len() - 1 - 50, 1.0, orient), sign_frac(c, 50, ci[8], -1.0, orient))
}

pub fn evaluate(g: &Genome, p: &Pheno) -> Aes {
    let rf = reference();
    let mut a = Aes::default();
    a.hausdorff = hausdorff(&densify(&p.outline, 0.25, true), &rf.c4_dense);
    let (hist, straight, minr) = shape_stats(&p.macro_outline, p.tip);
    a.emd = emd(&hist, &rf.hist); a.straight_mm = straight; a.min_concave_r = minr;
    let c = &p.curve; let ci = &p.cidx;
    let (sc, ic) = continuity(p); a.spine_convex = sc; a.inside_concave = ic;
    let ymin = |r: std::ops::RangeInclusive<usize>| r.map(|i| c[i].1).fold(f64::MAX, f64::min);
    a.seat_depth = c[ci[27]].1.min(c[ci[29]].1) - ymin(ci[27]..=ci[29]);
    a.lobe_prom = (c[ci[8]].1 + c[ci[14]].1) / 2.0 - ymin(ci[9]..=ci[13]);
    a.hook_drop = p.blade.hook_drop;
    let mut f = Vec::new();
    if !(a.hausdorff <= HAUSDORFF_MAX_MM) { f.push(format!("Hausdorff {:.2} > {HAUSDORFF_MAX_MM} mm vs C.4", a.hausdorff)); }
    if !(a.emd <= EMD_MAX) { f.push(format!("curvature-histogram EMD {:.3} > {EMD_MAX}", a.emd)); }
    if !(a.straight_mm <= rf.straight + STRAIGHT_SLACK_MM) { f.push(format!("straight stem {:.1} mm > C.4 {:.1}+{STRAIGHT_SLACK_MM}", a.straight_mm, rf.straight)); }
    if !(a.min_concave_r >= MIN_BLEND_R_MM.min(0.8 * rf.min_r)) { f.push(format!("blend radius {:.2} mm < {:.2}", a.min_concave_r, MIN_BLEND_R_MM.min(0.8 * rf.min_r))); }
    if a.spine_convex < rf.spine_convex - CONTINUITY_SLACK { f.push(format!("spine not a continuous convex crescent ({:.2} < C.4 {:.2}-{CONTINUITY_SLACK})", a.spine_convex, rf.spine_convex)); }
    if a.inside_concave < rf.inside_concave - CONTINUITY_SLACK { f.push(format!("hawkbill edge not continuously concave ({:.2} < C.4 {:.2}-{CONTINUITY_SLACK})", a.inside_concave, rf.inside_concave)); }
    if a.seat_depth < 0.4 { f.push(format!("no thumb seat ({:.2} mm)", a.seat_depth)); }
    if a.lobe_prom < 5.0 { f.push(format!("no guard lobe ({:.2} mm)", a.lobe_prom)); }
    if a.hook_drop < 25.0 { f.push(format!("hook drop {:.1} < 25 mm", a.hook_drop)); }
    if g.v[NECK_FILLET] < 8.0 { f.push("ring neck fillet < 8 mm".into()); }
    let texture = g.v[WRAP_L] >= 45.0 && (g.v[TEX_MODE] < 0.5 || g.v[TEX_D] >= 0.15);
    if !texture { f.push("no cord-wrap / textured grip zone".into()); }
    if !p.pad_flat { f.push("brand pad not flat".into()); }
    a.score = (-a.hausdorff / 6.0).exp() * (-a.emd / 0.05).exp() * (1.0 - 0.5 * ((a.straight_mm - rf.straight).max(0.0) / STRAIGHT_SLACK_MM).min(1.0));
    a.pass = f.is_empty(); a.fails = f;
    a
}
