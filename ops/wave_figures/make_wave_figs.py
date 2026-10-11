"""Per-wave FEM metrics plates (docs/WAVE_FIGURE_TEMPLATE.md). Offline plotting only."""
import sys, os, re, csv, json, numpy as np
sys.path.insert(0, os.path.dirname(__file__))
import plate_fem as pf
import matplotlib; matplotlib.use('Agg')
import matplotlib.pyplot as plt, matplotlib.tri as mtri
from matplotlib.patches import Polygon as MPoly

ROOT = sys.argv[1] if len(sys.argv) > 1 else '/workspace/wf'
OUT = os.path.join(ROOT, 'out/mh1/heatmaps')
IN2MM = 25.4; LIMIT = 3.375 * IN2MM
FLOORS = dict(hiker=180.0, hunter=260.0, ring=1500.0)
TWIST_NMM = 180.0 * 7.0          # hiker load x half blade height (proxy, not a floor)
TEMPS = (-10.0, 20.0, 100.0)

def num(pat, txt, default=float('nan')):
    m = re.search(pat, txt); return float(m.group(1)) if m else default

def read_report(d):
    t = open(os.path.join(d, 'best_report.md')).read()
    r = dict(txt=t)
    r['redteam_ok'] = 'redteam: Ok' in t
    r['material'] = re.search(r'material: (\S+)', t).group(1)
    r['t'] = num(r'thickness: ([\d.]+)', t); r['mass'] = num(r'mass: ([\d.]+)', t)
    r['fit'] = num(r'MC p05 (-?[\d.]+)', t)
    if np.isnan(r['fit']): r['fit'] = num(r'robust plate (-?[\d.]+) N/g', t); r['fit_kind'] = 'robust plate N/g (FEM-in-loop)'
    else: r['fit_kind'] = 'MC p05 strength-per-gram'
    r['surr'] = num(r'(?:governing strength|beam surrogate): ([\d.]+)', t)
    r['tth'] = num(r'tip_to_heel ([\d.]+)', t); r['reach'] = num(r'horizontal_reach ([\d.]+)', t)
    r['arc'] = num(r'sharpened_arc ([\d.]+)', t); r['grip'] = num(r'grip \(ring-neck to guard\): ([\d.]+)', t)
    r['ring_id'] = num(r'ring ID: ([\d.]+)', t); r['ricasso'] = num(r'ricasso land ([\d.]+)', t)
    r['repo_plate'] = num(r'plate FEM: lateral ([\d.]+)', t)
    return r

def serr_depths(d, mass):
    try:
        rows = list(csv.DictReader(open(os.path.join(d, 'history.csv'))))
        rows = [x for x in rows if x.get('serr_in_depth')]
        best = min(rows, key=lambda x: abs(float(x.get('best_mass_g', 0) or 0) - mass))
        return float(best['serr_in_depth']), float(best['serr_out_depth']), True
    except Exception:
        return 1.0, 1.0, False

