//! NSGA-II with optional island migration.
//! PRIMARY fitness stays MC-p05 strength-per-gram (N/g) subject to the firm floors
//! (hiker 180 N, hunter 260 N, ring pull 1500 N).
//! Secondary objectives (mass, blade-first cut margin) shape the front; the logged
//! Pareto view remains nominal strength vs mass. Red-team gate on every candidate
//! and every MC sample. Checkpoint is one text file, overwritten each generation.
//!
//! `Config.fem` (CLI: `JARAMBIT_FEM=1`) sets that nominal strength from one
//! Kirchhoff plate solve at 20 °C. The sample loop stays the beam surrogate and
//! supplies the knockdown. A missed plate mesh is infeasible. Floors are unchanged.
use jarambit_genotype::{Genotype, Rng, TiGrade};
use jarambit_monte_carlo::{try_run_cols, CheckedCols, CheckedError, ThreadRequest};
use jarambit_phenotype::Phenotype;
use jarambit_physics::{calib, evaluate, fine, floors, material, plate_capacities, primary_fitness, Eval};
use jarambit_physics::fine::FineCaps;

pub struct Config {
    pub pop: usize,
    pub gens: usize,
    pub mc_samples: usize,
    pub threads: usize,
    pub seed: u64,
    /// Independent NSGA-II populations. `1` is a single population.
    pub islands: usize,
    /// Ring-migrate the primary-best individual every this many generations. `0` disables.
    pub migrate_every: usize,
    /// Overwritten each completed generation. Also the resume source.
    pub checkpoint: Option<String>,
    pub resume: bool,
    /// Nominal plate strength, with the surrogate Monte Carlo knockdown.
    /// Do not resume a surrogate checkpoint with this set: the stored scores
    /// would mix the two models.
    pub fem: bool,
    /// CALIBRATED search (2026-10-11): detailed plate (`physics::fine`, converged mesh family)
    /// solved per candidate at SEARCH_AREA, divided by the measured mesh bias, times the
    /// surrogate MC p05/nominal knockdown; floors must also hold at 100 C nominal. Overrides `fem`.
    pub fine: bool,
    /// Legal starting genomes. Each island's initial population gets these plus mutants of them
    /// (up to half the population); the rest stay random. Not promoted: they are re-scored.
    pub seeds: Vec<Genotype>,
    /// PR-0.29.2: resume from a checkpoint written under a DIFFERENT manifest (explicit fork; the new manifest
    /// records the parent manifest sha). Without it a manifest mismatch refuses to resume.
    pub fork: bool,
    /// Stop after this many completed generations (checkpoint written), as if interrupted. Test / ops hook.
    pub stop_after: Option<usize>,
}

impl Config {
    pub fn new(pop: usize, gens: usize, mc_samples: usize, threads: usize, seed: u64) -> Self {
        Self { pop, gens, mc_samples, threads, seed, islands: 1, migrate_every: 5, checkpoint: None, resume: false, fem: false, fine: false, seeds: Vec::new(), fork: false, stop_after: None }
    }
}

/// Nominal (20 C, no tolerance) evaluation incl. red-team verdict.
pub fn nominal(g: &Genotype) -> (Phenotype, Result<(), Vec<jarambit_redteam::Reject>>, Eval) {
    let p = Phenotype::from_genotype(g);
    let rt = jarambit_redteam::check(g, &p);
    let e = evaluate(&p, g.edge_angle_deg, (g.serr_inner.depth, g.serr_outer.depth), material(g.material), 20.0);
    (p, rt, e)
}

/// One MC sample's columns: surrogate primary fitness, sharpness, surrogate lateral
/// strength (N), surrogate ring pull (N). The cut-margin column is omitted.
/// Active evaluation does not call `media_sample` or `cut_margin`.
fn sample_metrics(h: &Genotype, r: &mut Rng) -> [f64; 4] {
    let mut p = Phenotype::from_genotype(h);
    if jarambit_redteam::check(h, &p).is_err() { return [-1e3, 0.0, 0.0, 0.0]; }
    p.thickness = jarambit_monte_carlo::thickness_sample(h, r);
    let env = jarambit_monte_carlo::env_sample(r);
    let e = evaluate(&p, h.edge_angle_deg, (h.serr_inner.depth, h.serr_outer.depth), material(h.material), env.temp_c);
    // column 0 uses the calibrated surrogate so it cannot overstate the detailed plate.
    // columns 2-3 feed ratios, where the factor cancels. The 0.0 sharpness on a red-team
    // sample is a real credited value when statistical credit is true.
    [primary_fitness(&calib::calibrated_surrogate(&e)), e.sharpness, e.strength_n, e.ring_pull_n]
}

fn knocked(level: f64, nom: f64, p05: f64) -> f64 { level * (p05 / nom.max(1e-9)) }

/// Nominal plate capacities must clear the firm floors before a candidate is feasible.
fn plate_nominal_floors(plate_s: f64, plate_ring: f64) -> bool {
    plate_s >= floors::HIKER_LATERAL_N && plate_s >= floors::HUNTER_LATERAL_N && plate_ring >= floors::RING_PULL_N
}

/// Robust plate estimate: plate level × (surrogate p05 / surrogate nominal).
/// The ratio carries tolerance and temperature. It is not a scale factor that
/// forces the plate to agree with the beam.
fn robust_plate_eval(e: &Eval, plate_s: f64, plate_ring: f64, s_p05: f64, r_p05: f64) -> Eval {
    let mut pe = e.clone();
    let s_hat = knocked(plate_s, e.strength_n, s_p05);
    let r_hat = knocked(plate_ring, e.ring_pull_n, r_p05);
    pe.strength_n = s_hat;
    pe.ring_pull_n = r_hat;
    pe.hiker_ok = s_hat >= floors::HIKER_LATERAL_N;
    pe.hunter_ok = s_hat >= floors::HUNTER_LATERAL_N;
    pe.ring_ok = r_hat >= floors::RING_PULL_N;
    pe.strength_per_gram = s_hat / pe.mass_g.max(1e-6);
    pe
}

/// One MC sample: red-team reject => -1e3 (dominates p05), else primary fitness at sampled temp/thickness.
pub fn fitness_sample(h: &Genotype, r: &mut Rng) -> f64 { sample_metrics(h, r)[0] }

#[derive(Clone, Copy, Debug, PartialEq, Eq)]
pub enum AbsenceReason {
    EmptySample,
    StatisticalCreditFalse,
    MonteCarloError,
    ThreadBudget,
    WorkerPanic,
    LostWorker,
    NonFiniteAggregate,
}

impl AbsenceReason {
    pub fn token(self) -> &'static str {
        match self {
            Self::EmptySample => "empty_sample",
            Self::StatisticalCreditFalse => "statistical_credit_false",
            Self::MonteCarloError => "monte_carlo_error",
            Self::ThreadBudget => "thread_budget",
            Self::WorkerPanic => "worker_panic",
            Self::LostWorker => "lost_worker",
            Self::NonFiniteAggregate => "non_finite_aggregate",
        }
    }
    pub fn parse(token: &str) -> Result<Self, String> {
        Ok(match token {
            "empty_sample" => Self::EmptySample,
            "statistical_credit_false" => Self::StatisticalCreditFalse,
            "monte_carlo_error" => Self::MonteCarloError,
            "thread_budget" => Self::ThreadBudget,
            "worker_panic" => Self::WorkerPanic,
            "lost_worker" => Self::LostWorker,
            "non_finite_aggregate" => Self::NonFiniteAggregate,
            _ => return Err("unknown_absence_reason".into()),
        })
    }
}

/// Requested-n mean and sharp tail. Direct `Credited` values can be non-finite;
/// readers must use [`SampleStatistics::credited_pair`].
#[derive(Clone, Copy, Debug, PartialEq)]
pub enum SampleStatistics {
    Credited { mean: f64, sharp_p05: f64 },
    Historical { mean_bits: u64, sharp_bits: u64 },
    Unavailable { reason: AbsenceReason },
}

impl SampleStatistics {
    pub fn credited(mean: f64, sharp_p05: f64) -> Result<Self, String> {
        if mean.is_finite() && sharp_p05.is_finite() { Ok(Self::Credited { mean, sharp_p05 }) }
        else { Err("nonfinite_credited_statistics".into()) }
    }
    pub fn historical(mean_bits: u64, sharp_bits: u64) -> Self { Self::Historical { mean_bits, sharp_bits } }
    pub fn unavailable(reason: AbsenceReason) -> Self { Self::Unavailable { reason } }
    pub fn credited_pair(self) -> Option<(f64, f64)> {
        match self {
            Self::Credited { mean, sharp_p05 } if mean.is_finite() && sharp_p05.is_finite() => Some((mean, sharp_p05)),
            _ => None,
        }
    }
}

#[derive(Clone, Copy, Debug, PartialEq, Eq)]
pub enum CutRetiredReason { ModelRetiredNotPrevalence }

#[derive(Clone, Copy, Debug, PartialEq)]
pub enum CutAvailability {
    Historical { value: f64 },
    Retired { reason: CutRetiredReason },
}

impl CutAvailability {
    pub const TOKEN: &'static str = "retired:model_retired_not_prevalence";
    pub fn retired() -> Self { Self::Retired { reason: CutRetiredReason::ModelRetiredNotPrevalence } }
}

#[derive(Clone, Debug)]
pub struct Indiv {
    pub g: Genotype,
    pub fit: f64,
    pub stats: SampleStatistics,
    pub strength_n: f64,
    pub mass_g: f64,
    pub floors_ok: bool,
    pub cut: CutAvailability,
}
impl Indiv {
    /// Qualified only with floors, a positive score, and a finite credited pair.
    pub fn feasible(&self) -> bool { self.floors_ok && self.fit > 0.0 && self.stats.credited_pair().is_some() }
}

pub enum SharpFormat { Csv4, Log2, Report3 }

pub const CURRENT_HISTORY_COLUMNS: &[&str] = &[
    "gen", "terminal", "best_p05_spg", "feasible_mean_p05", "n_feasible", "diversity",
    "rejected_in_gen", "best_strength_n", "best_mass_g", "best_cut_availability",
    "best_stats_mean", "best_stats_sharp_p05", "best_genotype_hash",
];

pub fn format_cut_for_current_log(cut: &CutAvailability) -> Result<String, String> {
    match cut {
        CutAvailability::Retired { .. } => Ok(CutAvailability::TOKEN.into()),
        CutAvailability::Historical { .. } => Err("historical_cut_column_not_current".into()),
    }
}

pub fn format_stats_mean_cell(stats: &SampleStatistics) -> Result<String, String> {
    match *stats {
        SampleStatistics::Credited { mean, sharp_p05 } => {
            if !mean.is_finite() || !sharp_p05.is_finite() { return Err("nonfinite_credited_statistics".into()); }
            Ok(format!("{mean:.5}"))
        }
        SampleStatistics::Unavailable { reason } => Ok(format!("unavailable:{}", reason.token())),
        SampleStatistics::Historical { .. } => Err("historical_statistics_column_not_current".into()),
    }
}

pub fn format_stats_sharp_cell(stats: &SampleStatistics, spec: SharpFormat) -> Result<String, String> {
    match *stats {
        SampleStatistics::Credited { mean, sharp_p05 } => {
            if !mean.is_finite() || !sharp_p05.is_finite() { return Err("nonfinite_credited_statistics".into()); }
            Ok(match spec {
                SharpFormat::Csv4 => format!("{sharp_p05:.4}"),
                SharpFormat::Log2 => format!("{sharp_p05:.2}"),
                SharpFormat::Report3 => format!("{sharp_p05:.3}"),
            })
        }
        SampleStatistics::Unavailable { reason } => Ok(format!("unavailable:{}", reason.token())),
        SampleStatistics::Historical { .. } => Err("historical_statistics_column_not_current".into()),
    }
}

/// Column equality is token equality. `best_sharp_p05` is not a prefix of `best_stats_sharp_p05`.
pub fn history_header_status(existing_columns: &[&str], current_columns: &[&str]) -> Result<(), String> {
    if existing_columns == current_columns { return Ok(()); }
    if existing_columns.iter().any(|c| *c == "best_cut_p05") { return Err("historical_cut_column_not_current".into()); }
    if existing_columns.iter().any(|c| *c == "best_sharp_p05") { return Err("historical_statistics_column_not_current".into()); }
    Err("history_header_mismatch".into())
}

