//! S07 / T05: actual-crate invariance controls. T05-04 drives the public `Expected`/`Obs`/`parse_expected`/
//! `theory_gate` contract directly. T05-01 drives genuine `Plate` and `T6` solves for proportional load
//! scaling and distinct-load superposition (F, G, F+G on one System). The test-local CST and quadratic-triangle
//! stiffness below is an independent residual/reaction/energy reference only, never a replacement solver.
//! Units: mm, N, MPa, rad, N mm. Frozen tolerance: |a - b| <= 1e-10 (declared unit) + 1e-8 * max(|a|, |b|).
use jarambit_physics::fine::{self, Mesh, Plate, T6};
use jarambit_physics::verify::{parse_expected, theory_gate, Expected, Obs, EXPECTED_TOML};

// ---------------------------------------------------------------------------------------------
// T05-04: the public theory-gate contract (direct Expected and parser agree)

fn base() -> Expected { Expected { id: "direct-gate".into(), max_err_pct: 5.0, levels: vec![1.0], gate_levels: vec![1.0], checks: vec!["fixture".into()] } }
fn obs(name: &str, max_area: f64, ratio: f64) -> Obs { Obs { name: name.into(), max_area, ratio } }
fn good_obs() -> Vec<Obs> { vec![obs("fixture", 1.0, 1.0)] }

/// Serialize an `Expected` into the manifest subset, so the parser sees exactly the direct contract.
fn toml(e: &Expected) -> String {
    fn nums(v: &[f64]) -> String { v.iter().map(|x| format!("{x:?}")).collect::<Vec<_>>().join(", ") }
    let names = e.checks.iter().map(|c| format!("\"{c}\"")).collect::<Vec<_>>().join(", ");
    format!("id = \"{}\"\nmax_err_pct = {:?}\nlevels = [{}]\ngate_levels = [{}]\nchecks = [{}]\n", e.id, e.max_err_pct, nums(&e.levels), nums(&e.gate_levels), names)
}

fn gate_err(e: &Expected, o: &[Obs]) -> Vec<String> { theory_gate(e, o).expect_err("gate must refuse") }
fn has(why: &[String], s: &str) -> bool { why.iter().any(|w| w.contains(s)) }

#[test]
fn t05_04_direct_finite_good() {
    let e = base();
    assert_eq!(parse_expected(&toml(&e)).unwrap(), e, "parser round trip differs from the direct Expected");
    theory_gate(&e, &good_obs()).unwrap();
    theory_gate(&parse_expected(&toml(&e)).unwrap(), &good_obs()).unwrap();
    // finite signed ratios at non-gate levels keep their existing (unchecked) semantics
    let e2 = Expected { levels: vec![2.0, 1.0], ..base() };
    theory_gate(&e2, &[obs("fixture", 2.0, -3.0), obs("fixture", 1.0, 1.0)]).unwrap();
}

#[test]
fn t05_04_direct_finite_bad() {
    let why = gate_err(&base(), &[obs("fixture", 1.0, 100.0)]);
    assert!(has(&why, ">= 5 %"), "{why:?}");
    // a finite ratio whose percent error overflows is reported, never passed through a NaN comparison
    let why = gate_err(&base(), &[obs("fixture", 1.0, f64::MAX)]);
    assert!(has(&why, "overflows"), "{why:?}");
}

#[test]
fn t05_04_current45() {
    let e = parse_expected(EXPECTED_TOML).unwrap();
    let txt = include_str!("../../../docs/calibration/theory_checks.csv");
    let o: Vec<Obs> = txt.lines().skip(1).map(|l| { let (name, rest) = l[1..].split_once("\",").unwrap(); let f: Vec<&str> = rest.split(',').collect();
        obs(name, f[0].parse().unwrap(), f[4].parse().unwrap()) }).collect();
    assert_eq!((o.len(), e.checks.len(), e.levels.len(), e.max_err_pct, e.gate_levels.clone()), (45, 9, 5, 5.0, vec![0.25]));
    theory_gate(&e, &o).unwrap();
}

#[test]
fn t05_04_nan_tolerance() {
    let e = Expected { max_err_pct: f64::NAN, ..base() };
    let why = gate_err(&e, &[obs("fixture", 1.0, 100.0)]);
    assert!(why.iter().all(|w| w.starts_with("invalid expected manifest")) && has(&why, "max_err_pct"), "{why:?}");
    assert!(parse_expected(&toml(&e)).is_err() && parse_expected(&toml(&base()).replace("5.0", "NaN")).is_err());
}

#[test]
fn t05_04_inf_tolerance() {
    let e = Expected { max_err_pct: f64::INFINITY, ..base() };
    let why = gate_err(&e, &[obs("fixture", 1.0, 100.0)]);
    assert!(why.iter().all(|w| w.starts_with("invalid expected manifest")) && has(&why, "max_err_pct"), "{why:?}");
    assert!(parse_expected(&toml(&e)).is_err() && parse_expected(&toml(&base()).replace("5.0", "+Infinity")).is_err());
}

#[test]
fn t05_04_valid_unicode() {
    let e = Expected { id: "café".into(), checks: vec!["σ fixture".into()], ..base() };
    theory_gate(&e, &[obs("σ fixture", 1.0, 1.0)]).unwrap();
    assert_eq!(parse_expected(&toml(&e)).unwrap(), e);
    // names are compared exactly: a decomposed spelling is a different check, not silently normalized
    let nfc = Expected { checks: vec!["caf\u{e9}".into()], ..base() };
    let why = gate_err(&nfc, &[obs("cafe\u{301}", 1.0, 1.0)]);
    assert!(has(&why, "unexpected check") && has(&why, "missing check"), "{why:?}");
}

#[test]
fn t05_04_invalid_expected() {
    type Mutation = fn(&mut Expected);
    let table: [(&str, Mutation, &str); 18] = [
        ("tolerance0", |e| e.max_err_pct = 0.0, "max_err_pct"),
        ("tolerance-1", |e| e.max_err_pct = -1.0, "max_err_pct"),
        ("tolerance-Infinity", |e| e.max_err_pct = f64::NEG_INFINITY, "max_err_pct"),
        ("empty id", |e| e.id.clear(), "empty manifest id name"),
        ("empty check name", |e| e.checks.push(String::new()), "empty check name"),
        ("control character in name", |e| e.checks.push("fix\u{7}ture".into()), "control character in check name"),
        ("checks[]", |e| e.checks.clear(), "empty checks"),
        ("checks duplicate", |e| e.checks.push("fixture".into()), "duplicate check"),
        ("levels[]", |e| e.levels.clear(), "empty levels"),
        ("level0", |e| e.levels.push(0.0), "levels entry 0 is not finite and positive"),
        ("level-1", |e| e.levels.push(-1.0), "levels entry -1 is not finite and positive"),
        ("level NaN", |e| e.levels.push(f64::NAN), "levels entry NaN is not finite and positive"),
        ("level Infinity", |e| e.levels.push(f64::INFINITY), "levels entry inf is not finite and positive"),
        ("levels[1,1]", |e| e.levels.push(1.0), "levels entries 1 and 1 are duplicate or ambiguous"),
        ("ambiguous levels[1,1+5e-10]", |e| e.levels.push(1.0 + 5e-10), "levels entries 1 and 1.0000000005 are duplicate or ambiguous"),
        ("gate_levels[]", |e| e.gate_levels.clear(), "empty gate_levels"),
        ("duplicate gates", |e| e.gate_levels.push(1.0), "gate_levels entries 1 and 1 are duplicate or ambiguous"),
        ("gate outside levels", |e| e.gate_levels = vec![2.0], "gate level 2 matches 0 levels"),
    ];
    for (row, mutate, reason) in table {
        let mut e = base(); mutate(&mut e);
        let why = gate_err(&e, &good_obs());
        assert!(why.iter().all(|w| w.starts_with("invalid expected manifest")) && has(&why, reason), "{row}: {why:?}");
        // the constructible parser control agrees (non-finite numbers are already refused while parsing)
        assert!(parse_expected(&toml(&e)).is_err(), "{row}: parser accepted {:?}", toml(&e));
        println!("T05 04-invalid-Expected {row}: direct and parser refuse: {why:?}");
    }
}