def analyse(d):
    r = read_report(d)
    outer, hole = pf.parse_svg(os.path.join(d, 'best.svg'))
    xy, tri, on_hole, on_outer = pf.mesh(outer, hole, 0.6)
    P = pf.Plate2(xy, tri, r['t'], r['material']); tri = P.tri
    n = len(xy); cen = xy[tri].mean(1)
    si, so, ok = serr_depths(d, r['mass']); r['serr'] = (si, so, ok)
    he = max(pf.BLADE_H - si - so, 1.0); lat_k = pf.BLADE_H / he; in_k = lat_k ** 2
    blade = cen[:, 1] >= -0.5
    tip = np.argmax(np.where(on_outer, xy[:, 1], -1e9)); tp = xy[tip]
    near_tip = np.hypot(*(xy - tp).T) <= 2.0
    near_tip &= on_outer | (np.hypot(*(xy - tp).T) <= 1.0)
    ric = (xy[:, 1] <= 0.8) & (xy[:, 1] >= -r['ricasso'] - 0.8)
    hc = xy[ric].mean(0); dvec = (tp - hc) / np.linalg.norm(tp - hc); nvec = np.array([-dvec[1], dvec[0]])
    excl = np.hypot(*(cen - tp).T) < 4.0       # St-Venant zone at the load patch
    k = near_tip.sum()
    def F(fn):
        f = np.zeros(n * 5)
        for i in np.where(near_tip)[0]: fn(f, i)
        return f
    lc = {}
    # 1 tip lateral (out-of-plane), ring clamped — per 1 N
    u = P.solve(on_hole, F(lambda f, i: f.__setitem__(i*5+2, 1.0/k)))
    sm, sb = P.stresses(u); lc['lateral'] = np.where(blade, sb * lat_k, sb)
    # 2 twist about tip chord axis: generalized moment on (dw/dx, dw/dy) along n — per 1 N·mm
    def tw(f, i): f[i*5+3] += nvec[0]/k; f[i*5+4] += nvec[1]/k
    u = P.solve(on_hole, F(tw)); sm, sb = P.stresses(u); lc['twist'] = np.where(blade, sb * lat_k, sb)
    # 3 tip pry: in-plane, perpendicular to chord — per 1 N
    def pr(f, i): f[i*5] += nvec[0]/k; f[i*5+1] += nvec[1]/k
    u = P.solve(on_hole, F(pr)); sm, sb = P.stresses(u); lc['pry'] = np.where(blade, sm * in_k, sm)
    # 4 ring pull: ricasso seated, ring-hole nodes pulled -y — per 1 N
    f = np.zeros(n*5); hn = np.where(on_hole)[0]; f[hn*5+1] = -1.0/len(hn)
    u = P.solve(ric, f); sm, sb = P.stresses(u); lc['ring'] = sm
    loads = dict(lateral=FLOORS['hunter'], twist=TWIST_NMM, pry=FLOORS['hunter'], ring=FLOORS['ring'])
    vm_at = {kk: lc[kk] * loads[kk] for kk in lc}
    stack = np.vstack([vm_at[kk] for kk in ('lateral', 'twist', 'pry', 'ring')])
    env = stack.max(0); gov = stack.argmax(0)
    peak = {kk: lc[kk][~excl].max() for kk in lc}
    caps = {T: {kk: pf.yield_at(r['material'], T) / peak[kk] for kk in lc} for T in TEMPS}
    sy100 = pf.yield_at(r['material'], 100.0)
    sf = sy100 / np.maximum(env, 1e-9)
    area = abs(np.sum(outer[:,0]*np.roll(outer[:,1],-1)-np.roll(outer[:,0],-1)*outer[:,1]))/2 - abs(np.sum(hole[:,0]*np.roll(hole[:,1],-1)-np.roll(hole[:,0],-1)*hole[:,1]))/2
    dens = 4.43 if r['material'] == 'Ti-6Al-4V' else 4.48
    r.update(xy=xy, tri=tri, outer=outer, hole=hole, vm_at=vm_at, env=env, gov=gov, sf=sf, excl=excl, caps=caps,
             loads=loads, tip=tp, nel=len(tri), nnode=n, sy100=sy100, mass_geom=area*r['t']*dens/1000, lat_k=lat_k, n_cw=P.n_cw)
    return r

def badge(fig, x, y, text, color):
    fig.text(x, y, text, fontsize=8.5, fontweight='bold', color='white', ha='left', va='top',
            bbox=dict(boxstyle='round,pad=0.3', fc=color, ec='none'))

def knife_ax(ax, r, field, cmap, label, vmin=None, vmax=None, contour=None, mark_min=False):
    T = mtri.Triangulation(r['xy'][:, 0], r['xy'][:, 1], r['tri'])
    if vmax is None: vmax = float(np.max(np.where(r['excl'], -np.inf, field)))
    pc = ax.tripcolor(T, facecolors=field, cmap=cmap, vmin=vmin, vmax=vmax, edgecolors='none', rasterized=True)
    for poly in (r['outer'], r['hole']):
        ax.add_patch(MPoly(poly, closed=True, fill=False, lw=0.6, ec='k'))
    ax.set_aspect('equal'); ax.set_xlabel('x (mm)', fontsize=8); ax.set_ylabel('y (mm)', fontsize=8); ax.tick_params(labelsize=7)
    cb = plt.colorbar(pc, ax=ax, fraction=0.046, pad=0.02); cb.set_label(label, fontsize=8); cb.ax.tick_params(labelsize=7)
    ax.add_patch(plt.Circle(r['tip'], 4.0, fill=False, ls=':', lw=0.6, ec='0.3'))
    if mark_min:
        f = np.where(r['excl'], np.inf, field); i = int(np.argmin(f)); c = r['xy'][r['tri'][i]].mean(0)
        ax.plot(*c, marker='x', ms=7, mew=1.6, color='k'); ax.annotate(f'min SF {field[i]:.2f}', c, xytext=(-60, -14), textcoords='offset points', fontsize=7.5)
    return pc

def pass_str(ok): return 'PASS' if ok else 'FAIL'

