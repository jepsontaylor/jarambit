"""Wave-6 crescent plates (docs/WAVE_FIGURE_TEMPLATE.md layout, crescent lane). Offline plotting only.
Renders ONLY aesthetic-passing designs exported by `jarambit crescent-smoke` (plate JSON).
usage: python3 make_crescent_plate.py <run_dir> <heatmap_dir>"""
import sys, os, json, numpy as np
import matplotlib; matplotlib.use('Agg')
import matplotlib.pyplot as plt, matplotlib.tri as mtri
from matplotlib.patches import Polygon as MPoly

RUN, OUT = sys.argv[1], sys.argv[2]
os.makedirs(OUT, exist_ok=True)
IN = 25.4
evals = json.load(open(os.path.join(RUN, 'all_evals.json')))
labels = [l.strip() for l in open(os.path.join(RUN, 'plates.txt')) if l.strip()]
index = []

def outline(ax, d, c4=True):
    o = np.array(d['outline']); ax.add_patch(MPoly(o, closed=True, fill=False, ec='k', lw=0.6))
    for h in d['holes']: h = np.array(h); ax.add_patch(MPoly(h, closed=True, fill=False, ec='k', lw=0.5))
    if c4:
        c = np.array(d['c4']); ax.plot(np.r_[c[:, 0], c[0, 0]], np.r_[c[:, 1], c[0, 1]], ls='--', lw=0.5, color='#7a3cff', label='SWITCHBACK C.5')
    p = np.array(d['pad']); ax.add_patch(MPoly(p, closed=True, fill=False, ec='#d00', lw=0.7))
    ax.set_aspect('equal'); ax.set_xticks([]); ax.set_yticks([])
    lo = o.min(0) - 4; hi = o.max(0) + 4; ax.set_xlim(lo[0], hi[0]); ax.set_ylim(lo[1], hi[1])