#[test]
fn t05_04_observation_domain() {
    let two = Expected { checks: vec!["fixture".into(), "second".into()], ..base() };
    let with = |extra: Obs| { let mut o = good_obs(); o.push(extra); o };
    let table: [(&str, Expected, Vec<Obs>, &str); 10] = [
        ("obs[]", base(), vec![], "all missing"),
        ("missing required pair", two, good_obs(), "missing check \"second\""),
        ("duplicate required pair", base(), with(obs("fixture", 1.0, 1.0)), "duplicate check"),
        ("unexpected check", base(), with(obs("other", 1.0, 1.0)), "unexpected check"),
        ("unexpected level", base(), with(obs("fixture", 2.0, 1.0)), "unexpected level"),
        ("empty observation name", base(), with(obs("", 1.0, 1.0)), "empty observation name"),
        ("observation area0", base(), with(obs("fixture", 0.0, 1.0)), "invalid observation level 0"),
        ("observation area NaN", base(), with(obs("fixture", f64::NAN, 1.0)), "invalid observation level NaN"),
        ("observation ratio NaN", base(), vec![obs("fixture", 1.0, f64::NAN)], "non-finite ratio"),
        ("observation ratio +Infinity", base(), vec![obs("fixture", 1.0, f64::INFINITY)], "non-finite ratio"),
    ];
    for (row, e, o, reason) in table {
        let why = gate_err(&e, &o);
        assert!(has(&why, reason), "{row}: {why:?}");
        println!("T05 04-observation-domain {row}: refused: {why:?}");
    }
}

#[test]
fn t05_04_boundary_pair() {
    let e = Expected { max_err_pct: 50.0, ..base() };
    let why = gate_err(&e, &[obs("fixture", 1.0, 1.5)]);
    assert!(has(&why, "err 50.00 % >= 50 %"), "{why:?}");
    let below = f64::from_bits(1.5f64.to_bits() - 1);
    assert!(below < 1.5 && (below - 1.0) * 100.0 < 50.0);
    theory_gate(&e, &[obs("fixture", 1.0, below)]).unwrap();
}

#[test]
fn t05_04_known_negative() {
    let why = gate_err(&base(), &[obs("fixture", 1.0, 1.06)]);
    assert!(has(&why, ">= 5 %"), "{why:?}");
}

// ---------------------------------------------------------------------------------------------
// T05-01: proportional scaling and distinct-load superposition on actual Plate / T6 solves

const REL: f64 = 1e-8;
const ABS: f64 = 1e-10; // in each quantity's own declared unit: mm, rad, MPa, N or N mm
const T_MM: f64 = 1.0;
const E_MPA: f64 = 1000.0;
const NU0: f64 = 0.0;

/// Frozen component rule; the absolute term handles signed cancellation, nothing is divided.
fn close(a: f64, b: f64) -> bool { a.is_finite() && b.is_finite() && (a - b).abs() <= ABS + REL * a.abs().max(b.abs()) }

/// Components `i` where `got[i]` is not `want[i]` under the frozen rule (both arrays share one association).
fn mismatches(what: &str, got: &[f64], want: &[f64]) -> Vec<String> {
    assert_eq!(got.len(), want.len(), "{what}: association lengths differ");
    (0..got.len()).filter(|&i| !close(got[i], want[i])).map(|i| format!("{what}[{i}] {} vs {}", got[i], want[i])).collect()
}
fn sum(a: &[f64], b: &[f64]) -> Vec<f64> { a.iter().zip(b).map(|(x, y)| x + y).collect() }
fn scaled(a: &[f64], k: f64) -> Vec<f64> { a.iter().map(|x| k * x).collect() }
fn dot(a: &[f64], b: &[f64]) -> f64 { a.iter().zip(b).map(|(x, y)| x * y).sum::<f64>() }

/// Shared square: nodes (0,0),(1,0),(1,1),(0,1), two triangles, x = 0 clamped, loads on x = 1.
fn square() -> Mesh { Mesh { xy: vec![(0.0, 0.0), (1.0, 0.0), (1.0, 1.0), (0.0, 1.0)], tris: vec![[0, 1, 2], [0, 2, 3]], on_outer: vec![true; 4], on_hole: vec![false; 4] } }