def metrics_table(ax, r, wave):
    ax.axis('off')
    blade_ok = all(v >= LIMIT for v in (r['tth'], r['reach'], r['arc']))
    c = r['caps']
    rows = [
        ('Blade tip→heel', f"{r['tth']/IN2MM:.3f} in ({r['tth']:.1f} mm)", f"≥3.375 in: {pass_str(r['tth']>=LIMIT)}"),
        ('Blade horizontal reach', f"{r['reach']/IN2MM:.3f} in ({r['reach']:.1f} mm)", f"≥3.375 in: {pass_str(r['reach']>=LIMIT)}"),
        ('Blade edge arc (outer)', f"{r['arc']/IN2MM:.3f} in ({r['arc']:.1f} mm)", f"≥3.375 in: {pass_str(r['arc']>=LIMIT)}"),
        ('Grip (ring-neck→guard)', f"{r['grip']:.1f} mm", '60–80 mm'),
        ('Ring ID', f"{r['ring_id']:.2f} mm", '25.4±0.5 mm'),
        ('Stock / material', f"{r['t']:.1f} mm / {r['material']}", f"red-team: {'Ok' if r['redteam_ok'] else 'FAIL'}"),
        ('Est. weight', f"{r['mass']:.2f} g", f"geom check {r['mass_geom']:.2f} g"),
        ('Fitness', f"{r['fit']:.3f} N/g", r['fit_kind']),
        ('Beam surrogate S', f"{r['surr']:.0f} N", 'repo plate (fem.rs): ' + (f"{r['repo_plate']:.0f} N" if not np.isnan(r['repo_plate']) else 'n/a')),
    ]
    for T in TEMPS:
        lat = c[T]['lateral']
        rows.append((f'Plate FEM @ {T:+.0f} °C', f"lat {lat:.0f} N | ring {c[T]['ring']:.0f} N",
                     f"SF hiker {lat/180:.2f} / hunter {lat/260:.2f} / ring {c[T]['ring']/1500:.2f}"))
    rows.append(('Twist / pry SF @100 °C', f"twist {c[100.0]['twist']/TWIST_NMM:.2f} | pry {c[100.0]['pry']/260:.2f}", f"twist {TWIST_NMM/1000:.2f} N·m, pry 260 N"))
    tb = ax.table(cellText=[list(x) for x in rows], colLabels=['Metric', 'Value', 'Gate / note'], loc='upper center', cellLoc='left', colWidths=[0.30, 0.33, 0.40])
    tb.auto_set_font_size(False); tb.set_fontsize(7.4); tb.scale(1, 1.45)
    for (i, j), cell in tb.get_celld().items():
        cell.set_linewidth(0.3)
        if i == 0: cell.set_facecolor('#dde3ea'); cell.set_text_props(weight='bold')
        txt = cell.get_text().get_text()
        if 'FAIL' in txt: cell.set_text_props(color='#b00020', weight='bold')
        elif 'PASS' in txt: cell.set_text_props(color='#1b7f2a', weight='bold')
    hik = min(c[T]['lateral'] for T in TEMPS) >= 180; hun = min(c[T]['lateral'] for T in TEMPS) >= 260; rp = min(c[T]['ring'] for T in TEMPS) >= 1500
    ax.text(0.0, 0.0, f"Floors on offline plate, worst of -10/20/100 °C: hiker {pass_str(hik)} · hunter {pass_str(hun)} · ring {pass_str(rp)}\n"
            f"Temp: Ti yield linear derate ({pf.SY[r['material']][1]*100:+.2f} %/°C from 20 °C); maps use 100 °C yield {r['sy100']:.0f} MPa.\n"
            f"Serration knock-down on blade (h/h_eff={r['lat_k']:.2f}, from history genes{'' if r['serr'][2] else ' — DEFAULT 1.0/1.0 mm'}). "
            f"Load patch r≤4 mm excluded from peaks.", transform=ax.transAxes, fontsize=6.6, va='bottom')
    return blade_ok, hik and hun and rp

def pareto_ax(ax, pts, best, title, quarantined=False):
    if pts is not None and len(pts):
        ax.scatter(pts[:, 0], pts[:, 1], s=9, c='0.55' if quarantined else '#3a6ea5', label='front' + (' (all quarantined)' if quarantined else ''))
    ax.scatter([best[0]], [best[1]], s=60, marker='*', c='#d62728', zorder=5, label='this plate')
    ax.set_xlabel('mass (g)', fontsize=8); ax.set_ylabel('surrogate S (N)', fontsize=8); ax.tick_params(labelsize=7)
    ax.set_title(title, fontsize=8.5); ax.legend(fontsize=6.5, loc='lower right'); ax.grid(alpha=0.3, lw=0.4)

