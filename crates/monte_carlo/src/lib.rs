//! Monte Carlo over manufacturing tolerance, temperature, and cut medium.
//! Parallel via std::thread. Sample `i` is seeded from `(seed, i)`, so the
//! multiset of samples does not depend on the thread count.
use jarambit_genotype::{Genotype, Rng};
use std::cell::Cell;
use std::panic::{catch_unwind, AssertUnwindSafe};
use std::sync::{mpsc, Arc, Mutex, OnceLock};

mod scenario;
mod stats;
pub use scenario::*;
pub use stats::*;

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
    h.neck_flare += r.normal() * 0.05;
    h.neck_fillet_r = (h.neck_fillet_r + r.normal() * 0.1).max(0.0);
    h
}

/// Thickness as-machined (surface grind tolerance) — used by physics, not by the precision gate.
pub fn thickness_sample(g: &Genotype, r: &mut Rng) -> f64 { g.thickness + r.normal() * 0.03 }

/// Environment sample: temperature -10..100 C with 25% of samples at the extremes.
#[derive(Clone, Copy, Debug)]
pub struct Env { pub temp_c: f64 }
/// `Some` for the two extreme bands. `None` means the caller still draws `range(-10, 100)`
/// and must not draw that extra sample on the extreme bands.
pub fn env_temp_band(u: f64) -> Option<f64> {
    if u < 0.125 { Some(-10.0) } else if u < 0.25 { Some(100.0) } else { None }
}

pub fn env_sample(r: &mut Rng) -> Env {
    let u = r.f64();
    let temp_c = match env_temp_band(u) { Some(t) => t, None => r.range(-10.0, 100.0) };
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
/// Thresholds are on the unit draw: `[0, 0.20) wood`, then cord, hide, muscle, bone, else gel.
pub fn media_from_unit(u: f64) -> CutMedia {
    if u < 0.20 { CutMedia::Wood }
    else if u < 0.40 { CutMedia::Cord }
    else if u < 0.55 { CutMedia::Hide }
    else if u < 0.75 { CutMedia::Muscle }
    else if u < 0.85 { CutMedia::Bone }
    else { CutMedia::Gel }
}

pub fn media_sample(r: &mut Rng) -> CutMedia { media_from_unit(r.f64()) }

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

pub const MIX_SEED_0: u64 = 0x9E37_79B9_7F4A_7C15;
pub const MIX_SEED_1: u64 = 0xD1B5_4A32_D192_ED03;
pub const MIX_SEED_2: u64 = 0xBF58_476D_1CE4_E5B9;
pub const MIX_SEED_3: u64 = 0x94D0_49BB_1331_11EB;

/// Production sample index mixer. Exact 1/2/4 worker replay must call this, not a copy.
pub fn mix_seed(seed: u64, i: u64) -> u64 {
    let mut z = seed.wrapping_add(i.wrapping_mul(MIX_SEED_0)).wrapping_add(MIX_SEED_1);
    z = (z ^ (z >> 30)).wrapping_mul(MIX_SEED_2);
    z = (z ^ (z >> 27)).wrapping_mul(MIX_SEED_3);
    z ^ (z >> 31)
}

fn pct_index(n: usize, num: usize, den: usize) -> usize {
    ((n * num) / den).min(n.saturating_sub(1))
}

/// Per-host thread cap. Default 48 (shared-box safe). Override with env
/// `JARAMBIT_MAX_THREADS` (e.g. 64 on xbabe2, 80-96 on idle 128-core xbabe1/xbabe3);
/// always clamped to the machine's available parallelism.
pub fn max_threads() -> usize {
    let hw = std::thread::available_parallelism().map(|n| n.get()).unwrap_or(1);
    std::env::var("JARAMBIT_MAX_THREADS").ok().and_then(|v| v.parse::<usize>().ok()).unwrap_or(48).clamp(1, hw)
}

/// Process-lifetime workers. Spawning a fresh set per candidate flattened
/// wall time above 32 threads (sys time in clone/spawn). Do not call
/// `run_cols` from inside a sample: that worker would wait on itself.
/// Checked [`try_run_cols`] refuses that nesting with [`CheckedError::ReentrantPool`].
struct Pool {
    tx: Mutex<Vec<mpsc::Sender<Box<dyn FnOnce() + Send>>>>,
    /// Test-only budget on this pool instance. Zero in production. A positive
    /// value makes the next checked spawn return the real error arm.
    #[cfg(test)]
    spawn_failures: std::sync::atomic::AtomicUsize,
}

thread_local! {
    static IN_MC_WORKER: Cell<bool> = Cell::new(false);
    static SAMPLE_INDEX: Cell<Option<usize>> = Cell::new(None);
}

struct ClearWorkerFlag;
impl Drop for ClearWorkerFlag {
    fn drop(&mut self) {
        IN_MC_WORKER.with(|flag| flag.set(false));
        SAMPLE_INDEX.with(|slot| slot.set(None));
    }
}

fn worker_loop(recv: mpsc::Receiver<Box<dyn FnOnce() + Send>>) {
    while let Ok(job) = recv.recv() {
        job();
    }
}

fn pool() -> &'static Pool {
    static POOL: OnceLock<Pool> = OnceLock::new();
    POOL.get_or_init(|| Pool {
        tx: Mutex::new(Vec::new()),
        #[cfg(test)]
        spawn_failures: std::sync::atomic::AtomicUsize::new(0),
    })
}