for lab in labels:
    d = json.load(open(os.path.join(RUN, lab + '.json'))); m = d['metrics']
    if not m['aes_pass']:
        continue  # aesthetic passers only
    xy = np.array(d['mesh']['xy']); tri = np.array(d['mesh']['tris'])
    T = mtri.Triangulation(xy[:, 0], xy[:, 1], tri)
    env = np.array(d['mesh']['env_vm'], float); sf = np.array(d['mesh']['sf'], float)
    fig = plt.figure(figsize=(16, 11))
    gs = fig.add_gridspec(3, 2, height_ratios=[1, 1, 1], width_ratios=[2.3, 1.0], hspace=0.30, wspace=0.16, left=0.02, right=0.98, top=0.855, bottom=0.05)
    legal = m['legal']
    title = f"Wave 6 — crescent [{lab}] | Fitness {m['fit']:.3f} (SPG×A×(1+N)) | SPG {m['spg']:.3f} N/g | Est. weight {m['mass_g']:.1f} g" + ("" if legal else "  (NOT LEGAL — reference only)")
    fig.suptitle(title, fontsize=14, fontweight='bold', y=0.985)
    fig.text(0.5, 0.952, "Detailed plate FEM (physics::fine DKT bending + T6 membrane) with per-element thickness field (taper, grinds, relief, lattice, fuller, flutes, texture). "
             "Capacities CERTIFIED = min over 0.25 / 0.125 mm² meshes; robust = min(20 °C at −0.1 mm stock, 100 °C yield)", ha='center', fontsize=8.5)
    bl = min(m['tip_to_heel'], m['horizontal_reach'], max(m['arc_in'], m['arc_sp']))
    badges = [("AESTHETIC FLOOR: PASS\nH %.2f mm · EMD %.3f · A %.3f" % (m['hausdorff'], m['emd'], m['aes_score']), '#2a7'),
              ("BLADE ≥ 3.375 in on all three: %s\nmin %.3f in" % ('PASS' if bl >= 86.225 else 'FAIL', bl / IN), '#2a7' if bl >= 86.225 else '#c22'),
              ("HARD GATES: %s" % ('PASS' if not m['rejects'] else 'FAIL\n' + '; '.join(m['rejects'])[:60]), '#2a7' if not m['rejects'] else '#c22'),
              ("FLOORS 180 / 260 / 1500 N (certified): %s\nlat %.0f N · ring %.0f N" % ('PASS' if m['floors_ok'] else 'FAIL', m['lat_rob'], m['ring_rob']), '#2a7' if m['floors_ok'] else '#c22'),
              ("NOVELTY %.3f\n(k-NN, aesthetic passers only)" % m['novelty'], '#36c')]
    for i, (t, c) in enumerate(badges):
        fig.text(0.03 + i * 0.19 + 0.085, 0.912, t, fontsize=8, color='white', ha='center', va='center', bbox=dict(boxstyle='round,pad=0.35', fc=c, ec='none'))
    ax1 = fig.add_subplot(gs[0, 0]); vmax = np.nanpercentile(env[env > 0], 99.5) if (env > 0).any() else 1
    tp = ax1.tripcolor(T, facecolors=env, cmap='turbo', vmin=0, vmax=vmax, rasterized=True); outline(ax1, d)
    fig.colorbar(tp, ax=ax1, fraction=0.025, pad=0.005, label='σvm envelope at design loads (MPa)')
    ax1.set_title('von Mises envelope at design loads: lateral 260 N, pry 260 N, twist 1.26 N·m, ring pull 1500 N (4 mm tip-load zone excluded)', fontsize=9); ax1.legend(loc='lower left', fontsize=7)
    ax2 = fig.add_subplot(gs[1, 0])
    tp2 = ax2.tripcolor(T, facecolors=np.clip(sf, 0, 4), cmap='RdYlGn', vmin=0, vmax=4, rasterized=True); outline(ax2, d, c4=False)
    k = int(np.argmin(sf)); c = xy[tri[k]].mean(0); ax2.plot(*c, 'kx', ms=10, mew=2)
    fig.colorbar(tp2, ax=ax2, fraction=0.025, pad=0.005, label='SF = σy(100 °C) / σvm envelope')
    sy100 = np.where(env > 0, sf * env, np.nan); sy100 = np.nanmedian(sy100) if np.isfinite(sy100).any() else 0
    excl = env <= 0
    def case_sf(key, load):
        v = np.array(d['mesh'][key], float) * load; v[excl] = 0
        return sy100 / v.max() if v.max() > 0 else np.inf
    cs = dict(lateral=case_sf('lat', 260), pry=case_sf('pry', 260), ring=case_sf('ring', 1500), twist=case_sf('twist', 1260))
    ax2.set_title(f"safety factor at 100 °C, envelope of all four cases (min {sf.min():.2f} at x={c[0]:.0f}, y={c[1]:.0f} mm)\n"
                  f"per case: lateral 260 N {cs['lateral']:.2f} · pry 260 N {cs['pry']:.2f} · ring 1500 N {cs['ring']:.2f} · twist 1.26 N·m {cs['twist']:.2f} (advisory proxy, no floor)", fontsize=8.5)
    m['_case_sf'] = cs
    ax3 = fig.add_subplot(gs[2, 0]); f = d['field']; th = np.array(f['th'], float).reshape(f['ny'], f['nx'])
    im = ax3.imshow(th, origin='lower', extent=[f['x0'], f['x0'] + f['nx'] * f['g'], f['y0'], f['y0'] + f['ny'] * f['g']], cmap='viridis', interpolation='nearest')
    outline(ax3, d, c4=False); fig.colorbar(im, ax=ax3, fraction=0.02, pad=0.01, label='finished thickness (mm)')
    rm = m['removed_mm3']
    ax3.set_title(f"thickness field from {m['t']:.1f} mm stock (6.35 mm plate): removed relief {rm[0]:.0f} / lattice {rm[1]:.0f} / fuller {rm[2]:.0f} / flutes {rm[3]:.0f} / texture {rm[4]:.0f} mm³; min web {m['min_web']:.2f} mm", fontsize=8)
    ax4 = fig.add_subplot(gs[0, 1]); ax4.axis('off')
    rows = [("tip→heel", f"{m['tip_to_heel']/IN:.3f} in ({m['tip_to_heel']:.1f})"), ("horizontal reach", f"{m['horizontal_reach']/IN:.3f} in ({m['horizontal_reach']:.1f})"),
            ("edge arc inside / spine", f"{m['arc_in']/IN:.3f} / {m['arc_sp']/IN:.3f} in"), ("grip / stock / Ti", f"{m['grip']:.1f} mm / {m['t']:.1f} mm / {m['material']}"),
            ("weight (finished / blank)", f"{m['mass_g']:.1f} g / {m['blank_g']:.1f} g"), ("lateral 20 °C / robust", f"{m['lat20']:.0f} / {m['lat_rob']:.0f} N"),
            ("SF hiker 180 / hunter 260", f"{m['sf_hiker']:.2f} / {m['sf_hunter']:.2f}"), ("ring pull 20 °C / robust (SF)", f"{m['ring20']:.0f} / {m['ring_rob']:.0f} N ({m['sf_ring']:.1f})"),
            ("tip pry 20 °C / twist 20 °C", f"{m['pry20']:.0f} N / {m['twist20_nmm']/1000:.2f} N·m"),
            ("SF 100 °C lat / pry / ring / twist*", " / ".join(f"{m['_case_sf'][k]:.2f}" for k in ('lateral', 'pry', 'ring', 'twist'))), ("governing lateral at", f"({m['lat_at'][0]:.0f}, {m['lat_at'][1]:.0f}) mm"),
            ("holder box (oriented)", f"{m['holder_box'][0]:.1f} × {m['holder_box'][1]:.1f} mm @ {m['holder_box'][2]:.1f}°"),
            ("aesthetic A / H / EMD", f"{m['aes_score']:.3f} / {m['hausdorff']:.2f} mm / {m['emd']:.3f}"), ("straight run / min blend R", f"{m['straight_mm']:.1f} / {m['min_blend_r']:.1f} mm"),
            ("novelty / SPG", f"{m['novelty']:.3f} / {m['spg']:.3f} N/g")]
    tb = ax4.table(cellText=[[a, b] for a, b in rows], colWidths=[0.5, 0.5], loc='center', fontsize=7.5); tb.auto_set_font_size(False); tb.set_fontsize(8); tb.scale(1, 1.25)
    ax5 = fig.add_subplot(gs[1:, 1])
    P = [e for e in evals if e['aes_pass']]
    rel = lambda e: sum(e['removed_mm3'][:4]) / max(e['blank_g'] / 4.43 * 1000, 1)
    xs = [rel(e) for e in P]; ys = [e['hausdorff'] for e in P]; cs = [e['spg'] if e['legal'] else np.nan for e in P]
    ax5.scatter([rel(e) for e in evals if not e['aes_pass']][:2000], [e['hausdorff'] for e in evals if not e['aes_pass']][:2000], s=4, c='#ccc', label='aesthetic floor FAIL')
    sc = ax5.scatter(xs, ys, s=7, c=[0 if np.isnan(v) else v for v in cs], cmap='plasma', label='aesthetic passers (colour = SPG if LEGAL)')
    ax5.scatter([rel(m)], [m['hausdorff']], marker='*', s=220, c='lime', ec='k', zorder=5, label='this design')
    ax5.axhline(6.0, color='r', lw=0.8, ls='--'); ax5.text(0.0, 6.1, 'Hausdorff floor 6 mm vs C.4', fontsize=7, color='r')
    [ax5.axvline(b, color='#999', lw=0.4, ls=':') for b in (0.005, 0.01, 0.015, 0.02, 0.03, 0.045, 0.065)]
    ax5.set_xlabel('3-D feature volume removed / blank volume (QD relief bins dotted)'); ax5.set_ylabel('Hausdorff to C.4 (mm)'); ax5.set_ylim(0, max(12, max(ys + [0]) + 1)); ax5.legend(fontsize=6.5, loc='upper right')
    ax5.set_title('novelty / QD map (all evaluations of the smoke run)', fontsize=8.5)
    fig.text(0.5, 0.008, f"source {RUN} | author Jepson Taylor | generator ops/wave_figures/make_crescent_plate.py | utility / hiking karambit only", ha='center', fontsize=7)
    tag = f"SPG{m['spg']:.2f}" if legal else "NOTLEGAL"
    base = os.path.join(OUT, f"wave6_{lab}_{tag}_wgt{m['mass_g']:.1f}g".replace('.', 'p') + "_FEM_metrics")
    fig.savefig(base + '.png', dpi=320); fig.savefig(base + '.pdf'); plt.close(fig)
    index.append(dict(label=lab, file=os.path.basename(base) + '.png', case_sf_100C=m['_case_sf'], **{k: m[k] for k in ('fit', 'spg', 'mass_g', 'aes_score', 'hausdorff', 'emd', 'novelty', 'sf_hiker', 'sf_hunter', 'sf_ring', 'floors_ok', 'legal', 'tip_to_heel', 'horizontal_reach', 'arc_in', 'arc_sp', 't')}))
    print('wrote', base + '.png')
json.dump(index, open(os.path.join(OUT, 'crescent_index.json'), 'w'), indent=1)
