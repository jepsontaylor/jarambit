#!/usr/bin/env python3
"""WAVE REPORT pack generator (jarambit, SWITCHBACK-class titanium hiking/utility karambit).

Writes, per wave N:  docs/wave_reports/wave{N}_REPORT.md, wave{N}_FEM_metrics.png (300 dpi),
wave{N}_paper_data.csv (one row per D1-screened design) and wave{N}_paper_data.json (full pack + provenance).

Rules (CURRENT D1, owner Jepson Taylor): Ti-6Al-4V screening yield 828 MPa, JOINT thin+hot robust factor;
hiker 180 / hunter 260 (aim 286) / ring 1500 N at certification min(0.25, 0.125 mm^2) AND hunter at strict 0.0625 mm^2;
chord torsion 1.82 N*m BOTH modes (tip-only AND body+tip = min(body >15 mm, tip-submodel strict));
hand/blade yield-onset ratio >= 1.2; mass band 74-77 g, cap < 80 g; blade >= 3.375 in on all three;
C.6 aesthetic floor (automated) + HUMAN aesthetic sign-off (never auto-PASS). No promotion from this tool.

Badges are three-state. A value that is missing is NOT VERIFIED (grey) and can never render green.

Sources (any combination; later sources fill gaps, never overwrite):
  --d1-dir DIR      crescent-d1 collect dir (plates.txt, <label>.json, d1_rescreen.csv) or a P1 crescent-evolve dir
  --d1-csv CSV      extra d1_rescreen.csv rows (e.g. docs/d1/d1_rescreen_p0.csv)
  --pre-dir DIR     pre-D1 source-run dir (report.md, certification.csv, history.csv) for novelty/search capacities
  --prior-pack JSON prior wave's wave{N-1}_paper_data.json (strength + weight delta)
  --prior-pre-dir   prior wave's pre-D1 dir (used only when no prior pack exists)
Python is offline reporting only (no hot path)."""
import argparse, csv, datetime as dt, hashlib, json, math, os, re, sys
import numpy as np
import matplotlib; matplotlib.use('Agg')
import matplotlib.pyplot as plt, matplotlib.tri as mtri
from matplotlib.patches import Polygon as MPoly

IN = 25.4
RHO = 4.43                 # Ti-6Al-4V g/cm^3
LEGAL_BLADE = 85.725        # 3.375 in
GUARD_BLADE = 86.225        # +0.5 mm design guard
LOAD_CASE_VERSION = "D1-P1/2026-10-11: 828MPa-provisional JOINT(thin(t-0.1)^2 x hot sy100/sy20); lateral 260N (hiker 180 / hunter 260, aim 286); pry 260N (no floor); ring pull 1500N; chord torsion 1.82N*m tip-only (2mm patch, peak>=4mm, St-Venant 3D) + body(>15mm) + tip-submodel(4-15mm @0.0625); cert min(0.25,0.125mm2) no bias + strict 0.0625mm2"
NAMES = ['relief', 'lattice', 'fuller', 'flutes', 'texture', 'isogrid', 'ring flute']
UNQUALIFIED = [
    "4 mm tip-load patch excluded from peaks (St-Venant zone) - not qualified",
    "clamped-cut tip submodel = STUB (tip-sub SF is a refined local check of the 4-15 mm annulus, not a cut model)",
    "ring peel = STUB (no ring-peel case)",
    "fatigue = STUB (static screening only)",
    "pry 260 N computed but has NO floor",
    "828 MPa yield provisional until lot MTR",
    "flat Kirchhoff plate (DKT+T6) with per-element thickness; 3D only via St-Venant factor on twist",
]
FINAL_EDGE_NOTE = "grind-law JSON exported; analytic B-rep grind STEP = STUB; faceted STEP != machining release"

PASS, FAIL, NV = 'PASS', 'FAIL', 'NOT VERIFIED'
COL = {PASS: '#1f9d55', FAIL: '#c62828', NV: '#7f7f7f', 'INFO': '#b26a00'}

def fnum(v):
    if v is None: return None
    if isinstance(v, bool): return float(v)
    try:
        x = float(v)
        return x if math.isfinite(x) else None
    except (TypeError, ValueError):
        return None

def fbool(v):
    if isinstance(v, bool): return v
    if v is None: return None
    s = str(v).strip().lower()
    return True if s in ('true', '1', 'yes') else False if s in ('false', '0', 'no') else None

def gate(val, thr, ge=True):
    v = fnum(val)
    if v is None: return NV
    return PASS if (v >= thr if ge else v < thr) else FAIL

def all_of(*bs):
    if any(b == FAIL for b in bs): return FAIL
    if any(b == NV for b in bs): return NV
    return PASS

def sha16(s): return hashlib.sha256(s.encode()).hexdigest()[:16]

def mt(ts):
    """UTC epoch -> 'YYYY-MM-DD HH:MM MT (UTC hh:mm)'"""
    u = dt.datetime.fromtimestamp(ts, dt.timezone.utc)
    m = u + dt.timedelta(hours=-6)
    return f"{m:%Y-%m-%d %H:%M} MT ({u:%H:%M}Z)"

def fmt(v, f='{:.2f}', nv='NOT VERIFIED'):
    v2 = fnum(v)
    return nv if v2 is None else f.format(v2)

# ------------------------------------------------------------------ loading
def load_d1_dir(d, wave, recs):
    pl = os.path.join(d, 'plates.txt')
    labels = [l.strip() for l in open(pl)] if os.path.exists(pl) else []
    for lab in labels:
        if not lab or not lab.startswith(wave + '_'): continue
        jp = os.path.join(d, lab + '.json')
        if not os.path.exists(jp): continue
        J = json.load(open(jp))
        key = re.sub(r'_(D1|fit)$', '', lab)
        r = recs.setdefault(key, {'design': key})
        r.setdefault('_json', jp); r.setdefault('_J', J)
        r.setdefault('_mtime', os.path.getmtime(jp))
        gl = os.path.join(d, key + '_grind_law.json')
        if os.path.exists(gl): r.setdefault('grind_law_json', gl)
    cp = os.path.join(d, 'd1_rescreen.csv')
    if os.path.exists(cp): load_d1_csv(cp, wave, recs)
    # P1 crescent-evolve: certification.csv carries strict info by id
    cc = os.path.join(d, 'certification.csv')
    if os.path.exists(cc):
        for row in csv.DictReader(open(cc)):
            for r in recs.values():
                J = r.get('_J')
                if J and str(J['metrics'].get('id')) == row.get('id'):
                    r.setdefault('_cert_row', row)

def load_d1_csv(p, wave, recs):
    for row in csv.DictReader(open(p)):
        k = row.get('design', '')
        if not k.startswith(wave + '_'): continue
        r = recs.setdefault(k, {'design': k})
        r.setdefault('_csv', row); r.setdefault('_csv_path', p)

def parse_pre_report(pre_dir):
    """pre-D1 report.md: '- waveNN_cXX_fit (...): {json}' lines."""
    out = {}
    if not pre_dir: return out
    rp = os.path.join(pre_dir, 'report.md')
    if not os.path.exists(rp): return out
    for line in open(rp):
        m = re.match(r'^- (wave\d+_c\d+)_fit \((.*?)\): (\{.*\})\s*$', line.strip())
        if m:
            try: out[m.group(1)] = dict(json.loads(m.group(3)), _note=m.group(2))
            except Exception: pass
    cp = os.path.join(pre_dir, 'certification.csv')
    if os.path.exists(cp):
        byid = {str(v.get('id')): k for k, v in out.items()}
        for row in csv.DictReader(open(cp)):
            k = byid.get(row.get('id'))
            if k: out[k]['_cert'] = row
    return out

