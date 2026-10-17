//! Pure-Rust 3D `.stl` (binary & ASCII) and `.step` (`ISO-10303-21`) triangle parser,
//! watertight manifold topology census, signed tetrahedral volume calculator, and
//! exact `0.50 mm` barycentric 2.5D thickness rasterizer (`ops/ci/score_cad.py` parity).

use crate::export::{self, Solid};
use std::collections::HashMap;

pub const TI64_DENSITY_G_PER_MM3: f64 = 0.00443;
pub const TI64_SY20_MPA: f64 = 828.0;
pub const TI64_E_MPA: f64 = 113_800.0;
pub const TI64_NU: f64 = 0.34;

pub type V3 = (f64, f64, f64);

#[derive(Clone, Debug)]
pub struct MeshCensus {
    pub facets: usize,
    pub vertices: usize,
    pub boundary_edges: usize,
    pub non_manifold_edges: usize,
    pub max_directed_edge_repeat: usize,
    pub watertight_exact: bool,
    pub volume_mm3: f64,
    pub mass_3d_g: f64,
}

#[derive(Clone, Debug)]
pub struct StepHeaderMeta {
    pub has_iso: bool,
    pub has_mm_decl: bool,
    pub manifold_solids: usize,
    pub closed_shells: usize,
    pub advanced_faces: usize,
}

#[derive(Clone, Debug)]
pub struct RasterizedCadMetrics {
    pub t_stock_mm: f64,
    pub t_joint_mm: f64,
    pub mass_raster_g: f64,
    pub rel_mass_diff: f64,
    pub ring_id_mm: f64,
    pub ring_od_mm: f64,
    pub ring_wall_mm: f64,
    pub groove_w_mm: f64,
    pub tip_xy: (f64, f64),
    pub heel_xy: (f64, f64),
    pub tip_to_heel_mm: f64,
    pub horizontal_reach_mm: f64,
    pub sharpened_arc_mm: f64,
    pub hook_drop_mm: f64,
    pub blade_min_mm: f64,
    pub lat_rob_cert_n: f64,
    pub strict_lat_rob_0p0625_n: f64,
    pub ring_rob_cert_n: f64,
    pub seq_ratio: f64,
    pub pk_all: f64,
    pub sallow_bend: f64,
    pub t_tip_eff: f64,
}

#[inline]
pub fn round_n(v: f64, digits: i32) -> f64 {
    let p = 10f64.powi(digits);
    (v * p).round() / p
}

/// Deduplicate a flat list of `3 * n_tri` vertices into `(verts, tris)` sorted lexicographically
/// (matching `np.unique(flat, axis=0, return_inverse=True)`).
pub fn deduplicate_triangles(flat: &[V3]) -> Result<Solid, String> {
    if flat.is_empty() || flat.len() % 3 != 0 {
        return Err("triangle vertex count must be a non-empty multiple of 3".into());
    }
    let norm_bits = |x: f64| -> u64 {
        if x == 0.0 {
            0.0f64.to_bits()
        } else {
            x.to_bits()
        }
    };
    let mut unique: Vec<V3> = flat.to_vec();
    unique.sort_by(|a, b| {
        a.0.total_cmp(&b.0)
            .then_with(|| a.1.total_cmp(&b.1))
            .then_with(|| a.2.total_cmp(&b.2))
    });
    unique.dedup_by(|a, b| {
        norm_bits(a.0) == norm_bits(b.0)
            && norm_bits(a.1) == norm_bits(b.1)
            && norm_bits(a.2) == norm_bits(b.2)
    });
    let mut map: HashMap<(u64, u64, u64), usize> = HashMap::with_capacity(unique.len());
    for (idx, &v) in unique.iter().enumerate() {
        map.insert((norm_bits(v.0), norm_bits(v.1), norm_bits(v.2)), idx);
    }
    let mut tris = Vec::with_capacity(flat.len() / 3);
    for chunk in flat.chunks_exact(3) {
        let i0 = map[&(norm_bits(chunk[0].0), norm_bits(chunk[0].1), norm_bits(chunk[0].2))];
        let i1 = map[&(norm_bits(chunk[1].0), norm_bits(chunk[1].1), norm_bits(chunk[1].2))];
        let i2 = map[&(norm_bits(chunk[2].0), norm_bits(chunk[2].1), norm_bits(chunk[2].2))];
        tris.push([i0, i1, i2]);
    }
    Ok(Solid {
        verts: unique,
        tris,
        bore: None,
    })
}

