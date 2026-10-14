#!/usr/bin/env python3
"""Generate the data-bearing blocks of docs/WHITEPAPER.md (PR-0.32.0c). Deterministic: no clock, no git, no network.
Sources (all committed, CI-validated): docs/VERSION · evidence/rs_v2/*.json · docs/figures/components/components.json ·
evidence/bench/*.json · evidence/fem_solid/verify_0.30.2.json · evidence/fem_solid/gci/*_gci.json · requirements/RS-karambit-v2.toml.
Blocks: GEN:WP_STATUS, GEN:WP_METHODS, GEN:WP_COMPONENTS, GEN:WP_RSV2 (<!-- GEN:<name>:BEGIN --> ... <!-- GEN:<name>:END -->).
usage: gen_whitepaper.py [--check]"""
import glob, json, os, re, sys

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, ROOT)
sys.path.insert(0, os.path.join(ROOT, 'ops', 'ci'))
from ops.ci import rs_verdicts  # noqa: E402
from gen_readme import rd, js, toml, f  # noqa: E402

WP = 'docs/WHITEPAPER.md'
COMP = 'docs/figures/components/components.json'


def rsv2():
    out = []
    for fp in sorted(glob.glob(os.path.join(ROOT, 'evidence/rs_v2/*.json'))):
        out.append(json.load(open(fp)))
    return out


def gate_mins():
    r = toml('requirements/RS-karambit-v2.toml')
    return r['constants']['seq_target'], r['human_max']['ring_bearing_w_min_mm']


def status(context=None):
    ds = rsv2(); n = sum(d['all_hard'] for d in ds)
    v = rd('docs/VERSION').strip()
    return (f'**Honest status (v{v}, generated from `evidence/rs_v2/*.json`).** {n} of {len(ds)} named designs meet every RS-karambit-v2 hard gate; '
            f'{"no design is promoted and this version is a release candidate, not v1.0.0" if n == 0 else "see §IV-A"}. '
            'The v1 gate set (RS-karambit-v2) adds human-maximum loads, seq ≥ 1.2 as a hard gate, fatigue and ring handling to the v1 screen; '
            'Table IV-A lists every shortfall.')


def methods(context=None):
    b0, b1 = js('evidence/bench/baseline_0.31.1_xbabe3.json'), js('evidence/bench/faer_0.31.2_xbabe3.json')
    dr, vf = js('evidence/bench/issue32_drift.json'), js('evidence/fem_solid/verify_0.30.2.json')
    cc, wp = vf['cross_check_skfem'], vf['whole_part_mesh']
    s0, s1 = b0['tiers']['cert']['core_s_per_design_median'], b1['tiers']['cert']['core_s_per_design_median']
    L = ['| method (version) | evidence | result |', '|---|---|---|',
         f'| Solid FEM cross-check (v0.30) | `evidence/fem_solid/verify_0.30.2.json` | {vf["container"].split(" (")[0]} vs scikit-fem on the {cc["design"]} tip submodel ({cc["n_dof"]} DOF): SF nodal max {f(cc["SF_nodal_max"], 4)} vs {f(cc["ref_SF_nodal_max"], 4)} (rel. err {cc["rel_err_nodal_max"]:.1e}) |',
         f'| Whole-part solid mesh (v0.30) | same | {wp["n_tet10"]} TET10, {wp["n_dof"]} DOF at h = {wp["h_mm"]} mm; mass {wp["mass_g_at_4.43"]} g vs {wp["ref_mass_g"]} g reference |']
    history_paths = sorted(glob.glob(os.path.join(ROOT, 'evidence/fem_solid/gci/*_gci.json')))
    if context is not None:
        history = rs_verdicts.historical_gci_reports(history_paths)
        L.append(f'| Historical GCI software binding | admitted S02 reclassification | {len(history["rows"])} records; ordinary GCI unsupported, physical qualification not established |')
    for fp in history_paths:
        g = json.load(open(fp)); vm, sfb = g['vm_nodal_max_MPa'], g['SF_nodal_max']
        L.append(f'| GCI mesh study (v0.30) | `{os.path.relpath(fp, ROOT)}` | {g["design"]}: {len(g["levels"])} levels to {g["levels"][-1]["n_dof"]} DOF; '
                 f'GCI_fine (vM max) {100 * vm["gci_fine"]:.1f} %, p = {f(vm["p"], 2) if vm["p"] else "n/a"}; SF nodal max {f(sfb["fine"], 4)} [{f(sfb["lo"], 4)}, {f(sfb["hi"], 4)}] |')
    L += [f'| faer sparse Cholesky (v0.31) | `evidence/bench/faer_0.31.2_xbabe3.json` | cert tier {f(s0, 2)} → {f(s1, 2)} core-s/design ({f(s0 / s1, 2)}×) on `{b1["workload"]}` ({b1["host"]}) |',
          f'| faer vs skyline parity (v0.31, issue #32) | `evidence/bench/issue32_drift.json` | max drift {dr["max_rel_faer"]:.1e} per design > {dr["bar"]:.0e} bar → default solver skyline, faer opt-in |']
    return '\n'.join(L)


