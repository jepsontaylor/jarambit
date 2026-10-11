//! Monte Carlo over manufacturing tolerance, temperature, and cut medium.
//! Parallel via std::thread. Sample `i` is seeded from `(seed, i)`, so the
//! multiset of samples does not depend on the thread count.
use jarambit_genotype::{Genotype, Rng};

/// Perturb a genotype by CNC/waterjet tolerances (thickness +-0.05 mm, profile +-0.1 mm).
/// NOTE: no clamp/repair here except the caller re-quantises nothing — thickness
/// as-machined is applied separately via [`thickness_sample`], so tolerance
/// excursions can push a design over the hard limits and get rejected.
pub fn perturb(g: &Genotype, r: &mut Rng) -> Genotype {
    let mut h = g.clone();
    h.curve_radius += r.normal() * 0.1;
    h.blade_arc_len += r.normal() * 0.15;
    h.ring_wall += r.normal() * 0.1;
    h.ring_id += r.normal() * 0.05;
    h.grip_len += r.normal() * 0.1;
    h.edge_angle_deg += r.normal() * 0.5;
    h.serr_inner.depth = (h.serr_inner.depth + r.normal() * 0.05).max(0.05);
    h.serr_outer.depth = (h.serr_outer.depth + r.normal() * 0.05).max(0.05);
    h.holder.detent_depth += r.normal() * 0.05;
    h.holder.shoulder_w += r.normal() * 0.05;
    h.holder.holder_wall += r.normal() * 0.03;
    h
}

/// Thickness as-machined (surface grind tolerance) — used by physics, not by the precision gate.
pub fn thickness_sample(g: &Genotype, r: &mut Rng) -> f64 { g.thickness + r.normal() * 0.03 }

/// Environment sample: temperature -10..100 C with 25% of samples at the extremes.
#[derive(Clone, Copy, Debug)]
pub struct Env { pub temp_c: f64 }
pub fn env_sample(r: &mut Rng) -> Env {
    let u = r.f64();
    let temp_c = if u < 0.125 { -10.0 } else if u < 0.25 { 100.0 } else { r.range(-10.0, 100.0) };
    Env { temp_c }
}

/// Utility / game-processing cut medium. Gel is the repeatable calibration medium.
/// Demands are hiking and field-dressing loads, not a combat model.
#[derive(Clone, Copy, Debug, PartialEq, Eq)]
pub enum CutMedia { Wood, Cord, Hide, Muscle, Bone, Gel }

impl CutMedia {
    pub const ALL: [CutMedia; 6] = [CutMedia::Wood, CutMedia::Cord, CutMedia::Hide, CutMedia::Muscle, CutMedia::Bone, CutMedia::Gel];
    /// (work N, edge-lead fraction λ, edge-quality demand in 0..1).
    /// Blade-first: λ is the share of `work` aligned with the edge (in-plane draw);
    /// `1-λ` is the lateral component. Cord, hide and muscle lead with the edge.
    pub fn profile(self) -> (f64, f64, f64) {
        match self {
            CutMedia::Wood => (100.0, 0.35, 0.35),
            CutMedia::Cord => (70.0, 0.85, 0.55),
            CutMedia::Hide => (45.0, 0.90, 0.50),
            CutMedia::Muscle => (90.0, 0.70, 0.55),
            CutMedia::Bone => (160.0, 0.20, 0.25),
            CutMedia::Gel => (60.0, 0.50, 0.30),
        }
    }
    pub fn name(self) -> &'static str {
        match self {
            CutMedia::Wood => "wood", CutMedia::Cord => "cord", CutMedia::Hide => "hide",
            CutMedia::Muscle => "muscle", CutMedia::Bone => "bone", CutMedia::Gel => "gel",
        }
    }
}

/// Mix: wood 20%, cord/webbing 20%, hide 15%, muscle 20%, bone/joint 10%, gel 15%.
pub fn media_sample(r: &mut Rng) -> CutMedia {
    let u = r.f64();
    if u < 0.20 { CutMedia::Wood }
    else if u < 0.40 { CutMedia::Cord }
    else if u < 0.55 { CutMedia::Hide }
    else if u < 0.75 { CutMedia::Muscle }
    else if u < 0.85 { CutMedia::Bone }
    else { CutMedia::Gel }
}

/// Blade-first cut margin. Positive means the sampled medium clears both the
/// section capacity and the edge-quality demand. `blade_lat_n` / `inplane_n`
/// are yield capacities (N); `sharp` and `serr` are in 0..1.
pub fn cut_margin(blade_lat_n: f64, inplane_n: f64, sharp: f64, serr: f64, media: CutMedia) -> f64 {
    let (work, lead, edge_need) = media.profile();
    let lat = work * (1.0 - lead);
    let along = work * lead;
    let structural = 1.0 - (lat / blade_lat_n.max(1.0)).max(along / inplane_n.max(1.0));
    let edge = 0.6 * sharp.clamp(0.0, 1.0) + 0.4 * serr.clamp(0.0, 1.0) - edge_need;
    structural.min(edge)
}

/// Mean and both tails of one MC column. `p05` index is `floor(0.05 n)` (the
/// historical robust score). `p95` is `floor(0.95 n)`, clamped to the last element.
#[derive(Clone, Copy, Debug)]
pub struct Tails { pub mean: f64, pub p05: f64, pub p95: f64 }

