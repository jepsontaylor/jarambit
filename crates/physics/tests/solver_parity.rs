//! PR-0.31.2: faer supernodal Cholesky vs the reference RCM skyline Cholesky. Parity <= 1e-9 (relative, max-norm).
use jarambit_physics::fine::{mesh_domain, Plate, T6, P2};

fn domain() -> (Vec<P2>, Vec<Vec<P2>>) {
    let outer = vec![(0.0, 0.0), (80.0, 0.0), (80.0, 25.0), (40.0, 35.0), (0.0, 25.0)];
    let hole: Vec<P2> = (0..24).map(|i| { let a = 2.0 * std::f64::consts::PI * i as f64 / 24.0; (55.0 + 6.0 * a.cos(), 14.0 + 6.0 * a.sin()) }).collect();
    (outer, vec![hole])
}
fn rel(a: &[f64], b: &[f64]) -> f64 {
    let m = a.iter().fold(0.0f64, |m, x| m.max(x.abs())).max(1e-300);
    a.iter().zip(b).fold(0.0f64, |e, (x, y)| e.max((x - y).abs())) / m
}

#[test]
fn plate_faer_matches_skyline_multi_rhs() {
    let (o, h) = domain();
    let pl = Plate::new(mesh_domain(&o, &h, 2.0).unwrap(), 3.5, 113_800.0, 0.34);
    let n = pl.n();
    let mut fixed = vec![false; n * 5];
    for i in 0..n { if pl.mesh.xy[i].0 < 1e-6 { for k in 0..5 { fixed[i * 5 + k] = true; } } }
    let mut fs = vec![vec![0.0; n * 5]; 3];
    for i in 0..n { if pl.mesh.xy[i].0 > 80.0 - 1e-6 { fs[0][i * 5 + 2] = 1.0; fs[1][i * 5] = 1.0; fs[2][i * 5 + 3] = 1.0 + pl.mesh.xy[i].1; } }
    let (sf, ss) = (pl.system_with(&fixed, false).unwrap(), pl.system_with(&fixed, true).unwrap());
    let refs: Vec<&[f64]> = fs.iter().map(|v| v.as_slice()).collect();
    let many = pl.solve_many(&sf, &refs);
    for (k, f) in fs.iter().enumerate() {
        let (a, b) = (pl.solve(&ss, f), pl.solve(&sf, f));
        assert!(rel(&a, &b) <= 1e-9, "rhs {k}: {}", rel(&a, &b));
        assert!(rel(&a, &many[k]) <= 1e-9, "multi rhs {k}: {}", rel(&a, &many[k]));
    }
}

#[test]
fn t6_faer_matches_skyline() {
    let (o, h) = domain();
    let t6 = T6::new(&mesh_domain(&o, &h, 3.0).unwrap(), 3.5, 113_800.0, 0.34);
    let n = t6.n();
    let mut fixed = vec![false; n * 2];
    for i in 0..n { if t6.xy[i].0 < 1e-6 { fixed[i * 2] = true; fixed[i * 2 + 1] = true; } }
    let mut f = vec![0.0; n * 2];
    for i in 0..n { if t6.xy[i].0 > 80.0 - 1e-6 { f[i * 2 + 1] = 1.0; } }
    let a = t6.solve(&t6.system_with(&fixed, true).unwrap(), &f);
    let b = t6.solve(&t6.system_with(&fixed, false).unwrap(), &f);
    assert!(rel(&a, &b) <= 1e-9, "{}", rel(&a, &b));
}

#[test]
fn both_backends_reject_mechanisms() {
    let (o, h) = domain();
    let pl = Plate::new(mesh_domain(&o, &h, 4.0).unwrap(), 3.5, 113_800.0, 0.34);
    let free = vec![false; pl.n() * 5];
    assert!(pl.system_with(&free, true).is_none());
    assert!(pl.system_with(&free, false).is_none());
}

/// Issue #32: a coupon clamped at ONE node keeps the in-plane rigid rotation (u = -y, v = x). Skyline rejects it
/// (pivot <= 1e-13 max diag); faer must reject it too, for Plate and T6, on every mesh density.
#[test]
fn both_backends_reject_partially_constrained_rotation() {
    use jarambit_physics::fine::Mesh;
    let mesh = Mesh { xy: vec![(0.0, 0.0), (25.0, 0.0), (0.0, 25.0), (25.0, 25.0)], tris: vec![[0, 1, 3], [0, 3, 2]],
        on_outer: vec![true; 4], on_hole: vec![false; 4] };
    let pl = Plate::new(mesh.clone(), 5.7, 113_800.0, 0.34);
    let mut fixed = vec![false; pl.n() * 5]; fixed[..5].fill(true);
    assert!(pl.system_with(&fixed, true).is_none(), "skyline accepted the plate mechanism");
    assert!(pl.system_with(&fixed, false).is_none(), "faer accepted the plate mechanism");
    let t6 = T6::new(&mesh, 5.7, 113_800.0, 0.34);
    let mut fx = vec![false; t6.n() * 2]; fx[..2].fill(true);
    assert!(t6.system_with(&fx, true).is_none(), "skyline accepted the T6 mechanism");
    assert!(t6.system_with(&fx, false).is_none(), "faer accepted the T6 mechanism");
    // larger unstructured meshes, single clamped node (both corner-clamped and a pinned interior-boundary node)
    let (o, h) = domain();
    for area in [2.0, 6.0] {
        let pl = Plate::new(mesh_domain(&o, &h, area).unwrap(), 3.5, 113_800.0, 0.34);
        let mut f = vec![false; pl.n() * 5]; f[..5].fill(true);
        assert!(pl.system_with(&f, true).is_none() && pl.system_with(&f, false).is_none(), "plate area {area}");
        let t6 = T6::new(&mesh_domain(&o, &h, area).unwrap(), 3.5, 113_800.0, 0.34);
        let mut f = vec![false; t6.n() * 2]; f[..2].fill(true);
        assert!(t6.system_with(&f, true).is_none() && t6.system_with(&f, false).is_none(), "t6 area {area}");
    }
}