pub struct GenStats<'a> {
    pub gen: usize,
    pub pop: &'a [Indiv],
    pub diversity: f64,
    pub rejected: usize,
    pub quarantine: Vec<(Genotype, String)>,
    /// PR-0.29.3: true for the terminal snapshot (final populations after the last generation).
    pub terminal: bool,
}

/// Mean primary fitness over `feasible()` individuals only; None if there are none (PR-0.29.3; the CLI used a
/// `fit > -100` filter, which counted graded infeasible designs).
pub fn feasible_mean(pop: &[Indiv]) -> Option<f64> {
    let v: Vec<f64> = pop.iter().filter(|i| i.feasible()).map(|i| i.fit).collect();
    if v.is_empty() { None } else { Some(v.iter().sum::<f64>() / v.len() as f64) }
}

/// Stable 16-hex-digit identity of a genotype (SHA-256 of its exact f64 bits + material), for quarantine / logs.
pub fn genotype_hash(g: &Genotype) -> String { jarambit_evidence::hex(&sha2_256(genes_hex(g).as_bytes())[..8]) }

pub fn diversity(pop: &[Indiv]) -> f64 {
    let n = pop.len(); if n < 2 { return 0.0; }
    let mut s = 0.0; let mut c = 0;
    for i in 0..n { for j in (i + 1)..n { s += pop[i].g.distance(&pop[j].g); c += 1; } }
    s / c as f64
}

/// Non-dominated set: maximise strength, minimise mass, among floor-feasible red-team-clean designs.
pub fn pareto(arch: &[Indiv]) -> Vec<Indiv> {
    let f: Vec<&Indiv> = arch.iter().filter(|a| a.feasible()).collect();
    f.iter().filter(|a| !f.iter().any(|b| b.strength_n >= a.strength_n && b.mass_g <= a.mass_g && (b.strength_n > a.strength_n || b.mass_g < a.mass_g)))
        .map(|a| (*a).clone()).collect()
}

fn current_obj(i: &Indiv, k: usize) -> Result<f64, String> {
    match k {
        0 => Ok(i.fit),
        1 => Ok(i.mass_g),
        _ => Err("retired objective has no third component".into()),
    }
}

fn historical_cut_value(i: &Indiv) -> Option<f64> {
    match i.cut { CutAvailability::Historical { value } => Some(value), _ => None }
}

fn historical_obj(i: &Indiv, k: usize) -> Result<f64, String> {
    match k {
        0 => Ok(i.fit),
        1 => Ok(i.mass_g),
        2 => historical_cut_value(i).ok_or_else(|| "historical objective needs a historical cut".into()),
        _ => Err("historical objective has no further component".into()),
    }
}

/// Current domination. A historical cut or historical summary is not a current result.
/// Feasible designs compare fit and mass only. Infeasible designs compare fit, including
/// an explicit `Unavailable` summary.
fn malformed_credited(stats: &SampleStatistics) -> bool {
    match *stats {
        SampleStatistics::Credited { mean, sharp_p05 } => !mean.is_finite() || !sharp_p05.is_finite(),
        _ => false,
    }
}

pub fn dominates(a: &Indiv, b: &Indiv) -> bool {
    if malformed_credited(&a.stats) || malformed_credited(&b.stats) { return false; }
    if historical_cut_value(a).is_some() || historical_cut_value(b).is_some() { return false; }
    if matches!(a.stats, SampleStatistics::Historical { .. }) || matches!(b.stats, SampleStatistics::Historical { .. }) { return false; }
    let (fa, fb) = (a.feasible(), b.feasible());
    if fa != fb { return fa; }
    if !fa { return a.fit > b.fit + 1e-9; }
    let ge = a.fit >= b.fit - 1e-9 && a.mass_g <= b.mass_g + 1e-9;
    let gt = a.fit > b.fit + 1e-9 || a.mass_g < b.mass_g - 1e-9;
    ge && gt
}

/// Preserved three-objective predicate. It reads a historical cut value and is not current ranking.
/// Feasibility here is the old floors-and-positive-fit test. It does not require a credited pair.
pub fn dominates_historical_v1(a: &Indiv, b: &Indiv) -> bool {
    let (Some(ca), Some(cb)) = (historical_cut_value(a), historical_cut_value(b)) else { return false; };
    let old_feasible = |i: &Indiv| i.floors_ok && i.fit > 0.0;
    let (fa, fb) = (old_feasible(a), old_feasible(b));
    if fa != fb { return fa; }
    if !fa { return a.fit > b.fit + 1e-9; }
    let ge = a.fit >= b.fit - 1e-9 && a.mass_g <= b.mass_g + 1e-9 && ca >= cb - 1e-9;
    let gt = a.fit > b.fit + 1e-9 || a.mass_g < b.mass_g - 1e-9 || ca > cb + 1e-9;
    ge && gt
}

fn nondominated_sort(pop: &[Indiv]) -> Vec<Vec<usize>> {
    let n = pop.len();
    let mut n_p = vec![0usize; n];
    let mut beats: Vec<Vec<usize>> = vec![Vec::new(); n];
    let mut fronts: Vec<Vec<usize>> = vec![Vec::new()];
    for i in 0..n {
        for j in 0..n {
            if i == j { continue; }
            if dominates(&pop[i], &pop[j]) { beats[i].push(j); }
            else if dominates(&pop[j], &pop[i]) { n_p[i] += 1; }
        }
        if n_p[i] == 0 { fronts[0].push(i); }
    }
    let mut f = 0;
    while !fronts[f].is_empty() {
        let mut next = Vec::new();
        for &i in &fronts[f] {
            for &j in &beats[i] {
                n_p[j] -= 1;
                if n_p[j] == 0 { next.push(j); }
            }
        }
        f += 1;
        fronts.push(next);
    }
    fronts.pop();
    fronts
}

fn crowding_with(front: &[usize], pop: &[Indiv], axes: usize, obj: fn(&Indiv, usize) -> Result<f64, String>) -> Result<Vec<f64>, String> {
    let m = front.len();
    if m <= 2 { return Ok(vec![f64::INFINITY; m]); }
    let mut cd = vec![0.0; m];
    for k in 0..axes {
        let mut order: Vec<usize> = (0..m).collect();
        order.sort_by(|&a, &b| obj(&pop[front[a]], k).and_then(|x| obj(&pop[front[b]], k).map(|y| x.partial_cmp(&y).unwrap_or(std::cmp::Ordering::Equal))).unwrap_or(std::cmp::Ordering::Equal));
        cd[order[0]] = f64::INFINITY;
        cd[order[m - 1]] = f64::INFINITY;
        let lo = obj(&pop[front[order[0]]], k)?;
        let hi = obj(&pop[front[order[m - 1]]], k)?;
        let span = (hi - lo).abs().max(1e-12);
        for t in 1..m - 1 {
            let prev = obj(&pop[front[order[t - 1]]], k)?;
            let next = obj(&pop[front[order[t + 1]]], k)?;
            cd[order[t]] += (next - prev).abs() / span;
        }
    }
    Ok(cd)
}

fn population_gate(pop: &[Indiv]) -> Result<(), String> {
    for i in pop {
        if let SampleStatistics::Credited { mean, sharp_p05 } = i.stats {
            if !mean.is_finite() || !sharp_p05.is_finite() { return Err("nonfinite_credited_statistics".into()); }
        }
    }
    for i in pop {
        if matches!(i.stats, SampleStatistics::Historical { .. }) || matches!(i.cut, CutAvailability::Historical { .. }) {
            return Err("HistoricalCutInCurrentPopulation".into());
        }
    }
    Ok(())
}

fn rank_crowd(pop: &[Indiv]) -> Result<(Vec<usize>, Vec<f64>), String> {
    population_gate(pop)?;
    let fronts = nondominated_sort(pop);
    let mut rank = vec![usize::MAX; pop.len()];
    let mut crowd = vec![0.0; pop.len()];
    for (r, front) in fronts.iter().enumerate() {
        let cd = crowding_with(front, pop, 2, current_obj)?;
        for (k, &i) in front.iter().enumerate() { rank[i] = r; crowd[i] = cd[k]; }
    }
    Ok((rank, crowd))
}

fn select_n(pop: Vec<Indiv>, n: usize, axes: usize, obj: fn(&Indiv, usize) -> Result<f64, String>, fronts_from: fn(&[Indiv]) -> Vec<Vec<usize>>) -> Result<Vec<Indiv>, String> {
    if pop.len() <= n { return Ok(pop); }
    let fronts = fronts_from(&pop);
    let mut chosen = Vec::with_capacity(n);
    for front in &fronts {
        if chosen.len() + front.len() <= n { chosen.extend(front.iter().copied()); }
        else {
            let cd = crowding_with(front, &pop, axes, obj)?;
            let mut order: Vec<usize> = (0..front.len()).collect();
            order.sort_by(|&a, &b| cd[b].partial_cmp(&cd[a]).unwrap_or(std::cmp::Ordering::Equal));
            let need = n - chosen.len();
            chosen.extend(order.into_iter().take(need).map(|i| front[i]));
            break;
        }
    }
    let mut keep = vec![false; pop.len()];
    for i in chosen { keep[i] = true; }
    Ok(pop.into_iter().enumerate().filter_map(|(i, ind)| keep[i].then_some(ind)).collect())
}

/// Keep `n` individuals. Malformed credited values and historical cuts or statistics
/// are refused before the `len <= n` fast path.
pub fn truncate(pop: Vec<Indiv>, n: usize) -> Result<Vec<Indiv>, String> {
    population_gate(&pop)?;
    select_n(pop, n, 2, current_obj, nondominated_sort)
}

fn nondominated_sort_historical(pop: &[Indiv]) -> Vec<Vec<usize>> {
    let n = pop.len();
    let mut n_p = vec![0usize; n];
    let mut beats: Vec<Vec<usize>> = vec![Vec::new(); n];
    let mut fronts: Vec<Vec<usize>> = vec![Vec::new()];
    for i in 0..n {
        for j in 0..n {
            if i == j { continue; }
            if dominates_historical_v1(&pop[i], &pop[j]) { beats[i].push(j); }
            else if dominates_historical_v1(&pop[j], &pop[i]) { n_p[i] += 1; }
        }
        if n_p[i] == 0 { fronts[0].push(i); }
    }
    let mut f = 0;
    while !fronts[f].is_empty() {
        let mut next = Vec::new();
        for &i in &fronts[f] {
            for &j in &beats[i] { n_p[j] -= 1; if n_p[j] == 0 { next.push(j); } }
        }
        f += 1;
        fronts.push(next);
    }
    fronts.pop();
    fronts
}

fn truncate_historical_v1(pop: Vec<Indiv>, n: usize) -> Result<Vec<Indiv>, String> {
    select_n(pop, n, 3, historical_obj, nondominated_sort_historical)
}

fn tournament(pop: &[Indiv], rank: &[usize], crowd: &[f64], r: &mut Rng) -> usize {
    let n = pop.len();
    let at = |r: &mut Rng| { let x = (r.f64() * n as f64) as usize; if x >= n { n - 1 } else { x } };
    let i = at(r); let j = at(r);
    if rank[i] < rank[j] { i }
    else if rank[j] < rank[i] { j }
    else if crowd[i] >= crowd[j] { i } else { j }
}

struct Island { rng: Rng, pop: Vec<Indiv> }

fn absence_of(err: CheckedError) -> AbsenceReason {
    match err {
        CheckedError::EmptySample => AbsenceReason::EmptySample,
        CheckedError::ThreadBudget => AbsenceReason::ThreadBudget,
        CheckedError::WorkerPanic => AbsenceReason::WorkerPanic,
        CheckedError::WorkerLost => AbsenceReason::LostWorker,
        CheckedError::QuantileOverflow | CheckedError::UnrepresentableAggregate => AbsenceReason::NonFiniteAggregate,
        _ => AbsenceReason::MonteCarloError,
    }
}