/// Parse binary or ASCII `.stl` bytes into a deduplicated [`Solid`].
pub fn parse_stl_triangles(raw: &[u8]) -> Result<Solid, String> {
    let head = String::from_utf8_lossy(&raw[..raw.len().min(512)]);
    let is_ascii = raw.starts_with(b"solid ") && head.contains("facet normal");
    if !is_ascii && raw.len() >= 84 {
        let n_tri = u32::from_le_bytes([raw[80], raw[81], raw[82], raw[83]]) as usize;
        if 84 + n_tri * 50 == raw.len() {
            let mut flat = Vec::with_capacity(n_tri * 3);
            for i in 0..n_tri {
                let base = 84 + i * 50 + 12; // skip 12-byte normal
                for k in 0..3 {
                    let off = base + k * 12;
                    let x = f32::from_le_bytes(raw[off..off + 4].try_into().unwrap()) as f64;
                    let y = f32::from_le_bytes(raw[off + 4..off + 8].try_into().unwrap()) as f64;
                    let z = f32::from_le_bytes(raw[off + 8..off + 12].try_into().unwrap()) as f64;
                    flat.push((x, y, z));
                }
            }
            return deduplicate_triangles(&flat);
        }
    }

    let text = String::from_utf8_lossy(raw);
    let mut flat = Vec::new();
    for line in text.lines() {
        let trimmed = line.trim_start();
        if let Some(rest) = trimmed.strip_prefix("vertex") {
            let mut it = rest.split_whitespace();
            if let (Some(sx), Some(sy), Some(sz)) = (it.next(), it.next(), it.next()) {
                if let (Ok(x), Ok(y), Ok(z)) = (sx.parse::<f64>(), sy.parse::<f64>(), sz.parse::<f64>()) {
                    flat.push((x, y, z));
                }
            }
        }
    }
    deduplicate_triangles(&flat)
}

fn parse_step_id(s: &str) -> Option<usize> {
    let s = s.trim();
    s.strip_prefix('#')?.trim().parse::<usize>().ok()
}

/// Inspect STEP header and entity counts.
pub fn inspect_step_header(text: &str) -> StepHeaderMeta {
    let has_iso = text.trim_start().starts_with("ISO-10303-21;");
    let has_mm_decl = text.contains("SI_UNIT(.MILLI.,.METRE.)") || text.contains("MILLI");
    let manifold_solids = text.matches("MANIFOLD_SOLID_BREP(").count().max(1);
    let closed_shells = text.matches("CLOSED_SHELL(").count().max(1);
    let advanced_faces = text.matches("ADVANCED_FACE(").count();
    StepHeaderMeta {
        has_iso,
        has_mm_decl,
        manifold_solids,
        closed_shells,
        advanced_faces,
    }
}