#[cfg(test)]
fn private_pool() -> Pool {
    Pool { tx: Mutex::new(Vec::new()), spawn_failures: std::sync::atomic::AtomicUsize::new(0) }
}

impl Pool {
    fn ensure(&self, n: usize) {
        let mut tx = self.tx.lock().unwrap();
        while tx.len() < n {
            let (send, recv) = mpsc::channel::<Box<dyn FnOnce() + Send>>();
            std::thread::Builder::new().name("jarambit-mc".into()).spawn(move || worker_loop(recv)).expect("mc worker");
            tx.push(send);
        }
    }

    /// Checked spawn. A test budget on this instance returns `Err` before a thread
    /// exists. A real `spawn` error returns the same `Err`. Legacy [`Self::ensure`]
    /// does not use this seam.
    fn spawn_owned_worker(&self) -> Result<mpsc::Sender<Box<dyn FnOnce() + Send>>, ()> {
        #[cfg(test)]
        {
            let mut left = self.spawn_failures.load(std::sync::atomic::Ordering::SeqCst);
            while left > 0 {
                match self.spawn_failures.compare_exchange(
                    left,
                    left - 1,
                    std::sync::atomic::Ordering::SeqCst,
                    std::sync::atomic::Ordering::SeqCst,
                ) {
                    Ok(_) => return Err(()),
                    Err(seen) => left = seen,
                }
            }
        }
        let (send, recv) = mpsc::channel::<Box<dyn FnOnce() + Send>>();
        match std::thread::Builder::new().name("jarambit-mc".into()).spawn(move || worker_loop(recv)) {
            Ok(_) => Ok(send),
            Err(_) => Err(()),
        }
    }

    /// Fallible setup for [`try_run_cols`]. A spawn error or a poisoned pool mutex
    /// returns [`CheckedError::WorkerSetup`] and drops the guard without panicking.
    /// Workers created on an earlier call stay in the pool. There is no retry.
    fn try_ensure(&self, n: usize) -> Result<(), CheckedError> {
        let mut tx = match self.tx.lock() {
            Ok(guard) => guard,
            Err(_) => return Err(CheckedError::WorkerSetup),
        };
        while tx.len() < n {
            match self.spawn_owned_worker() {
                Ok(send) => tx.push(send),
                Err(()) => return Err(CheckedError::WorkerSetup),
            }
        }
        Ok(())
    }
}

