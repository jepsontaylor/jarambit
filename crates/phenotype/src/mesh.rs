//! Ear-cut caps and a closed extrusion (STL + faceted MANIFOLD_SOLID_BREP).
use super::{shoelace, P2, Phenotype};

pub type V3 = (f64, f64, f64);

#[derive(Clone, Debug)]
pub struct SolidMesh {
    pub verts: Vec<V3>,
    pub tris: Vec<[usize; 3]>,
}

fn dedup(poly: &[P2]) -> Vec<P2> {
    let mut o = Vec::with_capacity(poly.len());
    for p in poly {
        if o.last().map(|q: &P2| (q.0 - p.0).hypot(q.1 - p.1) > 1e-6).unwrap_or(true) { o.push(*p); }
    }
    if o.len() >= 2 && (o[0].0 - o[o.len() - 1].0).hypot(o[0].1 - o[o.len() - 1].1) < 1e-6 { o.pop(); }
    o
}

fn orient(mut poly: Vec<P2>, ccw: bool) -> Vec<P2> {
    let pos = shoelace(&poly) > 0.0;
    if pos != ccw { poly.reverse(); }
    poly
}

fn area2(a: P2, b: P2, c: P2) -> f64 { (b.0 - a.0) * (c.1 - a.1) - (b.1 - a.1) * (c.0 - a.0) }

fn proper_cross(a: P2, b: P2, c: P2, d: P2) -> bool {
    let o = |p: P2, q: P2, r: P2| (q.0 - p.0) * (r.1 - p.1) - (q.1 - p.1) * (r.0 - p.0);
    o(c, d, a) * o(c, d, b) < -1e-12 && o(a, b, c) * o(a, b, d) < -1e-12
}

fn shares_end(a: P2, b: P2, c: P2, d: P2) -> bool {
    let same = |p: P2, q: P2| (p.0 - q.0).abs() < 1e-9 && (p.1 - q.1).abs() < 1e-9;
    same(a, c) || same(a, d) || same(b, c) || same(b, d)
}

fn segment_clear(a: P2, b: P2, polys: &[&[P2]]) -> bool {
    for poly in polys {
        let n = poly.len();
        for i in 0..n {
            let c = poly[i]; let d = poly[(i + 1) % n];
            if shares_end(a, b, c, d) { continue; }
            if proper_cross(a, b, c, d) { return false; }
        }
    }
    true
}

/// Indices into `outer || hole` (outer CCW, hole CW). `None` if the polygon will not ear-clip.
pub fn triangulate(outer_in: &[P2], hole_in: &[P2]) -> Option<(Vec<P2>, Vec<P2>, Vec<[usize; 3]>)> {
    let outer = orient(dedup(outer_in), true);
    let hole = orient(dedup(hole_in), false);
    if outer.len() < 3 || hole.len() < 3 { return None; }
    let n = outer.len();
    let m = hole.len();
    let hi = hole.iter().enumerate().max_by(|(_, a), (_, b)| a.0.partial_cmp(&b.0).unwrap_or(std::cmp::Ordering::Equal)).unwrap().0;
    let hp = hole[hi];
    let mut best = None;
    let mut best_d = f64::MAX;
    for (i, p) in outer.iter().enumerate() {
        let d = (p.0 - hp.0).hypot(p.1 - hp.1);
        if d < best_d && segment_clear(hp, *p, &[&outer, &hole]) { best_d = d; best = Some(i); }
    }
    let best = best.or_else(|| {
        outer.iter().enumerate().min_by(|(_, a), (_, b)| {
            (a.0 - hp.0).hypot(a.1 - hp.1).partial_cmp(&(b.0 - hp.0).hypot(b.1 - hp.1)).unwrap_or(std::cmp::Ordering::Equal)
        }).map(|(i, _)| i)
    })?;
    let mut ring: Vec<usize> = (0..=best).collect();
    for k in 0..=m { ring.push(n + (hi + k) % m); }
    ring.push(best);
    if best + 1 < n { ring.extend(best + 1..n); }
    let pts: Vec<P2> = outer.iter().copied().chain(hole.iter().copied()).collect();
    let tris = earcut(&pts, &ring)?;
    Some((outer, hole, tris))
}