fn mix_seed(seed: u64, i: u64) -> u64 {
    let mut z = seed.wrapping_add(i.wrapping_mul(0x9E37_79B9_7F4A_7C15)).wrapping_add(0xD1B5_4A32_D192_ED03);
    z = (z ^ (z >> 30)).wrapping_mul(0xBF58476D1CE4E5B9);
    z = (z ^ (z >> 27)).wrapping_mul(0x94D049BB133111EB);
    z ^ (z >> 31)
}

fn pct_index(n: usize, num: usize, den: usize) -> usize {
    ((n * num) / den).min(n.saturating_sub(1))
}

/// Evaluate `n` samples across `threads` (capped at 48). Each sample returns `K` scalars.
/// Column tails are independent. Thread count does not change the sample multiset.
pub fn run_cols<const K: usize, F>(g: &Genotype, n: usize, threads: usize, seed: u64, f: F) -> [Tails; K]
where F: Fn(&Genotype, &mut Rng) -> [f64; K] + Sync {
    let n = n.max(1);
    let threads = threads.max(1).min(48).min(n);
    let all: Vec<[f64; K]> = std::thread::scope(|s| {
        let mut handles = Vec::with_capacity(threads);
        let mut start = 0usize;
        for t in 0..threads {
            let count = n / threads + usize::from(t < n % threads);
            let i0 = start;
            start += count;
            let f = &f;
            handles.push(s.spawn(move || {
                (0..count).map(|k| {
                    let mut r = Rng(mix_seed(seed, (i0 + k) as u64));
                    let h = perturb(g, &mut r);
                    f(&h, &mut r)
                }).collect::<Vec<_>>()
            }));
        }
        handles.into_iter().flat_map(|h| h.join().unwrap()).collect()
    });
    debug_assert_eq!(all.len(), n);
    let mut out = [Tails { mean: 0.0, p05: 0.0, p95: 0.0 }; K];
    let mut col = vec![0.0; n];
    for k in 0..K {
        for (i, row) in all.iter().enumerate() { col[i] = row[k]; }
        col.sort_by(|a, b| a.partial_cmp(b).unwrap_or(std::cmp::Ordering::Equal));
        let mean = col.iter().sum::<f64>() / n as f64;
        out[k] = Tails { mean, p05: col[pct_index(n, 5, 100)], p95: col[pct_index(n, 95, 100)] };
    }
    out
}

/// Run `n` samples of f(sample, rng) across `threads`; returns (mean, p05).
pub fn run<F>(g: &Genotype, n: usize, threads: usize, seed: u64, f: F) -> (f64, f64)
where F: Fn(&Genotype, &mut Rng) -> f64 + Sync {
    let t = run_cols(g, n, threads, seed, |h, r| [f(h, r)]);
    (t[0].mean, t[0].p05)
}

#[cfg(test)]
mod tests {
    use super::*;
    #[test] fn extremes_fraction() {
        let mut r = Rng(1); let n = 20000;
        let ext = (0..n).filter(|_| { let e = env_sample(&mut r); e.temp_c == -10.0 || e.temp_c == 100.0 }).count();
        let f = ext as f64 / n as f64; assert!((f - 0.25).abs() < 0.02, "{f}");
    }
    #[test] fn media_mix_fractions() {
        let mut r = Rng(2); let n = 20000;
        let mut c = [0usize; 6];
        for _ in 0..n { let m = media_sample(&mut r); c[CutMedia::ALL.iter().position(|x| *x == m).unwrap()] += 1; }
        let expect = [0.20, 0.20, 0.15, 0.20, 0.10, 0.15];
        for (i, e) in expect.iter().enumerate() {
            let f = c[i] as f64 / n as f64;
            assert!((f - e).abs() < 0.02, "{i} {f} vs {e}");
        }
    }
    #[test] fn sample_count_and_thread_stability() {
        let g = Genotype::random(&mut Rng(4));
        let f = |h: &Genotype, r: &mut Rng| h.blade_arc_len + r.normal();
        let a = run(&g, 4000, 1, 99, f);
        let b = run(&g, 4000, 7, 99, f);
        assert!((a.0 - b.0).abs() < 1e-9 && (a.1 - b.1).abs() < 1e-9, "{a:?} {b:?}");
        let cols = run_cols(&g, 10_000, 8, 7, |_h, r| [r.f64(), r.f64()]);
        assert!(cols[0].mean > 0.4 && cols[0].mean < 0.6, "{}", cols[0].mean);
        assert!(cols[0].p05 < 0.08 && cols[0].p95 > 0.90, "{:?}", cols[0]);
    }
    #[test] fn blade_first_bone_is_more_lateral_than_hide() {
        let (wb, lb, _) = CutMedia::Bone.profile();
        let (wh, lh, _) = CutMedia::Hide.profile();
        assert!(wb * (1.0 - lb) > wh * (1.0 - lh));
        assert!(lh > 0.8 && lb < 0.4);
        let easy = cut_margin(500.0, 2000.0, 1.0, 1.0, CutMedia::Gel);
        let dull = cut_margin(500.0, 2000.0, 0.0, 0.0, CutMedia::Cord);
        assert!(easy > 0.0 && dull < 0.0, "{easy} {dull}");
    }
}
