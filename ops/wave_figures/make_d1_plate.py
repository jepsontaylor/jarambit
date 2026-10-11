"""D1-rule crescent plates (exec/d1): CURRENT rules — 828 MPa screening yield, JOINT thin+hot, certification
min(0.25, 0.125 mm^2) + strict 0.0625 mm^2, failure-sequence proxy >= 1.2, twist reported BOTH ways
(tip-only 1.82 N*m = default hard evaluation; body + tip submodel). Failures are plated and labelled, not hidden.
Renders plate JSONs written by `jarambit crescent-d1` (D1_PLATES=1) or `crescent-evolve` (P1, wave17+).
usage: python3 make_d1_plate.py <json_dir> <heatmap_dir> <wave_tag> [mass_target_g=80]
env EVALS=<all_evals.json> for the Pareto/QD insets (search level of the ORIGINAL run); ANCHOR_REV (C.6)."""
import sys, os, json, numpy as np
import matplotlib; matplotlib.use('Agg')
import matplotlib.pyplot as plt, matplotlib.tri as mtri
from matplotlib.patches import Polygon as MPoly

RUN, OUT, WAVE = sys.argv[1], sys.argv[2], sys.argv[3]
CAP = float(sys.argv[4]) if len(sys.argv) > 4 else 80.0
REV = os.environ.get("ANCHOR_REV", "C.6")  # aesthetic anchor rev shown on the plate (C.6 from wave13)
os.makedirs(OUT, exist_ok=True)
IN = 25.4
EV = os.environ.get('EVALS', os.path.join(RUN, 'all_evals.json'))
evals = json.load(open(EV)) if os.path.exists(EV) else []
labels = [l.strip() for l in open(os.path.join(RUN, 'plates.txt')) if l.strip()]
PREF = os.environ.get('PREFIX', ''); labels = [l for l in labels if l.startswith(PREF)]
cert = {}
cp = os.path.join(RUN, 'certification.csv')
if os.path.exists(cp):
    import csv
    for r in csv.DictReader(open(cp)): cert[int(r['id'])] = r
index = []
RHO = {'Ti-6Al-4V': 4.43, 'Ti-3Al-2.5V': 4.48}
NAMES = ['relief', 'lattice', 'fuller', 'flutes', 'texture', 'isogrid', 'ring flute']

def relief(e):
    blank = max(e['blank_g'] / RHO.get(e.get('material', 'Ti-6Al-4V'), 4.43) * 1000, 1)
    return (sum(e['removed_mm3']) + e.get('win_area', 0.0) * e['t']) / blank

def outline(ax, d, c4=True):
    o = np.array(d['outline']); ax.add_patch(MPoly(o, closed=True, fill=False, ec='k', lw=0.6))
    for h, nm in zip(d['holes'], d['hole_names']):
        h = np.array(h); ax.add_patch(MPoly(h, closed=True, fill=False, ec='#06c' if nm == 'window' else 'k', lw=0.7 if nm == 'window' else 0.5))
    if c4:
        c = np.array(d['c4']); ax.plot(np.r_[c[:, 0], c[0, 0]], np.r_[c[:, 1], c[0, 1]], ls='--', lw=0.5, color='#7a3cff', label='SWITCHBACK ' + REV)
    p = np.array(d['pad']); ax.add_patch(MPoly(p, closed=True, fill=False, ec='#d00', lw=0.7))
    ax.set_aspect('equal'); ax.set_xticks([]); ax.set_yticks([])
    lo = o.min(0) - 4; hi = o.max(0) + 4; ax.set_xlim(lo[0], hi[0]); ax.set_ylim(lo[1], hi[1])