/// Evaluate `n` samples across `threads` (capped at `max_threads()`). Each sample returns `K` scalars.
/// Column tails are independent. Thread count does not change the sample multiset.
/// Workers are reused for the life of the process.
pub fn run_cols<const K: usize, F>(g: &Genotype, n: usize, threads: usize, seed: u64, f: F) -> [Tails; K]
where F: Fn(&Genotype, &mut Rng) -> [f64; K] + Sync + Send + 'static {
    let n = n.max(1);
    let threads = threads.max(1).min(max_threads()).min(n);
    let pool = pool();
    pool.ensure(threads);
    let (done_tx, done_rx) = mpsc::channel();
    let f = Arc::new(f);
    let mut start = 0usize;
    for t in 0..threads {
        let count = n / threads + usize::from(t < n % threads);
        let i0 = start;
        start += count;
        let f = Arc::clone(&f);
        let g = g.clone();
        let done_tx = done_tx.clone();
        let job = Box::new(move || {
            let rows = catch_unwind(AssertUnwindSafe(|| {
                (0..count).map(|k| {
                    let mut r = Rng(mix_seed(seed, (i0 + k) as u64));
                    let h = perturb(&g, &mut r);
                    f(&h, &mut r)
                }).collect::<Vec<_>>()
            }));
            let _ = done_tx.send((t, rows));
        });
        pool.tx.lock().unwrap()[t].send(job).expect("mc worker dead");
    }
    drop(done_tx);
    let mut parts: Vec<Option<Vec<[f64; K]>>> = (0..threads).map(|_| None).collect();
    for _ in 0..threads {
        let (t, rows) = done_rx.recv().expect("mc worker dropped");
        match rows {
            Ok(v) => parts[t] = Some(v),
            Err(payload) => std::panic::resume_unwind(payload),
        }
    }
    let all: Vec<[f64; K]> = parts.into_iter().flat_map(|p| p.unwrap()).collect();
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
where F: Fn(&Genotype, &mut Rng) -> f64 + Sync + Send + 'static {
    let t = run_cols(g, n, threads, seed, move |h, r| [f(h, r)]);
    (t[0].mean, t[0].p05)
}

#[derive(Clone, Copy, Debug)]
pub struct CheckedTails { pub mean: f64, pub p05: f64, pub p95: f64 }

#[derive(Clone, Debug)]
pub struct CheckedCols<const K: usize> {
    pub cols: Option<[CheckedTails; K]>,
    pub statistical_credit: bool,
    pub attempted: u64,
    pub valid: u64,
    pub invalid: u64,
    pub model_failed: u64,
    pub numerically_failed: u64,
}