def load_pareto(path):
    try:
        rows = list(csv.DictReader(open(path)))
        return np.array([(float(x['mass_g']), float(x['strength_n'])) for x in rows])
    except Exception:
        return None

def plate(wave_id, label, d, pareto_path, quarantined_front, outdir, extra_note=''):
    r = analyse(d)
    os.makedirs(outdir, exist_ok=True)
    fig = plt.figure(figsize=(15, 9.6))
    gs = fig.add_gridspec(2, 3, width_ratios=[1, 1, 1.55], height_ratios=[1, 0.62], hspace=0.30, wspace=0.30, top=0.87, bottom=0.07, left=0.05, right=0.98)
    fig.suptitle(f"Wave {wave_id} — {label}   |   Fitness {r['fit']:.3f} N/g   |   Est. weight {r['mass']:.1f} g",
                 fontsize=14, fontweight='bold', y=0.985)
    blade_ok = all(v >= LIMIT for v in (r['tth'], r['reach'], r['arc']))
    sub = ("FEM-UNCALIBRATED: offline Kirchhoff plate (numerical DKT + CST, %d tris) — not yet calibrated to MC / repo FEM. "
           "Envelope of hunter-lateral 260 N, twist %.2f N·m, tip-pry 260 N, ring-pull 1500 N." % (r['nel'], TWIST_NMM/1000))
    fig.text(0.5, 0.95, sub, ha='center', fontsize=8.8, style='italic')
    a1 = fig.add_subplot(gs[0, 0]); a2 = fig.add_subplot(gs[0, 1]); a3 = fig.add_subplot(gs[:, 2]); a4 = fig.add_subplot(gs[1, :2])
    knife_ax(a1, r, r['env'], 'turbo', 'von Mises envelope (MPa)')
    a1.set_title('(1) von Mises — worst load case per element', fontsize=9)
    knife_ax(a2, r, np.clip(r['sf'], 0, 4), 'RdYlGn', 'SF = σy(100 °C)/σvm', vmin=0, vmax=4, mark_min=True)
    a2.set_title('(2) Safety factor — worst case @100 °C', fontsize=9)
    floors_ok = None
    a3.set_title('(3) Metrics', fontsize=9, loc='left'); blade_ok, floors_ok = metrics_table(a3, r, wave_id)
    pts = load_pareto(pareto_path) if pareto_path else None
    pareto_ax(a4, pts, (r['mass'], r['surr']), '(4) Pareto (surrogate S vs mass)', quarantined_front)
    badge(fig, 0.06, 0.925, 'FEM-UNCALIBRATED', '#c0392b')
    badge(fig, 0.20, 0.925, 'QUARANTINED: blade < 3.375 in (all three)' if not blade_ok else 'blade ≥ 3.375 in: PASS', '#7d3c98' if not blade_ok else '#1b7f2a')
    badge(fig, 0.45, 0.925, f"hard geometric gates: {'red-team Ok' if r['redteam_ok'] else 'red-team FAIL'}", '#1f618d' if r['redteam_ok'] else '#b00020')
    badge(fig, 0.66, 0.925, f"floors 180/260/1500 N on plate: {'PASS' if floors_ok else 'FAIL'}", '#1b7f2a' if floors_ok else '#b00020')
    fig.text(0.01, 0.005, f"source: {os.path.relpath(d, ROOT)}  {extra_note}  | Jepson Taylor · jarambit (titanium hiking/utility karambit) · generated offline (ops/wave_figures)", fontsize=6.5, color='0.35')
    stem = os.path.join(outdir, f"wave{wave_id}_FEM_metrics")
    fig.savefig(stem + '.png', dpi=320); fig.savefig(stem + '.pdf'); plt.close(fig)
    # supplementary per-load-case sheet (twist / tip-pry / lateral / ring / worst SF / governing)
    spg = f"{r['fit']:.2f}".replace('.', 'p').replace('-', 'm'); wg = f"{r['mass']:.1f}".replace('.', 'p')
    fig, axs = plt.subplots(2, 3, figsize=(14, 9.2))
    fig.suptitle(f"Wave {wave_id} — {label}   |   Fitness {r['fit']:.3f} N/g   |   Est. weight {r['mass']:.1f} g", fontsize=14, fontweight='bold')
    fig.text(0.5, 0.935, 'FEM-UNCALIBRATED load-case maps (offline DKT+CST plate)' + ('' if blade_ok else ' — QUARANTINED: blade < 3.375 in'), ha='center', fontsize=9, style='italic', color='#7d0000')
    names = [('lateral', 'Tip lateral (hunter 260 N)'), ('twist', f'Tip twist ({TWIST_NMM/1000:.2f} N·m)'), ('pry', 'Tip pry in-plane (260 N)'), ('ring', 'Ring pull (1500 N)')]
    for ax, (kk, tt) in zip(axs.ravel()[:4], names):
        knife_ax(ax, r, r['vm_at'][kk], 'turbo', 'σvm (MPa)'); ax.set_title(f"{tt} — SF@100°C {r['caps'][100.0][kk]/r['loads'][kk]:.2f}", fontsize=9)
    knife_ax(axs[1, 1], r, np.clip(r['sf'], 0, 4), 'RdYlGn', 'SF worst case', vmin=0, vmax=4, mark_min=True); axs[1, 1].set_title('Worst-case SF @100 °C', fontsize=9)
    from matplotlib.colors import ListedColormap
    knife_ax(axs[1, 2], r, r['gov'].astype(float), ListedColormap(['#1f77b4', '#ff7f0e', '#2ca02c', '#d62728']), 'governing case: 0 lat · 1 twist · 2 pry · 3 ring', vmin=-0.5, vmax=3.5)
    axs[1, 2].set_title('Governing load case', fontsize=9)
    fig.tight_layout(rect=(0, 0, 1, 0.93))
    s2 = os.path.join(outdir, f"wave{wave_id}_best_SPG{spg}_wgt{wg}g_loadcases")
    fig.savefig(s2 + '.png', dpi=320); fig.savefig(s2 + '.pdf'); plt.close(fig)
    summ = dict(wave=wave_id, label=label, src=os.path.relpath(d, ROOT), fitness=r['fit'], fit_kind=r['fit_kind'], mass_g=r['mass'],
                blade_in=[round(v/IN2MM, 3) for v in (r['tth'], r['reach'], r['arc'])], blade_ok=blade_ok, redteam_ok=r['redteam_ok'],
                plate_floors_ok=bool(floors_ok), calibrated=False,
                caps={str(T): {kk: round(v, 1) for kk, v in r['caps'][T].items()} for T in TEMPS},
                min_sf_100C=round(float(np.min(np.where(r['excl'], np.inf, r['sf']))), 3), n_tris=r['nel'], cw_fixed=r['n_cw'],
                files=[stem + '.png', stem + '.pdf', s2 + '.png', s2 + '.pdf'])
    return summ