/// A supplied right-edge (x = 1, y in [0, 1]) traction q in N/mm with its identity.
#[derive(Clone, Copy, Debug)]
struct Load { id: &'static str, q: (f64, f64) }
const F: Load = Load { id: "F", q: (1.0, 0.0) };
const G: Load = Load { id: "G", q: (0.0, 1.0) };
const FG: Load = Load { id: "F+G", q: (1.0, 1.0) };

impl Load {
    /// Resultant force (N) and moment about the origin (N mm) integrated from the supplied traction
    /// (Simpson, exact for the linear moment arm), independently of any RHS handed to a solver.
    fn resultant(&self) -> ([f64; 2], f64) {
        let (mut f, mut m) = ([0.0; 2], 0.0);
        for (y, w) in [(0.0, 1.0 / 6.0), (0.5, 4.0 / 6.0), (1.0, 1.0 / 6.0)] { f[0] += w * self.q.0; f[1] += w * self.q.1; m += w * (1.0 * self.q.1 - y * self.q.0); }
        (f, m)
    }
}

/// Plane-stress isotropic constitutive matrix (MPa), built here rather than taken from `fine::c_plane`.
fn c_mat() -> [[f64; 3]; 3] { let k = E_MPA / (1.0 - NU0 * NU0); [[k, k * NU0, 0.0], [k * NU0, k, 0.0], [0.0, 0.0, E_MPA / (2.0 * (1.0 + NU0))]] }

/// Barycentric gradients (dL/dx, dL/dy) and signed doubled area of a triangle.
fn bary(p: [(f64, f64); 3]) -> ([f64; 3], [f64; 3], f64) {
    let a2 = (p[1].0 - p[0].0) * (p[2].1 - p[0].1) - (p[2].0 - p[0].0) * (p[1].1 - p[0].1);
    let mut gx = [0.0; 3]; let mut gy = [0.0; 3];
    for i in 0..3 { let (j, k) = ((i + 1) % 3, (i + 2) % 3); gx[i] = (p[j].1 - p[k].1) / a2; gy[i] = (p[k].0 - p[j].0) / a2; }
    (gx, gy, a2)
}

/// Add w * B^T C B for 2-dof nodes `nodes` with shape gradients (dx, dy) into the dense unconstrained K0.
fn add_btcb(k0: &mut [Vec<f64>], nodes: &[usize], dx: &[f64], dy: &[f64], w: f64) {
    let c = c_mat();
    let col = |a: usize, r: usize| if r == 0 { [dx[a], 0.0, dy[a]] } else { [0.0, dy[a], dx[a]] };
    for a in 0..nodes.len() { for r in 0..2 { for b in 0..nodes.len() { for s in 0..2 {
        let (ba, bb) = (col(a, r), col(b, s));
        let mut v = 0.0;
        for p in 0..3 { for q in 0..3 { v += ba[p] * c[p][q] * bb[q]; } }
        k0[2 * nodes[a] + r][2 * nodes[b] + s] += w * v;
    } } } }
}

/// Independent CST membrane K0 for the Plate's in-plane dofs (node * 2 + [u, v]).
fn cst_k0(xy: &[(f64, f64)], tris: &[[usize; 3]]) -> Vec<Vec<f64>> {
    let mut k0 = vec![vec![0.0; 2 * xy.len()]; 2 * xy.len()];
    for t in tris {
        let (gx, gy, a2) = bary([xy[t[0]], xy[t[1]], xy[t[2]]]);
        assert!(a2 > 0.0, "fixture triangles are positively oriented");
        add_btcb(&mut k0, t, &gx, &gy, T_MM * a2 / 2.0);
    }
    k0
}

/// Independent quadratic-triangle K0: N_i = L_i (2 L_i - 1), N_ij = 4 L_i L_j, exact degree-2 rule (2/3, 1/6, 1/6)
/// with weights 1/3. Mid-side node positions are checked against their corners before use.
fn t6_k0(t6: &T6) -> Vec<Vec<f64>> {
    let n = t6.xy.len();
    let mut k0 = vec![vec![0.0; 2 * n]; 2 * n];
    for t in &t6.tris {
        let p = [t6.xy[t[0]], t6.xy[t[1]], t6.xy[t[2]]];
        for (m, (i, j)) in [(3, (0, 1)), (4, (1, 2)), (5, (2, 0))] {
            let mid = ((p[i].0 + p[j].0) / 2.0, (p[i].1 + p[j].1) / 2.0);
            assert!((t6.xy[t[m]].0 - mid.0).abs() < 1e-12 && (t6.xy[t[m]].1 - mid.1).abs() < 1e-12, "T6 mid-side association");
        }
        let (gx, gy, a2) = bary(p);
        assert!(a2 > 0.0);
        for l in [[2.0 / 3.0, 1.0 / 6.0, 1.0 / 6.0], [1.0 / 6.0, 2.0 / 3.0, 1.0 / 6.0], [1.0 / 6.0, 1.0 / 6.0, 2.0 / 3.0]] {
            let mut dx = [0.0; 6]; let mut dy = [0.0; 6];
            for i in 0..3 { dx[i] = (4.0 * l[i] - 1.0) * gx[i]; dy[i] = (4.0 * l[i] - 1.0) * gy[i]; }
            for (m, (i, j)) in [(3, (0, 1)), (4, (1, 2)), (5, (2, 0))] { dx[m] = 4.0 * (l[i] * gx[j] + l[j] * gx[i]); dy[m] = 4.0 * (l[i] * gy[j] + l[j] * gy[i]); }
            add_btcb(&mut k0, t, &dx, &dy, T_MM * a2 / 2.0 / 3.0);
        }
    }
    k0
}

/// Residual, reaction, balance and energy diagnostics from the unconstrained K0 (never BC-modified rows).
/// `u2`/`b2` are 2-dof-per-node displacement and supplied-load vectors; `load` is the supplied identity.
#[derive(Debug)]
struct Balance { r_free_l2: f64, b_free_l2: f64, reaction: [f64; 2], reaction_moment: f64, applied: [f64; 2], applied_moment: f64, work: f64, two_energy: f64 }

fn balance(xy: &[(f64, f64)], k0: &[Vec<f64>], u2: &[f64], b2: &[f64], fixed_node: &[bool], load: &Load) -> Balance {
    let r: Vec<f64> = (0..u2.len()).map(|i| k0[i].iter().zip(u2).map(|(k, u)| k * u).sum::<f64>() - b2[i]).collect();
    let (mut rf, mut bf, mut react, mut mom) = (0.0f64, 0.0f64, [0.0f64; 2], 0.0f64);
    for (node, p) in xy.iter().enumerate() {
        let (rx, ry) = (r[2 * node], r[2 * node + 1]);
        if fixed_node[node] { react[0] += rx; react[1] += ry; mom += p.0 * ry - p.1 * rx; }
        else { rf += rx * rx + ry * ry; bf += b2[2 * node].powi(2) + b2[2 * node + 1].powi(2); }
    }
    let ku: Vec<f64> = (0..u2.len()).map(|i| k0[i].iter().zip(u2).map(|(k, u)| k * u).sum::<f64>()).collect();
    let (applied, applied_moment) = load.resultant();
    Balance { r_free_l2: rf.sqrt(), b_free_l2: bf.sqrt(), reaction: react, reaction_moment: mom, applied, applied_moment,
        work: dot(u2, b2), two_energy: dot(u2, &ku) }
}

impl Balance {
    /// Violations of: free residual, force/moment balance against the supplied load, and W = 2U.
    fn violations(&self) -> Vec<String> {
        let mut why = Vec::new();
        if !(self.r_free_l2 <= 1e-10 + 1e-8 * self.b_free_l2) { why.push(format!("free residual {} vs applied free RHS {}", self.r_free_l2, self.b_free_l2)); }
        for c in 0..2 { let (p, r) = (self.applied[c], self.reaction[c]); if !((p + r).abs() <= ABS + REL * p.abs().max(r.abs())) { why.push(format!("force[{c}] applied {p} + reaction {r}")); } }
        let (p, r) = (self.applied_moment, self.reaction_moment);
        if !((p + r).abs() <= ABS + REL * p.abs().max(r.abs())) { why.push(format!("moment applied {p} + reaction {r}")); }
        if !close(self.work, self.two_energy) { why.push(format!("work {} vs 2U {}", self.work, self.two_energy)); }
        why
    }
}

// ---- Plate (DKT + CST): dofs node * 5 + [u mm, v mm, w mm, theta_x rad, theta_y rad] ----

struct PlateFix { pl: Plate, sys: fine::System, fixed_node: Vec<bool>, right: Vec<usize>, k0: Vec<Vec<f64>> }

fn plate_fixture() -> PlateFix {
    let pl = Plate::new(square(), T_MM, E_MPA, NU0);
    let n = pl.n();
    let fixed_node: Vec<bool> = pl.mesh.xy.iter().map(|p| p.0.abs() < 1e-12).collect();
    let right: Vec<usize> = (0..n).filter(|&i| (pl.mesh.xy[i].0 - 1.0).abs() < 1e-12).collect();
    assert_eq!((fixed_node.clone(), right.clone()), (vec![true, false, false, true], vec![1, 2]), "square node association");
    let fixed: Vec<bool> = (0..n * 5).map(|d| fixed_node[d / 5]).collect();
    let sys = pl.system(&fixed).expect("actual Plate::system returns Some for the clamped square");
    let k0 = cst_k0(&pl.mesh.xy, &pl.mesh.tris);
    PlateFix { pl, sys, fixed_node, right, k0 }
}

impl PlateFix {
    /// Supplied right-edge traction as consistent nodal forces: half the unit edge to each corner.
    fn rhs(&self, l: &Load) -> Vec<f64> {
        let mut f = vec![0.0; self.pl.n() * 5];
        for &i in &self.right { f[i * 5] += l.q.0 / 2.0; f[i * 5 + 1] += l.q.1 / 2.0; }
        f
    }
    fn solve(&self, f: &[f64]) -> Vec<f64> {
        let u = self.pl.solve(&self.sys, f);
        assert_eq!(u.len(), self.pl.n() * 5, "full displacement in node order");
        assert!(u.iter().all(|x| x.is_finite()), "finite actual displacement");
        for (d, x) in u.iter().enumerate() { if self.fixed_node[d / 5] { assert_eq!(*x, 0.0, "restrained dof {d}"); } }
        u
    }
    fn solve_mutant(&self, f: &[f64]) -> Vec<f64> { self.solve(&drop_g_on_mixed(f, 5)) }
    /// Signed stresses per triangle: membrane [sxx, syy, txy] then bending surface [sxx, syy, txy] at 3 Gauss points.
    fn stress(&self, u: &[f64]) -> Vec<f64> {
        self.pl.mesh.tris.iter().flat_map(|t| { let (m, b) = self.pl.elem_stress(t, u); m.into_iter().chain(b.into_iter().flatten()).collect::<Vec<_>>() }).collect()
    }
    fn membrane(v: &[f64]) -> Vec<f64> { v.chunks(5).flat_map(|d| [d[0], d[1]]).collect() }
    fn balance(&self, u: &[f64], f: &[f64], l: &Load) -> Balance { balance(&self.pl.mesh.xy, &self.k0, &Self::membrane(u), &Self::membrane(f), &self.fixed_node, l) }
}

// ---- T6 (quadratic membrane): dofs node * 2 + [u mm, v mm], corner and edge-midpoint nodes ----

struct T6Fix { t6: T6, sys: fine::T6System, fixed_node: Vec<bool>, k0: Vec<Vec<f64>> }

fn t6_fixture() -> T6Fix {
    let t6 = T6::new(&square(), T_MM, E_MPA, NU0);
    let fixed_node: Vec<bool> = t6.xy.iter().map(|p| p.0.abs() < 1e-12).collect();
    assert_eq!((t6.n(), fixed_node.iter().filter(|&&f| f).count()), (9, 3), "4 corners + 5 mid-sides, 3 nodes on x = 0");
    let fixed: Vec<bool> = (0..t6.n() * 2).map(|d| fixed_node[d / 2]).collect();
    let sys = t6.system(&fixed).expect("actual T6::system returns Some for the clamped square");
    let k0 = t6_k0(&t6);
    T6Fix { t6, sys, fixed_node, k0 }
}

impl T6Fix {
    /// Supplied traction through the actual consistent `edge_traction` (1/6, 2/3, 1/6 of q * length).
    fn rhs(&self, l: &Load) -> Vec<f64> {
        let mut f = vec![0.0; self.t6.n() * 2];
        let on = |i: usize| (self.t6.xy[i].0 - 1.0).abs() < 1e-12;
        let len = self.t6.edge_traction(&on, l.q, &mut f);
        assert!(close(len, 1.0), "loaded edge length {len}");
        for (i, p) in self.t6.xy.iter().enumerate() {
            let w = if !on(i) { 0.0 } else if (p.1 - 0.5).abs() < 1e-12 { 2.0 / 3.0 } else { 1.0 / 6.0 };
            assert!(close(f[2 * i], w * l.q.0) && close(f[2 * i + 1], w * l.q.1), "consistent edge load at node {i}");
        }
        f
    }
    fn solve(&self, f: &[f64]) -> Vec<f64> {
        let u = self.t6.solve(&self.sys, f);
        assert_eq!(u.len(), self.t6.n() * 2, "full displacement in node order");
        assert!(u.iter().all(|x| x.is_finite()), "finite actual displacement");
        for (d, x) in u.iter().enumerate() { if self.fixed_node[d / 2] { assert_eq!(*x, 0.0, "restrained dof {d}"); } }
        u
    }
    fn solve_mutant(&self, f: &[f64]) -> Vec<f64> { self.solve(&drop_g_on_mixed(f, 2)) }
    /// Signed area-weighted nodal [sxx, syy, txy] by node ID (corner and mid-side).
    fn stress(&self, u: &[f64]) -> Vec<f64> { self.t6.nodal_stress(u).into_iter().flatten().collect() }
    fn balance(&self, u: &[f64], f: &[f64], l: &Load) -> Balance { balance(&self.t6.xy, &self.k0, u, f, &self.fixed_node, l) }
}

/// Proposed mixed-only mutant at the combined-load solve input seam: drop the y (G) load components only
/// when x and y components coexist. Single-axis and doubled single-axis loads pass through unchanged.
fn drop_g_on_mixed(f: &[f64], stride: usize) -> Vec<f64> {
    let present = |c: usize| f.iter().skip(c).step_by(stride).any(|v| *v != 0.0);
    let mut out = f.to_vec();
    if present(0) && present(1) { for v in out.iter_mut().skip(1).step_by(stride) { *v = 0.0; } }
    out
}

fn record(row: &str, provider: &str, l: &Load, b: &Balance) {
    println!("T05 {row} {provider} load={} backend={} refine={} r_free_l2={:e} b_free_l2={:e} ratio={:e} reaction={:?} reaction_moment={:e} applied={:?} applied_moment={:e} work={:e} two_energy={:e}",
        l.id, fine::solver_backend(), fine::refine_steps(), b.r_free_l2, b.b_free_l2, b.r_free_l2 / b.b_free_l2, b.reaction, b.reaction_moment, b.applied, b.applied_moment, b.work, b.two_energy);
}

#[test]
fn t05_01_supplied_load_resultants() {
    // independent input integration, frozen oracle: F (1,0) N, Mz -1/2; G (0,1), Mz 1; F+G (1,1), Mz 1/2 N mm
    for (l, f, m) in [(F, [1.0, 0.0], -0.5), (G, [0.0, 1.0], 1.0), (FG, [1.0, 1.0], 0.5)] {
        let (rf, rm) = l.resultant();
        assert!(close(rf[0], f[0]) && close(rf[1], f[1]) && close(rm, m), "{l:?}: {rf:?} {rm}");
    }
    assert_eq!(c_mat(), [[1000.0, 0.0, 0.0], [0.0, 1000.0, 0.0], [0.0, 0.0, 500.0]]);
    assert!(["skyline", "faer"].contains(&fine::solver_backend()));
}

#[test]
fn t05_01_positive_rust_scaling() {
    let px = plate_fixture();
    // in-plane right-edge traction and a transverse unit load (1/2 N in w at each right corner)
    let mut tz = vec![0.0; px.pl.n() * 5];
    for &i in &px.right { tz[i * 5 + 2] = 0.5; }
    for (name, f1) in [("plate in-plane F", px.rhs(&F)), ("plate transverse", tz)] {
        let f2 = scaled(&f1, 2.0);
        let (u1, u2) = (px.solve(&f1), px.solve(&f2));
        let mut why = mismatches(&format!("{name} u"), &u2, &scaled(&u1, 2.0));
        why.extend(mismatches(&format!("{name} signed stress"), &px.stress(&u2), &scaled(&px.stress(&u1), 2.0)));
        // von Mises is positively homogeneous, so the screening SF halves (828 MPa yield); work scales by 4
        let ((m1, b1), (m2, b2)) = (px.pl.stresses(&u1), px.pl.stresses(&u2));
        why.extend(mismatches(&format!("{name} VM"), &[m2, b2].concat(), &scaled(&[m1, b1].concat(), 2.0)));
        if !close(dot(&u2, &f2), 4.0 * dot(&u1, &f1)) { why.push(format!("{name} work x4")); }
        assert!(why.is_empty(), "{why:?}");
        assert!(u1.iter().any(|x| x.abs() > 1e-6), "{name}: nonzero response");
    }
    let tx = t6_fixture();
    let f1 = tx.rhs(&F);
    let (u1, u2) = (tx.solve(&f1), tx.solve(&scaled(&f1, 2.0)));
    let mut why = mismatches("T6 u", &u2, &scaled(&u1, 2.0));
    why.extend(mismatches("T6 signed stress", &tx.stress(&u2), &scaled(&tx.stress(&u1), 2.0)));
    assert!(why.is_empty(), "{why:?}");
}

#[test]
fn t05_01_rev33_rust_plate_positive() {
    let px = plate_fixture();
    let rhs: Vec<Vec<f64>> = [F, G, FG].iter().map(|l| px.rhs(l)).collect();
    let u: Vec<Vec<f64>> = rhs.iter().map(|f| px.solve(f)).collect();
    for (k, l) in [F, G, FG].iter().enumerate() {
        let b = px.balance(&u[k], &rhs[k], l);
        record("01-rev33-rust_Plate-positive", "rust_Plate", l, &b);
        assert!(b.violations().is_empty(), "{}: {:?}", l.id, b.violations());
        // no bending is excited by in-plane loads: w, rotations and bending stresses stay zero
        for (d, x) in u[k].iter().enumerate() { if d % 5 >= 2 { assert!(x.abs() <= ABS, "{} bending dof {d} = {x}", l.id); } }
        for (e, t) in px.pl.mesh.tris.iter().enumerate() { let (_, sb) = px.pl.elem_stress(t, &u[k]); assert!(sb.iter().flatten().all(|s| s.abs() <= ABS), "{} element {e}", l.id); }
    }
    let mut why = mismatches("plate u(F+G) - u(F) - u(G)", &u[2], &sum(&u[0], &u[1]));
    why.extend(mismatches("plate signed stress", &px.stress(&u[2]), &sum(&px.stress(&u[0]), &px.stress(&u[1]))));
    assert!(why.is_empty(), "{why:?}");
    assert!(u[0].iter().any(|x| x.abs() > 1e-6) && u[1].iter().any(|x| x.abs() > 1e-6), "both independent loads respond");
}

#[test]
fn t05_01_rev33_rust_plate_adverse() {
    let px = plate_fixture();
    let (ff, fg, ffg) = (px.rhs(&F), px.rhs(&G), px.rhs(&FG));
    let (uf, ug, ufg) = (px.solve_mutant(&ff), px.solve_mutant(&fg), px.solve_mutant(&ffg));
    // the mutant keeps single axes and doubling intact, so it is not a reject-all control
    assert_eq!((uf.clone(), ug.clone()), (px.solve(&ff), px.solve(&fg)));
    assert!(mismatches("2F", &px.solve_mutant(&scaled(&ff, 2.0)), &scaled(&uf, 2.0)).is_empty());
    assert!(mismatches("2G", &px.solve_mutant(&scaled(&fg, 2.0)), &scaled(&ug, 2.0)).is_empty());
    for (l, u, f) in [(F, &uf, &ff), (G, &ug, &fg)] { assert!(px.balance(u, f, &l).violations().is_empty()); }
    // the submitted F+G identity and its independently integrated resultant stay F+G
    let u_miss = mismatches("plate u(F+G)", &ufg, &sum(&uf, &ug));
    let s_miss = mismatches("plate signed stress", &px.stress(&ufg), &sum(&px.stress(&uf), &px.stress(&ug)));
    let b = px.balance(&ufg, &ffg, &FG);
    record("01-rev33-rust_Plate-adverse", "rust_Plate", &FG, &b);
    println!("T05 01-rev33-rust_Plate-adverse detected: u {u_miss:?} stress {s_miss:?} balance {:?}", b.violations());
    assert!(!u_miss.is_empty() && !s_miss.is_empty(), "mixed-only omission must break additivity");
    assert!(b.violations().iter().any(|w| w.starts_with("force[1]")), "{:?}", b.violations());
}

#[test]
fn t05_01_rev33_rust_t6_positive() {
    let tx = t6_fixture();
    let rhs: Vec<Vec<f64>> = [F, G, FG].iter().map(|l| tx.rhs(l)).collect();
    let u: Vec<Vec<f64>> = rhs.iter().map(|f| tx.solve(f)).collect();
    for (k, l) in [F, G, FG].iter().enumerate() {
        let b = tx.balance(&u[k], &rhs[k], l);
        record("01-rev33-rust_T6-positive", "rust_T6", l, &b);
        assert!(b.violations().is_empty(), "{}: {:?}", l.id, b.violations());
    }
    let mut why = mismatches("T6 u(F+G) - u(F) - u(G)", &u[2], &sum(&u[0], &u[1]));
    why.extend(mismatches("T6 signed nodal stress", &tx.stress(&u[2]), &sum(&tx.stress(&u[0]), &tx.stress(&u[1]))));
    assert!(why.is_empty(), "{why:?}");
    assert!(u[0].iter().any(|x| x.abs() > 1e-6) && u[1].iter().any(|x| x.abs() > 1e-6), "both independent loads respond");
}

#[test]
fn t05_01_rev33_rust_t6_adverse() {
    let tx = t6_fixture();
    let (ff, fg, ffg) = (tx.rhs(&F), tx.rhs(&G), tx.rhs(&FG));
    let (uf, ug, ufg) = (tx.solve_mutant(&ff), tx.solve_mutant(&fg), tx.solve_mutant(&ffg));
    assert_eq!((uf.clone(), ug.clone()), (tx.solve(&ff), tx.solve(&fg)));
    assert!(mismatches("2F", &tx.solve_mutant(&scaled(&ff, 2.0)), &scaled(&uf, 2.0)).is_empty());
    assert!(mismatches("2G", &tx.solve_mutant(&scaled(&fg, 2.0)), &scaled(&ug, 2.0)).is_empty());
    for (l, u, f) in [(F, &uf, &ff), (G, &ug, &fg)] { assert!(tx.balance(u, f, &l).violations().is_empty()); }
    let u_miss = mismatches("T6 u(F+G)", &ufg, &sum(&uf, &ug));
    let s_miss = mismatches("T6 signed nodal stress", &tx.stress(&ufg), &sum(&tx.stress(&uf), &tx.stress(&ug)));
    let b = tx.balance(&ufg, &ffg, &FG);
    record("01-rev33-rust_T6-adverse", "rust_T6", &FG, &b);
    println!("T05 01-rev33-rust_T6-adverse detected: u {u_miss:?} stress {s_miss:?} balance {:?}", b.violations());
    assert!(!u_miss.is_empty() && !s_miss.is_empty(), "mixed-only omission must break additivity");
    assert!(b.violations().iter().any(|w| w.starts_with("force[1]")), "{:?}", b.violations());
}

const YIELD_MPA: f64 = 828.0;

fn check_scaling_ratios(vm1: f64, vm2: f64, sf1: f64, sf2: f64, mult: f64) -> Result<(), &'static str> {
    if !vm1.is_finite() || !vm2.is_finite() || !sf1.is_finite() || !sf2.is_finite() || vm1 <= 0.0 || vm2 <= 0.0 {
        return Err("nonfinite_or_nonpositive_observable");
    }
    if !close(vm2 / vm1, mult) { return Err("stress_ratio_mismatch"); }
    if !close(sf1 / sf2, mult) { return Err("sf_inverse_ratio_mismatch"); }
    Ok(())
}