fn checked_metrics(g: &Genotype, sample_seed: u64, mc: usize, threads: usize) -> (Option<CheckedCols<4>>, SampleStatistics) {
    match try_run_cols(g, mc, ThreadRequest::Exact(threads), jarambit_monte_carlo::max_threads(), sample_seed, sample_metrics) {
        Ok(cols) if cols.statistical_credit => {
            let tails = cols.cols.unwrap();
            match SampleStatistics::credited(tails[0].mean, tails[1].p05) {
                Ok(stats) => (Some(cols), stats),
                Err(_) => (None, SampleStatistics::unavailable(AbsenceReason::NonFiniteAggregate)),
            }
        }
        Ok(_) => (None, SampleStatistics::unavailable(AbsenceReason::StatisticalCreditFalse)),
        Err(err) => (None, SampleStatistics::unavailable(absence_of(err))),
    }
}

fn retired(g: Genotype, fit: f64, stats: SampleStatistics, strength_n: f64, mass_g: f64, floors_ok: bool) -> Indiv {
    Indiv { g, fit, stats, strength_n, mass_g, floors_ok, cut: CutAvailability::retired() }
}

fn evaluate_one(g: Genotype, sample_seed: u64, mc: usize, threads: usize, q: &mut Vec<(Genotype, String)>, fem: bool) -> Indiv {
    let (p, rt, e) = nominal(&g);
    let crazy = !e.mass_g.is_finite() || !(5.0..=250.0).contains(&e.mass_g);
    if let Err(v) = &rt { q.push((g.clone(), format!("{v:?}"))); }
    else if crazy { q.push((g.clone(), format!("crazy phenotype mass {:.2} g", e.mass_g))); }
    let (cols, stats) = checked_metrics(&g, sample_seed, mc, threads);
    let Some(cols) = cols else {
        let strength = if !fem || rt.is_err() || crazy { e.strength_n } else { 0.0 };
        return retired(g, -1e3, stats, strength, e.mass_g, false);
    };
    let tails = cols.cols.unwrap();
    if !fem {
        let fit = if rt.is_err() || crazy { -1e3 } else { tails[0].p05 };
        return retired(g, fit, stats, e.strength_n, e.mass_g, e.floors_ok() && rt.is_ok() && !crazy);
    }
    if rt.is_err() || crazy {
        return retired(g, -1e3, stats, e.strength_n, e.mass_g, false);
    }
    let Some(c) = plate_capacities(&p, material(g.material), 20.0, (g.serr_inner.depth, g.serr_outer.depth)) else {
        q.push((g.clone(), "plate mesh miss".into()));
        return retired(g, -1e3, stats, 0.0, e.mass_g, false);
    };
    let ps = c.blade_lat_n.min(c.grip_lat_n);
    let pe = robust_plate_eval(&e, ps, c.ring_pull_n, tails[2].p05, tails[3].p05);
    retired(g, primary_fitness(&pe), stats, ps, e.mass_g, plate_nominal_floors(ps, c.ring_pull_n))
}

/// Calibrated robust capacities from a detailed-plate solve: (lateral, ring) in N, each the min of
/// the MC-knocked 20 C level and the 100 C nominal level, after dividing by the mesh bias.
pub fn calibrated_levels(c: &FineCaps, e: &Eval, s_p05: f64, r_p05: f64, m: &jarambit_physics::Material) -> (f64, f64) {
    let lat20 = c.lateral_n / calib::MESH_BIAS_LAT_MAX;
    let ring20 = c.ring_pull_n / calib::MESH_BIAS_RING_MAX;
    let hot = m.yield_at(100.0) / m.yield_at(20.0);
    let lat = knocked(lat20, e.strength_n, s_p05).min(lat20 * hot);
    let ring = knocked(ring20, e.ring_pull_n, r_p05).min(ring20 * hot);
    (lat, ring)
}

/// Firm floors on calibrated levels: lateral >= 180 AND >= 260 N, ring >= 1500 N.
pub fn calibrated_floors_ok(lat: f64, ring: f64) -> bool {
    lat >= floors::HIKER_LATERAL_N && lat >= floors::HUNTER_LATERAL_N && ring >= floors::RING_PULL_N
}

/// One graded-fine expression. A nonfinite mean never reaches `rej`.
fn fine_infeasible_fitness(hot_lat: f64, hot_ring: f64, lat: f64, ring: f64, mean: f64) -> Result<f64, String> {
    if !mean.is_finite() { return Err("nonfinite_credited_statistics".into()); }
    let d = |l: f64, r: f64| (1.0 - l / floors::HUNTER_LATERAL_N).max(0.0) + (1.0 - r / floors::RING_PULL_N).max(0.0);
    let rej = (-mean / 1e3).clamp(0.0, 1.0);
    Ok(-1.0 - 5.0 * d(hot_lat, hot_ring) - 5.0 * d(lat, ring) - 10.0 * rej)
}

fn evaluate_fine(g: Genotype, sample_seed: u64, mc: usize, threads: usize, q: &mut Vec<(Genotype, String)>, caps: Option<FineCaps>) -> Indiv {
    let (p, rt, e) = nominal(&g);
    let crazy = !e.mass_g.is_finite() || !(5.0..=250.0).contains(&e.mass_g);
    if let Err(v) = &rt { q.push((g.clone(), format!("{v:?}"))); }
    else if crazy { q.push((g.clone(), format!("crazy phenotype mass {:.2} g", e.mass_g))); }
    let (cols, stats) = checked_metrics(&g, sample_seed, mc, threads);
    let bad = |g: Genotype, fit: f64| retired(g, fit, stats, 0.0, e.mass_g, false);
    if let Err(v) = &rt {
        // short-blade-only rejects are shaped by the shortfall so the search can climb into the
        // legal (>= 3.375 in on all three) region; they stay infeasible and are never winners.
        let fit = if jarambit_redteam::only_blade_short(v) { -50.0 - jarambit_redteam::blade_shortfall_mm(&p) } else { -1e3 };
        return bad(g, fit);
    }
    if crazy || cols.is_none() { return bad(g, -1e3); }
    let tails = cols.unwrap().cols.unwrap();
    let Some(c) = caps else { q.push((g.clone(), "detailed plate mesh miss".into())); return bad(g, -1e3); };
    let (lat, ring) = calibrated_levels(&c, &e, tails[2].p05, tails[3].p05, material(g.material));
    let ok = calibrated_floors_ok(lat, ring);
    let fit = if ok { lat / e.mass_g.max(1e-6) } else {
        // graded: nominal-hot deficit + robust deficit + share of MC draws the red team rejects.
        // rej runs only on this credited path.
        let m = material(g.material);
        let hot = m.yield_at(100.0) / m.yield_at(20.0);
        let (lh, rh) = (c.lateral_n / calib::MESH_BIAS_LAT_MAX * hot, c.ring_pull_n / calib::MESH_BIAS_RING_MAX * hot);
        fine_infeasible_fitness(lh, rh, lat, ring, tails[0].mean).expect("credited mean")
    };
    retired(g, fit, stats, lat, e.mass_g, ok)
}

/// Evaluate a batch. In calibrated (`fine`) mode the detailed-plate solves run in parallel first
/// (`threads` workers, red-team-clean candidates only), then the MC knockdown per candidate.
fn eval_batch(items: Vec<(Genotype, u64)>, cfg: &Config, q: &mut Vec<(Genotype, String)>) -> Vec<Indiv> {
    if !cfg.fine {
        return items.into_iter().map(|(g, s)| evaluate_one(g, s, cfg.mc_samples, cfg.threads, q, cfg.fem)).collect();
    }
    let n = items.len();
    let next = std::sync::atomic::AtomicUsize::new(0);
    let caps: Vec<std::sync::Mutex<Option<FineCaps>>> = (0..n).map(|_| std::sync::Mutex::new(None)).collect();
    std::thread::scope(|s| {
        for _ in 0..cfg.threads.max(1).min(n.max(1)) {
            s.spawn(|| loop {
                let i = next.fetch_add(1, std::sync::atomic::Ordering::Relaxed);
                if i >= n { break; }
                let g = &items[i].0;
                let p = Phenotype::from_genotype(g);
                if jarambit_redteam::check(g, &p).is_err() { continue; }
                let c = fine::capacities(&p, material(g.material), 20.0, (g.serr_inner.depth, g.serr_outer.depth), fine::SEARCH_AREA);
                *caps[i].lock().unwrap() = c;
            });
        }
    });
    items.into_iter().zip(caps).map(|((g, s), c)| evaluate_fine(g, s, cfg.mc_samples, cfg.threads, q, c.into_inner().unwrap())).collect()
}

fn parse_genes(csv: &str) -> Result<Genotype, String> {
    let cols: Vec<&str> = csv.split(',').collect();
    // 22 = current (blade_angle_deg at index 20); 21 = legacy pre-knob checkpoint (un-raked blade).
    // 25 = current (neck genes 21-23); 22 = pre-neck (blade angle at 20); 21 = pre-knob.
    let n = match cols.len() { 21 => 20, 22 => 21, 25 => 24, k => return Err(format!("gene columns {k}")) };
    let mut v = vec![0.0; n];
    for i in 0..n { v[i] = cols[i].parse().map_err(|_| format!("gene {i}"))?; }
    let mat = match cols[n] {
        "Ti-3Al-2.5V" => TiGrade::Ti3Al2_5V,
        "Ti-6Al-4V" => TiGrade::Ti6Al4V,
        other => return Err(format!("material {other}")),
    };
    Ok(Genotype::from_vec(&v, mat))
}

fn parse_indiv(line: &str) -> Result<Indiv, String> {
    let mut it = line.splitn(8, char::is_whitespace);
    let num = |s: Option<&str>| s.ok_or("short indiv")?.parse::<f64>().map_err(|_| "num".to_string());
    let fit = num(it.next())?;
    let mean = num(it.next())?;
    let strength_n = num(it.next())?;
    let mass_g = num(it.next())?;
    let floors_ok = it.next().ok_or("floors")? == "1";
    let cut_p05 = num(it.next())?;
    let sharp_p05 = num(it.next())?;
    let g = parse_genes(it.next().ok_or("genes")?)?;
    Ok(Indiv {
        g, fit, strength_n, mass_g, floors_ok,
        stats: SampleStatistics::historical(mean.to_bits(), sharp_p05.to_bits()),
        cut: CutAvailability::Historical { value: cut_p05 },
    })
}

// ---- PR-0.29.2: lossless checkpoint (every f64 as its IEEE-754 bits in hex) bound to the run manifest ----

/// The run manifest of the legacy NSGA-II search. Every field that changes the trajectory is in it; `threads`
/// is not (results are thread-count stable). Resume refuses a checkpoint whose manifest sha differs.
/// The five policy params name the retired cut and the typed-credit method. They do not qualify the run.
pub fn manifest(cfg: &Config) -> jarambit_evidence::RunManifest {
    let seeds: Vec<String> = cfg.seeds.iter().map(genes_hex).collect();
    use jarambit_evidence::RunManifest;
    RunManifest::new("evolve", cfg.seed, "legacy-floors-180-260-1500")
        .param("pop", cfg.pop).param("gens", cfg.gens).param("mc_samples", cfg.mc_samples).param("islands", cfg.islands.max(1))
        .param("migrate_every", cfg.migrate_every).param("fem", cfg.fem).param("fine", cfg.fine)
        .param("seeds_sha256", jarambit_evidence::hex(&sha2_256(seeds.join("\n").as_bytes())))
        .param("floors_n", format!("{}/{}/{}", floors::HIKER_LATERAL_N, floors::HUNTER_LATERAL_N, floors::RING_PULL_N))
        .param("calib_mesh_bias", format!("{}/{}", calib::MESH_BIAS_LAT_MAX, calib::MESH_BIAS_RING_MAX))
        .param("search_area", fine::SEARCH_AREA)
        .param("objective_id", "search_objective.v4_cut_retired_stats_typed")
        .param("scenario_id", "scenario.active_no_cut_media_stats_typed")
        .param("cut_availability", CutAvailability::TOKEN)
        .param("objective_sha256", "688525497ed8a4a9be221f2c06e8eb9d64c0c370cd18a397c42651f2896eddb9")
        .param("scenario_sha256", "17a33a835407f26a47be01a73c46add197b3be7bee4a6c610e19b32ccb521384")
}
fn sha2_256(b: &[u8]) -> Vec<u8> { use sha2::Digest; sha2::Sha256::digest(b).to_vec() }