def run_header(pre_dir):
    if not pre_dir: return None, None
    rp = os.path.join(pre_dir, 'report.md')
    hdr = None
    if os.path.exists(rp):
        L = open(rp).read().splitlines()
        hdr = ' '.join(l for l in L[1:4] if l.strip())[:600]
    hp = os.path.join(pre_dir, 'history.csv')
    return hdr, (os.path.getmtime(hp) if os.path.exists(hp) else None)

# ------------------------------------------------------------------ per design
def build(r, pre):
    J = r.get('_J'); m = J['metrics'] if J else {}; x = (J.get('d1') or {}) if J else {}
    c = r.get('_csv', {}); cr = r.get('_cert_row', {})
    P = pre.get(r['design'], {})
    g = lambda *ks: next((fnum(s[k]) for s, k in ks if k in s and fnum(s[k]) is not None), None)
    d = {'design': r['design']}
    d['mass_g'] = g((m, 'mass_g'), (c, 'mass_g'))
    d['blank_g'] = g((m, 'blank_g'), (P, 'blank_g'))
    d['t_stock_mm'] = g((m, 't'), (c, 't'))
    d['t_joint_mm'] = g((m, 't_joint'), (c, 't_joint'))
    d['fit'] = g((m, 'fit'),); d['spg'] = g((m, 'spg'),)
    d['lat20_828'] = g((m, 'lat20'), (c, 'lat20_828'))
    d['joint_lat_cert'] = g((m, 'lat_rob'), (c, 'joint_lat_cert'))
    d['joint_lat_strict'] = g((x, 'strict_lat_rob_0p0625'), (c, 'strict_joint_lat_0p0625'), (cr, 'strict_lat_rob_0p0625'))
    vals = [v for v in (d['joint_lat_cert'], d['joint_lat_strict']) if v is not None]
    d['joint_lat_governing'] = min(vals) if len(vals) == 2 else None
    d['joint_factor'] = (d['joint_lat_cert'] / d['lat20_828']) if d['joint_lat_cert'] and d['lat20_828'] else None
    d['sf_hiker'] = g((m, 'sf_hiker'), (c, 'sf_hiker')); d['sf_hunter_cert'] = g((m, 'sf_hunter'), (c, 'sf_hunter'))
    d['sf_hunter_strict'] = d['joint_lat_strict'] / 260 if d['joint_lat_strict'] else None
    d['ring_joint_N'] = g((m, 'ring_rob'), (c, 'joint_ring_cert')); d['sf_ring'] = g((m, 'sf_ring'), (c, 'sf_ring'))
    d['pry20_N'] = g((m, 'pry20'),)
    d['twist_tip_only_sf'] = g((m, 'twist_tip_sf'), (c, 'twist_tip_sf_1p82_default_hard'), (c, 'twist_sf_1p82'))
    d['twist_tip_joint3d_nmm'] = g((m, 'twist_tip_joint3d_nmm'), (c, 'twist_joint3d_nmm'))
    d['twist_tip_peak_tipdist_mm'] = g((m, 'twist_tip_peak_tipdist'), (c, 'twist_peak_tipdist_mm'))
    d['twist_kc_3d'] = g((c, 'twist_kc_3d'),)
    d['twist_body_sf'] = g((m, 'twist_body_sf'), (c, 'twist_body_sf_1p82'))
    d['twist_tipsub_sf_strict'] = g((x, 'twist_tipzone_sf_strict'), (c, 'twist_tipzone_sf_strict'))
    bt = [d['twist_body_sf'], d['twist_tipsub_sf_strict']]
    d['twist_body_plus_tip_sf'] = min(bt) if all(v is not None for v in bt) else None
    d['hand_blade_ratio'] = g((m, 'seq_ratio'), (c, 'seq_ratio'))
    d['hand_blade_case'] = m.get('seq_case') or c.get('seq_case')
    d['aes_A'] = g((m, 'aes_score'), (P, 'aes_score')); d['aes_H_mm'] = g((m, 'hausdorff'), (P, 'hausdorff'))
    d['aes_emd'] = g((m, 'emd'), (P, 'emd')); d['aes_floor_pass'] = fbool(m.get('aes_pass', c.get('aes_pass')))
    d['aes_fails'] = m.get('aes_fails', [])
    nov = fnum(P.get('novelty'));  nv_d1 = fnum(m.get('novelty'))
    d['novelty'] = nov if nov is not None else (nv_d1 if (nv_d1 or 0) > 0 else None)
    d['novelty_source'] = 'source-run archive (pre-D1 k-NN)' if nov is not None else ('this run' if d['novelty'] is not None else 'NOT VERIFIED (re-screen does not recompute novelty)')
    d['tip_to_heel_mm'] = g((m, 'tip_to_heel'), (P, 'tip_to_heel')); d['horizontal_reach_mm'] = g((m, 'horizontal_reach'), (P, 'horizontal_reach'))
    ai, asp = g((m, 'arc_in'), (P, 'arc_in')), g((m, 'arc_sp'), (P, 'arc_sp'))
    d['sharpened_arc_mm'] = max(ai, asp) if ai is not None and asp is not None else None
    bl = [d['tip_to_heel_mm'], d['horizontal_reach_mm'], d['sharpened_arc_mm']]
    d['blade_min_mm'] = min(bl) if all(v is not None for v in bl) else None
    d['grip_mm'] = g((m, 'grip'),)
    d['rejects'] = m.get('rejects') if J else None
    d['removed_mm3'] = m.get('removed_mm3'); d['perf_area_mm2'] = g((m, 'perf_area'),); d['win_area_mm2'] = g((m, 'win_area'),)
    d['n_perf'] = m.get('n_perf'); d['n_win'] = m.get('n_win'); d['min_web_mm'] = g((m, 'min_web'),)
    d['p1'] = bool(m.get('p1')); d['rail_w_mm'] = g((m, 'rail_w'),); d['neck_l_mm'] = g((m, 'neck_l'),)
    d['pocket_d_mm'] = g((m, 'pocket_d'),); d['knots_mm'] = m.get('knots')
    d['holder_box'] = m.get('holder_box')
    # search-level (pre-D1 rules) capacities for the capacities-by-mesh record
    pc = P.get('_cert', {})
    d['search_lat_rob_preD1_2mm2'] = fnum(pc.get('search_lat_rob'))
    d['cert_lat_rob_preD1_880min'] = g((x, 'old_lat_rob_880_min'), (c, 'old_lat_rob_880_min'), (P, 'lat_rob'))
    d['mass_carry_g'] = None
    if J:
        gen = J.get('genome', '')
        d['genome_hash'] = 'sha256:' + sha16(gen)
        decs = max((len(t.split('.')[1]) for t in gen.split(',') if '.' in t), default=0)
        d['genome_precision'] = 'full-precision' if decs > 4 else '4-decimal (pre-D1 CSV; see D1 P0 reproducibility caveat)'
        geo = json.dumps([np.round(np.array(J['outline']), 3).tolist(), [np.round(np.array(h), 3).tolist() for h in J['holes']]], separators=(',', ':'))
        d['geometry_hash'] = 'sha256:' + sha16(geo)
        d['plate_mesh_tris'] = len(J['mesh']['tris']); d['plate_mesh_nodes'] = len(J['mesh']['xy'])
        d['plate_mesh_level'] = J.get('fine_area')
    else:
        d['genome_hash'] = d['geometry_hash'] = None; d['genome_precision'] = None
        d['plate_mesh_tris'] = d['plate_mesh_nodes'] = None; d['plate_mesh_level'] = None
    d['final_edge'] = ('grind-law JSON: ' + os.path.basename(r['grind_law_json']) + '; ' + FINAL_EDGE_NOTE) if r.get('grind_law_json') else 'NOT VERIFIED (no grind-law JSON found); ' + FINAL_EDGE_NOTE
    d['source_json'] = r.get('_json'); d['source_csv'] = r.get('_csv_path')
    d['source_mtime'] = mt(r['_mtime']) if r.get('_mtime') else None
    # ---------------- gates
    G = {}
    G['joint_lateral_260 (cert AND strict)'] = all_of(gate(d['joint_lat_cert'], 260), gate(d['joint_lat_strict'], 260))
    G['hiker_180 (cert)'] = gate(d['joint_lat_cert'], 180)
    G['ring_pull_1500 (joint)'] = gate(d['ring_joint_N'], 1500)
    G['twist_tip_only_SF>=1 @1.82'] = gate(d['twist_tip_only_sf'], 1.0)
    bts = [gate(d['twist_body_sf'], 1.0), gate(d['twist_tipsub_sf_strict'], 1.0)]
    G['twist_body+tip_SF>=1 @1.82'] = all_of(*bts)
    G['hand/blade_ratio>=1.2'] = gate(d['hand_blade_ratio'], 1.2)
    G['mass_band_74-77'] = NV if d['mass_g'] is None else (PASS if 74.0 <= d['mass_g'] <= 77.0 else FAIL)
    G['mass_cap_<80'] = gate(d['mass_g'], 80.0, ge=False)
    G['blade>=3.375in_all_three'] = gate(d['blade_min_mm'], LEGAL_BLADE)
    G['C.6_aesthetic_floor (automated)'] = NV if d['aes_floor_pass'] is None else (PASS if d['aes_floor_pass'] and not d['aes_fails'] else FAIL)
    G['hard_gates/redteam'] = NV if d['rejects'] is None else (PASS if not d['rejects'] else FAIL)
    G['aesthetic_signoff (human)'] = NV
    d['aim_286'] = None if d['joint_lat_governing'] is None else d['joint_lat_governing'] >= 286
    d['gates'] = G
    d['overall'] = all_of(*G.values())
    return d