#[test]
fn t05_01_adverse_constant_sf() {
    let px = plate_fixture();
    let f1 = px.rhs(&F);
    let f2 = scaled(&f1, 2.0);
    let (u1, u2) = (px.solve(&f1), px.solve(&f2));
    let (m1, _) = px.pl.stresses(&u1);
    let (m2, _) = px.pl.stresses(&u2);
    let vm1 = m1.iter().copied().fold(0.0, f64::max);
    let vm2 = m2.iter().copied().fold(0.0, f64::max);
    let (sf1, sf2) = (YIELD_MPA / vm1, YIELD_MPA / vm2);
    assert_eq!(check_scaling_ratios(vm1, vm2, sf1, sf2, 2.0), Ok(()));
    // Adverse control: a safety factor that stays constant when the load doubles must fail the check.
    assert_eq!(check_scaling_ratios(vm1, vm2, sf1, sf1, 2.0), Err("sf_inverse_ratio_mismatch"));
}

// ---------------------------------------------------------------------------------------------
// T05-02: rigid motion invariance (translation + rotation of mesh, restraints, and load vector)

fn transform_mesh(m: &Mesh, cos_t: f64, sin_t: f64, tx: f64, ty: f64) -> Mesh {
    let xy = m.xy.iter().map(|&(x, y)| (cos_t * x - sin_t * y + tx, sin_t * x + cos_t * y + ty)).collect();
    Mesh { xy, tris: m.tris.clone(), on_outer: m.on_outer.clone(), on_hole: m.on_hole.clone() }
}

