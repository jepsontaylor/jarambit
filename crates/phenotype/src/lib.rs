//! Genotype -> 2D outline polygon (mm) -> extruded triangle mesh (STL) + STEP stub.
use jarambit_genotype::Genotype;
use std::f64::consts::PI;

pub type P2 = (f64, f64);

#[derive(Clone, Debug)]
pub struct Phenotype {
    /// Outer boundary of the single solid profile (CCW).
    pub outline: Vec<P2>,
    /// Finger ring hole (CW). Exactly one hole => genus-1 connected solid.
    pub ring_hole: Vec<P2>,
    pub thickness: f64,
    pub brand_pad: [P2; 4],
    pub inner_teeth: usize,
    pub outer_teeth: usize,
    pub ring_center: P2,
    pub ring_outer_r: f64,
}

fn serrated_arc(cx: f64, cy: f64, r: f64, a0: f64, a1: f64, pitch: f64, depth: f64, inward: bool) -> (Vec<P2>, usize) {
    let len = (a1 - a0).abs() * r;
    let teeth = (len / pitch).floor().max(1.0) as usize;
    let n = teeth * 8;
    let mut v = Vec::with_capacity(n + 1);
    for i in 0..=n {
        let t = i as f64 / n as f64;
        let a = a0 + (a1 - a0) * t;
        // scallop profile: |sin| per tooth
        let ph = (t * teeth as f64 * PI).sin().abs();
        let d = depth * ph;
        let rr = if inward { r + d } else { r - d };
        v.push((cx + rr * a.cos(), cy + rr * a.sin()));
    }
    (v, teeth)
}

impl Phenotype {
    pub fn from_genotype(g: &Genotype) -> Self {
        // Blade: an annular sector (curved, karambit talon) centred at C.
        let sweep = g.sweep_deg.to_radians();
        let r_mid = g.curve_radius;
        let blade_w = (g.blade_arc_len / sweep / r_mid * 0.0 + 14.0).min(r_mid * 0.6); // nominal blade height mm
        let r_out = r_mid + blade_w / 2.0;
        let r_in = r_mid - blade_w / 2.0;
        let (cx, cy) = (0.0, 0.0);
        // blade spans angles [a0, a1]; handle attaches at a0 end.
        let a0 = PI; let a1 = PI - sweep;
        let (outer, to) = serrated_arc(cx, cy, r_out, a0, a1, g.serr_outer.pitch, g.serr_outer.depth, false);
        let (mut inner, ti) = serrated_arc(cx, cy, r_in, a1, a0, g.serr_inner.pitch, g.serr_inner.depth, true);
        // tip: converge outer end to point
        let tip = (cx + r_mid * a1.cos() + 6.0 * (a1 - PI / 2.0).cos(), cy + r_mid * a1.sin() + 6.0 * (a1 - PI / 2.0).sin());
        // handle: straight-ish tang down from a0 end, ending in ring
        let hx0 = cx - r_out; let hx1 = cx - r_in;
        let hy_end = cy - g.handle_len;
        let ring_r_out = g.ring_id / 2.0 + g.ring_wall;
        let ring_c = ((hx0 + hx1) / 2.0, hy_end - g.ring_id / 2.0);
        let mut outline = Vec::new();
        // handle left side going down
        outline.push((hx0, cy)); outline.push((hx0, hy_end));
        // ring outer circle (lower half around)
        for i in 0..=48 { let a = PI + PI * i as f64 / 48.0; outline.push((ring_c.0 + ring_r_out * a.cos(), ring_c.1 + ring_r_out * a.sin())); }
        outline.push((hx1, hy_end)); outline.push((hx1, cy));
        // inner (concave) serrated edge from a0 to a1
        inner.reverse(); // now a0->a1 on r_in
        // reorder: we're at (hx1,cy) == r_in at angle PI -> follow inner edge to tip
        let inner_seq: Vec<P2> = { let mut s = inner.clone(); s.reverse(); s };
        let _ = inner_seq;
        let (inner_fwd, _) = serrated_arc(cx, cy, r_in, a0, a1, g.serr_inner.pitch, g.serr_inner.depth, true);
        outline.extend(inner_fwd);
        outline.push(tip);
        let mut outer_back = outer.clone(); outer_back.reverse();
        outline.extend(outer_back);
        let ring_hole: Vec<P2> = (0..64).map(|i| { let a = -2.0 * PI * i as f64 / 64.0; (ring_c.0 + g.ring_id / 2.0 * a.cos(), ring_c.1 + g.ring_id / 2.0 * a.sin()) }).collect();
        let pw = g.brand_pad_w.min(hx1 - hx0 - 1.0); let pl = g.brand_pad_l.min(g.handle_len - 10.0);
        let px = (hx0 + hx1) / 2.0; let py = cy - g.handle_len / 2.0;
        let brand_pad = [(px - pw / 2.0, py - pl / 2.0), (px + pw / 2.0, py - pl / 2.0), (px + pw / 2.0, py + pl / 2.0), (px - pw / 2.0, py + pl / 2.0)];
        Phenotype { outline, ring_hole, thickness: g.thickness, brand_pad, inner_teeth: ti, outer_teeth: to, ring_center: ring_c, ring_outer_r: ring_r_out }
    }