# ------------------------------------------------------------------ geometry helpers for the figure
def region(xy, tip):
    x, y = xy; r = math.hypot(x, y); td = math.hypot(x - tip[0], y - tip[1])
    if td <= 15: return f'tip zone ({td:.1f} mm from apex)'
    if r <= 24: return 'ring / ring-neck'
    if x < 80: return 'grip / handle'
    return 'blade body'

def figure(wave, d, J, title, outpng, badges):
    xy = np.array(J['mesh']['xy']); tri = np.array(J['mesh']['tris']); T = mtri.Triangulation(xy[:, 0], xy[:, 1], tri)
    env = np.array(J['mesh']['env_vm'], float); sf = np.array(J['mesh']['sf'], float)
    cen = xy[tri].mean(1); o = np.array(J['outline'])
    excl = env <= 0
    # blade-tip apex = outline point farthest from the ring centre (0, 0)
    tip = tuple(o[np.argmax(np.hypot(o[:, 0], o[:, 1]))])
    sy100 = np.nanmedian(np.where(env > 0, sf * env, np.nan))
    kc = d.get('twist_kc_3d') or 1.0
    fields = {
        'lat': np.array(J['mesh']['lat'], float) * 260,
        'ring': np.array(J['mesh']['ring'], float) * 1500,
        'twist': np.array(J['mesh']['twist'], float) * 1820 * kc,
    }
    for k in fields: fields[k][excl] = 0
    tdist = np.hypot(cen[:, 0] - tip[0], cen[:, 1] - tip[1])
    peaks = {}
    def pk(key, mask=None):
        v = fields[key].copy()
        if mask is not None: v[~mask] = 0
        i = int(np.argmax(v)); c = tuple(cen[i])
        return dict(vm=float(v[i]), sf=float(sy100 / v[i]) if v[i] > 0 else None, at=c, region=region(c, tip))
    peaks['lateral 260 N'] = pk('lat')
    peaks['ring pull 1500 N'] = pk('ring')
    # tip-only twist governs the envelope near the tip: its certified peak is the min envelope-SF element within 15 mm of the apex
    kt = int(np.argmin(np.where(excl | (tdist > 15), np.inf, sf))); ct = tuple(cen[kt])
    peaks['twist tip-only 1.82 N*m'] = dict(vm=float(env[kt]), sf=float(sf[kt]), at=ct, region=region(ct, tip))
    pb_ = pk('twist', tdist > 15); pb_['sf'] = None
    peaks['twist body >15 mm (field locator)'] = pb_
    k = int(np.argmin(np.where(excl, np.inf, sf))); c = tuple(cen[k])
    peaks['worst SF (envelope, 100 C)'] = dict(vm=float(env[k]), sf=float(sf[k]), at=c, region=region(c, tip))

    fig = plt.figure(figsize=(20, 13.2))
    gs = fig.add_gridspec(3, 3, height_ratios=[1, 1, 1.02], hspace=0.30, wspace=0.08, left=0.015, right=0.99, top=0.865, bottom=0.03)
    fig.suptitle(title, fontsize=17, fontweight='bold', y=0.988)
    fig.text(0.5, 0.948, "D1 rules: Ti-6Al-4V 828 MPa (provisional) JOINT thin+hot; cert min(0.25, 0.125 mm²) + strict 0.0625 mm²; maps = detailed plate FEM (DKT + T6, per-element thickness) at 100 °C yield, nominal thickness.\n"
             "KPI numbers = certified JOINT scalars. 4 mm tip-load patch excluded from peaks. Utility/hiking karambit — NOT PROMOTED; human aesthetic sign-off required.", ha='center', va='center', fontsize=9.5)
    n = len(badges); w = 0.97 / n
    for i, (lab, st, val) in enumerate(badges):
        fig.text(0.015 + w * (i + 0.5), 0.912, f"{lab}\n{st}\n{val}", ha='center', va='center', fontsize=8.0, color='white', fontweight='bold',
                 bbox=dict(boxstyle='round,pad=0.35', fc=COL.get(st, COL['INFO']), ec='none'))

    def outline(ax):
        ax.add_patch(MPoly(o, closed=True, fill=False, ec='k', lw=0.6))
        for h in J['holes']: ax.add_patch(MPoly(np.array(h), closed=True, fill=False, ec='k', lw=0.5))
        ax.set_aspect('equal'); ax.set_xticks([]); ax.set_yticks([])
        lo = o.min(0) - 4; hi = o.max(0) + 4; ax.set_xlim(lo[0], hi[0]); ax.set_ylim(lo[1], hi[1])
    def mark(ax, p, lab, col='k', off=16):
        ax.plot(*p['at'], marker='x', color=col, ms=13, mew=2.6)
        x0, x1 = ax.get_xlim(); right = (p['at'][0] - x0) / (x1 - x0) > 0.55
        ax.annotate(f"{lab}\n({p['at'][0]:.0f},{p['at'][1]:.0f}) mm — {p['region']}", p['at'], xytext=(-14 if right else 12, off), textcoords='offset points', fontsize=8,
                    ha='right' if right else 'left',
                    bbox=dict(fc='white', ec=col, alpha=0.9, lw=0.8), arrowprops=dict(arrowstyle='-', color=col, lw=0.8))

    def vm_panel(ax, v, ttl, pks):
        vmax = np.percentile(v[v > 0], 99.5) if (v > 0).any() else 1
        tp = ax.tripcolor(T, facecolors=v, cmap='turbo', vmin=0, vmax=vmax, rasterized=True); outline(ax)
        fig.colorbar(tp, ax=ax, fraction=0.022, pad=0.005).set_label('σvm (MPa)', fontsize=8)
        for i, (lab, p, col) in enumerate(pks): mark(ax, p, lab, col, off=16 + 34 * i)
        ax.set_title(ttl, fontsize=10)
    ax = fig.add_subplot(gs[0, 0]); p = peaks['lateral 260 N']
    vm_panel(ax, fields['lat'], f"von Mises — tip lateral 260 N (hunter)\npeak {p['vm']:.0f} MPa, map SF {p['sf']:.2f}; certified joint lat {fmt(d['joint_lat_cert'],'{:.0f}')} N / strict {fmt(d['joint_lat_strict'],'{:.0f}')} N", [('lateral peak', p, 'k')])
    ax = fig.add_subplot(gs[0, 1]); pt, pb = peaks['twist tip-only 1.82 N*m'], peaks['twist body >15 mm (field locator)']
    vm_panel(ax, fields['twist'], f"von Mises — chord torsion 1.82 N·m (plate-export twist field × 3D k={kc:.3f}; distribution/locator)\ncertified: tip-only SF {fmt(d['twist_tip_only_sf'])} (envelope peak {pt['vm']:.0f} MPa) · body SF {fmt(d['twist_body_sf'])}", [('tip-only peak', pt, 'k'), ('body peak', pb, '#444')])
    ax = fig.add_subplot(gs[0, 2]); p = peaks['ring pull 1500 N']
    vm_panel(ax, fields['ring'], f"von Mises — ring pull 1500 N\npeak {p['vm']:.0f} MPa, map SF {p['sf']:.1f}; joint ring capacity {fmt(d['ring_joint_N'],'{:.0f}')} N", [('ring peak', p, 'k')])
    ax = fig.add_subplot(gs[1, 0]); pw = peaks['worst SF (envelope, 100 C)']
    tp = ax.tripcolor(T, facecolors=np.clip(sf, 0, 4), cmap='RdYlGn', vmin=0, vmax=4, rasterized=True); outline(ax)
    fig.colorbar(tp, ax=ax, fraction=0.022, pad=0.005).set_label('SF = σy(100 °C)/σvm', fontsize=8)
    mark(ax, pw, 'worst SF', 'k'); ax.set_title(f"SAFETY FACTOR — envelope of lateral/pry/ring/twist (worst case)\nmin SF {pw['sf']:.2f} at ({pw['at'][0]:.0f},{pw['at'][1]:.0f}) mm — {pw['region']}", fontsize=10)
    # twist SF, body+tip view
    ax = fig.add_subplot(gs[1, 1]); stw = np.where(fields['twist'] > 0, sy100 / np.maximum(fields['twist'], 1e-9), 4)
    tp = ax.tripcolor(T, facecolors=np.clip(stw, 0, 4), cmap='RdYlGn', vmin=0, vmax=4, rasterized=True); outline(ax)
    fig.colorbar(tp, ax=ax, fraction=0.022, pad=0.005).set_label('SF twist only', fontsize=8)
    mark(ax, pb, 'body peak', '#333', off=50); mark(ax, pt, 'tip peak', 'k', off=14)
    ax.set_title(f"twist-only SF field (locator) — certified body+tip twist: body {fmt(d['twist_body_sf'])} · tip-sub(strict) {fmt(d['twist_tipsub_sf_strict'])} → min {fmt(d['twist_body_plus_tip_sf'])}", fontsize=10)
    # tip zoom
    ax = fig.add_subplot(gs[1, 2])
    tp = ax.tripcolor(T, facecolors=np.clip(sf, 0, 2), cmap='RdYlGn', vmin=0, vmax=2, rasterized=True); outline(ax)
    ax.set_xlim(tip[0] - 30, tip[0] + 8); ax.set_ylim(tip[1] - 12, tip[1] + 20)
    ax.add_patch(plt.Circle(tip, 15, fill=False, ls=':', ec='b', lw=1))
    if excl.any(): ax.plot(cen[excl, 0], cen[excl, 1], '.', ms=1.5, color='#06c')
    mark(ax, pt, 'tip-only peak', 'k'); fig.colorbar(tp, ax=ax, fraction=0.03, pad=0.005).set_label('envelope SF (0-2)', fontsize=8)
    ax.set_title(f"TIP ZOOM — tip-only twist SF {fmt(d['twist_tip_only_sf'])} (certified;\npeak {fmt(d['twist_tip_peak_tipdist_mm'],'{:.1f}')} mm from load pt) · envelope SF · blue = excluded patch · dotted = 15 mm", fontsize=9)
    # thickness field + KPI table
    ax = fig.add_subplot(gs[2, 0]); f = J['field']; th = np.array([np.nan if v is None else v for v in f['th']], float).reshape(f['ny'], f['nx'])
    im = ax.imshow(th, origin='lower', extent=[f['x0'], f['x0'] + f['nx'] * f['g'], f['y0'], f['y0'] + f['ny'] * f['g']], cmap='viridis', interpolation='nearest'); outline(ax)
    fig.colorbar(im, ax=ax, fraction=0.022, pad=0.005).set_label('finished thickness (mm)', fontsize=8)
    ax.set_title(f"thickness field (stock {fmt(d['t_stock_mm'],'{:.1f}')} mm; joint t {fmt(d['t_joint_mm'],'{:.2f}')} mm; min web {fmt(d['min_web_mm'])} mm)", fontsize=10)
    ax = fig.add_subplot(gs[2, 1:]); ax.axis('off')
    rows = []
    for name, st in d['gates'].items(): rows.append([name, st])
    tb = ax.table(cellText=rows, colLabels=['gate (D1)', 'status'], colWidths=[0.38, 0.14], loc='upper left', bbox=[0.0, 0.0, 0.5, 1.0])
    tb.auto_set_font_size(False); tb.set_fontsize(9)
    for (i, j), cell in tb.get_celld().items():
        if i > 0 and j == 1:
            st = rows[i - 1][1]; cell.set_facecolor(COL[st]); cell.get_text().set_color('white'); cell.get_text().set_fontweight('bold')
    pk_rows = [[k, f"{v['vm']:.0f}", '-' if v['sf'] is None else f"{v['sf']:.2f}", f"({v['at'][0]:.0f},{v['at'][1]:.0f})", v['region']] for k, v in peaks.items()]
    tb2 = ax.table(cellText=pk_rows, colLabels=['case (map)', 'σvm MPa', 'map SF', 'x,y mm', 'region'], colWidths=[0.19, 0.05, 0.045, 0.06, 0.145], loc='upper right', bbox=[0.52, 0.30, 0.48, 0.70])
    tb2.auto_set_font_size(False); tb2.set_fontsize(8.5)
    ax.text(0.52, 0.25, f"OVERALL: {d['overall']}  (NEVER PROMOTED by this tool)\nmass {fmt(d['mass_g'],'{:.2f}')} g · stock {fmt(d['t_stock_mm'],'{:.1f}')} mm · SPG(cert) {fmt(d['spg'],'{:.3f}')} N/g\nA {fmt(d['aes_A'],'{:.3f}')} · H {fmt(d['aes_H_mm'])} mm · plate mesh {d['plate_mesh_tris']} tris\n"
            f"genome {d['genome_hash']}\ngeometry {d['geometry_hash']}", transform=ax.transAxes, fontsize=9.5, va='top',
            bbox=dict(fc=COL[d['overall']], ec='none', alpha=0.95), color='white', fontweight='bold')
    fig.text(0.5, 0.006, f"author Jepson Taylor | generator ops/wave_reports/make_wave_report.py | source {d['source_json']} | map SF uses σy(100 °C)={sy100:.0f} MPa without the thin factor; gate SFs are the certified JOINT values", ha='center', fontsize=7.5)
    fig.savefig(outpng, dpi=300); plt.close(fig)
    return peaks, float(sy100)