fn earcut(pts: &[P2], ring0: &[usize]) -> Option<Vec<[usize; 3]>> {
    let mut ring = ring0.to_vec();
    let mut tris = Vec::new();
    let mut guard = 0;
    let limit = ring.len() * ring.len() + 8;
    while ring.len() > 3 {
        guard += 1;
        if guard > limit { return None; }
        let m = ring.len();
        let mut clip = None;
        for i in 0..m {
            let a = ring[(i + m - 1) % m];
            let b = ring[i];
            let c = ring[(i + 1) % m];
            if is_ear(pts, &ring, a, b, c) { clip = Some(i); break; }
        }
        let i = clip?;
        let m = ring.len();
        tris.push([ring[(i + m - 1) % m], ring[i], ring[(i + 1) % m]]);
        ring.remove(i);
    }
    if ring.len() == 3 { tris.push([ring[0], ring[1], ring[2]]); }
    let tris: Vec<[usize; 3]> = tris.into_iter().filter(|t| t[0] != t[1] && t[1] != t[2] && t[0] != t[2] && area2(pts[t[0]], pts[t[1]], pts[t[2]]).abs() > 1e-8).collect();
    if tris.is_empty() { None } else { Some(tris) }
}

fn is_ear(pts: &[P2], ring: &[usize], a: usize, b: usize, c: usize) -> bool {
    let (pa, pb, pc) = (pts[a], pts[b], pts[c]);
    if area2(pa, pb, pc) <= 1e-8 { return false; }
    for &i in ring {
        if i == a || i == b || i == c { continue; }
        if strict_inside(pts[i], pa, pb, pc) { return false; }
    }
    true
}

fn strict_inside(p: P2, a: P2, b: P2, c: P2) -> bool {
    let a1 = area2(a, b, p);
    let a2 = area2(b, c, p);
    let a3 = area2(c, a, p);
    let e = 1e-8;
    (a1 > e && a2 > e && a3 > e) || (a1 < -e && a2 < -e && a3 < -e)
}

impl Phenotype {
    /// Closed triangle mesh of the extruded profile. Caps are ear-cut; walls follow the boundary.
    pub fn solid_mesh(&self) -> Option<SolidMesh> {
        let (outer, hole, cap) = triangulate(&self.outline, &self.ring_hole)?;
        let t = self.thickness.max(0.1);
        let mut verts = Vec::with_capacity((outer.len() + hole.len()) * 2);
        for p in outer.iter().chain(hole.iter()) { verts.push((p.0, p.1, 0.0)); }
        let nb = verts.len();
        for p in outer.iter().chain(hole.iter()) { verts.push((p.0, p.1, t)); }
        let mut tris = Vec::with_capacity(cap.len() * 2 + (outer.len() + hole.len()) * 2);
        for tri in &cap {
            let [a, b, c] = *tri;
            tris.push([a + nb, b + nb, c + nb]); // top, +z
            tris.push([a, c, b]);                 // bottom, -z
        }
        let mut wall = |i0: usize, i1: usize| {
            tris.push([i0, i1, i1 + nb]);
            tris.push([i0, i1 + nb, i0 + nb]);
        };
        for i in 0..outer.len() { wall(i, (i + 1) % outer.len()); }
        for j in 0..hole.len() {
            let a = outer.len() + j;
            let b = outer.len() + (j + 1) % hole.len();
            wall(a, b);
        }
        Some(SolidMesh { verts, tris })
    }
}

/// (boundary edges, edges used twice, edges used more than twice, max times one directed edge is repeated).
#[allow(dead_code)]
pub fn edge_census(tris: &[[usize; 3]]) -> (usize, usize, usize, usize) {
    use std::collections::HashMap;
    let mut und: HashMap<(usize, usize), usize> = HashMap::new();
    let mut dir: HashMap<(usize, usize), usize> = HashMap::new();
    for t in tris {
        for k in 0..3 {
            let a = t[k]; let b = t[(k + 1) % 3];
            if a == b { continue; }
            *dir.entry((a, b)).or_default() += 1;
            let key = if a < b { (a, b) } else { (b, a) };
            *und.entry(key).or_default() += 1;
        }
    }
    let mut once = 0; let mut twice = 0; let mut more = 0;
    for v in und.values() {
        if *v == 1 { once += 1; } else if *v == 2 { twice += 1; } else { more += 1; }
    }
    let dir_max = dir.values().copied().max().unwrap_or(0);
    (once, twice, more, dir_max)
}