fn hx(x: f64) -> String { format!("{:016x}", x.to_bits()) }
fn unhx(s: &str) -> Result<f64, String> { u64::from_str_radix(s, 16).map(f64::from_bits).map_err(|_| format!("bad f64 bits {s:?}")) }
fn genes_hex(g: &Genotype) -> String { let mut v: Vec<String> = g.to_vec().iter().map(|x| hx(*x)).collect(); v.push(g.material.name().into()); v.join(",") }
fn parse_genes_hex(s: &str) -> Result<Genotype, String> {
    let cols: Vec<&str> = s.split(',').collect(); let n = cols.len().checked_sub(1).ok_or("genes")?;
    let v: Vec<f64> = cols[..n].iter().map(|c| unhx(c)).collect::<Result<_, _>>()?;
    let mat = match cols[n] { "Ti-3Al-2.5V" => TiGrade::Ti3Al2_5V, "Ti-6Al-4V" => TiGrade::Ti6Al4V, o => return Err(format!("material {o}")) };
    let g = Genotype::from_vec(&v, mat);
    if g.to_vec().iter().map(|x| x.to_bits()).ne(v.iter().map(|x| x.to_bits())) { return Err("genome does not round-trip bit-exactly".into()); }
    Ok(g)
}
fn hex16(s: &str) -> Result<u64, String> {
    if s.len() != 16 || !s.bytes().all(|b| b.is_ascii_hexdigit()) { return Err(format!("bad f64 bits {s:?}")); }
    u64::from_str_radix(s, 16).map_err(|_| format!("bad f64 bits {s:?}"))
}

fn stats_token(stats: SampleStatistics) -> Result<String, String> {
    match stats {
        SampleStatistics::Credited { mean, sharp_p05 } => {
            if !mean.is_finite() || !sharp_p05.is_finite() { return Err("nonfinite_credited_statistics".into()); }
            Ok(format!("credited:{:016x}:{:016x}", mean.to_bits(), sharp_p05.to_bits()))
        }
        SampleStatistics::Unavailable { reason } => Ok(format!("unavailable:{}", reason.token())),
        SampleStatistics::Historical { .. } => Err("historical_statistics_column_not_current".into()),
    }
}

fn parse_stats_token(tok: &str) -> Result<SampleStatistics, String> {
    if let Some(rest) = tok.strip_prefix("unavailable:") {
        return Ok(SampleStatistics::unavailable(AbsenceReason::parse(rest)?));
    }
    if let Some(rest) = tok.strip_prefix("credited:") {
        let mut parts = rest.split(':');
        let mean_s = parts.next().unwrap_or("");
        let sharp_s = parts.next().unwrap_or("");
        if parts.next().is_some() || mean_s.len() != 16 || sharp_s.len() != 16 { return Err("statistics_token_not_credited".into()); }
        let mean = f64::from_bits(hex16(mean_s)?);
        let sharp = f64::from_bits(hex16(sharp_s)?);
        if !mean.is_finite() || !sharp.is_finite() { return Err("nonfinite_credited_statistics".into()); }
        return Ok(SampleStatistics::Credited { mean, sharp_p05: sharp });
    }
    Err("statistics_token_not_credited".into())
}

fn cut_token(cut: CutAvailability) -> Result<String, String> {
    match cut {
        CutAvailability::Retired { .. } => Ok(CutAvailability::TOKEN.into()),
        CutAvailability::Historical { .. } => Err("HistoricalCutInCurrentPopulation".into()),
    }
}

fn parse_cut_token(tok: &str) -> Result<CutAvailability, String> {
    if tok == CutAvailability::TOKEN { Ok(CutAvailability::retired()) } else { Err("active cut value in current checkpoint".into()) }
}

fn floors_flag(ok: bool) -> u8 { if ok { 1 } else { 0 } }
fn parse_floors(s: &str) -> Result<bool, String> { match s { "1" => Ok(true), "0" => Ok(false), o => Err(format!("floors {o}")) } }

fn indiv_v3(i: &Indiv) -> Result<String, String> {
    Ok(format!("{} {} {} {} {} {} {}", hx(i.fit), stats_token(i.stats)?, hx(i.strength_n), hx(i.mass_g), floors_flag(i.floors_ok), cut_token(i.cut)?, genes_hex(&i.g)))
}

fn parse_indiv_v3(line: &str) -> Result<Indiv, String> {
    let f: Vec<&str> = line.splitn(7, ' ').collect();
    if f.len() != 7 { return Err(format!("indiv fields {}", f.len())); }
    Ok(Indiv {
        fit: f64::from_bits(hex16(f[0])?), stats: parse_stats_token(f[1])?, strength_n: f64::from_bits(hex16(f[2])?), mass_g: f64::from_bits(hex16(f[3])?),
        floors_ok: parse_floors(f[4])?, cut: parse_cut_token(f[5])?, g: parse_genes_hex(f[6])?,
    })
}

/// Re-encode a v2 individual from the stored bits. A current save does not call this.
fn indiv_v2_historical(i: &Indiv) -> Result<String, String> {
    let SampleStatistics::Historical { mean_bits, sharp_bits } = i.stats else { return Err("historical checkpoint requires historical statistics".into()); };
    let cut = historical_cut_value(i).ok_or("historical checkpoint requires historical cut")?;
    Ok(format!("{} {:016x} {} {} {} {:016x} {:016x} {}", hx(i.fit), mean_bits, hx(i.strength_n), hx(i.mass_g), floors_flag(i.floors_ok), cut.to_bits(), sharp_bits, genes_hex(&i.g)))
}

fn parse_indiv_v2(line: &str) -> Result<Indiv, String> {
    let f: Vec<&str> = line.splitn(8, ' ').collect();
    if f.len() != 8 { return Err(format!("indiv fields {}", f.len())); }
    if f[1].contains(':') || f[5].contains(':') || f[6].contains(':') { return Err("retired token in historical checkpoint".into()); }
    let mean_bits = hex16(f[1])?;
    let cut_bits = hex16(f[5])?;
    let sharp_bits = hex16(f[6])?;
    Ok(Indiv {
        fit: unhx(f[0])?, stats: SampleStatistics::historical(mean_bits, sharp_bits), strength_n: unhx(f[2])?, mass_g: unhx(f[3])?,
        floors_ok: parse_floors(f[4])?, cut: CutAvailability::Historical { value: f64::from_bits(cut_bits) }, g: parse_genes_hex(f[7])?,
    })
}

fn save_ckpt(path: &str, next_gen: usize, man: &jarambit_evidence::RunManifest, islands: &[Island], archive: &[Indiv]) -> Result<(), String> {
    for isl in islands { population_gate(&isl.pop)?; }
    population_gate(archive)?;
    let mut s = String::new();
    s.push_str("jarambit-ckpt 3\n");
    s.push_str(&format!("manifest_sha256 {}\n", man.sha256()));
    s.push_str(&format!("manifest {}\n", man.canonical_json()));
    s.push_str(&format!("next_gen {next_gen}\n"));
    s.push_str(&format!("islands {}\n", islands.len()));
    for (i, isl) in islands.iter().enumerate() {
        s.push_str(&format!("island {i} rng {:016x} n {}\n", isl.rng.0, isl.pop.len()));
        for ind in &isl.pop { s.push_str(&indiv_v3(ind)?); s.push('\n'); }
    }
    s.push_str(&format!("archive {}\n", archive.len()));
    for ind in archive { s.push_str(&indiv_v3(ind)?); s.push('\n'); }
    s.push_str("end\n");
    if let Some(dir) = std::path::Path::new(path).parent() { let _ = std::fs::create_dir_all(dir); }
    let tmp = format!("{path}.tmp");
    { use std::io::Write; let mut f = std::fs::File::create(&tmp).unwrap_or_else(|e| panic!("checkpoint write {tmp}: {e}"));
      f.write_all(s.as_bytes()).and_then(|_| f.sync_all()).unwrap_or_else(|e| panic!("checkpoint write {tmp}: {e}")); }
    std::fs::rename(&tmp, path).unwrap_or_else(|e| panic!("checkpoint rename {path}: {e}"));
    Ok(())
}

struct Loaded { format_version: u8, next_gen: usize, manifest_sha: String, manifest_json: String, islands: Vec<Island>, archive: Vec<Indiv> }

fn kv<'a>(l: Option<&'a str>, key: &str) -> Result<&'a str, String> {
    let l = l.ok_or_else(|| format!("missing {key}"))?; l.strip_prefix(key).and_then(|r| r.strip_prefix(' ')).ok_or_else(|| format!("expected {key}, got {l:?}"))
}

fn bounded_reserve<T>(declared: usize, remaining: usize) -> Result<Vec<T>, String> {
    if declared > remaining {
        return Err(format!("checkpoint count {declared} exceeds remaining records {remaining}"));
    }
    let mut out = Vec::new();
    out.try_reserve_exact(declared).map_err(|_| format!("checkpoint count {declared} exceeds remaining records {remaining}"))?;
    Ok(out)
}

fn take_line<'a>(lines: &'a [&str], at: &mut usize) -> Option<&'a str> {
    let line = lines.get(*at).copied();
    if line.is_some() { *at += 1; }
    line
}

fn load_ckpt(path: &str) -> Result<Loaded, String> {
    let text = std::fs::read_to_string(path).map_err(|e| format!("{path}: {e}"))?;
    let lines: Vec<&str> = text.lines().collect();
    let mut at = 0usize;
    let format_version = match take_line(&lines, &mut at) {
        Some("jarambit-ckpt 3") => 3,
        Some("jarambit-ckpt 2") => 2,
        Some("jarambit-ckpt 1") => return Err("checkpoint format 1 is lossy (rounded decimals) and has no manifest; resume and fork are refused. Extract best genomes with --seed-ckpt and re-evaluate. --fork does not extract v1 genomes.".into()),
        m => return Err(format!("bad magic {m:?}")),
    };
    let manifest_sha = kv(take_line(&lines, &mut at), "manifest_sha256")?.to_string();
    let manifest_json = kv(take_line(&lines, &mut at), "manifest")?.to_string();
    let next_gen: usize = kv(take_line(&lines, &mut at), "next_gen")?.parse().map_err(|_| "next_gen")?;
    let nisl: usize = kv(take_line(&lines, &mut at), "islands")?.parse().map_err(|_| "islands")?;
    let mut islands: Vec<Island> = bounded_reserve(nisl, lines.len().saturating_sub(at))?;
    for i in 0..nisl {
        let hdr = take_line(&lines, &mut at).ok_or("island header")?;
        let p: Vec<&str> = hdr.split(' ').collect();
        if p.len() != 6 || p[0] != "island" || p[1] != i.to_string() || p[2] != "rng" || p[4] != "n" { return Err(format!("island header {hdr}")); }
        let rng_bits = if format_version == 3 {
            hex16(p[3])?
        } else {
            u64::from_str_radix(p[3], 16).map_err(|_| "rng".to_string())?
        };
        let n: usize = p[5].parse().map_err(|_| "pop n")?;
        let mut pop: Vec<Indiv> = bounded_reserve(n, lines.len().saturating_sub(at))?;
        for _ in 0..n {
            let line = take_line(&lines, &mut at).ok_or("truncated population")?;
            pop.push(if format_version == 3 { parse_indiv_v3(line)? } else { parse_indiv_v2(line)? });
        }
        islands.push(Island { rng: Rng(rng_bits), pop });
    }
    let an: usize = kv(take_line(&lines, &mut at), "archive")?.parse().map_err(|_| "archive n")?;
    let mut archive: Vec<Indiv> = bounded_reserve(an, lines.len().saturating_sub(at))?;
    for _ in 0..an {
        let line = take_line(&lines, &mut at).ok_or("truncated archive")?;
        archive.push(if format_version == 3 { parse_indiv_v3(line)? } else { parse_indiv_v2(line)? });
    }
    if take_line(&lines, &mut at) != Some("end") { return Err("checkpoint not terminated (torn write?)".into()); }
    if format_version == 3 {
        if let Some(extra) = take_line(&lines, &mut at) {
            return Err(format!("checkpoint trailing record {extra:?}"));
        }
    }
    Ok(Loaded { format_version, next_gen, manifest_sha, manifest_json, islands, archive })
}