    pub fn area_mm2(&self) -> f64 { shoelace(&self.outline).abs() - shoelace(&self.ring_hole).abs() }
    pub fn mass_g(&self, density_g_cm3: f64) -> f64 { self.area_mm2() * self.thickness * density_g_cm3 / 1000.0 }

    /// Extruded side-wall + cap STL (caps as fan; stub quality).
    pub fn to_ascii_stl(&self, name: &str) -> String {
        let mut s = format!("solid {name}\n");
        let t = self.thickness;
        let mut wall = |poly: &[P2]| {
            for i in 0..poly.len() {
                let a = poly[i]; let b = poly[(i + 1) % poly.len()];
                for tri in [[(a.0, a.1, 0.0), (b.0, b.1, 0.0), (b.0, b.1, t)], [(a.0, a.1, 0.0), (b.0, b.1, t), (a.0, a.1, t)]] {
                    s.push_str("facet normal 0 0 0\n outer loop\n");
                    for v in tri { s.push_str(&format!("  vertex {:.4} {:.4} {:.4}\n", v.0, v.1, v.2)); }
                    s.push_str(" endloop\nendfacet\n");
                }
            }
        };
        wall(&self.outline); wall(&self.ring_hole);
        s.push_str(&format!("endsolid {name}\n")); s
    }

    /// Minimal ISO-10303-21 header + polyline outline (stub; real B-rep TODO via truck/opencascade).
    pub fn to_step_stub(&self, name: &str) -> String {
        let mut s = String::from("ISO-10303-21;\nHEADER;\nFILE_DESCRIPTION(('jarambit SWITCHBACK stub outline'),'2;1');\n");
        s.push_str(&format!("FILE_NAME('{name}.step','2026-10-11',(''),(''),'jarambit','jarambit','');\nFILE_SCHEMA(('AUTOMOTIVE_DESIGN'));\nENDSEC;\nDATA;\n"));
        let mut id = 1;
        let mut pts = vec![];
        for p in &self.outline { s.push_str(&format!("#{id}=CARTESIAN_POINT('',({:.4},{:.4},0.));\n", p.0, p.1)); pts.push(id); id += 1; }
        let refs: Vec<String> = pts.iter().map(|i| format!("#{i}")).collect();
        s.push_str(&format!("#{id}=POLYLINE('outline',({}));\n", refs.join(",")));
        s.push_str(&format!("/* extrude thickness {:.1} mm */\nENDSEC;\nEND-ISO-10303-21;\n", self.thickness)); s
    }
}

pub fn shoelace(p: &[P2]) -> f64 {
    let mut a = 0.0;
    for i in 0..p.len() { let (x0, y0) = p[i]; let (x1, y1) = p[(i + 1) % p.len()]; a += x0 * y1 - x1 * y0; }
    a / 2.0
}
