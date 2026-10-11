//! Watertight variable-thickness solid (top z=+t/2, bottom z=-t/2 over a CDT of the planform,
//! side walls on every boundary edge) -> ASCII STL + faceted MANIFOLD_SOLID_BREP STEP.
use crate::geom::*;
use crate::pheno::*;
use jarambit_physics::fine;
use std::collections::HashMap;
type V3 = (f64, f64, f64);

pub struct Solid { pub verts: Vec<V3>, pub tris: Vec<[usize; 3]> }

pub fn solid(p: &Pheno, max_area: f64) -> Option<Solid> {
    let outer = dp_closed(&p.outline, 0.03);
    let holes: Vec<Vec<P2>> = p.holes.iter().map(|h| dp_closed(h, 0.02)).collect();
    let m = fine::mesh_domain(&outer, &holes, max_area)?;
    let n = m.xy.len();
    let th: Vec<f64> = m.xy.iter().map(|&q| p.field.at(q).max(0.3)).collect();
    let mut verts: Vec<V3> = m.xy.iter().zip(&th).map(|(q, t)| (q.0, q.1, t / 2.0)).collect();
    verts.extend(m.xy.iter().zip(&th).map(|(q, t)| (q.0, q.1, -t / 2.0)));
    let mut tris: Vec<[usize; 3]> = Vec::with_capacity(m.tris.len() * 2 + 2000);
    let mut cnt: HashMap<(usize, usize), (usize, (usize, usize))> = HashMap::new();
    for t in &m.tris {
        tris.push(*t); tris.push([t[0] + n, t[2] + n, t[1] + n]);
        for k in 0..3 { let (a, b) = (t[k], t[(k + 1) % 3]); let e = cnt.entry((a.min(b), a.max(b))).or_insert((0, (a, b))); e.0 += 1; }
    }
    for (_, (c, (a, b))) in cnt { if c == 1 { tris.push([a, a + n, b + n]); tris.push([a, b + n, b]); } }
    Some(Solid { verts, tris })
}

pub fn census(tris: &[[usize; 3]]) -> (usize, usize, usize) {
    let mut und: HashMap<(usize, usize), usize> = HashMap::new(); let mut dir: HashMap<(usize, usize), usize> = HashMap::new();
    for t in tris { for k in 0..3 { let (a, b) = (t[k], t[(k + 1) % 3]); *dir.entry((a, b)).or_default() += 1; *und.entry((a.min(b), a.max(b))).or_default() += 1; } }
    let once = und.values().filter(|&&v| v == 1).count(); let more = und.values().filter(|&&v| v > 2).count();
    (once, more, dir.values().copied().max().unwrap_or(0))
}

pub fn volume(s: &Solid) -> f64 {
    s.tris.iter().map(|t| { let (a, b, c) = (s.verts[t[0]], s.verts[t[1]], s.verts[t[2]]);
        (a.0 * (b.1 * c.2 - b.2 * c.1) - a.1 * (b.0 * c.2 - b.2 * c.0) + a.2 * (b.0 * c.1 - b.1 * c.0)) / 6.0 }).sum()
}

fn normal(a: V3, b: V3, c: V3) -> V3 {
    let u = (b.0 - a.0, b.1 - a.1, b.2 - a.2); let v = (c.0 - a.0, c.1 - a.1, c.2 - a.2);
    let n = (u.1 * v.2 - u.2 * v.1, u.2 * v.0 - u.0 * v.2, u.0 * v.1 - u.1 * v.0);
    let l = (n.0 * n.0 + n.1 * n.1 + n.2 * n.2).sqrt().max(1e-12); (n.0 / l, n.1 / l, n.2 / l)
}

pub fn stl(s: &Solid, name: &str) -> String {
    let mut o = format!("solid {name}\n");
    for t in &s.tris { let (a, b, c) = (s.verts[t[0]], s.verts[t[1]], s.verts[t[2]]); let nn = normal(a, b, c);
        o.push_str(&format!("facet normal {:.6} {:.6} {:.6}\n outer loop\n", nn.0, nn.1, nn.2));
        for v in [a, b, c] { o.push_str(&format!("  vertex {:.4} {:.4} {:.4}\n", v.0, v.1, v.2)); }
        o.push_str(" endloop\nendfacet\n"); }
    o.push_str(&format!("endsolid {name}\n")); o
}