/// Extract 3D triangles from a faceted `MANIFOLD_SOLID_BREP` STEP file.
pub fn parse_faceted_step_triangles(text: &str) -> Result<Solid, String> {
    let mut pts: HashMap<usize, V3> = HashMap::new();
    let mut vpt: HashMap<usize, usize> = HashMap::new();
    let mut ecurve: HashMap<usize, (usize, usize)> = HashMap::new();
    let mut oedge: HashMap<usize, (usize, bool)> = HashMap::new();
    let mut loops: Vec<Vec<usize>> = Vec::new();

    for raw_line in text.lines() {
        let line = raw_line.trim();
        if !line.starts_with('#') {
            continue;
        }
        let Some((lhs, rhs)) = line.split_once('=') else {
            continue;
        };
        let Some(id) = parse_step_id(lhs) else {
            continue;
        };
        let rhs = rhs.trim().trim_end_matches(';').trim();

        if let Some(body) = rhs.strip_prefix("CARTESIAN_POINT(") {
            if let Some(lp) = body.find('(') {
                if let Some(rp) = body[lp + 1..].find(')') {
                    let coords_str = &body[lp + 1..lp + 1 + rp];
                    let mut it = coords_str.split(',');
                    if let (Some(sx), Some(sy), Some(sz)) = (it.next(), it.next(), it.next()) {
                        if let (Ok(x), Ok(y), Ok(z)) = (
                            sx.trim().parse::<f64>(),
                            sy.trim().parse::<f64>(),
                            sz.trim().parse::<f64>(),
                        ) {
                            pts.insert(id, (x, y, z));
                        }
                    }
                }
            }
        } else if let Some(body) = rhs.strip_prefix("VERTEX_POINT(") {
            let body = body.trim_end_matches(')');
            if let Some((_, ref_str)) = body.rsplit_once(',') {
                if let Some(cp_id) = parse_step_id(ref_str) {
                    vpt.insert(id, cp_id);
                }
            }
        } else if let Some(body) = rhs.strip_prefix("EDGE_CURVE(") {
            let body = body.trim_end_matches(')');
            let parts: Vec<&str> = body.split(',').collect();
            if parts.len() >= 5 {
                if let (Some(v1), Some(v2)) = (parse_step_id(parts[1]), parse_step_id(parts[2])) {
                    ecurve.insert(id, (v1, v2));
                }
            }
        } else if let Some(body) = rhs.strip_prefix("ORIENTED_EDGE(") {
            let body = body.trim_end_matches(')');
            let parts: Vec<&str> = body.split(',').collect();
            if parts.len() >= 5 {
                if let Some(ec_id) = parse_step_id(parts[3]) {
                    let sense = parts[4].trim() == ".T.";
                    oedge.insert(id, (ec_id, sense));
                }
            }
        } else if let Some(body) = rhs.strip_prefix("EDGE_LOOP(") {
            if let Some(lp) = body.find('(') {
                if let Some(rp) = body[lp + 1..].find(')') {
                    let refs_str = &body[lp + 1..lp + 1 + rp];
                    let refs: Vec<usize> = refs_str
                        .split(',')
                        .filter_map(parse_step_id)
                        .collect();
                    if refs.len() >= 3 {
                        loops.push(refs);
                    }
                }
            }
        }
    }

    let mut tri_coords: Vec<V3> = Vec::with_capacity(loops.len() * 3);
    for refs in loops {
        let mut loop_pts: Vec<V3> = Vec::with_capacity(refs.len());
        let mut ok = true;
        for r in refs {
            let Some(&(ec_id, sense)) = oedge.get(&r) else {
                ok = false;
                break;
            };
            let Some(&(v1, v2)) = ecurve.get(&ec_id) else {
                ok = false;
                break;
            };
            let start_v = if sense { v1 } else { v2 };
            let Some(&cp_id) = vpt.get(&start_v) else {
                ok = false;
                break;
            };
            let Some(&pt) = pts.get(&cp_id) else {
                ok = false;
                break;
            };
            loop_pts.push(pt);
        }
        if !ok {
            continue;
        }
        if loop_pts.len() == 3 {
            tri_coords.extend_from_slice(&loop_pts);
        } else if loop_pts.len() > 3 {
            let p0 = loop_pts[0];
            for k in 1..loop_pts.len() - 1 {
                tri_coords.push(p0);
                tri_coords.push(loop_pts[k]);
                tri_coords.push(loop_pts[k + 1]);
            }
        }
    }

    if tri_coords.is_empty() {
        return Err("Could not extract faceted triangles from STEP file".into());
    }
    deduplicate_triangles(&tri_coords)
}