if __name__ == '__main__':
    O = os.path.join(ROOT, 'out'); res = []
    waves = [('1', 'smoke_constraints (first constrained evolve)', 'smoke_constraints', 'smoke_constraints/pareto.csv', False),
             ('2', 'bench10k (MC 10k benchmark)', 'bench10k', 'bench10k/pareto.csv', False),
             ('3', 'fem_smoke (plate-FEM-in-loop smoke)', 'fem_smoke', 'fem_smoke/pareto.csv', False)]
    groups = sorted(g for g in os.listdir(os.path.join(O, 'mh1')) if g.startswith('xbabe'))
    fits = {g: read_report(os.path.join(O, 'mh1', g))['fit'] for g in groups}
    bestg = max(fits, key=fits.get)
    waves.append(('4', f'mh1 merged 10k best ({bestg}, 17 groups)', f'mh1/{bestg}', 'mh1/merged_10k/pareto_merged.csv', True))
    for w, label, sub, par, q in waves:
        try: res.append(plate(w, label, os.path.join(O, sub), os.path.join(O, par), q, OUT)); print('ok', w, flush=True)
        except Exception as e: res.append(dict(wave=w, label=label, error=repr(e))); print('FAIL', w, e, flush=True)
    for g in groups:
        try: res.append(plate(f'4-{g}', f'mh1 island group {g}', os.path.join(O, 'mh1', g), os.path.join(O, 'mh1', g, 'pareto.csv'), True, os.path.join(OUT, 'mh1_groups'))); print('ok', g, flush=True)
        except Exception as e: res.append(dict(wave=f'4-{g}', error=repr(e))); print('FAIL', g, e, flush=True)
    res.append(dict(wave='0', label='smoke (pre-constraint scaffold)', error='no best.svg / best_report.md written by that binary; outline not recoverable — skipped'))
    json.dump(res, open(os.path.join(OUT, 'index.json'), 'w'), indent=1, default=float)