pub fn stl_string(p: &Phenotype, name: &str) -> String {
    let Some(mesh) = p.solid_mesh() else {
        return format!("solid {name}\nendsolid {name}\n");
    };
    let mut s = format!("solid {name}\n");
    for tri in &mesh.tris {
        let a = mesh.verts[tri[0]]; let b = mesh.verts[tri[1]]; let c = mesh.verts[tri[2]];
        let n = normal(a, b, c);
        s.push_str(&format!("facet normal {:.6} {:.6} {:.6}\n outer loop\n", n.0, n.1, n.2));
        for v in [a, b, c] { s.push_str(&format!("  vertex {:.4} {:.4} {:.4}\n", v.0, v.1, v.2)); }
        s.push_str(" endloop\nendfacet\n");
    }
    s.push_str(&format!("endsolid {name}\n"));
    s
}

fn normal(a: V3, b: V3, c: V3) -> V3 {
    let u = (b.0 - a.0, b.1 - a.1, b.2 - a.2);
    let v = (c.0 - a.0, c.1 - a.1, c.2 - a.2);
    let n = (u.1 * v.2 - u.2 * v.1, u.2 * v.0 - u.0 * v.2, u.0 * v.1 - u.1 * v.0);
    let l = (n.0 * n.0 + n.1 * n.1 + n.2 * n.2).sqrt().max(1e-12);
    (n.0 / l, n.1 / l, n.2 / l)
}