/// Checked column runner. A call from inside a checked worker is
/// [`CheckedError::ReentrantPool`] before the pool lock and before the empty-sample
/// check. `n == 0` is [`CheckedError::EmptySample`] and does not coerce to 1.
/// `K == 0` is [`CheckedError::InvalidConfig`] and does not start the pool.
/// Each requested row is counted once: any nonfinite column invalidates that row.
/// Finite -1000 stays a sample, not a model failure.
/// [`ThreadRequest::Exact`] does not clamp. A worker panic or a lost worker publishes no tails.
/// Setup failure is [`CheckedError::WorkerSetup`]. The legacy [`run`] / [`run_cols`] path is unchanged.
pub fn try_run_cols<const K: usize, F>(g: &Genotype, n: usize, request: ThreadRequest, admitted: usize, seed: u64, f: F) -> Result<CheckedCols<K>, CheckedError>
where F: Fn(&Genotype, &mut Rng) -> [f64; K] + Sync + Send + 'static {
    if IN_MC_WORKER.with(|flag| flag.get()) {
        return Err(CheckedError::ReentrantPool);
    }
    if n == 0 { return Err(CheckedError::EmptySample); }
    if K == 0 { return Err(CheckedError::InvalidConfig); }
    let plan = admit_threads(request, admitted, n)?;
    let threads = plan.actual.ok_or(CheckedError::ThreadBudget)?;
    if threads == 0 { return Err(CheckedError::ThreadBudget); }
    let ranges = plan_ranges(n, threads);
    let workers = ranges.len();
    let pool = pool();
    pool.try_ensure(workers)?;
    let (done_tx, done_rx) = mpsc::channel();
    let f = Arc::new(f);
    for (t, (i0, i1)) in ranges.iter().copied().enumerate() {
        let f = Arc::clone(&f);
        let g = g.clone();
        let done_tx = done_tx.clone();
        let job = Box::new(move || {
            let rows = catch_unwind(AssertUnwindSafe(|| {
                (i0..i1).map(|i| {
                    let mut r = Rng(mix_seed(seed, i as u64));
                    let h = perturb(&g, &mut r);
                    IN_MC_WORKER.with(|flag| flag.set(true));
                    SAMPLE_INDEX.with(|slot| slot.set(Some(i)));
                    let _clear = ClearWorkerFlag;
                    f(&h, &mut r)
                }).collect::<Vec<_>>()
            }));
            let _ = done_tx.send((t, rows));
        });
        if pool.tx.lock().unwrap()[t].send(job).is_err() {
            return Err(CheckedError::WorkerLost);
        }
    }
    drop(done_tx);
    let mut parts: Vec<Option<Vec<[f64; K]>>> = (0..workers).map(|_| None).collect();
    for _ in 0..workers {
        let (t, rows) = done_rx.recv().map_err(|_| CheckedError::WorkerLost)?;
        match rows {
            Ok(v) => parts[t] = Some(v),
            Err(_) => return Err(CheckedError::WorkerPanic),
        }
    }
    let all: Vec<[f64; K]> = parts.into_iter().flat_map(|p| p.unwrap()).collect();
    if all.len() != n { return Err(CheckedError::WorkerLost); }
    let mut row_valid = 0u64;
    let mut row_numerical = 0u64;
    for row in &all {
        if row.iter().all(|x| x.is_finite()) {
            row_valid += 1;
        } else {
            row_numerical += 1;
        }
    }
    let attempted = n as u64;
    if row_numerical != 0 {
        return Ok(CheckedCols {
            cols: None,
            statistical_credit: false,
            attempted,
            valid: row_valid,
            invalid: row_numerical,
            model_failed: 0,
            numerically_failed: row_numerical,
        });
    }
    let mut tails = [CheckedTails { mean: 0.0, p05: 0.0, p95: 0.0 }; K];
    for k in 0..K {
        let rows: Vec<Row> = all.iter().enumerate().map(|(id, row)| Row {
            id: id as u64,
            value: Observation::Finite(row[k]),
        }).collect();
        let summary = reduce_rows(attempted, &rows)?;
        if let Some(CheckedError::UnrepresentableAggregate) = summary.aggregate_error {
            return Err(CheckedError::UnrepresentableAggregate);
        }
        if !summary.statistical_credit {
            return Ok(CheckedCols {
                cols: None,
                statistical_credit: false,
                attempted,
                valid: row_valid,
                invalid: 0,
                model_failed: 0,
                numerically_failed: 0,
            });
        }
        tails[k] = CheckedTails { mean: summary.mean.unwrap(), p05: summary.p05.unwrap(), p95: summary.p95.unwrap() };
    }
    Ok(CheckedCols {
        cols: Some(tails),
        statistical_credit: true,
        attempted,
        valid: row_valid,
        invalid: 0,
        model_failed: 0,
        numerically_failed: 0,
    })
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
    #[test]
    fn requested_rows_count_each_invalid_union_once() {
        use std::sync::atomic::{AtomicUsize, Ordering};
        use std::sync::Arc;
        let g = Genotype::random(&mut Rng(77));
        assert_eq!(try_run_cols::<2, _>(&g, 0, ThreadRequest::Exact(1), 1, 91, |_, _| [1.0, 1.0]), Err(CheckedError::EmptySample));
        assert_eq!(try_run_cols::<0, _>(&g, 0, ThreadRequest::Exact(1), 1, 91, |_, _| []), Err(CheckedError::EmptySample));
        assert_eq!(try_run_cols::<0, _>(&g, 2, ThreadRequest::Exact(1), 1, 91, |_, _| []), Err(CheckedError::InvalidConfig));
        let counter = Arc::new(AtomicUsize::new(0));
        let c = counter.clone();
        let cols = try_run_cols::<2, _>(&g, 4, ThreadRequest::Exact(1), 1, 91, move |_, _| {
            match c.fetch_add(1, Ordering::SeqCst) {
                0 => [f64::NAN, 1.0],
                1 => [1.0, f64::INFINITY],
                _ => [1.0, 1.0],
            }
        }).unwrap();
        assert_eq!((cols.attempted, cols.valid, cols.invalid, cols.numerically_failed, cols.model_failed), (4, 2, 2, 2, 0));
        assert!(!cols.statistical_credit && cols.cols.is_none());
        assert_eq!(cols.valid + cols.invalid, cols.attempted);
        let same = try_run_cols::<2, _>(&g, 1, ThreadRequest::Exact(1), 1, 91, |_, _| [f64::NAN, f64::NEG_INFINITY]).unwrap();
        assert_eq!((same.attempted, same.valid, same.invalid, same.numerically_failed), (1, 0, 1, 1));
        assert!(!same.statistical_credit && same.cols.is_none());
        let finite = try_run_cols::<2, _>(&g, 2, ThreadRequest::Exact(1), 1, 91, |_, _| [1.0, 2.0]).unwrap();
        assert!(finite.statistical_credit && finite.cols.is_some());
        assert_eq!((finite.attempted, finite.valid, finite.invalid, finite.numerically_failed, finite.model_failed), (2, 2, 0, 0, 0));
        assert_eq!(finite.valid + finite.invalid, finite.attempted);
        assert_eq!(finite.cols.unwrap()[0].mean, 1.0);
        assert_eq!(finite.cols.unwrap()[1].mean, 2.0);
        let none = try_run_cols::<1, _>(&g, 2, ThreadRequest::Exact(1), 1, 91, |_, _| [f64::NAN]).unwrap();
        assert_eq!((none.attempted, none.valid, none.invalid, none.numerically_failed, none.model_failed), (2, 0, 2, 2, 0));
        assert!(!none.statistical_credit && none.cols.is_none());
        let sentinel = try_run_cols::<1, _>(&g, 2, ThreadRequest::Exact(1), 1, 91, |_, _| [-1000.0]).unwrap();
        assert!(sentinel.statistical_credit);
        assert_eq!((sentinel.attempted, sentinel.valid, sentinel.invalid, sentinel.model_failed, sentinel.numerically_failed), (2, 2, 0, 0, 0));
        assert_eq!(sentinel.cols.unwrap()[0].mean, -1000.0);
    }
    #[test]
    fn exact_request_above_n_does_not_run_and_four_workers_dispatch() {
        use std::collections::HashSet;
        use std::sync::atomic::{AtomicUsize, Ordering};
        use std::sync::{Arc, Mutex};
        let g = Genotype::random(&mut Rng(81));
        for n in [1usize, 2, 3] {
            let calls = Arc::new(AtomicUsize::new(0));
            let seen = calls.clone();
            let err = try_run_cols::<1, _>(&g, n, ThreadRequest::Exact(4), 4, 99, move |_, _| {
                seen.fetch_add(1, Ordering::SeqCst);
                [1.0]
            });
            assert_eq!(err, Err(CheckedError::InvalidConfig));
            assert_eq!(calls.load(Ordering::SeqCst), 0);
        }
        let budget_calls = Arc::new(AtomicUsize::new(0));
        let budget_seen = budget_calls.clone();
        let budget = try_run_cols::<1, _>(&g, 8, ThreadRequest::Exact(4), 1, 99, move |_, _| {
            budget_seen.fetch_add(1, Ordering::SeqCst);
            [1.0]
        });
        assert_eq!(budget, Err(CheckedError::ThreadBudget));
        assert_eq!(budget_calls.load(Ordering::SeqCst), 0);
        let ids = Arc::new(Mutex::new(Vec::new()));
        let id_seen = ids.clone();
        let calls = Arc::new(AtomicUsize::new(0));
        let seen = calls.clone();
        let got = try_run_cols::<1, _>(&g, 8, ThreadRequest::Exact(4), 4, 99, move |_, _| {
            seen.fetch_add(1, Ordering::SeqCst);
            id_seen.lock().unwrap().push(std::thread::current().id());
            [1.0]
        }).unwrap();
        assert!(got.statistical_credit);
        assert_eq!(calls.load(Ordering::SeqCst), 8);
        let distinct: HashSet<_> = ids.lock().unwrap().iter().copied().collect();
        assert_eq!(distinct.len(), 4);
    }
    #[test]
    fn private_pool_setup_failure_keeps_the_worker_and_the_mutex() {
        let pool = private_pool();
        pool.try_ensure(1).unwrap();
        assert_eq!(pool.tx.lock().unwrap().len(), 1);
        pool.spawn_failures.store(1, std::sync::atomic::Ordering::SeqCst);
        assert_eq!(pool.try_ensure(2), Err(CheckedError::WorkerSetup));
        assert_eq!(pool.tx.lock().unwrap().len(), 1);
        pool.spawn_failures.store(0, std::sync::atomic::Ordering::SeqCst);
        pool.try_ensure(2).unwrap();
        assert_eq!(pool.tx.lock().unwrap().len(), 2);
        let poisoned = private_pool();
        let _ = std::panic::catch_unwind(AssertUnwindSafe(|| {
            let _guard = poisoned.tx.lock().unwrap();
            panic!("poison this private pool only");
        }));
        assert_eq!(poisoned.try_ensure(1), Err(CheckedError::WorkerSetup));
    }
    #[test]
    fn nested_checked_call_is_refused_before_the_pool() {
        let g = Genotype::random(&mut Rng(6));
        let got = try_run_cols::<1, _>(&g, 1, ThreadRequest::Exact(1), 1, 11, |h, _r| {
            let nested = try_run_cols::<1, _>(h, 0, ThreadRequest::Exact(1), 1, 12, |_, _| [0.0]);
            assert_eq!(nested, Err(CheckedError::ReentrantPool));
            [1.0]
        }).unwrap();
        assert!(got.statistical_credit);
        assert_eq!(got.cols.unwrap()[0].mean, 1.0);
    }
    #[test]
    fn indexed_replay_binds_the_post_perturb_draw() {
        use std::collections::HashSet;
        use std::sync::{Arc, Mutex};
        let g = Genotype::random(&mut Rng(4));
        let n = 8usize;
        let seed = 99u64;
        // Frozen independent reference for seed 99, callback draw after perturb.
        // Controller closed form at head 3c9c3ee. Not an executed T03 group.
        let stage27 = [
            0x3feb_d436_3fad_a11eu64,
            0x3fea_c088_b75e_2652,
            0x3feb_c530_75fc_8b7e,
            0x3fe4_5fcb_a420_2be3,
            0x3fb5_30d9_8d6f_2fd0,
            0x3fe1_70f6_5814_1b61,
            0x3fd7_0995_5edd_d904,
            0x3fcd_1537_359a_15c8,
        ];
        for threads in [1usize, 2, 4] {
            let bits = Arc::new(Mutex::new(vec![None; n]));
            let ids = Arc::new(Mutex::new(Vec::new()));
            let bits_cb = bits.clone();
            let ids_cb = ids.clone();
            let got = try_run_cols::<1, _>(&g, n, ThreadRequest::Exact(threads), 4, seed, move |_h, r| {
                let i = SAMPLE_INDEX.with(|slot| slot.get()).expect("sample index");
                ids_cb.lock().unwrap().push(std::thread::current().id());
                bits_cb.lock().unwrap()[i] = Some(r.f64().to_bits());
                [0.0]
            }).unwrap();
            assert!(got.statistical_credit);
            let distinct: HashSet<_> = ids.lock().unwrap().iter().copied().collect();
            assert_eq!(distinct.len(), threads);
            let recorded = bits.lock().unwrap().clone();
            let mut stage_differs = false;
            for i in 0..n {
                let mut oracle = Rng(mix_seed(seed, i as u64));
                let _sample = perturb(&g, &mut oracle);
                let after = oracle.f64().to_bits();
                assert_eq!(recorded[i], Some(after), "index {i} threads {threads}");
                assert_eq!(after, stage27[i], "frozen reference index {i}");
                let mut fresh = Rng(mix_seed(seed, i as u64));
                if fresh.f64().to_bits() != after {
                    stage_differs = true;
                }
            }
            assert!(stage_differs);
        }
    }
}