/// Highest-fitness genotype in the saved island populations (format 2, or the legacy lossy format 1).
pub fn checkpoint_best(path: &str) -> Result<Genotype, String> {
    let pop: Vec<Indiv> = match load_ckpt(path) {
        Ok(l) => l.islands.into_iter().flat_map(|i| i.pop).collect(),
        Err(e) if e.contains("format 1") => load_ckpt_v1_pop(path)?,
        Err(e) => return Err(e),
    };
    pop.iter().max_by(|a, b| a.fit.partial_cmp(&b.fit).unwrap_or(std::cmp::Ordering::Equal)).map(|i| i.g.clone()).ok_or_else(|| "empty checkpoint".into())
}

/// Legacy format-1 reader: populations only (for seeding / best-genome extraction, never for resume).
fn load_ckpt_v1_pop(path: &str) -> Result<Vec<Indiv>, String> {
    let text = std::fs::read_to_string(path).map_err(|e| e.to_string())?;
    let mut lines = text.lines().filter(|l| !l.is_empty()).skip(1);
    let _next = lines.next(); let nisl: usize = lines.next().ok_or("islands")?.split_whitespace().nth(1).ok_or("islands")?.parse().map_err(|_| "islands")?;
    let _seed = lines.next(); let _mig = lines.next();
    let mut out = Vec::new();
    for _ in 0..nisl { let hdr = lines.next().ok_or("island header")?; let n: usize = hdr.split_whitespace().nth(5).ok_or("n")?.parse().map_err(|_| "n")?;
        for _ in 0..n { out.push(parse_indiv(lines.next().ok_or("truncated population")?)?); } }
    Ok(out)
}

/// Score and source identity of `raw` against the live manifest.
/// Unknown keys are rejected before a typed decode, so a planted header cannot hide them.
/// The returned tag does not contain the substring `manifest mismatch`.
fn score_carry_ok(raw: &str, header_sha: &str, live: &jarambit_evidence::RunManifest) -> Result<(), String> {
    let loaded_v = jarambit_evidence::identity::strict_json(raw.as_bytes()).map_err(|_| "manifest_json_rejected".to_string())?;
    let live_v = jarambit_evidence::identity::strict_json(live.canonical_json().as_bytes()).map_err(|_| "manifest_json_rejected".to_string())?;
    let loaded_obj = loaded_v.as_object().ok_or_else(|| "manifest_json_rejected".to_string())?;
    let live_obj = live_v.as_object().ok_or_else(|| "manifest_json_rejected".to_string())?;
    const TOP: &[&str] = &["schema", "tool", "tool_version", "requirement_set", "op_version", "command", "seed", "params", "scientific", "runtime"];
    if loaded_obj.keys().any(|k| !TOP.contains(&k.as_str())) { return Err("unknown_manifest_field".into()); }
    const ID: &[&str] = &["schema", "tool", "tool_version", "requirement_set", "op_version", "command"];
    for key in ID {
        if loaded_obj.get(*key) != live_obj.get(*key) { return Err("source_identity_mismatch".into()); }
    }
    if loaded_obj.get("scientific").is_some_and(|value| !value.is_null())
        || live_obj.get("scientific").is_some_and(|value| !value.is_null())
        || loaded_obj.get("runtime").is_some_and(|value| !value.is_null())
        || live_obj.get("runtime").is_some_and(|value| !value.is_null())
    {
        return Err("source_identity_mismatch".into());
    }
    let loaded_params = loaded_obj.get("params").and_then(|v| v.as_object()).ok_or_else(|| "manifest_json_rejected".to_string())?;
    let live_params = live_obj.get("params").and_then(|v| v.as_object()).ok_or_else(|| "manifest_json_rejected".to_string())?;
    const SCORE: &[&str] = &["mc_samples", "fem", "fine", "floors_n", "calib_mesh_bias", "search_area", "objective_id", "scenario_id", "cut_availability", "objective_sha256", "scenario_sha256"];
    const ALLOWED: &[&str] = &["pop", "gens", "islands", "migrate_every", "seeds_sha256"];
    const ANNOT: &[&str] = &["forked_from_manifest_sha256", "forked_at_gen"];
    for key in loaded_params.keys() {
        let name = key.as_str();
        if !SCORE.contains(&name) && !ALLOWED.contains(&name) && !ANNOT.contains(&name) { return Err("unknown_manifest_param".into()); }
    }
    for key in SCORE {
        match (loaded_params.get(*key), live_params.get(*key)) {
            (None, _) => return Err("missing_score_param".into()),
            (Some(a), Some(b)) if a == b => {}
            _ => return Err("score_config_mismatch".into()),
        }
    }
    let parsed = jarambit_evidence::identity::strict_decode::<jarambit_evidence::RunManifest>(raw.as_bytes()).map_err(|_| "manifest_json_rejected".to_string())?;
    if parsed.sha256() != header_sha { return Err("manifest_body_sha_mismatch".into()); }
    Ok(())
}

/// Run the search; panics on a refused resume (see [`try_run`]).
pub fn run(cfg: &Config, log: impl FnMut(&GenStats)) -> (Indiv, Vec<Indiv>) { try_run(cfg, log).unwrap_or_else(|e| panic!("{e}")) }

/// Run the search. Resume (PR-0.29.2) is lossless and manifest-bound: `resume` with no checkpoint, a torn or
/// legacy checkpoint, or a manifest mismatch (without `fork`) is an error, never a silent fresh start.
pub fn try_run(cfg: &Config, mut log: impl FnMut(&GenStats)) -> Result<(Indiv, Vec<Indiv>), String> {
    let n_islands = cfg.islands.max(1);
    let pop_n = cfg.pop.max(2);
    let mut man = manifest(cfg);
    let mut q = Vec::new();
    let mut archive: Vec<Indiv> = Vec::new();
    let mut start = 0usize;
    let mut islands: Vec<Island> = if cfg.resume || cfg.fork {
        let path = cfg.checkpoint.as_deref().ok_or("resume requested but no checkpoint path configured")?;
        if !std::path::Path::new(path).exists() { return Err(format!("resume requested but checkpoint {path} does not exist")); }
        let loaded = load_ckpt(path).map_err(|e| format!("resume {path}: {e}"))?;
        if loaded.format_version != 3 {
            return Err("historical checkpoint format 2 cannot resume or fork. Extract best genomes with --seed-ckpt and re-evaluate.".into());
        }
        if let Err(reason) = score_carry_ok(&loaded.manifest_json, &loaded.manifest_sha, &man) {
            if cfg.fork { return Err(format!("resume {path}: seed-ckpt refusal ({reason})")); }
            return Err(format!("manifest mismatch: {reason}"));
        }
        for isl in &loaded.islands { population_gate(&isl.pop)?; }
        population_gate(&loaded.archive)?;
        if loaded.manifest_sha != man.sha256() {
            if !cfg.fork { return Err(format!("resume {path}: manifest mismatch (checkpoint {} != run {}); refusing. Checkpoint manifest: {}; this run: {}. Use --fork to branch deliberately.",
                &loaded.manifest_sha[..12], &man.sha256()[..12], loaded.manifest_json, man.canonical_json())); }
            man = man.param("forked_from_manifest_sha256", loaded.manifest_sha.clone()).param("forked_at_gen", loaded.next_gen);
        }
        if loaded.islands.len() != n_islands { return Err(format!("checkpoint has {} islands, config asks for {n_islands}", loaded.islands.len())); }
        if loaded.islands.iter().any(|isl| isl.pop.is_empty()) {
            return Err(format!("resume {path}: empty current population"));
        }
        start = loaded.next_gen;
        archive = loaded.archive;
        loaded.islands
    } else { Vec::new() };
    if islands.is_empty() {
        islands = (0..n_islands).map(|i| {
            let mut rng = Rng(cfg.seed.wrapping_add((i as u64 + 1).wrapping_mul(0x9E37_79B9_7F4A_7C15)));
            let n_seed = if cfg.seeds.is_empty() { 0 } else { pop_n / 2 };
            let items: Vec<(Genotype, u64)> = (0..pop_n).map(|k| {
                let g = if k < n_seed {
                    let base = &cfg.seeds[k % cfg.seeds.len()];
                    if k < cfg.seeds.len() { let mut b = base.clone(); b.clamp(); b } else { base.mutate(&mut rng, 0.06) }
                } else { Genotype::random(&mut rng) };
                let s = rng.next_u64();
                (g, s)
            }).collect();
            let pop = eval_batch(items, cfg, &mut q);
            Island { rng, pop }
        }).collect();
        archive.extend(islands.iter().flat_map(|isl| isl.pop.iter().cloned()));
    }
    let mut stopped = false;
    for gen in start..cfg.gens {
        let mut combined: Vec<Indiv> = islands.iter().flat_map(|isl| isl.pop.iter().cloned()).collect();
        combined.sort_by(|a, b| b.fit.partial_cmp(&a.fit).unwrap_or(std::cmp::Ordering::Equal));
        let rejected = q.len();
        log(&GenStats { gen, pop: &combined, diversity: diversity(&combined), rejected, quarantine: std::mem::take(&mut q), terminal: false });
        if n_islands > 1 && cfg.migrate_every > 0 && gen > 0 && gen % cfg.migrate_every == 0 {
            let migrants: Vec<Indiv> = islands.iter().map(|isl| {
                isl.pop.iter().max_by(|a, b| a.fit.partial_cmp(&b.fit).unwrap_or(std::cmp::Ordering::Equal)).unwrap().clone()
            }).collect();
            for i in 0..n_islands {
                let dst_i = (i + 1) % n_islands;
                let worst = islands[dst_i].pop.iter().enumerate().min_by(|(_, a), (_, b)| a.fit.partial_cmp(&b.fit).unwrap_or(std::cmp::Ordering::Equal)).map(|(k, _)| k);
                if let Some(w) = worst {
                    if migrants[i].fit > islands[dst_i].pop[w].fit { islands[dst_i].pop[w] = migrants[i].clone(); }
                }
            }
        }
        let sigma = 0.10 * (1.0 - gen as f64 / (cfg.gens.max(1) as f64)) + 0.02;
        for isl in islands.iter_mut() {
            let (rank, crowd) = rank_crowd(&isl.pop)?;
            let mut items: Vec<(Genotype, u64)> = Vec::with_capacity(isl.pop.len());
            while items.len() < isl.pop.len() {
                let g = if isl.rng.f64() < 0.1 { Genotype::random(&mut isl.rng) }
                else {
                    let ia = tournament(&isl.pop, &rank, &crowd, &mut isl.rng);
                    let ib = tournament(&isl.pop, &rank, &crowd, &mut isl.rng);
                    isl.pop[ia].g.crossover(&isl.pop[ib].g, &mut isl.rng).mutate(&mut isl.rng, sigma)
                };
                let s = isl.rng.next_u64();
                items.push((g, s));
            }
            let kids = eval_batch(items, cfg, &mut q);
            archive.extend(kids.iter().cloned());
            let mut both = std::mem::take(&mut isl.pop);
            both.extend(kids);
            let keep = pop_n.min(both.len()).max(2);
            isl.pop = truncate(both, keep)?;
        }
        if let Some(path) = &cfg.checkpoint { save_ckpt(path, gen + 1, &man, &islands, &archive)?; }
        if cfg.stop_after == Some(gen + 1) { stopped = true; break; }
    }
    // terminal snapshot: the final populations (the returned best is always in it); not emitted when interrupted
    if !stopped {
    let mut combined: Vec<Indiv> = islands.iter().flat_map(|isl| isl.pop.iter().cloned()).collect();
    combined.sort_by(|a, b| b.fit.partial_cmp(&a.fit).unwrap_or(std::cmp::Ordering::Equal));
    log(&GenStats { gen: cfg.gens, pop: &combined, diversity: diversity(&combined), rejected: q.len(), quarantine: std::mem::take(&mut q), terminal: true });
    }
    let best = islands.iter().flat_map(|isl| isl.pop.iter()).max_by(|a, b| a.fit.partial_cmp(&b.fit).unwrap_or(std::cmp::Ordering::Equal)).unwrap().clone();
    Ok((best, pareto(&archive)))
}

#[cfg(test)]
mod tests {
    use super::*;

    fn retired_ind(fit: f64, mass: f64, floors: bool) -> Indiv {
        Indiv {
            g: Genotype::random(&mut Rng(1)), fit,
            stats: SampleStatistics::credited(fit, 0.5).expect("finite test stats"),
            strength_n: fit.max(0.0) * mass, mass_g: mass, floors_ok: floors,
            cut: CutAvailability::retired(),
        }
    }