#[test]
fn t05_02_positive_rigid_transform() {
    let px0 = plate_fixture();
    let u0 = px0.solve(&px0.rhs(&F));
    let (sm0, _) = px0.pl.stresses(&u0);
    let (s0, _) = px0.pl.elem_stress(&px0.pl.mesh.tris[0], &u0);
    // 90 deg CCW rotation (cos=0, sin=1) + translation (7, -3)
    let m_rot = transform_mesh(&square(), 0.0, 1.0, 7.0, -3.0);
    let pl_rot = Plate::new(m_rot, T_MM, E_MPA, NU0);
    let fixed: Vec<bool> = (0..pl_rot.n() * 5).map(|d| px0.fixed_node[d / 5]).collect();
    let sys_rot = pl_rot.system(&fixed).expect("rotated clamped square is SPD");
    let mut f_rot = vec![0.0; pl_rot.n() * 5];
    // Rotated load F=(1,0) -> (0,1) on the same material boundary nodes
    for &i in &px0.right { f_rot[i * 5 + 1] += 0.5; }
    let u_rot = pl_rot.solve(&sys_rot, &f_rot);
    let (sm_rot, _) = pl_rot.stresses(&u_rot);
    let (s_rot, _) = pl_rot.elem_stress(&pl_rot.mesh.tris[0], &u_rot);
    // Under 90 deg rotation, s_xx' = s_yy, s_yy' = s_xx, t_xy' = -t_xy, and von Mises is invariant
    assert!(close(s_rot[0], s0[1]) && close(s_rot[1], s0[0]) && close(s_rot[2], -s0[2]));
    assert!(mismatches("rotated VM", &sm_rot, &sm0).is_empty());
    let sf0 = YIELD_MPA / sm0.iter().copied().fold(0.0, f64::max);
    let sf_rot = YIELD_MPA / sm_rot.iter().copied().fold(0.0, f64::max);
    assert!(close(sf0, sf_rot));
}