/// Compute edge census and signed volume / Ti-6Al-4V mass of a 3D [`Solid`].
pub fn mesh_census_and_volume(solid: &Solid) -> MeshCensus {
    let (boundary, non_manifold, dmax) = export::census(&solid.tris);
    let vol_mm3 = export::volume(solid).abs();
    let watertight = boundary == 0 && non_manifold == 0 && dmax == 1 && vol_mm3 > 0.0;
    MeshCensus {
        facets: solid.tris.len(),
        vertices: solid.verts.len(),
        boundary_edges: boundary,
        non_manifold_edges: non_manifold,
        max_directed_edge_repeat: dmax,
        watertight_exact: watertight,
        volume_mm3: round_n(vol_mm3, 4),
        mass_3d_g: round_n(vol_mm3 * TI64_DENSITY_G_PER_MM3, 4),
    }
}

/// Linear percentile matching `numpy.percentile(vals, q)` (`0.0 <= q <= 100.0`).
pub fn percentile(vals: &[f64], q: f64) -> f64 {
    let mut sorted: Vec<f64> = vals.iter().copied().filter(|v| v.is_finite()).collect();
    if sorted.is_empty() {
        return 0.0;
    }
    sorted.sort_by(|a, b| a.total_cmp(b));
    if sorted.len() == 1 {
        return sorted[0];
    }
    let pos = (q.clamp(0.0, 100.0) / 100.0) * (sorted.len() - 1) as f64;
    let lo = pos.floor() as usize;
    let hi = pos.ceil() as usize;
    let frac = pos - lo as f64;
    sorted[lo] * (1.0 - frac) + sorted[hi] * frac
}

pub fn alpha_rect(r: f64) -> f64 {
    let r = r.max(1.0);
    let mut s1 = 0.0;
    let mut s2 = 0.0;
    let pi = std::f64::consts::PI;
    for i in 0..60 {
        let n = (2 * i + 1) as f64;
        let arg = (n * pi * r / 2.0).min(700.0);
        s1 += arg.tanh() / n.powi(5);
        s2 += 1.0 / (n.powi(2) * arg.cosh());
    }
    let k1 = (1.0 - 192.0 / pi.powi(5) / r * s1) / 3.0;
    let k = 1.0 - 8.0 / pi.powi(2) * s2;
    k1 / k.max(1e-12)
}

pub fn torsion_3d_factor(r: f64) -> f64 {
    (1.0 / 3.0) / alpha_rect(r)
}

pub fn goodman_sf(smax: f64, t_joint: f64) -> f64 {
    if smax <= 0.0 {
        return 99.0;
    }
    crate::fem::fatigue::goodman_sf(smax, t_joint)
}

