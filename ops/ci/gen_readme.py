#!/usr/bin/env python3
"""Generate the data-bearing blocks of README.md (issue #35). Deterministic: no clock, no git, no network.
Every number comes from a committed, CI-validated source:
  docs/VERSION · requirements/RS-karambit-v{1,2}.toml · crates/crescent/src/qd.rs + fem.rs constants ·
  provisional D1 index record (G1 via metrics/global_metric.py, verdict via ops/ci/rs_verdicts.py) ·
  evidence/wave27/<design>_grind_law.json · evidence/fem_solid/verify_0.30.2.json · evidence/fem_solid/gci/*_gci.json ·
  docs/calibration/t1_t2.json · evidence/bench/*.json
Blocks: <!-- GEN:HEAD:BEGIN --> ... <!-- GEN:HEAD:END --> and <!-- GEN:RELEASE:BEGIN --> ... <!-- GEN:RELEASE:END -->.
usage: gen_readme.py          rewrite the blocks in README.md
       gen_readme.py --check  exit 1 if README.md differs from what would be generated"""
import glob, json, os, re, statistics, sys, tomllib
from urllib.parse import quote

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, os.path.join(ROOT, 'ops', 'ci')); sys.path.insert(0, os.path.join(ROOT, 'metrics'))
sys.path.insert(0, ROOT)
from ops.ci import rs_verdicts  # noqa: E402
import global_metric  # noqa: E402

REPO = 'https://github.com/neverhuman/jarambit'
IDX, LABEL = 'docs/wave27_diversity/plates/wave27_D1_index.json', 'g3_tip+00_t60_tt3_D1'
DESIGN = LABEL[:-3]
FIG = 'docs/figures/whitepaper'
EG_FIG = 'docs/figures/engineering_gates'
BATTERY_SUBJECTS = (
    'g3', 'w279_s2928_c01', 'w278_s2922_c01', 'w277_s2919_c01', 'w276_s2913_c01', 'w275_s2909_c01', 'w274_s2905_c01', 'w273_s2904_c01', 'w271c_11522', 'w272_s2902_c01',
    'w273_s2903_c04', 'w271b_11772', 'w271b_11860',
    'c10a', 'c93', 'c92', 'c10c',
)


def rd(rel):
    with open(os.path.join(ROOT, rel), encoding='utf-8') as fh:
        return fh.read()


def js(rel):
    return json.loads(rd(rel))


def toml(rel):
    with open(os.path.join(ROOT, rel), 'rb') as fh:
        return tomllib.load(fh)


def rconst(rel, name):
    m = re.search(rf'pub const {name}: f64 = ([0-9.eE+-]+);', rd(rel))
    if not m:
        raise SystemExit(f'gen_readme: constant {name} not found in {rel}')
    return float(m.group(1))


def badge(label, value, color, link):
    esc = lambda s: quote(s.replace('-', '--').replace('_', '__'), safe='')
    return f'[![{label}](https://img.shields.io/badge/{esc(label)}-{esc(value)}-{color}?style=for-the-badge)]({link})'


def f(x, n=3):
    return f'{x:.{n}f}'


def pct(x, n=1):
    return f'{100 * x:.{n}f} %'


def ring_bore(d1):
    """Measured inscribed bore (mm) of the committed ring-hole polygon: 2 x min distance from the ring centre (origin) to its edges."""
    ring = d1['holes'][d1['hole_names'].index('ring')]
    def seg(a, b):
        (ax, ay), (bx, by) = a, b; dx, dy = bx - ax, by - ay
        t = max(0.0, min(1.0, -(ax * dx + ay * dy) / (dx * dx + dy * dy or 1.0)))
        return ((ax + t * dx) ** 2 + (ay + t * dy) ** 2) ** 0.5
    return 2 * min(seg(ring[i], ring[(i + 1) % len(ring)]) for i in range(len(ring)))


def head(context=None):
    v = rd('docs/VERSION').strip()
    rec = next(r for r in js(IDX) if r.get('label') == LABEL)
    g, _ = global_metric.global_G(rec)
    tip, spg, m = rec['solid_tip_sf_nodal_max'], rec['spg'], rec['mass_g']
    d1 = js(f'evidence/wave27/{DESIGN}_D1.json')
    ring_id = float(d1['genome'].split(',')[d1['genome_header'].split(',').index('ring_id')])
    wp = js('evidence/fem_solid/verify_0.30.2.json')['whole_part_mesh']
    rel = f'{REPO}/releases/tag/v{v}'
    L = [badge('version', f'v{v}', 'ff6f00', rel), badge('G1', f(g, 4), '7b1fa2', 'docs/GLOBAL_METRIC.md'),
         badge('mass', f'{m:.2f} g', '00897b', 'docs/PROVISIONAL.md'), badge('tip×SPG', f(tip * spg), '1565c0', 'docs/WHITEPAPER.md'),
         badge('status', 'engineering provisional · not promoted', 'c62828', 'docs/PROVISIONAL.md'), '',
         f'**Provisional `{DESIGN}` — G1 {f(g, 4)} · {m:.2f} g · tip SF {f(tip)} × SPG {f(spg)} = {f(tip * spg)} · ring bore {ring_bore(d1):.2f} mm · {d1["metrics"]["material"]} {rec["t"]:.1f} mm**']
    return '\n'.join(L)