    fn historical_ind(fit: f64, mass: f64, cut: f64, floors: bool) -> Indiv {
        Indiv {
            g: Genotype::random(&mut Rng(1)), fit,
            stats: SampleStatistics::credited(fit, 0.5).expect("finite test stats"),
            strength_n: fit.max(0.0) * mass, mass_g: mass, floors_ok: floors,
            cut: CutAvailability::Historical { value: cut },
        }
    }

    fn direct(stats: SampleStatistics, cut: CutAvailability, fit: f64, floors: bool) -> Indiv {
        Indiv { g: Genotype::random(&mut Rng(1)), fit, stats, strength_n: 10.0, mass_g: 30.0, floors_ok: floors, cut }
    }

    #[test] fn feasible_dominates_infeasible_and_front_keeps_extremes() {
        let good = retired_ind(10.0, 30.0, true);
        let heavy = retired_ind(9.0, 40.0, true);
        let bad = retired_ind(-3.0, 20.0, false);
        assert!(dominates(&good, &bad));
        assert!(!dominates(&bad, &good));
        assert!(dominates(&good, &heavy));
        assert!(!dominates(&heavy, &good));
        assert!(good.feasible() && good.stats.credited_pair().is_some());
        let pop = vec![good, heavy, bad, retired_ind(8.0, 25.0, true), retired_ind(7.0, 50.0, true)];
        let kept = truncate(pop, 2).expect("retired population");
        assert_eq!(kept.len(), 2);
        assert!(kept.iter().any(|i| (i.fit - 10.0).abs() < 1e-9), "unique primary best is an objective extreme");
        assert!(kept.iter().any(|i| (i.fit - 8.0).abs() < 1e-9 && (i.mass_g - 25.0).abs() < 1e-9));
        assert!(kept.iter().all(|i| (i.fit - 9.0).abs() > 1e-6));
    }

    #[test] fn historical_predicate_keeps_three_objectives_and_current_paths_refuse_it() {
        let good = historical_ind(10.0, 30.0, 0.2, true);
        let heavy = historical_ind(9.0, 40.0, 0.4, true);
        let bad = historical_ind(-3.0, 20.0, 0.9, false);
        assert!(!dominates(&good, &heavy) && !dominates(&heavy, &good));
        assert!(!dominates_historical_v1(&good, &heavy) && !dominates_historical_v1(&heavy, &good));
        assert!(dominates_historical_v1(&good, &bad));
        assert!(!dominates_historical_v1(&bad, &good));
        assert_eq!(current_obj(&good, 2).unwrap_err(), "retired objective has no third component");
        let one = historical_ind(1.0, 30.0, 0.2, true);
        assert_eq!(truncate(vec![one.clone()], 1).unwrap_err(), "HistoricalCutInCurrentPopulation");
        assert_eq!(rank_crowd(&[one.clone()]).unwrap_err(), "HistoricalCutInCurrentPopulation");
        assert_eq!(truncate(vec![one.clone(), historical_ind(2.0, 20.0, 0.1, true)], 1).unwrap_err(), "HistoricalCutInCurrentPopulation");
        let pop = vec![good, heavy, bad, historical_ind(8.0, 25.0, 0.1, true), historical_ind(7.0, 50.0, 0.0, true)];
        let kept = truncate_historical_v1(pop, 2).unwrap();
        assert_eq!(kept.len(), 2);
        assert!(kept.iter().any(|i| (i.fit - 10.0).abs() < 1e-9));
    }

    #[test] fn direct_nonfinite_credited_is_refused_before_the_fast_path() {
        let nan = direct(SampleStatistics::Credited { mean: f64::NAN, sharp_p05: 0.5 }, CutAvailability::retired(), 4.0, true);
        let inf = direct(SampleStatistics::Credited { mean: 1.0, sharp_p05: f64::INFINITY }, CutAvailability::retired(), 4.0, true);
        assert!(nan.stats.credited_pair().is_none() && inf.stats.credited_pair().is_none());
        assert!(!nan.feasible() && !inf.feasible());
        assert_eq!(truncate(vec![nan.clone()], 1).unwrap_err(), "nonfinite_credited_statistics");
        assert_eq!(rank_crowd(&[inf.clone()]).unwrap_err(), "nonfinite_credited_statistics");
        assert_eq!(truncate(vec![nan.clone(), historical_ind(1.0, 20.0, 0.2, true)], 5).unwrap_err(), "nonfinite_credited_statistics");
        assert_eq!(format_stats_mean_cell(&nan.stats).unwrap_err(), "nonfinite_credited_statistics");
        assert_eq!(format_stats_sharp_cell(&inf.stats, SharpFormat::Log2).unwrap_err(), "nonfinite_credited_statistics");
        assert_eq!(format_cut_for_current_log(&historical_ind(1.0, 1.0, 0.2, true).cut).unwrap_err(), "historical_cut_column_not_current");
        assert_eq!(indiv_v3(&nan).unwrap_err(), "nonfinite_credited_statistics");
        let finite = SampleStatistics::credited(-1000.0, 0.0).unwrap();
        assert_eq!(finite.credited_pair().unwrap().0.to_bits(), (-1000.0f64).to_bits());
        let ind = direct(finite, CutAvailability::retired(), -1000.0, false);
        let line = indiv_v3(&ind).unwrap();
        assert!(line.contains(&format!("credited:{:016x}:{:016x}", (-1000.0f64).to_bits(), 0.0f64.to_bits())));
        match parse_indiv_v3(&line).unwrap().stats {
            SampleStatistics::Credited { mean, sharp_p05 } => {
                assert_eq!(mean.to_bits(), (-1000.0f64).to_bits());
                assert_eq!(sharp_p05.to_bits(), 0.0f64.to_bits());
            }
            other => panic!("{other:?}"),
        }
        assert_eq!(format_stats_sharp_cell(&finite, SharpFormat::Csv4).unwrap(), "0.0000");
        assert_eq!(format_stats_mean_cell(&SampleStatistics::credited(0.0, 0.5).unwrap()).unwrap(), "0.00000");
        let unavailable = direct(SampleStatistics::unavailable(AbsenceReason::ThreadBudget), CutAvailability::retired(), -1e3, false);
        let kept = truncate(vec![unavailable.clone()], 1).unwrap();
        assert!(kept.iter().all(|i| !i.feasible()));
        let token_line = indiv_v3(&unavailable).unwrap();
        let token = token_line.split_whitespace().nth(1).unwrap();
        assert_eq!(token, "unavailable:thread_budget");
        assert!(token.parse::<f64>().is_err());
        assert!(matches!(parse_indiv_v3(&token_line).unwrap().stats, SampleStatistics::Unavailable { reason: AbsenceReason::ThreadBudget }));
        assert_eq!(parse_indiv_v3(&token_line.replacen("unavailable:thread_budget", "0000000000000000", 1)).unwrap_err(), "statistics_token_not_credited");
        assert_eq!(parse_indiv_v3(&token_line.replacen("unavailable:thread_budget", "historical:0000000000000000:0000000000000000", 1)).unwrap_err(), "statistics_token_not_credited");
        assert_eq!(parse_indiv_v3(&token_line.replacen(CutAvailability::TOKEN, "0000000000000000", 1)).unwrap_err(), "active cut value in current checkpoint");
        assert_eq!(format_cut_for_current_log(&retired_ind(1.0, 1.0, true).cut).unwrap(), CutAvailability::TOKEN);
        assert_eq!(format_stats_sharp_cell(&SampleStatistics::unavailable(AbsenceReason::EmptySample), SharpFormat::Report3).unwrap(), "unavailable:empty_sample");
    }

    #[test]
    fn direct_malformed_credit_does_not_dominate() {
        let unavailable = direct(SampleStatistics::unavailable(AbsenceReason::ThreadBudget), CutAvailability::retired(), -1000.0, false);
        let finite_infeasible = direct(SampleStatistics::credited(1.0, 0.5).unwrap(), CutAvailability::retired(), 4.0, false);
        let sentinel = direct(SampleStatistics::credited(-1000.0, 0.0).unwrap(), CutAvailability::retired(), -1000.0, false);
        assert!(dominates(&finite_infeasible, &unavailable));
        assert!(!dominates(&unavailable, &finite_infeasible));
        assert!(dominates(&finite_infeasible, &sentinel));
        assert!(!dominates(&sentinel, &finite_infeasible));
        let historical = historical_ind(4.0, 20.0, 0.1, true);
        assert!(!dominates(&historical, &finite_infeasible));
        assert!(!dominates(&finite_infeasible, &historical));
        let bad_stats = [
            SampleStatistics::Credited { mean: f64::NAN, sharp_p05: 0.5 },
            SampleStatistics::Credited { mean: 0.5, sharp_p05: f64::NAN },
            SampleStatistics::Credited { mean: f64::INFINITY, sharp_p05: 0.5 },
            SampleStatistics::Credited { mean: 0.5, sharp_p05: f64::INFINITY },
            SampleStatistics::Credited { mean: f64::NEG_INFINITY, sharp_p05: 0.5 },
            SampleStatistics::Credited { mean: 0.5, sharp_p05: f64::NEG_INFINITY },
        ];
        for stats in bad_stats {
            let bad = direct(stats, CutAvailability::retired(), 4.0, true);
            assert!(!bad.feasible());
            assert!(!dominates(&bad, &unavailable));
            assert!(!dominates(&unavailable, &bad));
            assert!(!dominates(&bad, &finite_infeasible));
            assert!(!dominates(&finite_infeasible, &bad));
            assert!(!dominates(&bad, &sentinel));
            assert!(!dominates(&sentinel, &bad));
        }
        assert_eq!(truncate(vec![finite_infeasible.clone()], 1).unwrap().len(), 1);
        println!("S04_CASE id=T03-04-dominates malformed_either_order=0 finite_infeasible_beats_unavailable=1 sentinel_bits={:016x}", (-1000.0f64).to_bits());
    }

    #[test]
    fn fine_rejection_share_is_the_one_formula() {
        let planted = Eval {
            mass_g: 40.0, strength_n: 300.0, blade_lat_n: 300.0, grip_lat_n: 300.0, ring_pull_n: 2000.0,
            inplane_n: 0.0, strength_per_gram: 7.5, hiker_ok: true, hunter_ok: true, ring_ok: true,
            safety_factor: 1.0, sharpness: 0.5, serration_score: 0.0, ergonomics: 0.0,
        };
        assert!(planted.strength_n >= floors::HIKER_LATERAL_N && planted.strength_n >= floors::HUNTER_LATERAL_N);
        assert!(planted.blade_lat_n >= floors::HUNTER_LATERAL_N && planted.ring_pull_n >= floors::RING_PULL_N);
        let zero = fine_infeasible_fitness(planted.blade_lat_n, planted.ring_pull_n, planted.strength_n, planted.ring_pull_n, 0.0).unwrap();
        let full = fine_infeasible_fitness(planted.blade_lat_n, planted.ring_pull_n, planted.strength_n, planted.ring_pull_n, -1000.0).unwrap();
        assert_eq!(zero, -1.0);
        assert_eq!(full, -11.0);
        // Case values reject a hyphen, so a leading minus is spelled neg.
        let case_num = |value: f64| {
            let text = format!("{value}");
            match text.strip_prefix('-') {
                Some(rest) => format!("neg{rest}"),
                None => text,
            }
        };
        assert_eq!(fine_infeasible_fitness(planted.blade_lat_n, planted.ring_pull_n, planted.strength_n, planted.ring_pull_n, f64::NAN).unwrap_err(), "nonfinite_credited_statistics");
        assert!(fine_infeasible_fitness(planted.blade_lat_n, planted.ring_pull_n, planted.strength_n, planted.ring_pull_n, f64::INFINITY).is_err());
        assert!(fine_infeasible_fitness(planted.blade_lat_n, planted.ring_pull_n, planted.strength_n, planted.ring_pull_n, f64::NEG_INFINITY).is_err());
        println!("S04_CASE id=T03-04-rej mean0={} mean_neg1000={} lat={} ring={} planted_mass_g={} label=software_fixture", case_num(zero), case_num(full), planted.strength_n, planted.ring_pull_n, planted.mass_g);
    }

    #[test] fn v2_historical_bits_reencode_and_headers_are_token_equal() {
        let bits = 0x3fc999999999999au64;
        assert_eq!(0.2f64.to_bits(), bits);
        let ind = direct(SampleStatistics::historical(bits, 0.5f64.to_bits()), CutAvailability::Historical { value: f64::from_bits(bits) }, 1.0, true);
        let line = indiv_v2_historical(&ind).unwrap();
        assert!(line.contains("3fc999999999999a"));
        assert_eq!(indiv_v2_historical(&parse_indiv_v2(&line).unwrap()).unwrap(), line);
        assert!(history_header_status(CURRENT_HISTORY_COLUMNS, CURRENT_HISTORY_COLUMNS).is_ok());
        let mut old = CURRENT_HISTORY_COLUMNS.to_vec();
        let i = old.iter().position(|c| *c == "best_cut_availability").unwrap();
        old[i] = "best_cut_p05";
        assert_eq!(history_header_status(&old, CURRENT_HISTORY_COLUMNS).unwrap_err(), "historical_cut_column_not_current");
        old[i] = "best_sharp_p05";
        assert_eq!(history_header_status(&old, CURRENT_HISTORY_COLUMNS).unwrap_err(), "historical_statistics_column_not_current");
        assert!(history_header_status(&["best_stats_sharp_p05"], &["best_stats_sharp_p05"]).is_ok());
        assert_eq!(history_header_status(&["best_stats_sharp_p05", "extra"], &["best_stats_sharp_p05"]).unwrap_err(), "history_header_mismatch");
        let j = manifest(&Config::new(4, 2, 8, 1, 1)).canonical_json();
        assert!(j.contains("\"objective_id\":\"search_objective.v4_cut_retired_stats_typed\""));
        assert!(j.contains("\"scenario_id\":\"scenario.active_no_cut_media_stats_typed\""));
        assert!(j.contains("\"cut_availability\":\"retired:model_retired_not_prevalence\""));
        assert!(j.contains("\"objective_sha256\":\"688525497ed8a4a9be221f2c06e8eb9d64c0c370cd18a397c42651f2896eddb9\""));
        assert!(j.contains("\"scenario_sha256\":\"17a33a835407f26a47be01a73c46add197b3be7bee4a6c610e19b32ccb521384\""));
        assert!(j.contains("\"op_version\":1") && j.contains("\"floors_n\":\"180/260/1500\"") && j.contains("\"command\":\"evolve\"") && j.contains("\"search_area\":2.0"));
        assert!(manifest(&Config::new(4, 2, 8, 1, 1)).scientific.is_none());
    }

    fn scratch(name: &str) -> String {
        let d = std::env::temp_dir().join(format!("jarambit_s04_src_{}", std::process::id()));
        std::fs::create_dir_all(&d).unwrap();
        d.join(name).to_string_lossy().into_owned()
    }

    fn write_current(path: &str, cfg: &Config, next_gen: usize) {
        let islands = vec![Island { rng: Rng(1), pop: vec![retired_ind(3.0, 40.0, true)] }];
        save_ckpt(path, next_gen, &manifest(cfg), &islands, &[]).unwrap();
    }

    fn refuse(cfg: &Config) -> String {
        let mut n = 0usize;
        let err = try_run(cfg, |_| n += 1).unwrap_err();
        assert_eq!(n, 0, "{err}");
        err
    }

    fn rewrite(text: &str, json: &str, sha: &str) -> String {
        let mut out = String::new();
        for line in text.lines() {
            if line.starts_with("manifest_sha256 ") { out.push_str(&format!("manifest_sha256 {sha}\n")); }
            else if line.starts_with("manifest ") { out.push_str(&format!("manifest {json}\n")); }
            else { out.push_str(line); out.push('\n'); }
        }
        out
    }

    #[test] fn admission_refuses_score_carry_even_when_the_header_matches() {
        let path = scratch("admit.ckpt");
        let mut cfg = Config::new(4, 2, 8, 1, 99);
        cfg.checkpoint = Some(path.clone());
        write_current(&path, &cfg, cfg.gens);
        cfg.resume = true;
        let (best, _) = try_run(&cfg, |_| {}).unwrap();
        assert!((best.fit - 3.0).abs() < 1e-9);
        cfg.mc_samples = 9;
        let e = refuse(&cfg);
        assert!(e.contains("manifest mismatch") && e.contains("score_config_mismatch") && !e.contains("seed-ckpt"), "{e}");
        cfg.mc_samples = 8;
        cfg.fem = true;
        cfg.resume = false;
        cfg.fork = true;
        let e = refuse(&cfg);
        assert!(e.contains("seed-ckpt") && e.contains("score_config_mismatch") && !e.contains("manifest mismatch"), "{e}");
        cfg.fem = false;
        cfg.fine = true;
        let e = refuse(&cfg);
        assert!(e.contains("seed-ckpt") && !e.contains("manifest mismatch"), "{e}");
        cfg.fine = false;
        let original = std::fs::read_to_string(&path).unwrap();
        let loaded = load_ckpt(&path).unwrap();
        let live_sha = manifest(&cfg).sha256();
        let plant = |json: &str| std::fs::write(&path, rewrite(&original, json, &live_sha)).unwrap();
        plant(&loaded.manifest_json.replace("search_objective.v4_cut_retired_stats_typed", "search_objective.tampered"));
        let e = refuse(&cfg);
        assert!(e.contains("seed-ckpt") && e.contains("score_config_mismatch") && !e.contains("manifest mismatch"), "{e}");
        plant(&loaded.manifest_json.replace("\"search_area\":2.0", "\"search_area\":4.0"));
        let e = refuse(&cfg);
        assert!(e.contains("seed-ckpt") && e.contains("score_config_mismatch") && !e.contains("manifest mismatch"), "{e}");
        plant(&loaded.manifest_json.replace("\"command\":\"evolve\"", "\"command\":\"evolvx\""));
        let e = refuse(&cfg);
        assert!(e.contains("seed-ckpt") && e.contains("source_identity_mismatch") && !e.contains("manifest mismatch"), "{e}");
        plant(&loaded.manifest_json.replace("\"op_version\":1", "\"op_version\":2"));
        let e = refuse(&cfg);
        assert!(e.contains("seed-ckpt") && e.contains("source_identity_mismatch") && !e.contains("manifest mismatch"), "{e}");
        plant(&loaded.manifest_json.replace("\"params\":{", "\"params\":{\"not_a_score\":1,"));
        let e = refuse(&cfg);
        assert!(e.contains("seed-ckpt") && e.contains("unknown_manifest_param") && !e.contains("manifest mismatch"), "{e}");
        cfg.fork = false;
        cfg.resume = true;
        let e = refuse(&cfg);
        assert!(e.contains("manifest mismatch") && e.contains("unknown_manifest_param") && !e.contains("seed-ckpt"), "{e}");
        let mut extra = loaded.manifest_json.clone();
        extra.pop();
        extra.push_str(",\"extra\":1}");
        plant(&extra);
        let e = refuse(&cfg);
        assert!(e.contains("manifest mismatch") && e.contains("unknown_manifest_field"), "{e}");
        cfg.fork = true;
        cfg.resume = false;
        let e = refuse(&cfg);
        assert!(e.contains("seed-ckpt") && e.contains("unknown_manifest_field") && !e.contains("manifest mismatch"), "{e}");
        let missing = loaded.manifest_json.replace("\"objective_sha256\":\"688525497ed8a4a9be221f2c06e8eb9d64c0c370cd18a397c42651f2896eddb9\",", "");
        plant(&missing);
        let e = refuse(&cfg);
        assert!(e.contains("seed-ckpt") && e.contains("missing_score_param") && !e.contains("manifest mismatch"), "{e}");
        std::fs::write(&path, rewrite(&original, &loaded.manifest_json.replace(&format!("\"seed\":{}", cfg.seed), &format!("\"seed\":{}", cfg.seed + 1)), &loaded.manifest_sha)).unwrap();
        let e = refuse(&cfg);
        assert!(e.contains("seed-ckpt") && e.contains("manifest_body_sha_mismatch") && !e.contains("manifest mismatch"), "{e}");
        cfg.fork = false;
        cfg.resume = true;
        let e = refuse(&cfg);
        assert!(e.contains("manifest mismatch") && e.contains("manifest_body_sha_mismatch") && !e.contains("seed-ckpt"), "{e}");
        plant("[");
        cfg.fork = true;
        cfg.resume = false;
        let e = refuse(&cfg);
        assert!(e.contains("seed-ckpt") && e.contains("manifest_json_rejected") && !e.contains("manifest mismatch"), "{e}");
        let path_g = scratch("gens0.ckpt");
        let mut stored = Config::new(4, 1, 8, 1, 99);
        stored.checkpoint = Some(path_g.clone());
        write_current(&path_g, &stored, 2);
        let mut live = Config::new(4, 2, 8, 1, 99);
        live.checkpoint = Some(path_g.clone());
        live.fork = true;
        let (best, _) = try_run(&live, |_| {}).unwrap();
        assert!((best.fit - 3.0).abs() < 1e-9);
        let mut islands_only = original.replace("\nislands 1\n", "\nislands 2\n");
        let row = original.lines().find(|l| l.split_whitespace().nth(1).map(|t| t.starts_with("credited:")).unwrap_or(false)).unwrap();
        islands_only = islands_only.replace("archive 0\n", &format!("island 1 rng 0000000000000002 n 1\n{row}\narchive 0\n"));
        std::fs::write(&path, &islands_only).unwrap();
        cfg.fork = false;
        cfg.resume = true;
        cfg.gens = 2;
        let e = refuse(&cfg);
        assert!(e.contains("checkpoint has 2 islands") && !e.contains("manifest mismatch"), "{e}");
        let _ = std::fs::remove_file(&path);
        let _ = std::fs::remove_file(&path_g);
    }

    #[test] fn v1_and_v2_checkpoints_do_not_resume_or_fork() {
        let v2 = scratch("v2.ckpt");
        let ind = direct(SampleStatistics::historical(0.2f64.to_bits(), 0.5f64.to_bits()), CutAvailability::Historical { value: f64::from_bits(0x3fc999999999999a) }, 1.0, true);
        let line = indiv_v2_historical(&ind).unwrap();
        std::fs::write(&v2, format!("jarambit-ckpt 2\nmanifest_sha256 {}\nmanifest {{}}\nnext_gen 1\nislands 1\nisland 0 rng 0000000000000001 n 1\n{line}\narchive 0\nend\n", "ab".repeat(32))).unwrap();
        assert_eq!(load_ckpt(&v2).unwrap().format_version, 2);
        let mut cfg = Config::new(4, 1, 8, 1, 3);
        cfg.checkpoint = Some(v2.clone());
        cfg.resume = true;
        let e = refuse(&cfg);
        assert!(e.contains("format 2") && e.contains("seed-ckpt") && !e.contains("manifest mismatch"), "{e}");
        cfg.resume = false;
        cfg.fork = true;
        let e = refuse(&cfg);
        assert!(e.contains("format 2") && e.contains("seed-ckpt") && !e.contains("manifest mismatch"), "{e}");
        let v1 = scratch("v1.ckpt");
        let g = Genotype::random(&mut Rng(3));
        let row = format!("1.5 1.5 10 40 1 0.2 0.5 {}", g.to_csv_row());
        std::fs::write(&v1, format!("jarambit-ckpt 1\n0\nislands 1\n1\n1\nisland 0 rng 0000000000000001 n 1\n{row}\n")).unwrap();
        let e = match load_ckpt(&v1) {
            Err(e) => e,
            Ok(_) => panic!("format 1 returned Loaded"),
        };
        assert!(e.contains("format 1") && e.contains("seed-ckpt") && e.contains("--fork does not extract v1 genomes."), "{e}");
        assert_eq!(checkpoint_best(&v1).unwrap().to_vec().len(), 24);
        cfg.checkpoint = Some(v1.clone());
        cfg.fork = true;
        cfg.resume = false;
        let e = refuse(&cfg);
        assert!(e.contains("format 1") && !e.contains("manifest mismatch"), "{e}");
        let _ = std::fs::remove_file(&v2);
        let _ = std::fs::remove_file(&v1);
    }

    #[test]
    fn current_checkpoint_bounds_counts_grammar_and_framing() {
        let path = scratch("frame.ckpt");
        let mut cfg = Config::new(4, 2, 8, 1, 42);
        cfg.checkpoint = Some(path.clone());
        write_current(&path, &cfg, cfg.gens);
        let original = std::fs::read_to_string(&path).unwrap();
        let loaded = load_ckpt(&path).unwrap();
        assert_eq!(loaded.format_version, 3);
        assert_eq!(loaded.archive.len(), 0);
        assert_eq!(loaded.islands[0].pop[0].fit.to_bits(), 3.0f64.to_bits());
        assert_eq!(loaded.islands[0].rng.0, 1);
        let again = indiv_v3(&loaded.islands[0].pop[0]).unwrap();
        assert!(original.contains(&again));
        let refuse_text = |name: &str, body: String| {
            let p = scratch(name);
            std::fs::write(&p, body).unwrap();
            match load_ckpt(&p) {
                Err(e) => e,
                Ok(_) => panic!("{name}: malformed current checkpoint returned Loaded"),
            }
        };
        assert!(refuse_text("trail", format!("{original}AFTER_END\n")).contains("trailing record"));
        assert!(refuse_text("extra-end", format!("{original}end\n")).contains("trailing record"));
        assert!(refuse_text("second", format!("{original}{original}")).contains("trailing record"));
        let credited = original.lines().find(|l| l.split(' ').nth(1).is_some_and(|t| t.starts_with("credited:"))).unwrap();
        let retoken = |index: usize, token: &str| {
            let mut parts: Vec<&str> = credited.splitn(7, ' ').collect();
            parts[index] = token;
            original.replace(credited, &parts.join(" "))
        };
        assert!(refuse_text("short-fit", retoken(0, "0")).contains("bad f64 bits"));
        assert!(refuse_text("long-fit", retoken(0, "00000000000000000")).contains("bad f64 bits"));
        assert!(refuse_text("bad-fit", retoken(0, "zzzzzzzzzzzzzzzz")).contains("bad f64 bits"));
        assert!(refuse_text("short-strength", retoken(2, "0")).contains("bad f64 bits"));
        assert!(refuse_text("short-mass", retoken(3, "0")).contains("bad f64 bits"));
        assert!(refuse_text("short-rng", original.replace("rng 0000000000000001", "rng 0")).contains("bad f64 bits"));
        assert!(refuse_text("long-rng", original.replace("rng 0000000000000001", "rng 00000000000000001")).contains("bad f64 bits"));
        assert!(refuse_text("bad-rng", original.replace("rng 0000000000000001", "rng gggggggggggggggg")).contains("bad f64 bits"));
        assert!(refuse_text("huge-islands", original.replace("\nislands 1\n", "\nislands 18446744073709551615\n")).contains("exceeds remaining records"));
        assert!(refuse_text("huge-pop", original.replace(" n 1\n", " n 18446744073709551615\n")).contains("exceeds remaining records"));
        assert!(refuse_text("huge-archive", original.replace("\narchive 0\n", "\narchive 18446744073709551615\n")).contains("exceeds remaining records"));
        let header_only = original.lines().take_while(|l| !l.split(' ').nth(1).is_some_and(|t| t.starts_with("credited:"))).collect::<Vec<_>>().join("\n");
        assert!(refuse_text("truncated", format!("{header_only}\n")).contains("exceeds remaining records"));
        let empty = scratch("empty-pop.ckpt");
        save_ckpt(&empty, cfg.gens, &manifest(&cfg), &[Island { rng: Rng(1), pop: vec![] }], &[]).unwrap();
        assert_eq!(load_ckpt(&empty).unwrap().archive.len(), 0);
        cfg.checkpoint = Some(empty.clone());
        cfg.resume = true;
        let e = refuse(&cfg);
        assert!(e.contains("empty current population") && !e.contains("manifest mismatch"), "{e}");
        cfg.resume = false;
        cfg.fork = true;
        let e = refuse(&cfg);
        assert!(e.contains("empty current population"), "{e}");
        let v2 = scratch("v2-short.ckpt");
        let historical = direct(SampleStatistics::historical(0.2f64.to_bits(), 0.5f64.to_bits()), CutAvailability::Historical { value: f64::from_bits(0x3fc999999999999a) }, 1.5, true);
        let v2_line = indiv_v2_historical(&historical).unwrap();
        let short_fit = format!("0 {}", v2_line.split_once(' ').unwrap().1);
        std::fs::write(&v2, format!("jarambit-ckpt 2\nmanifest_sha256 {}\nmanifest {{}}\nnext_gen 1\nislands 1\nisland 0 rng 1 n 1\n{short_fit}\narchive 0\nend\nAFTER_END\n", "ab".repeat(32))).unwrap();
        let old = load_ckpt(&v2).unwrap();
        assert_eq!(old.format_version, 2);
        assert_eq!(old.islands[0].rng.0, 1);
        assert_eq!(old.islands[0].pop[0].fit, 0.0);
        println!("S04_CASE id=T03-10-framing v3_roundtrip=1 archive0=1 trailing=refused huge=refused empty_resume=refused v2_short_fit=kept v2_trailing=kept");
        const EXPECTED_MANIFEST_JSON: &str = r#"{"schema":1,"tool":"jarambit","tool_version":"0.31.0","requirement_set":"legacy-floors-180-260-1500","op_version":1,"command":"evolve","seed":1,"params":{"calib_mesh_bias":"1.07/1.062","cut_availability":"retired:model_retired_not_prevalence","fem":false,"fine":false,"floors_n":"180/260/1500","gens":2,"islands":1,"mc_samples":8,"migrate_every":5,"objective_id":"search_objective.v4_cut_retired_stats_typed","objective_sha256":"688525497ed8a4a9be221f2c06e8eb9d64c0c370cd18a397c42651f2896eddb9","pop":4,"scenario_id":"scenario.active_no_cut_media_stats_typed","scenario_sha256":"17a33a835407f26a47be01a73c46add197b3be7bee4a6c610e19b32ccb521384","search_area":2.0,"seeds_sha256":"e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855"}}"#;
        const EXPECTED_MANIFEST_SHA256: &str = "6491551e3180f6807423d2db9205bf798aa23f642ec2ba02ad6542ba17efc909";
        assert_eq!(EXPECTED_MANIFEST_JSON.len(), 746);
        assert!(!EXPECTED_MANIFEST_JSON.ends_with('\n'));
        assert_eq!(jarambit_evidence::hex(&sha2_256(EXPECTED_MANIFEST_JSON.as_bytes())), EXPECTED_MANIFEST_SHA256);
        let digest_cfg = Config::new(4, 2, 8, 1, 1);
        assert!(digest_cfg.seeds.is_empty() && digest_cfg.checkpoint.is_none() && !digest_cfg.resume && !digest_cfg.fork && digest_cfg.stop_after.is_none());
        let produced = manifest(&digest_cfg);
        assert_eq!(produced.schema, 1);
        assert!(produced.scientific.is_none() && produced.runtime.is_none());
        let observed = produced.canonical_json();
        let observed_sha = produced.sha256();
        let bytes_hex: String = observed.bytes().map(|byte| format!("{byte:02x}")).collect();
        println!("S04_CASE id=T03-10-manifest-digest oracle=present expected_sha256={EXPECTED_MANIFEST_SHA256} observed_sha256={observed_sha} observed_len={} reason=schema1_literal_not_scientific_qualification bytes_hex={bytes_hex}", observed.len());
        assert_eq!(observed, EXPECTED_MANIFEST_JSON, "frozen literal mismatch; leave the constant and the serializer unchanged");
        assert_eq!(observed_sha, EXPECTED_MANIFEST_SHA256);
        let _ = std::fs::remove_file(&path);
        let _ = std::fs::remove_file(&empty);
        let _ = std::fs::remove_file(&v2);
    }

    #[test] fn checkpoint_roundtrip_and_short_search() {
        let path = "out/ckpt_evolve_test.txt";
        let _ = std::fs::create_dir_all("out");
        let mut cfg = Config::new(4, 2, 16, 2, 12345);
        cfg.islands = 2;
        cfg.migrate_every = 1;
        cfg.checkpoint = Some(path.into());
        let (best, front) = run(&cfg, |_| {});
        assert!(best.fit.is_finite());
        assert!(front.iter().all(|i| i.feasible()));
        if best.feasible() {
            let (p, rt, _) = nominal(&best.g);
            assert!(rt.is_ok(), "{rt:?} teeth {}/{}", p.inner_teeth, p.outer_teeth);
        }
        let loaded = load_ckpt(path).unwrap();
        let best_g = checkpoint_best(path).unwrap();
        assert_eq!(best_g.to_vec().len(), 24);
        assert_eq!(loaded.next_gen, 2);
        assert_eq!(loaded.format_version, 3);
        assert_eq!(loaded.islands.len(), 2);
        assert!(!loaded.islands[0].pop.is_empty());
        assert!(std::fs::read_to_string(path).unwrap().starts_with("jarambit-ckpt 3\n"));
        cfg.gens = 3;
        cfg.resume = true;
        assert!(try_run(&cfg, |_| {}).unwrap_err().contains("manifest mismatch"), "changing gens must refuse a plain resume");
        cfg.fork = true;
        let (best2, _) = run(&cfg, |_| {});
        assert!(best2.fit.is_finite());
        let saved = std::fs::read_to_string(path).unwrap();
        assert!(saved.contains("forked_from_manifest_sha256") && saved.contains("forked_at_gen"));
        let _ = std::fs::remove_file(path);
    }

    fn eval_at(strength: f64, ring: f64, mass: f64) -> Eval {
        Eval {
            mass_g: mass, strength_n: strength, blade_lat_n: strength, grip_lat_n: strength,
            ring_pull_n: ring, inplane_n: strength, strength_per_gram: strength / mass,
            hiker_ok: true, hunter_ok: true, ring_ok: true, safety_factor: 1.0,
            sharpness: 0.5, serration_score: 0.5, ergonomics: 0.5,
        }
    }

    #[test]
    fn fem_knockdown_keeps_firm_floors() {
        let e = eval_at(800.0, 4000.0, 40.0);
        let pe = robust_plate_eval(&e, 400.0, 2000.0, 720.0, 3600.0);
        assert!(pe.floors_ok());
        let fit = primary_fitness(&pe);
        assert!((fit - 9.0).abs() < 1e-9, "{fit}");
        let pe2 = robust_plate_eval(&e, 400.0, 2000.0, 400.0, 2000.0);
        assert!(!pe2.floors_ok());
        assert!(primary_fitness(&pe2) < 0.0);
        assert!(plate_nominal_floors(260.0, 1500.0));
        assert!(!plate_nominal_floors(180.0, 1500.0));
        assert!(!plate_nominal_floors(260.0, 1499.0));
        assert!(!plate_nominal_floors(259.0, 1500.0));
        assert_eq!(floors::HIKER_LATERAL_N, 180.0);
        assert_eq!(floors::HUNTER_LATERAL_N, 260.0);
        assert_eq!(floors::RING_PULL_N, 1500.0);
    }

    #[test]
    fn fem_candidate_stores_plate_strength() {
        let g = Genotype::random(&mut Rng(11));
        let mut q = Vec::new();
        let ind = evaluate_one(g.clone(), 3, 8, 2, &mut q, true);
        let p = Phenotype::from_genotype(&g);
        if jarambit_redteam::check(&g, &p).is_err() {
            // Blade-length floor (2026-10-11): red-team rejects never reach the plate and score -1e3.
            // Plate-path coverage returns once the phenotype can meet all-three >= 86.225 mm.
            assert_eq!(ind.fit, -1.0e3);
            assert!(!ind.floors_ok);
            assert!(q.iter().any(|(_, w)| w.contains("BladeTooShort")), "{q:?}");
            return;
        }
        match plate_capacities(&p, material(g.material), 20.0, (g.serr_inner.depth, g.serr_outer.depth)) {
            Some(c) => {
                let ps = c.blade_lat_n.min(c.grip_lat_n);
                assert!((ind.strength_n - ps).abs() < 1e-6, "{} vs {ps}", ind.strength_n);
                assert!(ind.fit.is_finite());
            }
            None => {
                assert_eq!(ind.fit, -1.0e3);
                assert!(q.iter().any(|(_, w)| w.contains("plate")));
            }
        }
    }
}