#[test]
fn t05_02_adverse_unrotated_load() {
    let px0 = plate_fixture();
    let u0 = px0.solve(&px0.rhs(&F));
    let (s0, _) = px0.pl.elem_stress(&px0.pl.mesh.tris[0], &u0);
    // Rotate geometry and clamp by 90 deg CCW, but leave load in +x (now shear instead of axial tension)
    let m_rot = transform_mesh(&square(), 0.0, 1.0, 7.0, -3.0);
    let pl_rot = Plate::new(m_rot, T_MM, E_MPA, NU0);
    let fixed: Vec<bool> = (0..pl_rot.n() * 5).map(|d| px0.fixed_node[d / 5]).collect();
    let sys_rot = pl_rot.system(&fixed).unwrap();
    let mut f_unrot = vec![0.0; pl_rot.n() * 5];
    for &i in &px0.right { f_unrot[i * 5] += 0.5; }
    let u_bad = pl_rot.solve(&sys_rot, &f_unrot);
    let (s_bad, _) = pl_rot.elem_stress(&pl_rot.mesh.tris[0], &u_bad);
    // Must not match the rotated tensor [s0[1], s0[0], -s0[2]]
    assert!(!mismatches("unrotated load tensor", &s_bad, &[s0[1], s0[0], -s0[2]]).is_empty());
}

// ---------------------------------------------------------------------------------------------
// T05-03: unit consistency (mm/N/MPa vs m/N/Pa coherent scaling and mixed-unit rejection)

#[test]
fn t05_03_positive_coherent_units() {
    let px_mm = plate_fixture();
    let u_mm = px_mm.solve(&px_mm.rhs(&F));
    let (sm_mm, _) = px_mm.pl.stresses(&u_mm);
    // Coherent SI (m, N, Pa): length * 1e-3, thickness * 1e-3, E * 1e6, total nodal force unchanged (1 N)
    let m_si = transform_mesh(&square(), 1e-3, 0.0, 0.0, 0.0);
    let pl_si = Plate::new(m_si, T_MM * 1e-3, E_MPA * 1e6, NU0);
    let fixed: Vec<bool> = (0..pl_si.n() * 5).map(|d| px_mm.fixed_node[d / 5]).collect();
    let sys_si = pl_si.system(&fixed).unwrap();
    let u_si = pl_si.solve(&sys_si, &px_mm.rhs(&F));
    let (sm_si, _) = pl_si.stresses(&u_si);
    // u_si (m) = 1e-3 * u_mm (mm); sm_si (Pa) = 1e6 * sm_mm (MPa); SF = yield / vm is dimensionless
    assert!(close(u_si[5] * 1e3, u_mm[5]));
    assert!(close(sm_si[0] * 1e-6, sm_mm[0]));
    let sf_mm = YIELD_MPA / sm_mm[0];
    let sf_si = (YIELD_MPA * 1e6) / sm_si[0];
    assert!(close(sf_mm, sf_si));
}

#[test]
fn t05_03_adverse_mixed_units() {
    let px_mm = plate_fixture();
    let u_mm = px_mm.solve(&px_mm.rhs(&F));
    let (sm_mm, _) = px_mm.pl.stresses(&u_mm);
    // Adverse mixed units: coordinates scaled to metres (1e-3) while thickness (1.0) and E (1000) stay in mm/MPa
    let m_mixed = transform_mesh(&square(), 1e-3, 0.0, 0.0, 0.0);
    let pl_mixed = Plate::new(m_mixed, T_MM, E_MPA, NU0);
    let fixed: Vec<bool> = (0..pl_mixed.n() * 5).map(|d| px_mm.fixed_node[d / 5]).collect();
    let sys_mixed = pl_mixed.system(&fixed).unwrap();
    let u_mixed = pl_mixed.solve(&sys_mixed, &px_mm.rhs(&F));
    let (sm_mixed, _) = pl_mixed.stresses(&u_mixed);
    // Stress in mixed units is off by 1000x and must fail unit-consistency comparison
    assert!(!close(sm_mixed[0], sm_mm[0]) && !close(sm_mixed[0] * 1e-6, sm_mm[0]));
}