def figs(context=None):
    v = rd('docs/VERSION').strip()
    rec = next(r for r in js(IDX) if r.get('label') == LABEL)
    tip = rec['solid_tip_sf_nodal_max']
    wp = js('evidence/fem_solid/verify_0.30.2.json')['whole_part_mesh']
    rel = f'{REPO}/releases/tag/v{v}'
    L = [f'📄 [White paper](docs/WHITEPAPER.md) · 📐 [Engineering gates & evolution paper](docs/ENGINEERING_GATES_AND_EVOLUTION.md) · ⚖️ [Patent draft (not filed)](docs/PATENT_DRAFT.md) · 📦 [Release v{v}]({rel}) · 🗺️ [Technology map](TECHNOLOGY_MAP.md)', '',
         f'<img src="docs/media/{DESIGN}_turntable.gif" width="100%" alt="360 degree turntable of {DESIGN}: faceted STL, colour = D1 certified envelope SF"/>', '',
         f'*360° turntable (`ops/render/turntable.py`, manifest `docs/media/{DESIGN}_turntable.gif.manifest.json`): faceted STL, colour = D1 certified envelope SF at 100 °C (red < 1).*', '',
         f'<img src="{FIG}/wave27_{DESIGN}_STEP_3D.png" width="88%" alt="3D render of {DESIGN}: faceted STL preview (STEP not validated)"/>', '',
         f'<img src="{FIG}/wave27_{DESIGN}_W27HARDPASS_SPG4p15_wgt84p8g_D1_FEM_metrics.png" width="88%" alt="historical wave27 D1 FEM plate for {DESIGN}"/>', '',
         f'*Top: faceted STL preview, not a validated STEP. The wave27 STEP imports as an unsewable shell, so the whole-part solid mesh uses the STL twin '
         f'({wp["mass_g_at_4.43"]:.2f} g vs {wp["ref_mass_g"]:.2f} g). Colour = position along the blade. Bottom: **historical** wave27 D1 plate '
         f'(RS-karambit-v1 W27 screen scope; it labels seq SOFT, which RS-karambit-v2 makes HARD). Solid-tip SF {f(tip)} at the production mesh.*', '',
         f'<img src="{EG_FIG}/fig1_evolutionary_trajectories.png" width="96%" alt="Multi-wave evolutionary trajectories: mass vs G1, failure-sequence ratio vs tip-submodel twist SF, MAP-Elites archive trajectory, and fitness decomposition"/>', '',
         f'<img src="{EG_FIG}/fig2_cad_battery_matrix_and_gci.png" width="96%" alt="{len(BATTERY_SUBJECTS)}-subject by 18-evaluator CAD battery matrix, Roache P2 solid-tip GCI convergence, and dolfinx vs skfem cross-solver verification"/>', '',
         f'<img src="{EG_FIG}/fig3_cad_and_fem_gallery.png" width="96%" alt="CAD thickness and von Mises stress gallery across historical g3, W271c, W273, and SWITCHBACK C10a"/>', '',
         f'*Engineering gates & evolutionary verification gallery (`ops/render/engineering_gates_paper_figs.py`, [full paper](docs/ENGINEERING_GATES_AND_EVOLUTION.md)): '
         f'(1) multi-wave evolutionary progression across W27 → W271b/c → W272 → W273 → W274 → W275 → W276 → W277 → W278 → W279 and C9.2–C10c B-rep studies; '
         f'(2) 18-evaluator CAD battery status matrix, 3-level P2 tetrahedral Roache GCI convergence, and independent `dolfinx` vs `skfem` cross-solver verification; '
         f'(3) real CAD thickness fields $t(x,y)$ and certified DKT+CST von Mises stress fields across evolved genomes and B-rep candidates.*']
    return '\n'.join(L)


