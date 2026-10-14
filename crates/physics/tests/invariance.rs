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