# ------------------------------------------------------------------ ledger
def ledger(d):
    if d.get('removed_mm3') is None or d.get('blank_g') is None or d.get('mass_g') is None: return None
    rm = [float(v) for v in d['removed_mm3']] + [0.0] * (7 - len(d['removed_mm3']))
    gram = lambda mm3: mm3 * RHO / 1000.0
    t = d['t_stock_mm'] or 0
    L = {
        'rails (P1 full-thickness rails/neck; nothing removed by design)': 0.0 if d['p1'] else 'n/a (P0 layout, no rail genes)',
        'pockets (relief + lattice + isogrid + texture)': gram(rm[0] + rm[1] + rm[4] + rm[5]),
        'through-perfs/windows (vs unperforated blank)': gram(((d['perf_area_mm2'] or 0) + (d['win_area_mm2'] or 0)) * t),
        'ring (ring-face flute)': gram(rm[6]),
        'grind (fuller + flutes)': gram(rm[2] + rm[3]),
    }
    item = sum(gram(v) for v in rm)  # perfs are holes in the outline area, so they are not part of blank - finished
    L['grind/taper/edge bevel residual (blank - finished - itemised machining)'] = d['blank_g'] - d['mass_g'] - item
    return L

# ------------------------------------------------------------------ main
def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--wave', required=True, type=int)
    ap.add_argument('--d1-dir', action='append', default=[])
    ap.add_argument('--d1-csv', action='append', default=[])
    ap.add_argument('--pre-dir'); ap.add_argument('--prior-pack'); ap.add_argument('--prior-pre-dir')
    ap.add_argument('--out', default='docs/wave_reports'); ap.add_argument('--solver-commit', default=None)
    ap.add_argument('--run-label', default=''); ap.add_argument('--signoff-dir', default=None)
    ap.add_argument('--copy-to', action='append', default=[])
    a = ap.parse_args()
    wave = f"wave{a.wave}"; os.makedirs(a.out, exist_ok=True)
    recs = {}
    for dd in a.d1_dir: load_d1_dir(dd, wave, recs)
    for cc in a.d1_csv: load_d1_csv(cc, wave, recs)
    pre = parse_pre_report(a.pre_dir)
    hdr, hist_mtime = run_header(a.pre_dir)
    designs = [build(r, pre) for r in sorted(recs.values(), key=lambda r: r['design'])]
    if a.signoff_dir:
        for d in designs:
            so = os.path.join(a.signoff_dir, d['design'] + '.signoff')
            if os.path.exists(so) and open(so).read().strip().upper().startswith('APPROVED'):
                d['gates']['aesthetic_signoff (human)'] = PASS; d['overall'] = all_of(*d['gates'].values())
    plated = [d for d in designs if recs[d['design']].get('_J')]
    now = dt.datetime.now(dt.timezone.utc).timestamp()
    if not plated:
        print(f"{wave}: no D1 plate JSON found -> NOT VERIFIED pack only", file=sys.stderr)
    rank = {PASS: 0, NV: 1, FAIL: 2}
    def key(d):
        nfail = sum(1 for s in d['gates'].values() if s == FAIL)
        return (rank[d['overall']], nfail, -(d['joint_lat_governing'] or 0), d['mass_g'] or 1e9)
    head = sorted(plated or designs, key=key)[0] if (plated or designs) else None
    # prior
    prior = json.load(open(a.prior_pack)) if a.prior_pack and os.path.exists(a.prior_pack) else None
    prior_pre = parse_pre_report(a.prior_pre_dir) if (not prior and a.prior_pre_dir) else {}
    hd = head
    J = recs[hd['design']]['_J'] if hd and recs[hd['design']].get('_J') else None
    title = (f"WAVE {a.wave} | fitness {fmt(hd and hd['fit'],'{:.3f}')} / SPG {fmt(hd and hd['spg'],'{:.3f}')} N/g | {fmt(hd and hd['mass_g'],'{:.1f}')} g | {fmt(hd and hd['t_stock_mm'],'{:.1f}')} mm stock"
             + f"  [{hd['design'] if hd else '—'}]  OVERALL {hd['overall'] if hd else NV}")
    badges = []
    if hd:
        G = hd['gates']
        badges = [('JOINT LATERAL ≥260 (aim 286)', G['joint_lateral_260 (cert AND strict)'], f"gov {fmt(hd['joint_lat_governing'],'{:.0f}')} N · aim {'MET' if hd['aim_286'] else 'NOT MET' if hd['aim_286'] is not None else 'NV'}"),
                  ('TWIST TIP-ONLY @1.82', G['twist_tip_only_SF>=1 @1.82'], f"SF {fmt(hd['twist_tip_only_sf'])}"),
                  ('TWIST BODY+TIP @1.82', G['twist_body+tip_SF>=1 @1.82'], f"SF {fmt(hd['twist_body_plus_tip_sf'])}"),
                  ('RING PULL ≥1500', G['ring_pull_1500 (joint)'], f"{fmt(hd['ring_joint_N'],'{:.0f}')} N"),
                  ('HAND/BLADE ≥1.2', G['hand/blade_ratio>=1.2'], f"{fmt(hd['hand_blade_ratio'])}"),
                  ('MASS 74–77 / <80', all_of(G['mass_band_74-77'], G['mass_cap_<80']), f"{fmt(hd['mass_g'],'{:.2f}')} g"),
                  ('BLADE ≥3.375 in ×3', G['blade>=3.375in_all_three'], f"min {fmt(hd['blade_min_mm'] and hd['blade_min_mm']/IN,'{:.3f}')} in"),
                  ('C.6 AESTHETIC (auto)', G['C.6_aesthetic_floor (automated)'], f"A {fmt(hd['aes_A'],'{:.3f}')} H {fmt(hd['aes_H_mm'])}"),
                  ('AESTHETIC SIGN-OFF', G['aesthetic_signoff (human)'], 'Jepson required')]
    png = os.path.join(a.out, f"{wave}_FEM_metrics.png")
    peaks, sy100 = ({}, None)
    if J: peaks, sy100 = figure(wave, hd, J, title, png, badges)
    # ---------------- ledger + deltas
    led = ledger(hd) if hd else None
    pd_head = None
    if prior: pd_head = prior.get('headline')
    delta = {}
    if hd and pd_head:
        for k in ('mass_g', 'joint_lat_cert', 'joint_lat_strict', 'joint_lat_governing', 'sf_hunter_cert', 'twist_tip_only_sf', 'twist_body_plus_tip_sf', 'ring_joint_N', 'hand_blade_ratio', 'aes_A'):
            a1, b1 = fnum(hd.get(k)), fnum(pd_head.get(k))
            delta[k] = None if a1 is None or b1 is None else a1 - b1
        delta['_vs'] = f"{pd_head['design']} (D1 rules, prior wave pack)"
        if led and prior.get('ledger'):
            num = lambda v: v if isinstance(v, (int, float)) else None
            delta['_ledger'] = {k: (None if num(led.get(k)) is None or num(prior['ledger'].get(k)) is None else led[k] - prior['ledger'][k]) for k in led}
    elif hd and prior_pre:
        pb = max(prior_pre.values(), key=lambda e: e.get('fit', 0))
        hp = pre.get(hd['design'], {})
        delta['_vs'] = f"prior wave best-fit {[k for k, v in prior_pre.items() if v is pb][0]} — PRE-D1 RULES ONLY (880 MPa, min-factor); D1 delta NOT VERIFIED (prior wave never D1-screened)"
        for k_new, k_old in (('mass_g', 'mass_g'), ('cert_lat_rob_preD1_880min', 'lat_rob'), ('ring_joint_N', None)):
            pass
        if hp:
            delta['mass_g'] = fnum(hp.get('mass_g')) - fnum(pb.get('mass_g'))
            delta['preD1_lat_rob'] = fnum(hp.get('lat_rob')) - fnum(pb.get('lat_rob'))
            delta['preD1_sf_hunter'] = fnum(hp.get('sf_hunter')) - fnum(pb.get('sf_hunter'))
            delta['preD1_ring_rob'] = fnum(hp.get('ring_rob')) - fnum(pb.get('ring_rob'))
            rmn, rmo = hp.get('removed_mm3'), pb.get('removed_mm3')
            if rmn and rmo:
                delta['_preD1_removed_g'] = {NAMES[i]: (rmn[i] - rmo[i]) * RHO / 1000 for i in range(7)}
                delta['_preD1_perf_g'] = ((hp.get('perf_area', 0) * hp.get('t', 0)) - (pb.get('perf_area', 0) * pb.get('t', 0))) * RHO / 1000
    # ---------------- break points
    bp = []
    if hd:
        for d in designs:
            for gname, st in d['gates'].items():
                if st == FAIL: bp.append((d['design'], gname))
    near = []
    for d in designs:
        for nm, v, thr in (('joint lat cert', d['joint_lat_cert'], 260), ('joint lat strict', d['joint_lat_strict'], 260), ('tip-only twist SF', d['twist_tip_only_sf'], 1.0),
                           ('body+tip twist SF', d['twist_body_plus_tip_sf'], 1.0), ('hand/blade', d['hand_blade_ratio'], 1.2), ('ring', d['ring_joint_N'], 1500)):
            if v is not None and thr <= v < thr * 1.05: near.append((d['design'], nm, v, thr))
    # ---------------- paper data
    cols = ['wave', 'design', 'headline', 'overall', 'genome_hash', 'genome_precision', 'geometry_hash', 'solver_commit', 'load_case_version', 'mesh_search_mm2', 'mesh_cert_mm2', 'mesh_strict_mm2',
            'plate_mesh_tris', 'plate_mesh_nodes', 'cap_search_lat_rob_preD1_N', 'cap_cert_lat_rob_preD1_880min_N', 'cap_lat20_828_N', 'cap_joint_lat_cert_N', 'cap_joint_lat_strict_0p0625_N',
            'cap_lat_0p25_only_N', 'cap_lat_0p125_only_N', 'joint_lat_governing_N', 'joint_factor_thin_hot', 't_stock_mm', 't_joint_mm', 'sf_hiker', 'sf_hunter_cert', 'sf_hunter_strict', 'aim_286',
            'twist_tip_only_sf', 'twist_tip_joint3d_nmm', 'twist_tip_peak_tipdist_mm', 'twist_kc_3d', 'twist_body_sf', 'twist_tipsub_sf_strict', 'twist_body_plus_tip_sf',
            'ring_joint_N', 'sf_ring', 'pry20_N', 'hand_blade_ratio', 'hand_blade_case', 'mass_bare_g', 'mass_carry_g', 'blank_g', 'aes_A', 'aes_H_mm', 'aes_emd', 'aes_floor_pass', 'aesthetic_signoff',
            'novelty', 'novelty_source', 'blade_min_in', 'tip_to_heel_mm', 'horizontal_reach_mm', 'sharpened_arc_mm', 'unqualified_regions', 'final_edge', 'source_json', 'source_mtime', 'generated_at']
    gen_at = mt(now)
    rows = []
    for d in designs:
        row = dict(wave=a.wave, design=d['design'], headline=(hd is d), overall=d['overall'], genome_hash=d['genome_hash'], genome_precision=d['genome_precision'], geometry_hash=d['geometry_hash'],
                   solver_commit=a.solver_commit, load_case_version=LOAD_CASE_VERSION, mesh_search_mm2=2.0, mesh_cert_mm2='min(0.25,0.125)', mesh_strict_mm2=0.0625,
                   plate_mesh_tris=d['plate_mesh_tris'], plate_mesh_nodes=d['plate_mesh_nodes'], cap_search_lat_rob_preD1_N=d['search_lat_rob_preD1_2mm2'],
                   cap_cert_lat_rob_preD1_880min_N=d['cert_lat_rob_preD1_880min'], cap_lat20_828_N=d['lat20_828'], cap_joint_lat_cert_N=d['joint_lat_cert'],
                   cap_joint_lat_strict_0p0625_N=d['joint_lat_strict'], cap_lat_0p25_only_N=None, cap_lat_0p125_only_N=None, joint_lat_governing_N=d['joint_lat_governing'],
                   joint_factor_thin_hot=d['joint_factor'], t_stock_mm=d['t_stock_mm'], t_joint_mm=d['t_joint_mm'], sf_hiker=d['sf_hiker'], sf_hunter_cert=d['sf_hunter_cert'],
                   sf_hunter_strict=d['sf_hunter_strict'], aim_286=d['aim_286'], twist_tip_only_sf=d['twist_tip_only_sf'], twist_tip_joint3d_nmm=d['twist_tip_joint3d_nmm'],
                   twist_tip_peak_tipdist_mm=d['twist_tip_peak_tipdist_mm'], twist_kc_3d=d['twist_kc_3d'], twist_body_sf=d['twist_body_sf'], twist_tipsub_sf_strict=d['twist_tipsub_sf_strict'],
                   twist_body_plus_tip_sf=d['twist_body_plus_tip_sf'], ring_joint_N=d['ring_joint_N'], sf_ring=d['sf_ring'], pry20_N=d['pry20_N'], hand_blade_ratio=d['hand_blade_ratio'],
                   hand_blade_case=d['hand_blade_case'], mass_bare_g=d['mass_g'], mass_carry_g=d['mass_carry_g'], blank_g=d['blank_g'], aes_A=d['aes_A'], aes_H_mm=d['aes_H_mm'], aes_emd=d['aes_emd'],
                   aes_floor_pass=d['aes_floor_pass'], aesthetic_signoff=d['gates']['aesthetic_signoff (human)'], novelty=d['novelty'], novelty_source=d['novelty_source'],
                   blade_min_in=(d['blade_min_mm'] / IN if d['blade_min_mm'] else None), tip_to_heel_mm=d['tip_to_heel_mm'], horizontal_reach_mm=d['horizontal_reach_mm'],
                   sharpened_arc_mm=d['sharpened_arc_mm'], unqualified_regions=' | '.join(UNQUALIFIED), final_edge=d['final_edge'], source_json=d['source_json'], source_mtime=d['source_mtime'], generated_at=gen_at)
        rows.append({k: (NV if row.get(k) is None else row[k]) for k in cols})
    with open(os.path.join(a.out, f"{wave}_paper_data.csv"), 'w', newline='') as fh:
        w = csv.DictWriter(fh, fieldnames=cols); w.writeheader(); w.writerows(rows)
    pack = dict(wave=a.wave, generated_at=gen_at, generator='ops/wave_reports/make_wave_report.py', author='Jepson Taylor', solver_commit=a.solver_commit, load_case_version=LOAD_CASE_VERSION,
                run_label=a.run_label, run_header=hdr, run_history_mtime=(mt(hist_mtime) if hist_mtime else None), sources=dict(d1_dir=a.d1_dir, d1_csv=a.d1_csv, pre_dir=a.pre_dir, prior_pack=a.prior_pack),
                headline=hd, designs=designs, ledger=led, delta=delta, peaks=peaks, sy100_map=sy100, unqualified_regions=UNQUALIFIED, promoted=False,
                overall=(hd['overall'] if hd else NV), break_points=bp, near_misses=near, not_verified_fields=sorted({k for r in rows for k, v in r.items() if v == NV}))
    json.dump(pack, open(os.path.join(a.out, f"{wave}_paper_data.json"), 'w'), indent=1, default=str)
    # ---------------- markdown
    B = lambda s: {PASS: '🟢 **PASS**', FAIL: '🔴 **FAIL**', NV: '⚪ **NOT VERIFIED**'}.get(s, s)
    L = []
    L.append(f"# {title}\n")
    L.append(f"OVERALL: {B(pack['overall'])} — NOT PROMOTED (this tool never promotes; human aesthetic sign-off by Jepson is required for any promotion).  ")
    L.append(f"Generated {gen_at} by `ops/wave_reports/make_wave_report.py`. Rules: CURRENT D1 (`{LOAD_CASE_VERSION}`). Solver: `{a.solver_commit}`.  ")
    if hdr: L.append(f"Source run: {hdr}  ")
    if hist_mtime: L.append(f"Source run history last written {mt(hist_mtime)}.  ")
    L.append(f"Headline design: **{hd['design'] if hd else 'none'}** (best D1 standing in the wave: fewest FAILs, then highest governing joint lateral, then lightest). Badge legend: 🟢 PASS · 🔴 FAIL · ⚪ NOT VERIFIED (missing data is never green).\n")
    if hd:
        L.append("## KPI dashboard (headline design)\n")
        L.append("| KPI | value | gate | status |\n|---|---|---|---|")
        G = hd['gates']
        L.append(f"| Joint lateral (cert / strict 0.0625 / governing) | {fmt(hd['joint_lat_cert'],'{:.1f}')} / {fmt(hd['joint_lat_strict'],'{:.1f}')} / **{fmt(hd['joint_lat_governing'],'{:.1f}')} N** | floor 260 (aim 286 → {'MET' if hd['aim_286'] else 'NOT MET' if hd['aim_286'] is not None else 'NOT VERIFIED'}) | {B(G['joint_lateral_260 (cert AND strict)'])} |")
        L.append(f"| Hiker (cert joint) | {fmt(hd['joint_lat_cert'],'{:.1f}')} N (SF {fmt(hd['sf_hiker'],'{:.3f}')}) | ≥180 | {B(G['hiker_180 (cert)'])} |")
        L.append(f"| Tip-only twist SF @1.82 N·m | {fmt(hd['twist_tip_only_sf'],'{:.3f}')} (cap {fmt(hd['twist_tip_joint3d_nmm'],'{:.0f}')} N·mm, peak {fmt(hd['twist_tip_peak_tipdist_mm'],'{:.1f}')} mm from tip, 3D k {fmt(hd['twist_kc_3d'],'{:.3f}')}) | ≥1.0 | {B(G['twist_tip_only_SF>=1 @1.82'])} |")
        L.append(f"| Body+tip twist SF @1.82 N·m | min(body {fmt(hd['twist_body_sf'],'{:.3f}')}, tip-sub strict {fmt(hd['twist_tipsub_sf_strict'],'{:.3f}')}) = **{fmt(hd['twist_body_plus_tip_sf'],'{:.3f}')}** | ≥1.0 | {B(G['twist_body+tip_SF>=1 @1.82'])} |")
        L.append(f"| Ring pull (joint) @1500 N | {fmt(hd['ring_joint_N'],'{:.0f}')} N (SF {fmt(hd['sf_ring'],'{:.2f}')}) | ≥1500 | {B(G['ring_pull_1500 (joint)'])} |")
        L.append(f"| Hand/blade yield-onset ratio | {fmt(hd['hand_blade_ratio'],'{:.3f}')} ({hd['hand_blade_case'] or 'NOT VERIFIED'}) | ≥1.2 | {B(G['hand/blade_ratio>=1.2'])} |")
        L.append(f"| Aesthetic A / H (C.6 floor, automated) | A {fmt(hd['aes_A'],'{:.3f}')} / H {fmt(hd['aes_H_mm'],'{:.3f}')} mm / EMD {fmt(hd['aes_emd'],'{:.4f}')} | C.6 floor | {B(G['C.6_aesthetic_floor (automated)'])} |")
        L.append(f"| Aesthetic sign-off (human) | — | Jepson | {B(G['aesthetic_signoff (human)'])} |")
        L.append(f"| Mass bare / carry | {fmt(hd['mass_g'],'{:.2f}')} g / {fmt(hd['mass_carry_g'])} | band 74–77 · cap <80 | band {B(G['mass_band_74-77'])} · cap {B(G['mass_cap_<80'])} |")
        L.append(f"| Blade all-three (tip-heel / reach / arc) | {fmt(hd['tip_to_heel_mm'] and hd['tip_to_heel_mm']/IN,'{:.3f}')} / {fmt(hd['horizontal_reach_mm'] and hd['horizontal_reach_mm']/IN,'{:.3f}')} / {fmt(hd['sharpened_arc_mm'] and hd['sharpened_arc_mm']/IN,'{:.3f}')} in | ≥3.375 in | {B(G['blade>=3.375in_all_three'])} |")
        L.append(f"| Hard gates / red-team | rejects {hd['rejects'] if hd['rejects'] is not None else 'NOT VERIFIED'} | none | {B(G['hard_gates/redteam'])} |")
        L.append(f"| Stock / joint t / fitness / SPG | {fmt(hd['t_stock_mm'],'{:.1f}')} mm / {fmt(hd['t_joint_mm'],'{:.2f}')} mm / {fmt(hd['fit'],'{:.4f}')} / {fmt(hd['spg'],'{:.4f}')} N/g | — | info |\n")
        L.append(f"## FEM visuals\n\n![wave{a.wave} FEM metrics]({wave}_FEM_metrics.png)\n")
        L.append("Panels: von Mises for lateral 260 N, chord torsion 1.82 N·m (tip-only + body peaks), ring pull 1500 N; SF envelope (worst case); body+tip twist SF; tip zoom (tip-only); thickness field; gate table. Map SF is σy(100 °C)/σvm at nominal thickness (no thin factor) and is for locating peaks; the gate SFs are the certified JOINT scalars.\n")
        L.append("| case | peak σvm (MPa) | map SF | location (x, y mm) | region |\n|---|---|---|---|---|")
        for k, v in peaks.items(): L.append(f"| {k} | {v['vm']:.0f} | {'-' if v['sf'] is None else f'{v['sf']:.2f}'} | ({v['at'][0]:.1f}, {v['at'][1]:.1f}) | {v['region']} |")
        L.append("")
    L.append("## Break-point summary\n")
    if hd:
        fails = [g for g, s in hd['gates'].items() if s == FAIL]
        L.append(f"- **Failed (headline {hd['design']}):** " + (', '.join(fails) if fails else 'none'))
        nvs = [g for g, s in hd['gates'].items() if s == NV]
        L.append(f"- **Not verified (headline):** " + (', '.join(nvs) if nvs else 'none'))
    L.append(f"- **Near misses (within 5 % above a floor):** " + ('; '.join(f"{a_} {b_} {c_:.3f} vs {d_}" for a_, b_, c_, d_ in near) if near else 'none'))
    cnt = {}
    for dsg, gname in bp: cnt[gname] = cnt.get(gname, 0) + 1
    L.append(f"- **Gate failures across all {len(designs)} D1-screened designs:** " + (', '.join(f"{k} {v}/{len(designs)}" for k, v in sorted(cnt.items(), key=lambda x: -x[1])) if cnt else 'none'))
    if delta:
        L.append(f"- **Strength delta vs prior wave** ({delta.get('_vs')}):")
        for k, v in delta.items():
            if k.startswith('_'): continue
            L.append(f"  - Δ{k}: {'NOT VERIFIED' if v is None else f'{v:+.3f}'}")
    else:
        L.append("- **Strength delta vs prior wave:** NOT VERIFIED (no prior pack / prior source)")
    L.append("")
    L.append("## Weight ledger (headline design)\n")
    if led:
        L.append("| where | g removed |\n|---|---|")
        for k, v in led.items(): L.append(f"| {k} | {'NOT VERIFIED' if v is None else v if isinstance(v, str) else f'{v:.2f}'} |")
        L.append(f"| **blank ({fmt(hd['t_stock_mm'],'{:.1f}')} mm plate outline) → finished** | {fmt(hd['blank_g'],'{:.2f}')} → **{fmt(hd['mass_g'],'{:.2f}')} g** |")
        L.append(f"\nC.6 ring-face racetrack groove volume is not itemised in the plate JSON → NOT VERIFIED as a separate line (it sits inside the residual). Machined volumes are the phenotype raster ledger (`removed_mm3`: {', '.join(NAMES)}).\n")
        if delta.get('_ledger'):
            L.append("Δ vs prior wave headline (g, + = more removed):  ")
            L.append(', '.join(f"{k.split(' (')[0]} {('NV' if v is None else f'{v:+.2f}')}" for k, v in delta['_ledger'].items()))
            L.append(f"  \nagainst ΔSF: hunter(cert) {fmt(delta.get('sf_hunter_cert'),'{:+.3f}')}, tip-only twist {fmt(delta.get('twist_tip_only_sf'),'{:+.3f}')}, body+tip twist {fmt(delta.get('twist_body_plus_tip_sf'),'{:+.3f}')}, governing lat {fmt(delta.get('joint_lat_governing'),'{:+.1f}')} N, Δmass {fmt(delta.get('mass_g'),'{:+.2f}')} g\n")
        elif delta.get('_preD1_removed_g'):
            L.append("Δ machined mass vs prior wave best (PRE-D1 records, g, + = more removed): " + ', '.join(f"{k} {v:+.2f}" for k, v in delta['_preD1_removed_g'].items()) + f", perfs {delta['_preD1_perf_g']:+.2f}  ")
            L.append(f"against pre-D1 ΔSF hunter {delta.get('preD1_sf_hunter', 0):+.3f}, Δlat_rob {delta.get('preD1_lat_rob', 0):+.1f} N, Δmass {delta.get('mass_g', 0):+.2f} g (D1-rule SF delta NOT VERIFIED).\n")
    else:
        L.append("NOT VERIFIED (no machining ledger in the source)\n")
    L.append("## All D1-screened designs in this wave\n")
    L.append("| design | mass g | t | joint lat cert/strict N | tip-only twist | body+tip twist | ring N | hand/blade | band 74–77 | OVERALL |\n|---|---|---|---|---|---|---|---|---|---|")
    for d in designs:
        L.append(f"| {d['design']}{' ★' if d is hd else ''} | {fmt(d['mass_g'],'{:.2f}')} | {fmt(d['t_stock_mm'],'{:.1f}')} | {fmt(d['joint_lat_cert'],'{:.1f}')} / {fmt(d['joint_lat_strict'],'{:.1f}')} | {fmt(d['twist_tip_only_sf'],'{:.2f}')} | {fmt(d['twist_body_plus_tip_sf'],'{:.2f}')} | {fmt(d['ring_joint_N'],'{:.0f}')} | {fmt(d['hand_blade_ratio'],'{:.2f}')} | {d['gates']['mass_band_74-77']} | {B(d['overall'])} |")
    if pre:
        unscreened = sorted(set(pre) - {d['design'] for d in designs})
        if unscreened:
            L.append(f"\nPre-D1 certified designs in this wave **not** re-screened under D1 (all D1 gates ⚪ NOT VERIFIED): {', '.join(unscreened)}.\n")
    L.append("## Paper data SAVE\n")
    L.append(f"- CSV: `{wave}_paper_data.csv` (one row per D1-screened design) · JSON: `{wave}_paper_data.json` (full pack: gates, peaks, ledger, deltas, provenance).")
    if hd:
        L.append(f"- genome_hash `{hd['genome_hash']}` ({hd['genome_precision']}) · geometry_hash `{hd['geometry_hash']}` · solver_commit `{a.solver_commit}`")
        L.append(f"- mesh: search 2.0 mm² · cert min(0.25, 0.125) mm² · strict 0.0625 mm² · plate export {hd['plate_mesh_tris']} tris / {hd['plate_mesh_nodes']} nodes ({hd['plate_mesh_level']})")
        L.append(f"- capacities by mesh: search (pre-D1) {fmt(hd['search_lat_rob_preD1_2mm2'],'{:.1f}')} N · cert pre-D1 880/min {fmt(hd['cert_lat_rob_preD1_880min'],'{:.1f}')} N · cert D1 joint {fmt(hd['joint_lat_cert'],'{:.1f}')} N · strict D1 joint {fmt(hd['joint_lat_strict'],'{:.1f}')} N · 0.25-only / 0.125-only NOT VERIFIED (not exported separately)")
        L.append(f"- joint thin+hot: t_joint {fmt(hd['t_joint_mm'],'{:.2f}')} mm, factor lat_rob/lat20 = {fmt(hd['joint_factor'],'{:.4f}')}")
        L.append(f"- final_edge: {hd['final_edge']} → ⚪ NOT VERIFIED as a machining release")
        L.append(f"- novelty: {fmt(hd['novelty'],'{:.4f}')} ({hd['novelty_source']})")
    L.append(f"- unqualified regions: " + '; '.join(UNQUALIFIED))
    L.append(f"- fields NOT VERIFIED in at least one design row of this wave's CSV: {', '.join(pack['not_verified_fields']) or 'none'}")
    if hd: L.append(f"- headline fields NOT VERIFIED: {', '.join(k for k, v in next(r for r in rows if r['headline'] is True).items() if v == NV) or 'none'}")
    L.append(f"- timestamps: generated {gen_at}; headline source written {hd['source_mtime'] if hd else 'NOT VERIFIED'}\n")
    L.append("## Gates context\nJoint thin+hot 828 MPa; lateral ≥260 (aim 286); mass 74–77 g, cap <80; C.6 aesthetic; blade ≥3.375 in all three; hand/blade ≥1.2; BOTH twist modes @1.82 N·m. **No promotion.** Aesthetic sign-off still required.\n")
    open(os.path.join(a.out, f"{wave}_REPORT.md"), 'w').write('\n'.join(L) + '\n')
    for dst in a.copy_to:
        os.makedirs(dst, exist_ok=True)
        import shutil
        for ext in ('_REPORT.md', '_FEM_metrics.png', '_paper_data.csv', '_paper_data.json'):
            p = os.path.join(a.out, wave + ext)
            if os.path.exists(p): shutil.copy2(p, dst)
    print(json.dumps(dict(wave=a.wave, overall=pack['overall'], headline=hd['design'] if hd else None, n=len(designs), not_verified=pack['not_verified_fields'])))

if __name__ == '__main__':
    main()