P_all = [e for e in evals if e['aes_pass']]
legal = [e for e in P_all if e['legal']]
for lab in labels:
    d = json.load(open(os.path.join(RUN, lab + '.json'))); m = d['metrics']
    x = d.get('d1', {}) or {}
    xy = np.array(d['mesh']['xy']); tri = np.array(d['mesh']['tris'])
    T = mtri.Triangulation(xy[:, 0], xy[:, 1], tri)
    env = np.array(d['mesh']['env_vm'], float); sf = np.array(d['mesh']['sf'], float)
    fig = plt.figure(figsize=(17, 11.5))
    gs = fig.add_gridspec(3, 3, height_ratios=[1, 1, 1], width_ratios=[2.3, 0.62, 0.62], hspace=0.34, wspace=0.22, left=0.02, right=0.985, top=0.855, bottom=0.05)
    lg = m['legal']; under = m['mass_g'] < CAP
    strict = x.get('strict_lat_rob_0p0625', float('nan')); s_ok = strict >= 260
    seq_ok = m['seq_ratio'] >= 1.2; p828 = m['floors_ok'] and s_ok
    pall = p828 and seq_ok and m['aes_pass'] and not m['rejects']
    tzs = x.get('twist_tipzone_sf_strict', float('nan')); tw_ok = m['twist_body_sf'] >= 1 and tzs >= 1
    band = 74.0 <= m['mass_g'] <= 77.0
    prom = pall and tw_ok and band and m['mass_g'] < 80
    title = f"{WAVE.replace('wave', 'Wave ')} [{lab}] — D1 RULES (828 MPa joint) — {'PROMOTE-ELIGIBLE' if prom else 'NOT ELIGIBLE'} (828+strict+seq {'PASS' if pall else 'FAIL'}, twist {'PASS' if tw_ok else 'FAIL'}, 74–77 g {'yes' if band else 'no'}) | SPG(cert) {m['spg']:.3f} N/g | {m['mass_g']:.1f} g | NOT PROMOTED: needs human aesthetic sign-off"
    fig.suptitle(title, fontsize=9.5, fontweight='bold', y=0.985)
    fig.text(0.5, 0.952, "Detailed plate FEM (physics::fine DKT bending + T6 membrane), per-element thickness (taper, grinds, isogrid pockets, ring flute, relief, flutes); through-windows meshed as holes. "
             "Ti-6Al-4V screening yield 828 MPa (provisional). CERTIFIED = min over 0.25 / 0.125 mm², no bias; robust = JOINT (t−0.1)² × σy(100 °C)/σy(20 °C); strict check 0.0625 mm²", ha='center', fontsize=8.2)
    bl = min(m['tip_to_heel'], m['horizontal_reach'], max(m['arc_in'], m['arc_sp']))
    badges = [("AESTHETIC FLOOR (" + REV + "): PASS\nH %.2f mm · EMD %.3f · A %.3f" % (m['hausdorff'], m['emd'], m['aes_score']), '#2a7'),
              ("BLADE ≥ 3.375 in all three: %s\nmin %.3f in" % ('PASS' if bl >= 86.225 else 'FAIL', bl / IN), '#2a7' if bl >= 86.225 else '#c22'),
              ("HARD GATES + MFG: %s" % ('PASS' if not m['rejects'] else 'FAIL\n' + '; '.join(m['rejects'])[:60]), '#2a7' if not m['rejects'] else '#c22'),
              ("828 JOINT 180/260/1500 + strict: %s\ncert lat %.0f · strict %.0f · ring %.0f N" % ('PASS' if p828 else 'FAIL', m['lat_rob'], strict, m['ring_rob']), '#2a7' if p828 else '#c22'),
              ("FAILURE SEQ ≥ 1.2: %s\n%.2f (%s)" % ('PASS' if seq_ok else 'FAIL', m['seq_ratio'], m['seq_case']), '#2a7' if seq_ok else '#c22'),
              ("TWIST 1.82 N·m body AND tip-sub (LOCKED): %s\nbody %.2f · tip-sub %.2f · tip-only %.2f" % ('PASS' if tw_ok else 'FAIL', m['twist_body_sf'], tzs, m['twist_tip_sf']), '#2a7' if tw_ok else '#c22')]
    for i, (t, c) in enumerate(badges):
        fig.text(0.02 + i * 0.163 + 0.078, 0.912, t, fontsize=7, color='white', ha='center', va='center', bbox=dict(boxstyle='round,pad=0.35', fc=c, ec='none'))
    ax1 = fig.add_subplot(gs[0, 0]); vmax = np.nanpercentile(env[env > 0], 99.5) if (env > 0).any() else 1
    tp = ax1.tripcolor(T, facecolors=env, cmap='turbo', vmin=0, vmax=vmax, rasterized=True); outline(ax1, d)
    fig.colorbar(tp, ax=ax1, fraction=0.025, pad=0.005, label='σvm envelope at design loads (MPa)')
    ax1.set_title('von Mises envelope at design loads (828 MPa rules): lateral 260 N, pry 260 N, chord torsion 1.82 N·m × St-Venant 3D, ring pull 1500 N (4 mm tip-load zone excluded)', fontsize=9); ax1.legend(loc='lower left', fontsize=7)
    ax2 = fig.add_subplot(gs[1, 0])
    tp2 = ax2.tripcolor(T, facecolors=np.clip(sf, 0, 4), cmap='RdYlGn', vmin=0, vmax=4, rasterized=True); outline(ax2, d, c4=False)
    k = int(np.argmin(sf)); c = xy[tri[k]].mean(0); ax2.plot(*c, 'kx', ms=10, mew=2)
    fig.colorbar(tp2, ax=ax2, fraction=0.025, pad=0.005, label='SF = σy(100 °C) / σvm envelope')
    sy100 = np.where(env > 0, sf * env, np.nan); sy100 = np.nanmedian(sy100) if np.isfinite(sy100).any() else 0
    excl = env <= 0
    def case_sf(key, load):
        v = np.array(d['mesh'][key], float) * load; v[excl] = 0
        return sy100 / v.max() if v.max() > 0 else np.inf
    cs = dict(lateral=case_sf('lat', 260), pry=case_sf('pry', 260), ring=case_sf('ring', 1500), twist=m['twist_tip_sf'])
    ax2.set_title(f"safety factor at 100 °C, envelope of all four cases (min {sf.min():.2f} at x={c[0]:.0f}, y={c[1]:.0f} mm)\n"
                  f"per case: lateral 260 N {cs['lateral']:.2f} · pry 260 N {cs['pry']:.2f} · ring 1500 N {cs['ring']:.2f} · chord torsion 1.82 N·m tip-only {m['twist_tip_sf']:.2f} / body {m['twist_body_sf']:.2f} (floor LOCKED = body AND tip-sub)", fontsize=8.5)
    m['_case_sf'] = cs
    ax3 = fig.add_subplot(gs[2, 0]); f = d['field']; th = np.array(f['th'], float).reshape(f['ny'], f['nx'])
    im = ax3.imshow(th, origin='lower', extent=[f['x0'], f['x0'] + f['nx'] * f['g'], f['y0'], f['y0'] + f['ny'] * f['g']], cmap='viridis', interpolation='nearest')
    outline(ax3, d, c4=False); fig.colorbar(im, ax=ax3, fraction=0.02, pad=0.01, label='finished thickness (mm)')
    rm = m['removed_mm3']; nwin = sum(1 for n in d['hole_names'] if n == 'window')
    parts = " / ".join(f"{NAMES[i]} {rm[i]:.0f}" for i in range(min(len(rm), len(NAMES))) if rm[i] > 0.5)
    ax3.set_title(f"thickness field, {m['t']:.1f} mm finished from 6.35 mm plate — machined mm³: {parts or 'none'}; through-windows {nwin} (blue); min web {m['min_web']:.2f} mm", fontsize=8)
    ax4 = fig.add_subplot(gs[0, 1:]); ax4.axis('off')
    cr = cert.get(m['id'], {})
    rows = [("tip→heel / reach", f"{m['tip_to_heel']/IN:.3f} / {m['horizontal_reach']/IN:.3f} in"),
            ("edge arc inside / spine", f"{m['arc_in']/IN:.3f} / {m['arc_sp']/IN:.3f} in"), ("grip / stock / Ti", f"{m['grip']:.1f} mm / {m['t']:.1f} mm / {m['material']}"),
            ("weight (finished / blank)", f"{m['mass_g']:.1f} g / {m['blank_g']:.1f} g"), ("lateral 20 °C / robust (cert)", f"{m['lat20']:.0f} / {m['lat_rob']:.0f} N"),
            ("SF hiker 180 / hunter 260", f"{m['sf_hiker']:.2f} / {m['sf_hunter']:.2f}"), ("ring pull robust (SF)", f"{m['ring_rob']:.0f} N ({m['sf_ring']:.1f})"),
            ("SF 100 °C lat/pry/ring", " / ".join(f"{m['_case_sf'][k]:.2f}" for k in ('lateral', 'pry', 'ring'))),
            ("strict 0.0625 joint lat (SF hunter)", f"{strict:.0f} N ({strict/260:.3f})"), ("hunter aim 286 N", 'yes' if min(m['lat_rob'], strict) >= 286 else 'no'),
            ("twist tip-only / body / tip-sub SF", f"{m['twist_tip_sf']:.2f} / {m['twist_body_sf']:.2f} / {x.get('twist_tipzone_sf_strict', float('nan')):.2f}"),
            ("tip peak dist / seq ratio", f"{m['twist_tip_peak_tipdist']:.1f} mm / {m['seq_ratio']:.2f} ({m['seq_case']})"),
            ("P1 rails / neck / pocket / knots", (f"{m['rail_w']:.1f} / {m['neck_l']:.1f} / {m['pocket_d']:.2f}@R{m['pocket_r']:.1f} / " + ",".join(f"{k:.2f}" for k in m['knots'])) if m.get('p1') else 'P0 layout (perfs/isogrid allowed)'),
            ("pre-D1 880/min lateral", f"{x.get('old_lat_rob_880_min', float('nan')):.0f} N"),
            ("governing lateral at", f"({m['lat_at'][0]:.0f}, {m['lat_at'][1]:.0f}) mm"),
            ("holder box (oriented)", f"{m['holder_box'][0]:.1f} × {m['holder_box'][1]:.1f} mm @ {m['holder_box'][2]:.1f}°"),
            ("aesthetic A / H / EMD", f"{m['aes_score']:.3f} / {m['hausdorff']:.2f} mm / {m['emd']:.3f}"),
            ("machined fraction / windows", f"{relief(m):.3f} / {nwin}"), ("novelty / SPG (cert)", f"{m['novelty']:.3f} / {m['spg']:.3f} N/g")]
    tb = ax4.table(cellText=[[a, b] for a, b in rows], colWidths=[0.5, 0.5], loc='center'); tb.auto_set_font_size(False); tb.set_fontsize(6.6); tb.scale(1, 1.0)
    # ---- Pareto inset: mass vs robust lateral (search level) over LEGAL designs ----
    ax5 = fig.add_subplot(gs[1, 1:])
    mx = np.array([e['mass_g'] for e in legal]); ly = np.array([e['lat_rob'] for e in legal]); nv = np.array([e['novelty'] for e in legal])
    ax5.scatter([e['mass_g'] for e in P_all if not e['legal'] and e['lat_rob'] > 0][:4000], [e['lat_rob'] for e in P_all if not e['legal'] and e['lat_rob'] > 0][:4000], s=3, c='#ccc', label='aesthetic passers, floors/gates FAIL')
    sc = ax5.scatter(mx, ly, s=6, c=nv, cmap='viridis', label='LEGAL (search level), colour = novelty')
    # non-dominated front: min mass, max lateral
    o = np.argsort(mx); best = -1; fr = []
    for i in o:
        if ly[i] > best: fr.append(i); best = ly[i]
    if fr: ax5.plot(mx[fr], ly[fr], 'r-', lw=1.0, label='Pareto front (mass↓, lateral↑)')
    ax5.scatter([m['mass_g']], [m['lat_rob']], marker='*', s=240, c='lime', ec='k', zorder=5, label='this design (D1 certified, 828 joint)')
    ax5.axvline(CAP, color='#c80', ls='--', lw=0.9); ax5.axhline(260, color='r', ls=':', lw=0.9)
    ax5.text(CAP + 0.1, ax5.get_ylim()[0] if False else 262, f'{CAP:.0f} g target', fontsize=7, color='#c80'); ax5.text(min(mx.min() if len(mx) else 75, 75), 262, 'hunter 260 N', fontsize=7, color='r')
    xs = np.linspace(70, 92, 10)
    for s in (3.0, 3.5, 4.0): ax5.plot(xs, s * xs, color='#999', lw=0.4, ls='-.'); ax5.text(xs[-1], s * xs[-1], f'{s} N/g', fontsize=6, color='#777')
    ax5.set_xlim(66, 92); ax5.set_ylim(200, max(380, (ly.max() + 10) if len(ly) else 380))
    ax5.set_xlabel('finished mass (g)', fontsize=8); ax5.set_ylabel('robust lateral (N, search level)', fontsize=8); ax5.tick_params(labelsize=7)
    ax5.legend(fontsize=6, loc='upper left'); ax5.set_title('Pareto inset: mass vs robust lateral (LEGAL evaluations of the source run, its own search rules)', fontsize=8.5)
    # ---- QD map ----
    ax6 = fig.add_subplot(gs[2, 1:])
    rx = [relief(e) for e in P_all]; my = [e['mass_g'] for e in P_all]; cc = [e['spg'] if e['legal'] else np.nan for e in P_all]
    ax6.scatter([relief(e) for e in evals if not e['aes_pass']][:3000], [e['mass_g'] for e in evals if not e['aes_pass']][:3000], s=3, c='#e3e3e3', label='aesthetic floor FAIL')
    ax6.scatter(rx, my, s=5, c=[0 if np.isnan(v) else v for v in cc], cmap='plasma', label='aesthetic passers (colour = SPG if LEGAL)')
    ax6.scatter([relief(m)], [m['mass_g']], marker='*', s=240, c='lime', ec='k', zorder=5, label='this design')
    ax6.axhline(CAP, color='#c80', ls='--', lw=0.9)
    [ax6.axvline(b, color='#999', lw=0.4, ls=':') for b in (0.005, 0.01, 0.02, 0.03, 0.045, 0.065, 0.09, 0.12, 0.16, 0.21)]
    ax6.set_xlabel('machined volume / blank volume (QD bins dotted)', fontsize=8); ax6.set_ylabel('finished mass (g)', fontsize=8); ax6.tick_params(labelsize=7)
    ax6.set_ylim(66, 95); ax6.legend(fontsize=6, loc='upper right'); ax6.set_title('QD map: machining fraction × mass (MAP-Elites axes)', fontsize=8.5)
    fig.text(0.5, 0.008, f"source {RUN} | author Jepson Taylor | generator ops/wave_figures/make_d1_plate.py (D1 rules) | utility / hiking karambit only", ha='center', fontsize=7)
    tag = ("D1ELIGIBLE" if prom else "D1FAIL") + f"_SPG{m['spg']:.2f}"
    base = os.path.join(OUT, f"{WAVE}_{lab.replace(WAVE + '_', '').replace('_D1', '')}_{tag}_wgt{m['mass_g']:.1f}g".replace('.', 'p') + "_D1_FEM_metrics")
    fig.savefig(base + '.png', dpi=220); fig.savefig(base + '.pdf'); plt.close(fig)
    index.append(dict(label=lab, file=os.path.basename(base) + '.png', case_sf_100C=m['_case_sf'], relief_frac=relief(m), n_win=nwin, d1=x, d1_pass=pall, twist_floor_ok=tw_ok, promote_eligible=prom,
                      **{k: m[k] for k in ('id', 'fit', 'spg', 'mass_g', 'aes_score', 'hausdorff', 'emd', 'novelty', 'sf_hiker', 'sf_hunter', 'sf_ring', 'floors_ok', 'legal', 'tip_to_heel', 'horizontal_reach', 'arc_in', 'arc_sp', 't', 'lat_rob', 'ring_rob', 'seq_ratio', 'twist_tip_sf', 'twist_body_sf', 't_joint')}))
    print('wrote', base + '.png')
json.dump(index, open(os.path.join(OUT, f'{WAVE}_D1_index.json'), 'w'), indent=1)