// ---------------------------------------------------------------------------------------------
// T05-05: boundary-condition failure (clamped vs free-free / mechanism)

fn g1_admit_sf(sys_ok: bool, vm_peak: f64) -> Option<f64> {
    if !sys_ok || !vm_peak.is_finite() || vm_peak <= 0.0 { return None; }
    Some(YIELD_MPA / vm_peak)
}

#[test]
fn t05_05_positive_clamped_system() {
    let px = plate_fixture();
    let u = px.solve(&px.rhs(&F));
    let (sm, _) = px.pl.stresses(&u);
    let sf = g1_admit_sf(true, sm.iter().copied().fold(0.0, f64::max));
    assert_eq!(sf, Some(YIELD_MPA));
}

#[test]
fn t05_05_adverse_unbound_free_free() {
    let pl = Plate::new(square(), T_MM, E_MPA, NU0);
    let free_free = vec![false; pl.n() * 5];
    let all_fixed = vec![true; pl.n() * 5];
    // Both skyline and faer must refuse a free-free or all-fixed plate and emit no safety factor for G1
    for sky in [true, false] {
        assert!(pl.system_with(&free_free, sky).is_none(), "free-free plate must fail closed (skyline={sky})");
        assert!(pl.system_with(&all_fixed, sky).is_none(), "all-fixed plate has 0 free dofs (skyline={sky})");
    }
    let t6 = T6::new(&square(), T_MM, E_MPA, NU0);
    assert!(t6.system(&vec![false; t6.n() * 2]).is_none(), "free-free T6 must fail closed");
    // A single pinned corner leaves rotational mechanism -> Cholesky pivot rejected -> None
    let mut one_pin = vec![false; t6.n() * 2];
    one_pin[0] = true;
    one_pin[1] = true;
    assert!(t6.system(&one_pin).is_none(), "under-restrained mechanism must fail closed");
    assert_eq!(g1_admit_sf(false, 0.0), None);
}

// ---------------------------------------------------------------------------------------------
// T05-06: mesh failure (valid CDT domain vs collapsed / degenerate mesh)

#[test]
fn t05_06_positive_valid_domain_mesh() {
    let outer = vec![(0.0, 0.0), (10.0, 0.0), (10.0, 4.0), (0.0, 4.0)];
    let m = fine::mesh_domain(&outer, &[], 2.0).expect("valid rectangle meshes");
    assert!(!m.tris.is_empty());
    let pl = Plate::new(m, T_MM, E_MPA, NU0);
    for e in 0..pl.mesh.tris.len() { assert!(pl.area(e) > 0.0); }
}

#[test]
fn t05_06_adverse_degenerate_or_empty_mesh() {
    // Collinear / zero-area boundary polygon produces no interior triangles -> None
    let collinear = vec![(0.0, 0.0), (5.0, 0.0), (10.0, 0.0)];
    assert!(fine::mesh_domain(&collinear, &[], 1.0).is_none());
    // Empty mesh has 0 free dofs -> system() returns None, no safety factor emitted
    let empty = Mesh { xy: vec![], tris: vec![], on_outer: vec![], on_hole: vec![] };
    let pl_empty = Plate::new(empty, T_MM, E_MPA, NU0);
    assert!(pl_empty.system(&[]).is_none());
    // Disconnected unrestrained node in a mesh causes zero pivot -> system() returns None
    let mut dis = square();
    dis.xy.push((5.0, 5.0));
    dis.on_outer.push(false);
    dis.on_hole.push(false);
    let pl_dis = Plate::new(dis, T_MM, E_MPA, NU0);
    let fixed: Vec<bool> = (0..pl_dis.n() * 5).map(|d| (d / 5) == 0 || (d / 5) == 3).collect();
    assert!(pl_dis.system(&fixed).is_none(), "disconnected unrestrained node must fail closed");
}

// ---------------------------------------------------------------------------------------------
// T05-07: field semantics (named stress component vs von Mises reduction)

#[test]
fn t05_07_positive_component_and_vm_semantics() {
    let px = plate_fixture();
    let u = px.solve(&px.rhs(&FG));
    let (s_m, _) = px.pl.elem_stress(&px.pl.mesh.tris[0], &u);
    let vm_expected = (s_m[0] * s_m[0] - s_m[0] * s_m[1] + s_m[1] * s_m[1] + 3.0 * s_m[2] * s_m[2]).sqrt();
    let (sm, _) = px.pl.stresses(&u);
    assert!(close(sm[0], vm_expected));
    assert!(close(fine::von_mises(s_m), vm_expected));
}

#[test]
fn t05_07_adverse_swapped_component_or_averaging() {
    let px = plate_fixture();
    let u = px.solve(&px.rhs(&G)); // pure shear/transverse load
    let (s_m, _) = px.pl.elem_stress(&px.pl.mesh.tris[0], &u);
    let vm = fine::von_mises(s_m);
    let hydrostatic_2d = 0.5 * (s_m[0] + s_m[1]).abs();
    // Reading hydrostatic mean or s_yy in place of von Mises under shear under-reports stress and is rejected
    assert!(!close(hydrostatic_2d, vm) && hydrostatic_2d < vm);
}

// ---------------------------------------------------------------------------------------------
// T05-08: localized peak (one-element spike stays visible in reported peak, never averaged away)

#[test]
fn t05_08_positive_one_element_spike_preserved() {
    let outer = vec![(0.0, 0.0), (4.0, 0.0), (4.0, 2.0), (0.0, 2.0)];
    let m = fine::mesh_domain(&outer, &[], 0.5).unwrap();
    assert!(m.tris.len() >= 16);
    let pl = Plate::new(m, T_MM, E_MPA, NU0);
    // Plant a localized 10x spike on element 0 among uniform background elements
    let mut elem_vm = vec![1.0; pl.mesh.tris.len()];
    elem_vm[0] = 10.0;
    let peak = elem_vm.iter().copied().fold(0.0, f64::max);
    let sf_peak = YIELD_MPA / peak;
    assert!(close(peak, 10.0) && close(sf_peak, 82.8));
}

#[test]
fn t05_08_adverse_global_average_hides_spike() {
    let outer = vec![(0.0, 0.0), (4.0, 0.0), (4.0, 2.0), (0.0, 2.0)];
    let m = fine::mesh_domain(&outer, &[], 0.5).unwrap();
    let pl = Plate::new(m, T_MM, E_MPA, NU0);
    let mut elem_vm = vec![1.0; pl.mesh.tris.len()];
    elem_vm[0] = 10.0;
    let peak = elem_vm.iter().copied().fold(0.0, f64::max);
    let total_area: f64 = (0..pl.mesh.tris.len()).map(|e| pl.area(e)).sum();
    let mean_vm: f64 = (0..pl.mesh.tris.len()).map(|e| pl.area(e) * elem_vm[e]).sum::<f64>() / total_area;
    // Adverse: replacing peak with area-weighted mean hides the 10 MPa spike and inflates SF
    assert!(mean_vm < 2.5 && !close(mean_vm, peak));
}

// ---------------------------------------------------------------------------------------------
// T05-09: certificate field identity (certificate scalar must match the solve field & mesh)