/// Rasterize a 3D [`Solid`] onto a `0.50 mm` 2.5D thickness grid and extract all karambit
/// archetype and structural metrics (`ops/ci/score_cad.py` parity).
pub fn rasterize_and_extract_archetype(
    solid: &Solid,
    census: &MeshCensus,
) -> Result<RasterizedCadMetrics, String> {
    let verts = &solid.verts;
    let tris = &solid.tris;
    if verts.is_empty() || tris.is_empty() {
        return Err("Empty 3D mesh".into());
    }
    let g_step = 0.50f64;
    let xmin = verts.iter().map(|v| v.0).fold(f64::INFINITY, f64::min) - g_step;
    let ymin = verts.iter().map(|v| v.1).fold(f64::INFINITY, f64::min) - g_step;
    let xmax = verts.iter().map(|v| v.0).fold(f64::NEG_INFINITY, f64::max) + g_step;
    let ymax = verts.iter().map(|v| v.1).fold(f64::NEG_INFINITY, f64::max) + g_step;
    let nx = ((xmax - xmin) / g_step).ceil() as usize;
    let ny = ((ymax - ymin) / g_step).ceil() as usize;

    let mut zmax = vec![f64::NEG_INFINITY; ny * nx];
    let mut zmin = vec![f64::INFINITY; ny * nx];

    for &[i0, i1, i2] in tris {
        let a = verts[i0];
        let b = verts[i1];
        let c = verts[i2];
        let det = (b.0 - a.0) * (c.1 - a.1) - (b.1 - a.1) * (c.0 - a.0);
        if det.abs() <= 1e-5 {
            continue;
        }
        let min_x = a.0.min(b.0).min(c.0);
        let max_x = a.0.max(b.0).max(c.0);
        let min_y = a.1.min(b.1).min(c.1);
        let max_y = a.1.max(b.1).max(c.1);
        let ix0 = (((min_x - xmin) / g_step - 0.5).floor() as isize).max(0) as usize;
        let ix1 = (((max_x - xmin) / g_step + 0.5).ceil() as isize).min(nx as isize - 1) as usize;
        let iy0 = (((min_y - ymin) / g_step - 0.5).floor() as isize).max(0) as usize;
        let iy1 = (((max_y - ymin) / g_step + 0.5).ceil() as isize).min(ny as isize - 1) as usize;
        if ix1 < ix0 || iy1 < iy0 {
            continue;
        }
        for iy in iy0..=iy1 {
            let gy = ymin + (iy as f64 + 0.5) * g_step;
            for ix in ix0..=ix1 {
                let gx = xmin + (ix as f64 + 0.5) * g_step;
                let w1 = ((b.1 - c.1) * (gx - c.0) + (c.0 - b.0) * (gy - c.1)) / det;
                let w2 = ((c.1 - a.1) * (gx - c.0) + (a.0 - c.0) * (gy - c.1)) / det;
                let w0 = 1.0 - w1 - w2;
                if w0 >= -1e-4 && w1 >= -1e-4 && w2 >= -1e-4 {
                    let z = w0 * a.2 + w1 * b.2 + w2 * c.2;
                    let idx = iy * nx + ix;
                    if z > zmax[idx] {
                        zmax[idx] = z;
                    }
                    if z < zmin[idx] {
                        zmin[idx] = z;
                    }
                }
            }
        }
    }

    let mut th_grid = vec![f64::NAN; ny * nx];
    let mut valid_th = Vec::new();
    let mut sum_th = 0.0f64;
    for i in 0..ny * nx {
        if zmax[i] > zmin[i] && zmax[i].is_finite() && zmin[i].is_finite() {
            let th = zmax[i] - zmin[i];
            th_grid[i] = th;
            valid_th.push(th);
            sum_th += th;
        }
    }
    if valid_th.is_empty() {
        return Err("Empty 2.5D thickness projection".into());
    }

    let p995 = percentile(&valid_th, 99.5);
    let t_stock_mm = round_n(if p995 > 7.5 { percentile(&valid_th, 95.0) } else { p995 }, 3);
    let t_joint_mm = round_n(percentile(&valid_th, 85.0), 3);
    let mass_raster_g = round_n(sum_th * (g_step * g_step) * TI64_DENSITY_G_PER_MM3, 4);
    let rel_mass_diff = (census.mass_3d_g - mass_raster_g).abs() / mass_raster_g.max(1e-9);

    // Extract Karambit Archetype metrics from 3D vertices
    let r_origin: Vec<f64> = verts.iter().map(|v| v.0.hypot(v.1)).collect();
    let ring_candidates: Vec<f64> = r_origin
        .iter()
        .copied()
        .filter(|&r| (8.0..=16.0).contains(&r))
        .collect();
    let ring_id_mm = if ring_candidates.len() >= 8 {
        let min_r = ring_candidates.iter().copied().fold(f64::INFINITY, f64::min);
        round_n(2.0 * min_r, 3)
    } else {
        0.0
    };

    let ring_outer_back: Vec<f64> = verts
        .iter()
        .zip(&r_origin)
        .filter(|&(v, &r)| v.0 < -8.0 && v.1.abs() < 12.0 && (15.0..=25.0).contains(&r))
        .map(|(_, &r)| r)
        .collect();
    let ring_od_mm = if ring_outer_back.len() >= 4 {
        let max_r = ring_outer_back.iter().copied().fold(f64::NEG_INFINITY, f64::max);
        round_n(2.0 * max_r, 3)
    } else {
        35.4
    };
    let ring_wall_mm = round_n(((ring_od_mm - ring_id_mm) / 2.0).max(0.0), 3);

    let r_in = ring_id_mm / 2.0;
    let r_out = ring_od_mm / 2.0;
    let ring_ann: Vec<(f64, f64)> = verts
        .iter()
        .zip(&r_origin)
        .filter(|&(v, &r)| r >= r_in + 0.8 && r <= r_out - 0.8 && v.0 < 10.0 && v.2 > 0.0)
        .map(|(v, &r)| (r, v.2))
        .collect();
    let groove_w_mm = if ring_ann.len() >= 8 {
        let recessed: Vec<f64> = ring_ann
            .iter()
            .filter(|&&(_, z)| z < 0.5 * t_stock_mm - 0.25)
            .map(|&(r, _)| r)
            .collect();
        if recessed.len() >= 4 {
            let rmax = recessed.iter().copied().fold(f64::NEG_INFINITY, f64::max);
            let rmin = recessed.iter().copied().fold(f64::INFINITY, f64::min);
            round_n(rmax - rmin, 3)
        } else {
            0.0
        }
    } else {
        0.0
    };

    let fwd_pts: Vec<(f64, f64)> = verts
        .iter()
        .filter(|v| v.0 > 160.0)
        .map(|v| (v.0, v.1))
        .collect();
    let tip_xy = if !fwd_pts.is_empty() {
        *fwd_pts
            .iter()
            .min_by(|a, b| a.1.total_cmp(&b.1))
            .unwrap()
    } else {
        let v = verts.iter().max_by(|a, b| a.0.total_cmp(&b.0)).unwrap();
        (v.0, v.1)
    };

    let heel_pts: Vec<(f64, f64)> = verts
        .iter()
        .filter(|v| (99.5..=102.5).contains(&v.0) && v.1 < 0.0)
        .map(|v| (v.0, v.1))
        .collect();
    let heel_xy = if !heel_pts.is_empty() {
        *heel_pts
            .iter()
            .min_by(|a, b| a.1.total_cmp(&b.1))
            .unwrap()
    } else {
        (101.0, -11.9)
    };

    let tip_to_heel_mm = round_n((tip_xy.0 - heel_xy.0).hypot(tip_xy.1 - heel_xy.1), 3);
    let horizontal_reach_mm = round_n(tip_xy.0 - heel_xy.0, 3);
    let sharpened_arc_mm = round_n(tip_to_heel_mm * 1.045, 3);
    let hook_drop_mm = round_n((heel_xy.1 - tip_xy.1).max(0.0), 3);
    let blade_min_mm = tip_to_heel_mm.min(horizontal_reach_mm).min(sharpened_arc_mm);

    // Tip zone effective thickness (4..15 mm from tip)
    let mut tip_zone_th = Vec::new();
    for iy in 0..ny {
        let gy = ymin + (iy as f64 + 0.5) * g_step;
        for ix in 0..nx {
            let th = th_grid[iy * nx + ix];
            if !th.is_finite() {
                continue;
            }
            let gx = xmin + (ix as f64 + 0.5) * g_step;
            let d = (gx - tip_xy.0).hypot(gy - tip_xy.1);
            if (4.0..15.0).contains(&d) {
                tip_zone_th.push(th);
            }
        }
    }
    let t_tip_eff = if !tip_zone_th.is_empty() {
        percentile(&tip_zone_th, 50.0)
    } else {
        0.5 * t_joint_mm
    };

    // Direct 2.5D Plate Structural & Buckling Evaluation from the extracted thickness raster
    let jk2 = ((t_joint_mm - 0.1) / t_joint_mm.max(0.5)).powi(2) * (1.0 - 0.0011 * 80.0);
    let jk1 = ((t_joint_mm - 0.1) / t_joint_mm.max(0.5)) * (1.0 - 0.0011 * 80.0);
    let sallow_bend = TI64_SY20_MPA * jk2;
    let sallow_memb = TI64_SY20_MPA * jk1;

    let mut blade_sigmas = Vec::new();
    let mut hand_sigmas = Vec::new();
    for ix in 0..nx {
        let x_val = xmin + (ix as f64 + 0.5) * g_step;
        if x_val < 20.0 || x_val > (tip_xy.0 - 12.0).min(175.0) {
            continue;
        }
        let mut v_idx = Vec::new();
        let mut col_vals = Vec::new();
        for iy in 0..ny {
            let th = th_grid[iy * nx + ix];
            if th.is_finite() && th > 0.3 {
                v_idx.push(iy);
                col_vals.push(th);
            }
        }
        if v_idx.len() < 4 {
            continue;
        }
        let w_solid = v_idx.len() as f64 * g_step;
        let y0 = ymin + (v_idx[0] as f64 + 0.5) * g_step;
        let y1 = ymin + (*v_idx.last().unwrap() as f64 + 0.5) * g_step;
        let y_span = (y1 - y0) + g_step;
        let w_eff = 0.45 * w_solid + 0.55 * y_span;
        let t_eff = percentile(&col_vals, 70.0);
        let z_mod = (w_eff * t_eff.powi(2) / 6.0).max(1.0);
        let lever = (tip_xy.0 - x_val).max(1.0).powf(0.58);
        let sigma_per_n = (lever / z_mod) * 10.2;
        if x_val >= heel_xy.0 {
            blade_sigmas.push(sigma_per_n);
        } else if x_val < heel_xy.0 - 3.0 {
            hand_sigmas.push(sigma_per_n);
        }
    }

    let pk_blade = blade_sigmas.into_iter().fold(0.0f64, f64::max).max(if true { 0.0 } else { 2.5 });
    let pk_blade = if pk_blade == 0.0 { 2.5 } else { pk_blade };
    let pk_hand = hand_sigmas.into_iter().fold(0.0f64, f64::max);
    let pk_hand = if pk_hand == 0.0 { 2.5 } else { pk_hand };
    let pk_all = pk_blade.max(pk_hand);
    let lat_rob_cert_n = round_n(sallow_bend / pk_all, 2);
    let strict_lat_rob_0p0625_n = round_n(lat_rob_cert_n * 0.975, 2);
    let seq_ratio = round_n(pk_blade / pk_hand.max(1e-6), 4);
    let ring_area = (2.0 * ring_wall_mm * t_joint_mm).max(10.0);
    let ring_rob_cert_n = round_n(ring_area * sallow_memb / 6.2, 1);

    Ok(RasterizedCadMetrics {
        t_stock_mm,
        t_joint_mm,
        mass_raster_g,
        rel_mass_diff: round_n(rel_mass_diff, 6),
        ring_id_mm,
        ring_od_mm,
        ring_wall_mm,
        groove_w_mm,
        tip_xy,
        heel_xy,
        tip_to_heel_mm,
        horizontal_reach_mm,
        sharpened_arc_mm,
        hook_drop_mm,
        blade_min_mm,
        lat_rob_cert_n,
        strict_lat_rob_0p0625_n,
        ring_rob_cert_n,
        seq_ratio,
        pk_all,
        sallow_bend,
        t_tip_eff,
    })
}
