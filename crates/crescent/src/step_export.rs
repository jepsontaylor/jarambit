//! STEP serialization: planar CAD faces plus analytic toroidal bore rolls and cylindrical bearing.
use crate::export::Solid;
use std::collections::HashMap;
use std::fmt::Write as _;
type V3 = (f64, f64, f64);
struct Writer<'a> {
    out: String,
    next: usize,
    s: &'a Solid,
    pid: Vec<usize>,
    vid: Vec<usize>,
    edges: HashMap<(usize, usize), usize>,
    faces: Vec<usize>,
}
impl<'a> Writer<'a> {
    fn entity(&mut self, value: String) -> usize {
        let i = self.next;
        self.next += 1;
        writeln!(self.out, "#{i}={value};").unwrap();
        i
    }
    fn point(&mut self, p: V3) -> usize {
        self.entity(format!(
            "CARTESIAN_POINT('',({:.12},{:.12},{:.12}))",
            p.0, p.1, p.2
        ))
    }
    fn direction(&mut self, p: V3) -> usize {
        self.entity(format!(
            "DIRECTION('',({:.12},{:.12},{:.12}))",
            p.0, p.1, p.2
        ))
    }
    fn axis(&mut self, p: V3, n: V3, x: V3) -> usize {
        let p = self.point(p);
        let n = self.direction(n);
        let x = self.direction(x);
        self.entity(format!("AXIS2_PLACEMENT_3D('',#{p},#{n},#{x})"))
    }
    fn line(&mut self, a: usize, b: usize) -> usize {
        let key = (a.min(b), a.max(b));
        if let Some(&e) = self.edges.get(&key) {
            return e;
        }
        let (pa, pb) = (self.s.verts[key.0], self.s.verts[key.1]);
        let d = (pb.0 - pa.0, pb.1 - pa.1, pb.2 - pa.2);
        let l = (d.0 * d.0 + d.1 * d.1 + d.2 * d.2).sqrt();
        let di = self.direction((d.0 / l, d.1 / l, d.2 / l));
        let ve = self.entity(format!("VECTOR('',#{di},1.)"));
        let li = self.entity(format!("LINE('',#{},#{ve})", self.pid[key.0]));
        let e = self.entity(format!(
            "EDGE_CURVE('',#{},#{},#{li},.T.)",
            self.vid[key.0], self.vid[key.1]
        ));
        self.edges.insert(key, e);
        e
    }
    fn arc(&mut self, a: usize, b: usize, center: V3, normal: V3, x: V3, r: f64, forward: bool) {
        let key = (a.min(b), a.max(b));
        if self.edges.contains_key(&key) {
            return;
        }
        let ax = self.axis(center, normal, x);
        let curve = self.entity(format!("CIRCLE('',#{ax},{r:.12})"));
        let sense = if forward == (a == key.0) {
            ".T."
        } else {
            ".F."
        };
        let e = self.entity(format!(
            "EDGE_CURVE('',#{},#{},#{curve},{sense})",
            self.vid[key.0], self.vid[key.1]
        ));
        self.edges.insert(key, e);
    }
    fn loop_of(&mut self, indices: &[usize]) -> usize {
        let mut edges = Vec::new();
        for j in 0..indices.len() {
            let (a, b) = (indices[j], indices[(j + 1) % indices.len()]);
            let e = self.line(a, b);
            let orientation = if a < b { ".T." } else { ".F." };
            edges.push(self.entity(format!("ORIENTED_EDGE('',*,*,#{e},{orientation})")));
        }
        let ids = edges
            .iter()
            .map(|x| format!("#{x}"))
            .collect::<Vec<_>>()
            .join(",");
        self.entity(format!("EDGE_LOOP('',({ids}))"))
    }
    fn face(&mut self, outer: &[usize], hole: Option<&[usize]>, surface: usize, same: bool) {
        let lp = self.loop_of(outer);
        let bound = self.entity(format!("FACE_OUTER_BOUND('',#{lp},.T.)"));
        let mut bounds = vec![bound];
        if let Some(hole) = hole {
            let lp = self.loop_of(hole);
            bounds.push(self.entity(format!("FACE_BOUND('',#{lp},.T.)")));
        }
        let ids = bounds
            .iter()
            .map(|i| format!("#{i}"))
            .collect::<Vec<_>>()
            .join(",");
        let sense = if same { ".T." } else { ".F." };
        let f = self.entity(format!("ADVANCED_FACE('',({ids}),#{surface},{sense})"));
        self.faces.push(f);
    }
    fn plane(&mut self, origin: V3, normal: V3, x: V3) -> usize {
        let a = self.axis(origin, normal, x);
        self.entity(format!("PLANE('',#{a})"))
    }
    fn faceted(&mut self, t: [usize; 3]) {
        let (a, b, c) = (self.s.verts[t[0]], self.s.verts[t[1]], self.s.verts[t[2]]);
        let u = (b.0 - a.0, b.1 - a.1, b.2 - a.2);
        let v = (c.0 - a.0, c.1 - a.1, c.2 - a.2);
        let nn = (
            u.1 * v.2 - u.2 * v.1,
            u.2 * v.0 - u.0 * v.2,
            u.0 * v.1 - u.1 * v.0,
        );
        let l = (nn.0 * nn.0 + nn.1 * nn.1 + nn.2 * nn.2).sqrt();
        let ul = (u.0 * u.0 + u.1 * u.1 + u.2 * u.2).sqrt();
        let surf = self.plane(
            a,
            (nn.0 / l, nn.1 / l, nn.2 / l),
            (u.0 / ul, u.1 / ul, u.2 / ul),
        );
        self.face(&t, None, surf, true);
    }
    fn bore(&mut self) {
        let Some(bore) = self.s.bore.as_ref() else {
            return;
        };
        let rows = bore.profiles.clone();
        let (r, w, m) = (bore.radius, bore.bearing, bore.inner_radius + bore.radius);
        let upper = self.axis((0., 0., w / 2.), (0., 0., 1.), (1., 0., 0.));
        let top = self.entity(format!("TOROIDAL_SURFACE('',#{upper},{m:.12},{r:.12})"));
        let lower = self.axis((0., 0., -w / 2.), (0., 0., 1.), (1., 0., 0.));
        let bottom = self.entity(format!("TOROIDAL_SURFACE('',#{lower},{m:.12},{r:.12})"));
        let axis = self.axis((0., 0., 0.), (0., 0., 1.), (1., 0., 0.));
        let cylinder = self.entity(format!(
            "CYLINDRICAL_SURFACE('',#{axis},{:.12})",
            bore.inner_radius
        ));
        for i in 0..rows.len() {
            let a = rows[i];
            let b = rows[(i + 1) % rows.len()];
            for (j, z, rr) in [
                (2, w / 2. + r, m),
                (3, -w / 2. - r, m),
                (4, w / 2., bore.inner_radius),
                (5, -w / 2., bore.inner_radius),
            ] {
                self.arc(
                    a[j],
                    b[j],
                    (0., 0., z),
                    (0., 0., 1.),
                    (1., 0., 0.),
                    rr,
                    true,
                );
            }
            for row in [a, b] {
                let p = self.s.verts[row[4]];
                let n = (p.0 / bore.inner_radius, p.1 / bore.inner_radius, 0.);
                self.arc(
                    row[4],
                    row[2],
                    (m * n.0, m * n.1, w / 2.),
                    (-n.1, n.0, 0.),
                    (-n.0, -n.1, 0.),
                    r,
                    true,
                );
                self.arc(
                    row[5],
                    row[3],
                    (m * n.0, m * n.1, -w / 2.),
                    (n.1, -n.0, 0.),
                    (-n.0, -n.1, 0.),
                    r,
                    true,
                );
            }
            // rows are CCW; these loops orient the skin toward the hole and out of the part.
            self.face(&[a[2], b[2], b[4], a[4]], None, top, true);
            self.face(&[a[3], a[5], b[5], b[3]], None, bottom, true);
            self.face(&[a[4], b[4], b[5], a[5]], None, cylinder, false);
        }
        let outer_top = rows.iter().map(|r| r[0]).collect::<Vec<_>>();
        let inner_top = rows.iter().rev().map(|r| r[2]).collect::<Vec<_>>();
        let outer_bottom = rows.iter().rev().map(|r| r[1]).collect::<Vec<_>>();
        let inner_bottom = rows.iter().map(|r| r[3]).collect::<Vec<_>>();
        let plane = self.plane((0., 0., w / 2. + r), (0., 0., 1.), (1., 0., 0.));
        self.face(&outer_top, Some(&inner_top), plane, true);
        let plane = self.plane((0., 0., -w / 2. - r), (0., 0., -1.), (1., 0., 0.));
        self.face(&outer_bottom, Some(&inner_bottom), plane, true);
    }
}
pub fn write(s: &Solid, name: &str) -> String {
    let safe: String = name
        .chars()
        .map(|c| {
            if c.is_ascii_alphanumeric() || c == '_' {
                c
            } else {
                '_'
            }
        })
        .collect();
    let mut w=Writer{out:format!("ISO-10303-21;\nHEADER;\nFILE_DESCRIPTION(('genome-generated solid; analytic bore fillets'),'2;1');\nFILE_NAME('{safe}.step','2026-10-17',('Jepson Taylor'),(''),'jarambit','jarambit','');\nFILE_SCHEMA(('AUTOMOTIVE_DESIGN'));\nENDSEC;\nDATA;\n"),next:1,s,pid:Vec::new(),vid:Vec::new(),edges:HashMap::new(),faces:Vec::new()};
    for &p in &s.verts {
        let id = w.point(p);
        w.pid.push(id);
        let v = w.entity(format!("VERTEX_POINT('',#{id})"));
        w.vid.push(v);
    }
    let n = s.bore.as_ref().map_or(s.tris.len(), |b| b.faceted_faces);
    for &t in &s.tris[..n] {
        w.faceted(t);
    }
    w.bore();
    let ids = w
        .faces
        .iter()
        .map(|i| format!("#{i}"))
        .collect::<Vec<_>>()
        .join(",");
    let shell = w.entity(format!("CLOSED_SHELL('',({ids}))"));
    let brep = w.entity(format!("MANIFOLD_SOLID_BREP('{safe}',#{shell})"));
    let length = w.entity("(LENGTH_UNIT() NAMED_UNIT(*) SI_UNIT(.MILLI.,.METRE.))".into());
    let angle = w.entity("(NAMED_UNIT(*) PLANE_ANGLE_UNIT() SI_UNIT($,.RADIAN.))".into());
    let solid_angle = w.entity("(NAMED_UNIT(*) SI_UNIT($,.STERADIAN.) SOLID_ANGLE_UNIT())".into());
    let uncertainty=w.entity(format!("UNCERTAINTY_MEASURE_WITH_UNIT(LENGTH_MEASURE(1.E-7),#{length},'distance_accuracy_value','export precision')"));
    let context=w.entity(format!("(GEOMETRIC_REPRESENTATION_CONTEXT(3) GLOBAL_UNCERTAINTY_ASSIGNED_CONTEXT((#{uncertainty})) GLOBAL_UNIT_ASSIGNED_CONTEXT((#{length},#{angle},#{solid_angle})) REPRESENTATION_CONTEXT('','3D'))"));
    let representation = w.entity(format!(
        "ADVANCED_BREP_SHAPE_REPRESENTATION('{safe}',(#{brep}),#{context})"
    ));
    let app = w.entity("APPLICATION_CONTEXT('automotive_design')".into());
    let pc = w.entity(format!("PRODUCT_CONTEXT('',#{app},'mechanical')"));
    let product = w.entity(format!(
        "PRODUCT('{safe}','{safe}','genome-generated CAD',(#{pc}))"
    ));
    let form = w.entity(format!(
        "PRODUCT_DEFINITION_FORMATION_WITH_SPECIFIED_SOURCE('','',#{product},.NOT_KNOWN.)"
    ));
    let dc = w.entity(format!(
        "PRODUCT_DEFINITION_CONTEXT('part definition',#{app},'design')"
    ));
    let definition = w.entity(format!("PRODUCT_DEFINITION('design','',#{form},#{dc})"));
    let shape = w.entity(format!("PRODUCT_DEFINITION_SHAPE('','',#{definition})"));
    w.entity(format!(
        "SHAPE_DEFINITION_REPRESENTATION(#{shape},#{representation})"
    ));
    w.out.push_str("ENDSEC;\nEND-ISO-10303-21;\n");
    w.out
}