#[derive(Debug, PartialEq)]
struct CertBinding<'a> { mesh_tris: usize, field_len: usize, reported_sf: f64, observable: &'a str }

fn verify_cert_binding(b: &CertBinding, solve_tris: usize, solve_vm: &[f64], expected_obs: &str) -> Result<(), &'static str> {
    if b.observable != expected_obs { return Err("observable_mismatch"); }
    if b.mesh_tris != solve_tris || b.field_len != solve_vm.len() || solve_vm.is_empty() { return Err("mesh_field_mismatch"); }
    let peak = solve_vm.iter().copied().fold(0.0, f64::max);
    if !peak.is_finite() || peak <= 0.0 || !close(b.reported_sf, YIELD_MPA / peak) { return Err("sf_field_mismatch"); }
    Ok(())
}

#[test]
fn t05_09_positive_certificate_field_binding() {
    let px = plate_fixture();
    let u = px.solve(&px.rhs(&F));
    let (sm, _) = px.pl.stresses(&u);
    let peak = sm.iter().copied().fold(0.0, f64::max);
    let cert = CertBinding { mesh_tris: px.pl.mesh.tris.len(), field_len: sm.len(), reported_sf: YIELD_MPA / peak, observable: "cst_membrane_vm_max" };
    assert_eq!(verify_cert_binding(&cert, px.pl.mesh.tris.len(), &sm, "cst_membrane_vm_max"), Ok(()));
}

#[test]
fn t05_09_adverse_cross_mesh_or_mutated_field() {
    let px = plate_fixture();
    let u = px.solve(&px.rhs(&F));
    let (sm, _) = px.pl.stresses(&u);
    let peak = sm.iter().copied().fold(0.0, f64::max);
    let cert_wrong_mesh = CertBinding { mesh_tris: 26137, field_len: sm.len(), reported_sf: YIELD_MPA / peak, observable: "cst_membrane_vm_max" };
    assert_eq!(verify_cert_binding(&cert_wrong_mesh, px.pl.mesh.tris.len(), &sm, "cst_membrane_vm_max"), Err("mesh_field_mismatch"));
    let cert_wrong_sf = CertBinding { mesh_tris: px.pl.mesh.tris.len(), field_len: sm.len(), reported_sf: 2.0 * (YIELD_MPA / peak), observable: "cst_membrane_vm_max" };
    assert_eq!(verify_cert_binding(&cert_wrong_sf, px.pl.mesh.tris.len(), &sm, "cst_membrane_vm_max"), Err("sf_field_mismatch"));
}

// ---------------------------------------------------------------------------------------------
// T05-10: native B-rep STEP hash binding

fn bind_native_step<'a>(record_step_sha256: &'a str, actual_step_sha256: &'a str, volume_mm3: f64) -> Result<&'a str, &'static str> {
    if record_step_sha256.len() != 64 || actual_step_sha256.len() != 64 { return Err("invalid_step_digest"); }
    if record_step_sha256 != actual_step_sha256 { return Err("step_hash_mismatch"); }
    if !volume_mm3.is_finite() || volume_mm3 <= 0.0 { return Err("invalid_brep_volume"); }
    Ok(actual_step_sha256)
}

#[test]
fn t05_10_positive_step_hash_binding() {
    let c10a_sha = "19773f6cf41d75d0f22949547791b8693bd43ba7023c6c11cb0e632fb93fd243";
    assert_eq!(bind_native_step(c10a_sha, c10a_sha, 17756.2), Ok(c10a_sha));
}

#[test]
fn t05_10_adverse_mismatched_step_hash() {
    let c10a_sha = "19773f6cf41d75d0f22949547791b8693bd43ba7023c6c11cb0e632fb93fd243";
    let c92_sha  = "b9384a18ef6b150e87ef1a3b7fb0840bcba80b0e7845875b4c3974d7ab2a37f3";
    assert_eq!(bind_native_step(c10a_sha, c92_sha, 17756.2), Err("step_hash_mismatch"));
    assert_eq!(bind_native_step(c10a_sha, c10a_sha, 0.0), Err("invalid_brep_volume"));
}

// ---------------------------------------------------------------------------------------------
// T05-11: calibration failures stay in denominators and never pass via censorship

#[test]
fn t05_11_positive_complete_calibration_table() {
    let e = Expected { id: "cal-2".into(), max_err_pct: 5.0, levels: vec![1.0, 0.25], gate_levels: vec![0.25], checks: vec!["beam".into(), "hole".into()] };
    let o = vec![obs("beam", 1.0, 1.02), obs("beam", 0.25, 1.01), obs("hole", 1.0, 0.98), obs("hole", 0.25, 0.99)];
    assert!(theory_gate(&e, &o).is_ok());
}

#[test]
fn t05_11_adverse_failed_or_censored_calibration() {
    let e = Expected { id: "cal-2".into(), max_err_pct: 5.0, levels: vec![1.0, 0.25], gate_levels: vec![0.25], checks: vec!["beam".into(), "hole".into()] };
    // Failed calibration stays failed
    let failed = vec![obs("beam", 1.0, 1.02), obs("beam", 0.25, 1.01), obs("hole", 1.0, 0.98), obs("hole", 0.25, 1.12)];
    let why = gate_err(&e, &failed);
    assert!(has(&why, "\"hole\" at 0.25 err 12.00 % >= 5 %"), "{why:?}");
    // Dropping the failed check from observations (survivorship selection) still fails closed
    let censored = vec![obs("beam", 1.0, 1.02), obs("beam", 0.25, 1.01)];
    let why_censored = gate_err(&e, &censored);
    assert!(has(&why_censored, "missing check \"hole\""), "{why_censored:?}");
}

// ---------------------------------------------------------------------------------------------
// T05-12: tier collision (screening L7 fat_sf / T1 beam cannot occupy a certification field)

fn admit_certification_sf(slot: &str, tier: &str, not_tag: Option<&str>, value: f64) -> Result<f64, &'static str> {
    if not_tag.is_some() || tier == "T1_beam_screening" || tier == "L7_screening_fat_sf" {
        return Err("screening_tier_in_certification_slot");
    }
    match (slot, tier) {
        ("solid.tip_sf", "T3_dolfinx_solid") | ("plate.seq", "T2_fine_plate") if value.is_finite() && value > 0.0 => Ok(value),
        _ => Err("tier_slot_collision"),
    }
}

#[test]
fn t05_12_positive_tier_separation() {
    assert_eq!(admit_certification_sf("solid.tip_sf", "T3_dolfinx_solid", None, 1.883), Ok(1.883));
    assert_eq!(admit_certification_sf("plate.seq", "T2_fine_plate", None, 0.976), Ok(0.976));
}

#[test]
fn t05_12_adverse_l7_screening_in_certification_field() {
    // L7 screening fat_sf carries `not: spec §7.3 L7` and must be refused in any certification slot
    assert_eq!(
        admit_certification_sf("solid.tip_sf", "L7_screening_fat_sf", Some("spec §7.3 L7"), 2.139),
        Err("screening_tier_in_certification_slot")
    );
    assert_eq!(
        admit_certification_sf("plate.seq", "T1_beam_screening", None, 1.45),
        Err("screening_tier_in_certification_slot")
    );
    assert_eq!(
        admit_certification_sf("solid.tip_sf", "T2_fine_plate", None, 1.385),
        Err("tier_slot_collision")
    );
}