def components(context=None):
    c = js(COMP); p = c['partition']
    L = [f'Design `{c["label"][:-3] if c["label"].endswith("_D1") else c["label"]}` ({f(c["mass_g"], 2)} g). Plan partition (`ops/render/components.py`): ring = within bore radius + 1.6 × ring band '
         f'({f(p["bore_radius_est_mm"], 2)} + 1.6 × {f(p["ring_band_mm"], 2)} mm) of the ring centre; grip/spine = next {p["grip_mm"]:.0f} mm; tip = within {p["tip_radius_mm"]:.0f} mm of the tip; blade = rest. '
         f'(b) panels show the {c["sf_field"]}; that field is the RS-karambit-v1 screen field. The last column lists the design\'s RS-karambit-v2 gate values from `evidence/rs_v2/` (tip: strict 0.0625 mm² tip-submodel twist SF and the genome-bound solid tip SF, which are the locked gate values; the plate min element SF is the screen field only).', '']
    for k, x in enumerate(c['components'], 1):
        rs = ', '.join(f'{g} {f(v, 3) if isinstance(v, float) else v}' for g, v in x['rs_v2'].items())
        L += [f'![Fig. C{k}]({os.path.relpath(os.path.join(ROOT, x["figure"]), os.path.join(ROOT, "docs"))})', '',
              f'*Fig. C{k}. {x["title"]}: (a) 3D CAD view (faceted STL, component highlighted); (b) plan FEM colormap.*', '']
    L += ['| component | elements | area share | min element SF (D1, 100 °C) | median element SF | area SF < 1 | RS-karambit-v2 gate values |', '|---|---|---|---|---|---|---|']
    for x in c['components']:
        rs = '; '.join(f'`{g}` {f(v, 3) if isinstance(v, float) else v}' for g, v in x['rs_v2'].items())
        L.append(f'| {x["title"]} | {x["n_elements"]} | {100 * x["area_share"]:.1f} % | {f(x["sf_min"])} | {f(x["sf_median"])} | {100 * x["frac_area_sf_below_1"]:.1f} % | {rs} |')
    return '\n'.join(L)


def rsv2_table(context=None):
    seq_t, bw = gate_mins(); ds = rsv2()
    st = lambda v: {'pass': 'PASS', 'fail': 'FAIL', 'unverified': 'unverified'}[v]
    num = lambda x, n=3: '—' if x is None else f(x, n)
    L = ['| design (RS-karambit-v2) | mass g | v1 screen | strict lateral N (≥ 260) | strict tip-sub twist SF | solid tip SF | seq (≥ ' + f'{seq_t}' + ') | twist SF | tip SF | spine SF | ring-back SF | fatigue SF | bearing mm (≥ ' + f'{bw:.0f}' + ') | all hard gates |',
         '|---|---|---|---|---|---|---|---|---|---|---|---|---|---|']
    for d in ds:
        L.append(f'| {d["label"]} | {f(d["mass_g"], 2)} | {st(d["screen"])} | {num(d["strict_lat_rob_0p0625_n"], 1)} | {num(d["twist_tipzone_sf_strict"])} | {num(d["solid_tip_sf"])} ({st(d["gates"]["solid_tip_sf"])}) | {f(d["seq_ratio"])} | '
                 f'{f(d["hm_twist_sf"])} | {f(d["hm_tip_inplane_sf"])} | {f(d["hm_spine_sf"])} | {f(d["hm_ringback_sf"])} | {f(d["fat_sf"])} | {f(d["ring_bearing_w_mm"], 2)} | **{"PASS" if d["all_hard"] else "FAIL"}** |')
    rej = [f'`{d["label"]}`: {"; ".join(d["rejects"])}' for d in ds if d.get('rejects')]
    L += ['', f'**{sum(d["all_hard"] for d in ds)} of {len(ds)} designs pass every RS-karambit-v2 hard gate.** An unverified gate (no evidence) never counts as met. ' + ('Screen rejects: ' + ' · '.join(rej) if rej else '')]
    return '\n'.join(L)


def render(text, context=None):
    for name, fn in (('WP_STATUS', status), ('WP_METHODS', methods), ('WP_COMPONENTS', components), ('WP_RSV2', rsv2_table)):
        pat = re.compile(rf'(<!-- GEN:{name}:BEGIN -->\n).*?(\n<!-- GEN:{name}:END -->)', re.S)
        if not pat.search(text):
            raise SystemExit(f'gen_whitepaper: {WP} lacks the GEN:{name} block')
        text = pat.sub(lambda m: m.group(1) + fn(context) + m.group(2), text)
    if context is not None:
        text = rs_verdicts.replace_claim_block(text, context)
    return text


def verify_components():
    """Component figures and their inputs must match the sha256s recorded in components.json."""
    import hashlib
    c = js(COMP); errs = []
    sha = lambda rel: hashlib.sha256(open(os.path.join(ROOT, rel), 'rb').read()).hexdigest()
    for x in c['components']:
        if not os.path.exists(os.path.join(ROOT, x['figure'])) or sha(x['figure']) != x['figure_sha256']:
            errs.append(f'{x["figure"]}: missing or sha256 mismatch')
    for rel, h in c['inputs'].items():
        if sha(rel) != h:
            errs.append(f'{rel}: input changed since components were rendered (re-run ops/render/components.py)')
    return errs


if __name__ == '__main__':
    cur = rd(WP); new = render(cur)
    if '--check' in sys.argv:
        e = verify_components()
        if e:
            print('\n'.join(e)); sys.exit(1)
        if cur != new:
            print(f'{WP} generated blocks are stale: run python3 ops/ci/gen_whitepaper.py'); sys.exit(1)
        print(f'{WP} up to date'); sys.exit(0)
    open(os.path.join(ROOT, WP), 'w', encoding='utf-8').write(new); print(f'wrote {WP}')