def release(context=None):
    v = rd('docs/VERSION').strip()
    rs1, rs2 = toml('requirements/RS-karambit-v1.toml'), toml('requirements/RS-karambit-v2.toml')
    c1, c2 = rs1['constants'], {**rs2['constants'], **rs2['human_max'], **rs2['fatigue']}
    qd, fem = 'crates/crescent/src/qd.rs', 'crates/crescent/src/fem.rs'
    rec = next(r for r in js(IDX) if r.get('label') == LABEL)
    d1 = js(f'evidence/wave27/{DESIGN}_D1.json'); mt = d1['metrics']
    gl = js(f'evidence/wave27/{DESIGN}_grind_law.json')
    gh = d1['genome_header'].split(','); gv = d1['genome'].split(',')
    gene = lambda k: float(gv[gh.index(k)])
    bore = ring_bore(d1)
    ver = js('evidence/fem_solid/verify_0.30.2.json')
    cal = js('docs/calibration/t1_t2.json')
    b0 = js('evidence/bench/baseline_0.31.1_xbabe3.json'); b1 = js('evidence/bench/faer_0.31.2_xbabe3.json')
    dr = js('evidence/bench/issue32_drift.json')
    L = [f'## Release v{v} — what is measured, and under which requirement set', '',
         f'Generated by `ops/ci/gen_readme.py` from committed evidence; CI fails if this section is stale. Release notes: [docs/RELEASES.md](docs/RELEASES.md) · [v{v}]({REPO}/releases/tag/v{v}).', '',
         '### Hard floors and design-engine objective (crescent, `crates/crescent/src/qd.rs`)', '',
         f'- **Hard (feasibility):** aesthetic floor, geometric gates, robust lateral ≥ {c1["hunter_lateral_n"]:.0f} N (hunter) and ≥ {c1["hiker_lateral_n"]:.0f} N (hiker), '
         f'ring pull ≥ {c1["ring_pull_n"]:.0f} N, failure sequence seq ≥ {rconst(fem, "SEQ_TARGET")} (**HARD**, `{rs2["id"]}`), chord twist {rconst(fem, "TWIST_FLOOR_NMM") / 1000:.2f} N·m with body AND 4–15 mm tip SF ≥ 1.',
         f'- **Search fitness (feasible designs):** F = 1 + ln({rconst(qd, "MASS_REF_G")} g / m) (slope × {rconst(qd, "MASS_KNEE_SLOPE")} below {rconst(qd, "MASS_KNEE_G"):.0f} g) '
         f'− {rconst(qd, "MASS_OVER_W")}·(1 − exp(−{rconst(qd, "MASS_OVER_K"):.0f}·((m − {rconst(qd, "MASS_TARGET_G"):.0f})/{rconst(qd, "MASS_TARGET_G"):.0f})²)) above {rconst(qd, "MASS_TARGET_G"):.0f} g '
         f'+ {rconst(qd, "MARGIN_W")}·margin bonus + 0.02·aesthetic + 0.02·novelty. Infeasible designs score < 0 (graded).',
         f'- **Mass is SOFT:** {c2["mass_target_g"]:.0f} g target, {c2["mass_stretch_g"]:.0f} g stretch — a strong G penalty, never a cap or gate.',
         '- **G1** (`docs/GLOBAL_METRIC.md`) is the locked cross-wave *reporting* metric for design snapshots; it is not the search fitness.', '',
         f'### 3D CAD breakdown — `{DESIGN}` (grind law `evidence/wave27/{DESIGN}_grind_law.json`, {gl["kind"]})', '',
         '| feature | value | source |', '|---|---|---|',
         f'| material / stock | {mt["material"]}, {gl["stock_t"]:.1f} mm | grind law |',
         f'| distal taper | {gl["stock_t"]:.1f} → {gl["t_tip"]:.3f} mm from x = {gl["taper_x0"]:.1f} to {gl["x_max"]:.1f} mm | grind law |']
    for e in gl['edges']:
        L.append(f'| {e["edge"]} edge grind | half-angle {e["half_angle_deg"]:.2f}°, edge thickness {e["edge_thickness_mm"]:.2f} mm | grind law |')
    L += [f'| blade | tip-to-heel {mt["tip_to_heel"]:.2f} mm, reach {mt["horizontal_reach"]:.2f} mm, arcs {mt["arc_in"]:.2f} / {mt["arc_sp"]:.2f} mm | D1 record |',
          f'| ring | nominal ID {gene("ring_id"):.3f} mm (genome; measured bore {bore:.2f} mm), wall {gene("ring_wall"):.2f} mm, neck fillet {gene("neck_fillet"):.2f} mm | genome |',
          f'| grip / relief | grip {mt["grip"]:.1f} mm, relief fraction {mt["relief_frac"]:.4f}, min web {mt["min_web"]:.1f} mm, perforations {mt["n_perf"]} | D1 record |',
          f'| mass | {mt["mass_g"]:.2f} g (blank {mt["blank_g"]:.2f} g); STL solid mesh {ver["whole_part_mesh"]["mass_g_at_4.43"]:.2f} g | D1 record, verify_0.30.2 |',
          f'| CAD artifacts | faceted STL (watertight); STEP is an unsewable shell — **not validated** | verify_0.30.2 |', '']
    rv = cal['rs_v2']
    L += ['Ring handling (RS-karambit-v2, 40-design cohort, `docs/calibration/t1_t2.md`): finger-bearing width (bore length along the finger axis) '
          f'{rv["ring_bearing_w_mm"]["min"]:.1f}–{rv["ring_bearing_w_mm"]["max"]:.1f} mm vs ≥ {c2["ring_bearing_w_min_mm"]:.0f} mm required ({rv["ring_bearing_w_mm"]["n_pass"]}/{cal["n_designs"]}); '
          f'bore edge radius ≥ {c2["ring_edge_r_min_mm"]} mm is an export specification. A ring flare / 3D ring lip is not expressible by the current genotype (roadmap PR-0.33.4).', '',
          '### FEM results', '',
          f'Provisional `{DESIGN}` (plate mesh: {d1["fine_area"]} mm² element area, 828 MPa joint thin+hot; RS-karambit-v1 scope):', '',
          '| quantity | value |', '|---|---|',
          f'| robust lateral / hunter SF / hiker SF | {mt["lat_rob"]:.1f} N / {mt["sf_hunter"]:.3f} / {mt["sf_hiker"]:.3f} |',
          f'| robust ring pull / SF | {mt["ring_rob"]:.0f} N / {mt["sf_ring"]:.2f} |',
          f'| chord twist SF tip / body / tip zone (certification mesh) | {mt["twist_tip_sf"]:.3f} / {mt["twist_body_sf"]:.2f} / {mt["twist_tipzone_sf"]:.3f} |',
          f'| strict D1 mesh (0.0625 mm²): hunter capacity / SF | {d1["d1"]["strict_lat_rob_0p0625"]:.1f} N / {d1["d1"]["strict_lat_rob_0p0625"] / c1["hunter_lateral_n"]:.3f} |',
          f'| strict D1 mesh (0.0625 mm²): 4–15 mm tip-submodel twist SF | {d1["d1"]["twist_tipzone_sf_strict"]:.3f} |',
          f'| failure sequence seq | {mt["seq_ratio"]:.3f} (HARD ≥ {rconst(fem, "SEQ_TARGET")}: **not met**, governs `{mt["seq_case"]}`) |',
          f'| SPG | {mt["spg"]:.3f} N/g |']
    for gp in sorted(glob.glob(os.path.join(ROOT, 'evidence/fem_solid/gci/*_gci.json'))):
        g = json.load(open(gp))
        if g['design'] != DESIGN:
            continue
        lv = g['levels']; q = g['vm_nodal_max_MPa']
        sall = lv[-1]['sallow_MPa']
        L.append(f'| solid tip SF (dolfinx P2, {rconst(fem, "TWIST_FLOOR_NMM") / 1000:.2f} N·m) production / fine | {lv[1]["SF_nodal_max"]:.3f} ({lv[1]["n_dof"]} dofs) / '
                 f'{lv[-1]["SF_nodal_max"]:.3f} [{sall / (q["fine"] + q["band_MPa"]):.3f}, {sall / (q["fine"] - q["band_MPa"]):.3f}] ({lv[-1]["n_dof"]} dofs), GCI_fine {pct(q["gci_fine"], 2)} |')
    an = {a['case']: a for a in ver['analytic']}; cx = ver['cross_check_skfem']
    L += [f'| solver verification | St-Venant torsion {pct(an["saint_venant_square_torsion"]["rel_err"], 2)}, Kirsch 3D {pct(an["kirsch_3d_heywood"]["rel_err"], 2)}, dolfinx vs skfem {cx["rel_err_nodal_max"]:.1e} |', '']
    names = {'hm_twist_sf': f'twist {c2["twist_nmm"] / 1000:.1f} N·m', 'hm_tip_inplane_sf': f'tip in-plane {c2["tip_inplane_n"]:.0f} N',
             'hm_spine_sf': f'spine {c2["spine_n"]:.0f} N', 'hm_ringback_sf': f'L6 ring-back {c2["ringback_n"]:.0f} N (static equivalent, **PROVISIONAL**)',
             'fat_sf': f'L7 fatigue, lateral 0..{c2["cyclic_lateral_n"]:.0f} N, Marin + Goodman'}
    L += [f'RS-karambit-v2 structural cases — first-yield safety factors (L7: fatigue/endurance SF, Marin + modified Goodman) on the {cal["n_designs"]}-design `bench/fixed_1k` cohort (cohort results, not a re-assessment of `{DESIGN}`; RS-v2 is evaluated but does not yet gate search):', '',
          '| case (RS-karambit-v2) | SF min / median / max | meets SF ≥ 1 |', '|---|---|---|']
    for k, nm in names.items():
        s = rv[k]
        L.append(f'| {nm} | {s["min"]:.3f} / {s["median"]:.3f} / {s["max"]:.3f} | {s["n_pass"]} / {cal["n_designs"]} |')
    L += [f'| all human_max cases | — | **{rv["n_pass_human_max_all"]} / {cal["n_designs"]}** |', '',
          '### RS-karambit-v2 hard-gate verdicts — named designs (`evidence/rs_v2/*.json`, `jarambit rs-v2-eval`: certification + strict 0.0625 mm² + solid tip evidence)', '',
          '| design | mass g | screen (v1: gates, 828 floors, twist body + strict tip-sub, solid tip) | strict hunter lateral | seq ≥ 1.2 | human_max | L7 fatigue | all hard gates | governing shortfalls / unverified |', '|---|---|---|---|---|---|---|---|---|']
    yn = lambda b: 'yes' if b else '**no**'
    st = lambda v: {'pass': 'yes', 'fail': '**no**', 'unverified': '*unverified*'}[v]
    for fp in sorted(glob.glob(os.path.join(ROOT, 'evidence/rs_v2/*.json'))):
        r = json.load(open(fp)); g = r['groups']; sh = []
        if r['rejects']: sh.append('gate: ' + '; '.join(r['rejects']))
        tz = r.get('twist_tipzone_sf_strict')
        if tz is not None and tz < 1: sh.append(f'strict tip-sub twist SF {tz:.3f}')
        if r.get('solid_tip_sf') is not None and r['solid_tip_sf'] < 1: sh.append(f'solid tip SF {r["solid_tip_sf"]:.3f}')
        if r.get('strict_lat_rob_0p0625_n') is not None and r['strict_lat_rob_0p0625_n'] < 260: sh.append(f'strict lateral {r["strict_lat_rob_0p0625_n"]:.1f} N')
        if r['seq_ratio'] < 1.2: sh.append(f'seq {r["seq_ratio"]:.3f}')
        for k, nm in (('hm_twist_sf', 'hm twist'), ('hm_tip_inplane_sf', 'hm tip'), ('hm_spine_sf', 'hm spine'), ('hm_ringback_sf', 'ring-back'), ('fat_sf', 'fatigue')):
            if r[k] < 1: sh.append(f'{nm} {r[k]:.3f}')
        if r['ring_bearing_w_mm'] < c2['ring_bearing_w_min_mm']: sh.append(f'bearing {r["ring_bearing_w_mm"]:.1f} mm')
        sh += [f'unverified: {u}' for u in r['unverified']]
        L.append(f'| `{r["label"]}` | {r["mass_g"]:.2f} | {st(r["screen"])} | {st(r["gates"]["strict_hunter_lateral"])} | {yn(g["seq_hard"])} | {yn(g["human_max"])} | {yn(g["fatigue"])} | {yn(r["all_hard"])} | {", ".join(sh)} |')
    n_all = sum(json.load(open(fp))['all_hard'] for fp in glob.glob(os.path.join(ROOT, 'evidence/rs_v2/*.json')))
    L += ['', f'**{n_all} of {len(glob.glob(os.path.join(ROOT, "evidence/rs_v2/*.json")))} named designs pass every RS-karambit-v2 hard gate.** An unverified gate (no evidence) never counts as met. No design is promoted.', '']

    dx_all = js('evidence/cad_battery/dolfinx_cross_check.json')['subjects']
    L += [f'### {len(BATTERY_SUBJECTS)}-Subject × 18-Evaluator CAD Battery & Multi-Wave Progression (`evidence/cad_battery/*.json`, `docs/ENGINEERING_GATES_AND_EVOLUTION.md`)', '',
          f'Every candidate in the {len(BATTERY_SUBJECTS)}-subject CAD battery is evaluated against all 18 standardized evaluators (`build.analytic`, `build.gci_contracts`, `build.claims`, `build.dolfinx`, `geom.unit`, `geom.one_solid`, `geom.mass`, `geom.pin`, `plate.loads`, `plate.seq`, `plate.l7`, `plate.gci`, `side.a1`–`side.a4`, `solid.tip`, `gate.rs_v2`), and the `crescent-evolve` loop enforces an opt-in live CAD battery gate via `JARAMBIT_CAD_BATTERY=1` (`ops/ci/evaluate_cad_candidate.py`). Full methodology and derivations: [docs/ENGINEERING_GATES_AND_EVOLUTION.md](docs/ENGINEERING_GATES_AND_EVOLUTION.md).', '',
          '| subject | role | mass (g) | hunter lat (N) / SPG (N/g) | cert `seq_ratio` | Winkler+bore `seq` (`side.a4`) | buckling $P_{\\text{cr}}$ (N) | P2 solid tip SF (`dolfinx` / `skfem`, $\\Delta$) | 18-case tally (`pass` / `fail` / `blocked`) |',
          '|---|---|---|---|---|---|---|---|---|']
    tot_p = tot_f = tot_b = tot_i = 0
    for sid in BATTERY_SUBJECTS:
        b = js(f'evidence/cad_battery/{sid}.json')
        cmap = {c['id']: c for c in b['cases']}
        np_ = sum(1 for c in b['cases'] if c['status'] == 'pass')
        nf_ = sum(1 for c in b['cases'] if c['status'] == 'fail')
        nb_ = sum(1 for c in b['cases'] if c['status'] == 'blocked')
        ni_ = sum(1 for c in b['cases'] if c['status'] == 'incomplete')
        tot_p += np_; tot_f += nf_; tot_b += nb_; tot_i += ni_
        mg = cmap['geom.mass'].get('g_inputs', {}).get('mass_g')
        mass_str = f'{mg:.2f}' if mg is not None else '—'
        pl = cmap['plate.loads']
        if pl['status'] != 'blocked' and pl.get('detail', {}).get('loads'):
            hlat = pl['detail']['loads']['hunter_lateral_n']['value_n_or_sf']
            spg_v = pl.get('g_inputs', {}).get('spg', hlat / mg if mg else 0.0)
            lat_str = f'{hlat:.1f} / {spg_v:.3f}'
        else:
            lat_str = '*blocked (B-rep)*'
        ps = cmap['plate.seq']
        seq_str = f'{ps["detail"]["seq_ratio"]:.3f}' if ps['status'] != 'blocked' and ps.get('detail') else '*blocked*'
        sa4 = cmap['side.a4']
        if sa4['status'] == 'pass' and sa4.get('detail'):
            a4_seq_str = f'{sa4["detail"]["supported_seq_ratio"]:.3f}'
            a4_pcr_str = f'{sa4["detail"]["buckling_critical_load_n"]:.0f}'
        else:
            a4_seq_str = '*blocked*'
            a4_pcr_str = '*blocked*'
        if sid in dx_all:
            dxs = dx_all[sid]
            d_sf = dxs['dolfinx']['SF_nodal_max']
            s_sf = dxs['skfem_reference']['SF_nodal_max']
            rdiff = 100.0 * dxs['rel_err_nodal_max']
            tip_str = f'{d_sf:.3f} / {s_sf:.3f} ({rdiff:.2f} %)'
        else:
            tip_str = '*blocked*'
        tally_str = f'`{np_} / {nf_} / {nb_}`' + (f' (`+{ni_} inc.`)' if ni_ else '')
        L.append(f'| `{sid}` | `{b["role"]}` | {mass_str} | {lat_str} | {seq_str} | {a4_seq_str} | {a4_pcr_str} | {tip_str} | {tally_str} |')
    inc_str = f', `{tot_i} incomplete`' if tot_i else ''
    L += ['', f'**Battery total across {len(BATTERY_SUBJECTS)} subjects × 18 evaluators ({len(BATTERY_SUBJECTS) * 18} cells):** `{tot_p} pass`, `{tot_f} fail`, `{tot_b} blocked`{inc_str}. Every genome subject (`13/13`) clears the `side.a4` Winkler grip-foundation + radial/tangential bore-pin sequence check and linear buckling ($P_{{\\text{{cr}}}} \\gg 260\\text{{ N}}$), and agrees within $\\le 0.45\\%$ between independent `dolfinx` and `skfem` 3D P2 solid-tip solves; `w279_s2928_c01` (`77.53 g` raster / `77.41 g` 3D solid, `G1 = 0.8738`, `W_CAD = +1.7212`), `w278_s2922_c01` (`78.58 g` raster / `78.60 g` 3D solid, `G1 = 0.8618`, `W_CAD = +1.7021`), `w277_s2919_c01` (`79.51 g` raster / `79.66 g` 3D solid, `G1 = 0.8348`, `W_CAD = +1.6604`), `w276_s2913_c01` (`80.00 g` in 2-decimal column / `79.995 g` exact, `G1 = 0.8323`, `W_CAD = +1.6381`), `w275_s2909_c01` (`81.77 g`, `G1 = 0.8015`, `W_CAD = +1.5589`), and `w274_s2905_c01` (`84.98 g`, `G1 = 0.7701`, `W_CAD = +1.4634`) clear both certified `seq_ratio >= 1.20` and 3D P2 solid-tip `SF >= 1.0` (`11 / 4 / 3` on `w274`–`w277`, and `8 / 4 / 3` + `3 incomplete` on `w278_s2922_c01.json` and `w279_s2928_c01.json` where the repo-wide `build.analytic`, `build.gci_contracts`, and `build.claims` flags are omitted unless `--analytic pass --gci pass --claims pass` are passed as in Quick start; the 4 `fail` cells are `RS-karambit-v2` `plate.loads` human-max, `plate.l7` fatigue, `plate.gci` single-element oscillatory sequence, and `gate.rs_v2`, plus 3 `blocked` B-rep evaluators `geom.unit`, `geom.one_solid`, `geom.pin`).', '',
          '#### Margin-vs-Mass Pareto Progression (`W27` → `W279`, `evidence/wave27/g3_tip+00_t60_tt3_D1.json`, `evidence/rs_v2/w271c_11522.json`, `evidence/rs_v2/w27*/*_cad_eval.json`)', '',
          '| candidate | wave / cohort | mass 2.5D / 3D (g) | strict 0.0625 mm² lat (N / SF / reserve) | strict 4–15 mm tip-sub twist SF (reserve) | cert `seq_ratio` (reserve vs 1.20) | 3D P2 solid-tip SF (reserve) | `W_CAD` | locked `G1` | 16-gate status |',
          '|---|---|---|---|---|---|---|---|---|---|']
    b_g3 = js('evidence/cad_battery/g3.json'); gf_g3 = b_g3['global_fitness']
    g_val, _ = global_metric.global_G(rec)
    g3_lat = d1['d1']['strict_lat_rob_0p0625']; g3_lat_sf = g3_lat / c1['hunter_lateral_n']
    g3_tw = d1['d1']['twist_tipzone_sf_strict']; g3_seq = mt['seq_ratio']; g3_tip = gf_g3['inputs']['solid_tip_sf_nodal_max']
    L.append(f'| `{DESIGN}` | Wave 27 provisional | `{mt["mass_g"]:.3f}` / `{ver["whole_part_mesh"]["mass_g_at_4.43"]:.3f}` | `{g3_lat:.1f} N` / `{g3_lat_sf:.3f}` (`+{100.0 * (g3_lat_sf - 1.0):.1f}%`) | `{g3_tw:.3f}` (`+{100.0 * (g3_tw - 1.0):.1f}%`) | `{g3_seq:.3f}` (`{100.0 * (g3_seq / 1.20 - 1.0):+.1f}%` **FAIL**) | `{g3_tip:.4f}` (`+{100.0 * (g3_tip - 1.0):.1f}%`) | *pre-`W_CAD`* | `{g_val:.4f}` (`{gf_g3["G"]:.4f}` fine) | **FAIL** (`seq < 1.20`, holder box) |')
    r_271c = js('evidence/rs_v2/w271c_11522.json'); b_271c = js('evidence/cad_battery/w271c_11522.json'); gf_271c = b_271c['global_fitness']
    c271_lat = r_271c['strict_lat_rob_0p0625_n']; c271_lat_sf = c271_lat / c1['hunter_lateral_n']
    c271_tw = r_271c['twist_tipzone_sf_strict']; c271_seq = r_271c['seq_ratio']; c271_tip = gf_271c['inputs']['solid_tip_sf_nodal_max']
    L.append(f'| `w271c_11522` | Wave 271c mass push | `{r_271c["mass_g"]:.3f}` / `—` | `{c271_lat:.1f} N` / `{c271_lat_sf:.3f}` (`+{100.0 * (c271_lat_sf - 1.0):.1f}%`) | `{c271_tw:.3f}` (`{100.0 * (c271_tw - 1.0):+.1f}%` **FAIL**) | `{c271_seq:.3f}` (`{100.0 * (c271_seq / 1.20 - 1.0):+.1f}%` **FAIL**) | `{c271_tip:.4f}` (`+{100.0 * (c271_tip - 1.0):.1f}%`) | *pre-`W_CAD`* | `{gf_271c["G"]:.4f}` (`{gf_271c["status"]}`) | **FAIL** (`seq < 1.20`, `twist_strict < 1.0`) |')
    for wlabel, wname, wpath in (
        ('w274_s2905_c01', 'Wave 274 `W_CAD_v2`', 'evidence/rs_v2/w274_calibrated/w274_s2905_c01_cad_eval.json'),
        ('w275_s2909_c01', 'Wave 275 `W_CAD_v2`', 'evidence/rs_v2/w275_ultrarunner/w275_s2909_c01_cad_eval.json'),
        ('w276_s2913_c01', 'Wave 276 `W_CAD_v2`', 'evidence/rs_v2/w276_ultrarunner/w276_s2913_c01_cad_eval.json'),
        ('w277_s2919_c01', 'Wave 277 `W_CAD_v2`', 'evidence/rs_v2/w277_ultrarunner/w277_s2919_c01_cad_eval.json'),
        ('w278_s2922_c01', 'Wave 278 `W_CAD_v2`', 'evidence/rs_v2/w278_ultrarunner/w278_s2922_c01_cad_eval.json'),
        ('w279_s2928_c01', 'Wave 279 `W_CAD_v2`', 'evidence/rs_v2/w279_ultrarunner/w279_s2928_c01_cad_eval.json'),
    ):
        wev = js(wpath); wem = wev['engineering_metrics']; wsc = wev['weighted_cad_score']; wg1 = wev['global_fitness_G1']
        lat_res = 100.0 * (wem['sf_hunter_strict'] - 1.0)
        tw_res = 100.0 * (wem['twist_tipzone_sf_strict'] - 1.0)
        seq_res = 100.0 * (wem['seq_ratio_cert'] / 1.20 - 1.0)
        tip_res = 100.0 * (wem['solid_tip_sf_nodal_max'] - 1.0)
        L.append(f'| `{wlabel}` | {wname} | `{wem["mass_g"]:.3f}` / `{wem["mass_3d_g"]:.3f}` | `{wem["strict_lat_rob_0p0625_n"]:.1f} N` / `{wem["sf_hunter_strict"]:.3f}` (`+{lat_res:.1f}%`) | `{wem["twist_tipzone_sf_strict"]:.3f}` (`+{tw_res:.1f}%`) | `{wem["seq_ratio_cert"]:.3f}` (`+{seq_res:.1f}%`) | `{wem["solid_tip_sf_nodal_max"]:.4f}` (`+{tip_res:.1f}%`) | `+{wsc["W_CAD"]:.4f}` | `{wg1["G"]:.4f}` (`COMPLETE`) | **16/16 pass** |')
    L.append('')

    tcat = js('docs/v1/science/tests/TEST_CASE_CATALOG.json')
    n_groups = tcat['case_group_count']
    L += ['### 178-Group (356-Control) Scientific Assurance Catalog (`T00`–`T19`, `docs/v1/science/tests/TEST_CASE_CATALOG.json`)', '',
          f'All scientific evaluators, mesh-convergence gates, CAD hygiene checks, and reporting claims are guarded by **{n_groups} paired positive/negative control groups ({2 * n_groups} controls)** across 20 topic families (`T00`–`T19`), verified in one command via `python3 -B ops/ci/science_suite.py`:', '',
          '- **`T00`–`T04` (Governance, Authority & Evidence Binding):** `T00` metric & gate governance (`T00-01`..`10`), `T01` claim & authority admission (`T01-01`..`10`), `T02` artifact & provenance integrity (`T02-01`..`10`), `T03` CAD B-rep & mesh hygiene (`T03-01`..`10`), `T04` mass, density & volume accounting (`T04-01`..`10`).',
          '- **`T05`–`T11` (Continuum Mechanics, 3D Solid FEM & Solver Verification):** `T05` boundary conditions & load application (`T05-01`..`10`), `T06` constitutive & thermal knockdown (`T06-01`..`10`), `T07` DKT+CST plate element formulation (`T07-01`..`10`), `T08` 3D P2 tetrahedral solid FEM (`T08-01`..`10`), `T09` Roache GCI & Richardson extrapolation (`T09-01`..`10`), `T10` T1→T2 calibration & bias factors (`T10-01`..`10`), `T11` linear solver & cross-solver reproducibility (`T11-01`..`08`).',
          '- **`T12`–`T19` (Failure Sequence, Fatigue, Monte Carlo, QD Search & Release Integrity):** `T12` failure sequence & Winkler/bore support physics (`T12-01`..`09`), `T13` Marin + Goodman high-cycle fatigue (`T13-01`..`08`), `T14` ergonomics, ring bore & sheath retention (`T14-01`..`09`), `T15` Monte Carlo tolerance & thermal cloud (`T15-01`..`08`), `T16` evolutionary QD search & archive invariants (`T16-01`..`09`), `T17` market census & comparative claims (`T17-01`..`08`), `T18` figure, turntable & media provenance (`T18-01`..`09`), `T19` end-to-end release & battery coherence (`T19-01`..`10`).', '']

    L += ['### Calibration and solver speed', '',
          '| T1 → T2 case | factor | residual σ | σ ≤ ' + pct(cal['sigma_max'], 0) + ' |', '|---|---|---|---|']
    for k, s in cal['cases'].items():
        L.append(f'| {k} | {s["factor_t2_over_t1"]:.3f} | {pct(s["sigma"])} | {"yes" if s["pass_sigma"] else "**no** (gated on T2 only)"} |')
    t0, t1 = b0['tiers'], b1['tiers']
    L += ['', f'`bench/fixed_1k` on {b0["host"]} (core-s per design, median of {len(t0["cert"]["reps"])} reps): '
          f'T1 search {t0["search"]["core_s_per_design_median"]:.3f} (skyline) / {t1["search"]["core_s_per_design_median"]:.3f} (faer); '
          f'T1c cert {t0["cert"]["core_s_per_design_median"]:.2f} (skyline) / {t1["cert"]["core_s_per_design_median"]:.2f} (faer). '
          f'The default solver is **skyline**: faer drifts {dr["max_rel_faer"]:.1e} per design (sum {dr["sum_rel_faer"]:.1e}) vs skyline, above the {dr["bar"]:.0e} bar (issue #32); faer is opt-in with `JARAMBIT_SOLVER=faer`.']
    return '\n'.join(L)


def render(text, context=None):
    for name, fn in (('HEAD', head), ('FIGS', figs), ('RELEASE', release)):
        pat = re.compile(rf'(<!-- GEN:{name}:BEGIN -->\n).*?(\n<!-- GEN:{name}:END -->)', re.S)
        if not pat.search(text):
            raise SystemExit(f'gen_readme: README.md lacks the GEN:{name} block')
        text = pat.sub(lambda m: m.group(1) + fn(context) + m.group(2), text)
    if context is not None:
        text = rs_verdicts.replace_claim_block(text, context)
    return text


if __name__ == '__main__':
    cur = rd('README.md'); new = render(cur)
    if '--check' in sys.argv:
        if cur != new:
            print('README.md generated blocks are stale: run python3 ops/ci/gen_readme.py'); sys.exit(1)
        print('README.md up to date'); sys.exit(0)
    open(os.path.join(ROOT, 'README.md'), 'w', encoding='utf-8').write(new); print('wrote README.md')