pub fn step_string(p: &Phenotype, name: &str) -> String {
    let safe: String = name.chars().map(|c| if c.is_ascii_alphanumeric() || c == '_' { c } else { '_' }).collect();
    let Some(mesh) = p.solid_mesh() else {
        return format!("ISO-10303-21;\nHEADER;\nENDSEC;\nDATA;\n/* mesh failed */\nENDSEC;\nEND-ISO-10303-21;\n");
    };
    let mut s = String::from("ISO-10303-21;\nHEADER;\nFILE_DESCRIPTION(('jarambit SWITCHBACK faceted solid'),'2;1');\n");
    s.push_str(&format!("FILE_NAME('{safe}.step','2026-10-11',(''),(''),'jarambit','jarambit','');\nFILE_SCHEMA(('AUTOMOTIVE_DESIGN'));\nENDSEC;\nDATA;\n"));
    let mut id = 1usize;
    let mut point_id = Vec::with_capacity(mesh.verts.len());
    let mut vertex_id = Vec::with_capacity(mesh.verts.len());
    for v in &mesh.verts {
        s.push_str(&format!("#{id}=CARTESIAN_POINT('',({:.5},{:.5},{:.5}));\n", v.0, v.1, v.2));
        point_id.push(id); id += 1;
        s.push_str(&format!("#{id}=VERTEX_POINT('',#{});\n", point_id[point_id.len() - 1]));
        vertex_id.push(id); id += 1;
    }
    use std::collections::HashMap;
    let mut edge_of: HashMap<(usize, usize), (usize, bool)> = HashMap::new();
    let mut face_ids = Vec::with_capacity(mesh.tris.len());
    for tri in &mesh.tris {
        let mut oriented = Vec::with_capacity(3);
        for k in 0..3 {
            let a = tri[k]; let b = tri[(k + 1) % 3];
            let (lo, hi, fwd) = if a < b { (a, b, true) } else { (b, a, false) };
            let edge_id = if let Some((eid, stored_fwd)) = edge_of.get(&(lo, hi)) {
                // stored EDGE_CURVE runs lo -> hi when stored_fwd, else hi -> lo
                let _ = stored_fwd;
                *eid
            } else {
                let (va, vb) = (vertex_id[lo], vertex_id[hi]);
                let pa = mesh.verts[lo]; let pb = mesh.verts[hi];
                let d = (pb.0 - pa.0, pb.1 - pa.1, pb.2 - pa.2);
                let len = (d.0 * d.0 + d.1 * d.1 + d.2 * d.2).sqrt().max(1e-9);
                s.push_str(&format!("#{id}=DIRECTION('',({:.6},{:.6},{:.6}));\n", d.0 / len, d.1 / len, d.2 / len));
                let dir = id; id += 1;
                s.push_str(&format!("#{id}=VECTOR('',#{dir},1.);\n"));
                let vec = id; id += 1;
                s.push_str(&format!("#{id}=LINE('',#{},#{vec});\n", point_id[lo]));
                let line = id; id += 1;
                s.push_str(&format!("#{id}=EDGE_CURVE('',#{va},#{vb},#{line},.T.);\n"));
                let eid = id; id += 1;
                edge_of.insert((lo, hi), (eid, true));
                eid
            };
            // EDGE_CURVE is lo -> hi. Face wants a -> b.
            let sense = if a == lo { ".T." } else { ".F." };
            let _ = fwd;
            s.push_str(&format!("#{id}=ORIENTED_EDGE('',*,*,#{edge_id},{sense});\n"));
            oriented.push(id); id += 1;
        }
        let refs: Vec<String> = oriented.iter().map(|i| format!("#{i}")).collect();
        s.push_str(&format!("#{id}=EDGE_LOOP('',({}));\n", refs.join(",")));
        let loop_id = id; id += 1;
        s.push_str(&format!("#{id}=FACE_OUTER_BOUND('',#{loop_id},.T.);\n"));
        let bound = id; id += 1;
        let a = mesh.verts[tri[0]]; let b = mesh.verts[tri[1]]; let c = mesh.verts[tri[2]];
        let n = normal(a, b, c);
        let rd = {
            let d = (b.0 - a.0, b.1 - a.1, b.2 - a.2);
            let along = d.0 * n.0 + d.1 * n.1 + d.2 * n.2;
            let r = (d.0 - along * n.0, d.1 - along * n.1, d.2 - along * n.2);
            let l = (r.0 * r.0 + r.1 * r.1 + r.2 * r.2).sqrt().max(1e-9);
            (r.0 / l, r.1 / l, r.2 / l)
        };
        s.push_str(&format!("#{id}=CARTESIAN_POINT('',({:.5},{:.5},{:.5}));\n", a.0, a.1, a.2));
        let origin = id; id += 1;
        s.push_str(&format!("#{id}=DIRECTION('',({:.6},{:.6},{:.6}));\n", n.0, n.1, n.2));
        let nd = id; id += 1;
        s.push_str(&format!("#{id}=DIRECTION('',({:.6},{:.6},{:.6}));\n", rd.0, rd.1, rd.2));
        let rdir = id; id += 1;
        s.push_str(&format!("#{id}=AXIS2_PLACEMENT_3D('',#{origin},#{nd},#{rdir});\n"));
        let axis = id; id += 1;
        s.push_str(&format!("#{id}=PLANE('',#{axis});\n"));
        let plane = id; id += 1;
        s.push_str(&format!("#{id}=ADVANCED_FACE('',(#{bound}),#{plane},.T.);\n"));
        face_ids.push(id); id += 1;
    }
    let faces: Vec<String> = face_ids.iter().map(|i| format!("#{i}")).collect();
    s.push_str(&format!("#{id}=CLOSED_SHELL('',({}));\n", faces.join(",")));
    let shell = id; id += 1;
    s.push_str(&format!("#{id}=MANIFOLD_SOLID_BREP('{safe}',#{shell});\n"));
    s.push_str("ENDSEC;\nEND-ISO-10303-21;\n");
    s
}

#[cfg(test)]
mod tests {
    use super::*;
    use jarambit_genotype::{Genotype, Rng};

    #[test] fn random_extrusion_is_watertight_and_step_is_brep() {
        let mut r = Rng(8);
        for _ in 0..30 {
            let g = Genotype::random(&mut r);
            let p = Phenotype::from_genotype(&g);
            let mesh = p.solid_mesh().expect("mesh");
            let (once, _twice, more, dir_max) = edge_census(&mesh.tris);
            assert_eq!(once, 0, "boundary edges");
            assert_eq!(more, 0, "nonmanifold edges");
            assert_eq!(dir_max, 1, "inconsistent orientation");
            let step = p.to_step("switchback");
            assert!(step.contains("MANIFOLD_SOLID_BREP"));
            assert!(step.contains("CLOSED_SHELL"));
            assert!(step.contains("ADVANCED_FACE"));
            assert!(!step.contains("POLYLINE"));
            let faces = step.matches("ADVANCED_FACE").count();
            assert_eq!(faces, mesh.tris.len());
        }
    }
}