pub fn step(s: &Solid, name: &str) -> String {
    let safe: String = name.chars().map(|c| if c.is_ascii_alphanumeric() || c == '_' { c } else { '_' }).collect();
    let mut o = String::from("ISO-10303-21;\nHEADER;\nFILE_DESCRIPTION(('jarambit crescent variable-thickness faceted solid'),'2;1');\n");
    o.push_str(&format!("FILE_NAME('{safe}.step','2026-10-11',('Jepson Taylor'),(''),'jarambit','jarambit','');\nFILE_SCHEMA(('AUTOMOTIVE_DESIGN'));\nENDSEC;\nDATA;\n"));
    let mut id = 1usize; let mut pid = Vec::new(); let mut vid = Vec::new();
    for v in &s.verts { o.push_str(&format!("#{id}=CARTESIAN_POINT('',({:.5},{:.5},{:.5}));\n", v.0, v.1, v.2)); pid.push(id); id += 1;
        o.push_str(&format!("#{id}=VERTEX_POINT('',#{});\n", id - 1)); vid.push(id); id += 1; }
    let mut edge: HashMap<(usize, usize), usize> = HashMap::new(); let mut faces = Vec::new();
    for t in &s.tris {
        let mut oe = Vec::new();
        for k in 0..3 { let (a, b) = (t[k], t[(k + 1) % 3]); let (lo, hi) = (a.min(b), a.max(b));
            let eid = if let Some(e) = edge.get(&(lo, hi)) { *e } else {
                let (pa, pb) = (s.verts[lo], s.verts[hi]); let d = (pb.0 - pa.0, pb.1 - pa.1, pb.2 - pa.2); let l = (d.0 * d.0 + d.1 * d.1 + d.2 * d.2).sqrt().max(1e-9);
                o.push_str(&format!("#{id}=DIRECTION('',({:.6},{:.6},{:.6}));\n", d.0 / l, d.1 / l, d.2 / l)); let di = id; id += 1;
                o.push_str(&format!("#{id}=VECTOR('',#{di},1.);\n")); let ve = id; id += 1;
                o.push_str(&format!("#{id}=LINE('',#{},#{ve});\n", pid[lo])); let li = id; id += 1;
                o.push_str(&format!("#{id}=EDGE_CURVE('',#{},#{},#{li},.T.);\n", vid[lo], vid[hi])); let e = id; id += 1;
                edge.insert((lo, hi), e); e };
            o.push_str(&format!("#{id}=ORIENTED_EDGE('',*,*,#{eid},{});\n", if a == lo { ".T." } else { ".F." })); oe.push(id); id += 1; }
        o.push_str(&format!("#{id}=EDGE_LOOP('',(#{},#{},#{}));\n", oe[0], oe[1], oe[2])); let lp = id; id += 1;
        o.push_str(&format!("#{id}=FACE_OUTER_BOUND('',#{lp},.T.);\n")); let bd = id; id += 1;
        let (a, b, c) = (s.verts[t[0]], s.verts[t[1]], s.verts[t[2]]); let nn = normal(a, b, c);
        let d = (b.0 - a.0, b.1 - a.1, b.2 - a.2); let al = d.0 * nn.0 + d.1 * nn.1 + d.2 * nn.2;
        let rd = { let r = (d.0 - al * nn.0, d.1 - al * nn.1, d.2 - al * nn.2); let l = (r.0 * r.0 + r.1 * r.1 + r.2 * r.2).sqrt().max(1e-9); (r.0 / l, r.1 / l, r.2 / l) };
        o.push_str(&format!("#{id}=CARTESIAN_POINT('',({:.5},{:.5},{:.5}));\n", a.0, a.1, a.2)); let og = id; id += 1;
        o.push_str(&format!("#{id}=DIRECTION('',({:.6},{:.6},{:.6}));\n", nn.0, nn.1, nn.2)); let nd = id; id += 1;
        o.push_str(&format!("#{id}=DIRECTION('',({:.6},{:.6},{:.6}));\n", rd.0, rd.1, rd.2)); let rdi = id; id += 1;
        o.push_str(&format!("#{id}=AXIS2_PLACEMENT_3D('',#{og},#{nd},#{rdi});\n")); let ax = id; id += 1;
        o.push_str(&format!("#{id}=PLANE('',#{ax});\n")); let pl = id; id += 1;
        o.push_str(&format!("#{id}=ADVANCED_FACE('',(#{bd}),#{pl},.T.);\n")); faces.push(id); id += 1;
    }
    let fs: Vec<String> = faces.iter().map(|i| format!("#{i}")).collect();
    o.push_str(&format!("#{id}=CLOSED_SHELL('',({}));\n", fs.join(","))); let sh = id; id += 1;
    o.push_str(&format!("#{id}=MANIFOLD_SOLID_BREP('{safe}',#{sh});\nENDSEC;\nEND-ISO-10303-21;\n"));
    o
}
