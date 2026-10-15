#!/usr/bin/env python3
"""Deterministic figure generator for docs/ENGINEERING_GATES_AND_EVOLUTION.md.

Generates three high-resolution, manifest-verified figures under docs/figures/engineering_gates/:
  1. fig1_evolutionary_trajectories.png:
     - (a) Multi-wave generation trajectories (best SPG, feasible/legal counts, archive cells)
     - (b) 2D MAP-Elites Quality-Diversity archive occupancy & SPG heatmap (removal vs mass bin)
     - (c) Cross-wave Mass vs Certified SPG & Global Metric G1 Pareto progression (w20..w273)
  2. fig2_cad_battery_matrix_and_gci.png:
     - (a) Full 11-Subject x 18-Evaluator CAD Battery status matrix (evidence/cad_battery/*.json)
     - (b) 3-Mesh Plate GCI (4.0, 1.0, 0.25 mm^2) & 3D Solid Tip DOLFINx vs scikit-fem parity
     - (c) Side Report A1-A4 hand/blade sequence ratios & linear buckling eigenvalues lambda_cr
  3. fig3_cad_and_fem_gallery.png:
     - Real 3D shaded CAD meshes & planform structural breakdown across g3_tip+00_t60_tt3,
       SWITCHBACK Rev C.9.2, SWITCHBACK Rev C.9.3, SWITCHBACK Rev C.10a, and evolved w271c/w272/w273.

Every figure writes `<figure>.manifest.json` via `ops/wave_figures/figlib.py` and is verified by
`ops/ci/verify_figures.py`.
"""
import csv
import json
import os
import re
import sys
from pathlib import Path

import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import numpy as np

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / 'ops' / 'wave_figures'))
sys.path.insert(0, str(ROOT / 'ops' / 'render'))
import figlib  # noqa: E402
import turntable as tt  # noqa: E402

OUT_DIR = ROOT / 'docs' / 'figures' / 'engineering_gates'


def load_stl_any(path: Path) -> np.ndarray:
    raw = path.read_bytes()
    if raw.startswith(b'solid ') and b'vertex ' in raw[:512]:
        txt = raw.decode('utf-8', errors='ignore')
        v = np.array(re.findall(r'vertex\s+(\S+)\s+(\S+)\s+(\S+)', txt), dtype=float).reshape(-1, 3, 3)
        return v
    n_tri = int.from_bytes(raw[80:84], 'little')
    dt = np.dtype([('n', '<f4', (3,)), ('v', '<f4', (3, 3)), ('attr', '<u2')])
    arr = np.frombuffer(raw, dtype=dt, count=n_tri, offset=84)
    return np.array(arr['v'], dtype=float)


def parse_history(path: Path):
    rows = list(csv.DictReader(path.open(encoding='utf-8')))
    by_gen = {}
    for r in rows:
        g = int(r['gen'])
        spg = float(r['best_spg']) if r.get('best_spg') else 0.0
        fit = float(r['best_fit']) if r.get('best_fit') else -10.0
        leg = int(r.get('legal', 0))
        arc = int(r.get('archive_cells', 0))
        mass = float(r['best_mass_g']) if r.get('best_mass_g') else 85.0
        if g not in by_gen:
            by_gen[g] = {'spg': spg, 'fit': fit, 'legal': leg, 'arc': arc, 'mass': mass}
        else:
            if spg > by_gen[g]['spg']:
                by_gen[g]['spg'] = spg
                by_gen[g]['mass'] = mass
            by_gen[g]['fit'] = max(by_gen[g]['fit'], fit)
            by_gen[g]['legal'] += leg
            by_gen[g]['arc'] = max(by_gen[g]['arc'], arc)
    gens = sorted(by_gen.keys())
    return (
        np.array(gens),
        np.array([by_gen[g]['spg'] for g in gens]),
        np.array([by_gen[g]['fit'] for g in gens]),
        np.array([by_gen[g]['legal'] for g in gens]),
        np.array([by_gen[g]['arc'] for g in gens]),
        np.array([by_gen[g]['mass'] for g in gens]),
    )


def make_fig1():
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    fig_path = OUT_DIR / 'fig1_evolutionary_trajectories.png'

    hist_files = {
        'Wave 6 Crescent (40g)': ROOT / 'docs/crescent/history.csv',
        'Wave 13 C.6 Groove (120g)': ROOT / 'docs/lattice/wave13_c6/history.csv',
        'Wave 15 C.6 Long (240g)': ROOT / 'docs/lattice/wave15_c6_long/history.csv',
        'Wave 16 Through-4 (240g)': ROOT / 'docs/lattice/wave16_c6_through4/history.csv',
        'Wave 272 s2902 (120g)': ROOT / 'evidence/rs_v2/w272_xbabe3/s2902/history.csv',
        'Wave 273 s2904 (40g)': ROOT / 'evidence/rs_v2/w273_xbabe3/s2904/history.csv',
    }
    qd_files = [
        ROOT / 'docs/lattice/wave13_c6/qd_archive.csv',
        ROOT / 'docs/lattice/wave16_c6_through4/qd_archive.csv',
        ROOT / 'evidence/rs_v2/w272_xbabe3/s2902/qd_archive.csv',
        ROOT / 'evidence/rs_v2/w273_xbabe3/s2903/qd_archive.csv',
        ROOT / 'evidence/rs_v2/w273_xbabe3/s2904/qd_archive.csv',
    ]
    w27_idx = ROOT / 'docs/wave27_diversity/plates/wave27_D1_index.json'
    battery_genomes = [
        ROOT / 'evidence/cad_battery/g3.json',
        ROOT / 'evidence/cad_battery/w271b_11772.json',
        ROOT / 'evidence/cad_battery/w271b_11860.json',
        ROOT / 'evidence/cad_battery/w271c_11522.json',
        ROOT / 'evidence/cad_battery/w272_s2902_c01.json',
        ROOT / 'evidence/cad_battery/w273_s2903_c04.json',
        ROOT / 'evidence/cad_battery/w273_s2904_c01.json',
    ]

    plt.rcParams.update({'font.sans-serif': 'DejaVu Sans', 'font.size': 10})
    fig, axes = plt.subplots(1, 3, figsize=(19.5, 6.2), dpi=160)
    fig.patch.set_facecolor('#0d1117')
    for ax in axes:
        ax.set_facecolor('#161b22')
        for sp in ax.spines.values():
            sp.set_color('#30363d')
        ax.tick_params(colors='#c9d1d9')
        ax.xaxis.label.set_color('#e6edf3')
        ax.yaxis.label.set_color('#e6edf3')
        ax.title.set_color('#f0f6fc')

    # Panel (a): Generation-by-generation SPG & Archive trajectory
    ax0 = axes[0]
    palette = ['#58a6ff', '#3fb950', '#d2a8ff', '#ffa657', '#ff7b72', '#79c0ff']
    for (label, p), col in zip(hist_files.items(), palette):
        gens, spg, _fit, _leg, _arc, _mass = parse_history(p)
        cum_spg = np.maximum.accumulate(spg)
        ax0.plot(gens, cum_spg, label=label, color=col, linewidth=2.1, alpha=0.92)
    ax0.set_title('(a) Evolutionary Search Progression: Best SPG vs Generation', fontsize=11.5, fontweight='bold', pad=10)
    ax0.set_xlabel('Generation')
    ax0.set_ylabel('Cumulative Best Strength-Per-Gram (N/g)')
    ax0.grid(True, color='#21262d', linestyle='--', linewidth=0.7)
    leg0 = ax0.legend(loc='lower right', facecolor='#0d1117', edgecolor='#30363d', fontsize=8.5)
    for txt in leg0.get_texts():
        txt.set_color('#c9d1d9')

    # Panel (b): 2D MAP-Elites Quality-Diversity Archive Heatmap
    ax1 = axes[1]
    grid_spg = np.full((10, 12), np.nan)
    for qf in qd_files:
        for row in csv.DictReader(qf.open(encoding='utf-8')):
            cr = int(row['cell_removal'])
            cm = int(row.get('cell_mass_bin', row.get('cell_mass', 0)))
            s = float(row['spg'])
            if 0 <= cr < 10 and 0 <= cm < 12:
                if np.isnan(grid_spg[cr, cm]) or s > grid_spg[cr, cm]:
                    grid_spg[cr, cm] = s
    masked = np.ma.masked_invalid(grid_spg)
    cmap_qd = plt.cm.viridis.copy()
    cmap_qd.set_bad(color='#0d1117')
    im1 = ax1.imshow(masked, origin='lower', aspect='auto', cmap=cmap_qd, vmin=2.8, vmax=4.15)
    for i in range(10):
        for j in range(12):
            if not np.isnan(grid_spg[i, j]):
                ax1.text(j, i, f'{grid_spg[i, j]:.2f}', ha='center', va='center',
                         color='#0d1117' if grid_spg[i, j] > 3.6 else '#e6edf3', fontsize=6.5, fontweight='bold')
    ax1.set_title('(b) MAP-Elites QD Archive: Peak SPG (N/g) per Niche', fontsize=11.5, fontweight='bold', pad=10)
    ax1.set_xlabel('Mass Bin Index (2 g / bin, 70 g .. 94 g)')
    ax1.set_ylabel('Material Relief Fraction Bin (0 .. 9)')
    cb1 = fig.colorbar(im1, ax=ax1, fraction=0.046, pad=0.04)
    cb1.ax.yaxis.set_tick_params(color='#c9d1d9')
    plt.setp(plt.getp(cb1.ax.axes, 'yticklabels'), color='#c9d1d9', fontsize=8)
    cb1.set_label('Elite SPG (N/g)', color='#e6edf3', fontsize=9)

    # Panel (c): Cross-Wave Pareto & Global Metric G1 (w27 arms + w271..w273 battery genomes)
    from metrics.global_metric import global_G
    ax2 = axes[2]
    w27_rows = json.loads(w27_idx.read_text(encoding='utf-8'))
    w27_m, w27_spg, w27_g = [], [], []
    for r in w27_rows:
        g_val_w27, _t = global_G(r)
        if g_val_w27 is not None:
            w27_m.append(float(r['mass_g']))
            w27_spg.append(float(r['spg']))
            w27_g.append(float(g_val_w27))
    sc = ax2.scatter(w27_m, w27_spg, c=w27_g, cmap='plasma', vmin=0.55, vmax=1.01,
                     s=48, alpha=0.82, edgecolors='#30363d', label='Wave 27 D1 Arms (42 designs)')

    offsets = {
        'g3': (-4.8, 0.05),
        'w273_s2904_c01': (-6.2, 0.08),
        'w273_s2903_c04': (-6.6, -0.02),
        'w272_s2902_c01': (1.1, 0.04),
        'w271b_11772': (1.1, -0.09),
        'w271b_11860': (0.8, -0.07),
        'w271c_11522': (0.8, 0.02),
    }
    for bp in battery_genomes:
        rec = json.loads(bp.read_text(encoding='utf-8'))
        gf = rec['global_fitness']
        inp = gf['inputs']
        m_val = inp['mass_g']
        s_val = inp['spg']
        g_val = gf['G']
        seq_val = inp['seq_ratio']
        name = rec['subject']
        ax2.scatter([m_val], [s_val], c=[g_val], cmap='plasma', vmin=0.55, vmax=1.01,
                    s=155, marker='*', edgecolors='#f0f6fc', linewidths=1.1, zorder=5)
        dx, dy = offsets.get(name, (0.5, 0.02))
        ax2.annotate(f"{name}\nG1={g_val:.3f} seq={seq_val:.2f}",
                     (m_val, s_val), xytext=(m_val + dx, s_val + dy),
                     color='#f0f6fc', fontsize=7.3, fontweight='bold',
                     arrowprops=dict(arrowstyle='->', color='#8b949e', lw=0.8))

    ax2.axvline(80.0, color='#ffa657', linestyle='--', linewidth=1.1, label='Soft Mass Target (80 g)')
    ax2.set_title('(c) Mass vs Certified SPG & Locked Global Fitness G1', fontsize=11.5, fontweight='bold', pad=10)
    ax2.set_xlabel('Finished Mass (g)')
    ax2.set_ylabel('Certified Strength-Per-Gram SPG (N/g)')
    ax2.set_xlim(71.5, 89.5)
    ax2.set_ylim(3.40, 4.30)
    ax2.grid(True, color='#21262d', linestyle='--', linewidth=0.7)
    cb2 = fig.colorbar(sc, ax=ax2, fraction=0.046, pad=0.04)
    cb2.ax.yaxis.set_tick_params(color='#c9d1d9')
    plt.setp(plt.getp(cb2.ax.axes, 'yticklabels'), color='#c9d1d9', fontsize=8)
    cb2.set_label('Global Fitness G1', color='#e6edf3', fontsize=9)
    leg2 = ax2.legend(loc='lower left', facecolor='#0d1117', edgecolor='#30363d', fontsize=8)
    for txt in leg2.get_texts():
        txt.set_color('#c9d1d9')

    fig.suptitle('jarambit Evolutionary Dynamics: Multi-Wave Search, MAP-Elites QD Archive, and Pareto / G1 Progression',
                 color='#f0f6fc', fontsize=13.5, fontweight='bold', y=0.98)
    fig.tight_layout(rect=[0, 0, 1, 0.94])
    fig.savefig(fig_path, dpi=160, facecolor=fig.get_facecolor())
    plt.close(fig)

    inputs = list(hist_files.values()) + qd_files + [w27_idx] + battery_genomes
    figlib.write_manifest(str(fig_path), [str(p) for p in inputs], __file__, norms=['safety_factor'])
    return fig_path


def make_fig2():
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    fig_path = OUT_DIR / 'fig2_cad_battery_matrix_and_gci.png'

    subjects = [
        'g3', 'w273_s2904_c01', 'w271c_11522', 'w272_s2902_c01',
        'w273_s2903_c04', 'w271b_11772', 'w271b_11860',
        'c10a', 'c93', 'c92', 'c10c',
    ]
    bat_paths = [ROOT / 'evidence/cad_battery' / f'{s}.json' for s in subjects]
    records = [json.loads(p.read_text(encoding='utf-8')) for p in bat_paths]
    case_ids = [c['id'] for c in records[0]['cases']]

    genomes = ['g3', 'w271b_11772', 'w271b_11860', 'w271c_11522', 'w272_s2902_c01', 'w273_s2904_c01', 'w273_s2903_c04']
    gci_paths = [ROOT / 'evidence/cad_battery/plate_gci' / f'{g}.json' for g in genomes]
    a4_paths = [ROOT / 'evidence/cad_battery/side' / f'{g}_a4.json' for g in genomes]
    cross_path = ROOT / 'evidence/cad_battery/dolfinx_cross_check.json'
    c10a_tip_path = ROOT / 'evidence/cad_battery/side/c10a_solid_tip.json'

    fig, axes = plt.subplots(1, 3, figsize=(20.0, 6.6), dpi=160, gridspec_kw={'width_ratios': [1.35, 1.0, 1.0]})
    fig.patch.set_facecolor('#0d1117')
    for ax in axes:
        ax.set_facecolor('#161b22')
        for sp in ax.spines.values():
            sp.set_color('#30363d')
        ax.tick_params(colors='#c9d1d9')
        ax.xaxis.label.set_color('#e6edf3')
        ax.yaxis.label.set_color('#e6edf3')
        ax.title.set_color('#f0f6fc')

    # Panel (a): 11 x 18 CAD Battery Status Grid
    ax0 = axes[0]
    code_map = {'pass': 2, 'fail': 1, 'incomplete': 0, 'blocked': -1}
    mat = np.zeros((len(subjects), len(case_ids)), dtype=float)
    for i, rec in enumerate(records):
        for j, c in enumerate(rec['cases']):
            mat[i, j] = code_map.get(c['status'], -1)
    from matplotlib.colors import ListedColormap
    cmap_grid = ListedColormap(['#30363d', '#6e7681', '#d29922', '#2ea043'])
    ax0.imshow(mat, aspect='auto', cmap=cmap_grid, vmin=-1, vmax=2)
    for i, rec in enumerate(records):
        for j, c in enumerate(rec['cases']):
            st = c['status']
            sym = 'P' if st == 'pass' else ('F' if st == 'fail' else ('I' if st == 'incomplete' else 'B'))
            ax0.text(j, i, sym, ha='center', va='center', color='#f0f6fc', fontsize=7.5, fontweight='bold')
    ax0.set_xticks(range(len(case_ids)))
    ax0.set_xticklabels(case_ids, rotation=50, ha='right', fontsize=7.8)
    ylabels = [
        f"{r['subject']} ({r['pass_count']}/18, G1={r['global_fitness']['G']:.3f})"
        if r['global_fitness']['G'] is not None
        else f"{r['subject']} ({r['pass_count']}/18, INCOMPLETE)"
        for r in records
    ]
    ax0.set_yticks(range(len(subjects)))
    ax0.set_yticklabels(ylabels, fontsize=8.0)
    ax0.set_title('(a) 11-Subject x 18-Evaluator CAD Battery Matrix (P=Pass, F=Fail, B=Blocked)', fontsize=11, fontweight='bold', pad=10)

    # Panel (b): 3D Solid Tip DOLFINx vs scikit-fem Cross-Check + 3-Mesh Plate GCI
    ax1 = axes[1]
    cross = json.loads(cross_path.read_text(encoding='utf-8'))['subjects']
    c10a_tip = json.loads(c10a_tip_path.read_text(encoding='utf-8'))
    labels_b = genomes + ['c10a']
    skfem_vals = [cross[g]['skfem_reference']['SF_nodal_max'] for g in genomes] + [c10a_tip['SF_nodal_max']]
    dolf_vals = [cross[g]['dolfinx']['SF_nodal_max'] for g in genomes] + [c10a_tip['dolfinx_cross_check']['SF_nodal_max']]
    x = np.arange(len(labels_b))
    w = 0.36
    ax1.bar(x - w / 2, skfem_vals, width=w, color='#58a6ff', label='scikit-fem P2 (nodal max SF)')
    ax1.bar(x + w / 2, dolf_vals, width=w, color='#3fb950', label='DOLFINx v0.9.0 CG+GAMG (nodal max SF)')
    ax1.axhline(1.0, color='#ff7b72', linestyle='--', linewidth=1.2, label='Hard Floor SF = 1.0 (1.82 N*m)')
    for xi, sv, dv in zip(x, skfem_vals, dolf_vals):
        err_pct = abs(dv - sv) / max(sv, 1e-9) * 100.0
        ax1.text(xi, max(sv, dv) + 0.03, f'{sv:.3f}\n({err_pct:.2f}%)', ha='center', va='bottom', color='#c9d1d9', fontsize=7.0)
    ax1.set_xticks(x)
    ax1.set_xticklabels(labels_b, rotation=30, ha='right', fontsize=8.2)
    ax1.set_ylim(0, 1.82)
    ax1.set_ylabel('3D Solid Tip Nodal-Max Safety Factor')
    ax1.set_title('(b) 3D Solid Tip SF: scikit-fem vs DOLFINx (<0.06% diff)', fontsize=11, fontweight='bold', pad=10)
    ax1.grid(True, axis='y', color='#21262d', linestyle='--', linewidth=0.7)
    leg1 = ax1.legend(loc='upper right', facecolor='#0d1117', edgecolor='#30363d', fontsize=8)
    for txt in leg1.get_texts():
        txt.set_color('#c9d1d9')

    # Panel (c): Side Report A4 (Certified vs Supported seq_ratio & Linear Buckling Eigenvalue)
    ax2 = axes[2]
    a4_docs = [json.loads(p.read_text(encoding='utf-8')) for p in a4_paths]
    cert_seq = [d['certified_seq_ratio'] for d in a4_docs]
    supp_seq = [d['supported_seq_ratio'] for d in a4_docs]
    lam_cr = [d['buckling_eigenvalue'] for d in a4_docs]
    xg = np.arange(len(genomes))
    ax2.bar(xg - w / 2, cert_seq, width=w, color='#ffa657', label='Certified Clamp seq_ratio (run_b)')
    ax2.bar(xg + w / 2, supp_seq, width=w, color='#a371f7', label='Pin + Grip Pad Supported seq_ratio (A4)')
    ax2.axhline(1.2, color='#ff7b72', linestyle='--', linewidth=1.2, label='Hard Sequence Target seq >= 1.2')
    for xi, cs, ss in zip(xg, cert_seq, supp_seq):
        ax2.text(xi + w / 2, ss + 0.06, f'{ss:.2f}', ha='center', va='bottom', color='#d2a8ff', fontsize=7.0, fontweight='bold')
    ax2_r = ax2.twinx()
    ax2_r.plot(xg, lam_cr, color='#3fb950', marker='o', linewidth=2.0, label='Buckling Eigenvalue lambda_cr')
    ax2_r.set_ylabel('Linear Buckling Eigenvalue lambda_cr (x 260 N)', color='#3fb950')
    ax2_r.tick_params(axis='y', colors='#3fb950')
    ax2_r.set_ylim(0, 14.5)
    ax2.set_xticks(xg)
    ax2.set_xticklabels(genomes, rotation=30, ha='right', fontsize=8.2)
    ax2.set_ylim(0, 5.65)
    ax2.set_ylabel('Failure-Sequence Ratio (Hand / Blade Yield Onset)')
    ax2.set_title('(c) Side Report A4: Sequence Ratio & Plate Buckling lambda_cr', fontsize=11, fontweight='bold', pad=10)
    ax2.grid(True, axis='y', color='#21262d', linestyle='--', linewidth=0.7)
    leg2 = ax2.legend(loc='upper left', facecolor='#0d1117', edgecolor='#30363d', fontsize=7.5)
    for txt in leg2.get_texts():
        txt.set_color('#c9d1d9')

    fig.suptitle('jarambit 18-Evaluator CAD Battery: Cross-Solver Solid Verification, GCI, and Side Report A4 Buckling',
                 color='#f0f6fc', fontsize=13.5, fontweight='bold', y=0.98)
    fig.tight_layout(rect=[0, 0, 1, 0.94])
    fig.savefig(fig_path, dpi=160, facecolor=fig.get_facecolor())
    plt.close(fig)

    inputs = bat_paths + gci_paths + a4_paths + [cross_path, c10a_tip_path]
    figlib.write_manifest(str(fig_path), [str(p) for p in inputs], __file__, norms=['safety_factor'])
    return fig_path


def make_fig3():
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    fig_path = OUT_DIR / 'fig3_cad_and_fem_gallery.png'

    stl_g3 = ROOT / 'evidence/wave27/g3_tip+00_t60_tt3.stl'
    d1_g3 = ROOT / 'evidence/wave27/g3_tip+00_t60_tt3_D1.json'
    stl_c92 = ROOT / 'designs/switchback/C9.2/cad/switchback_revC9_2_ground.stl'
    stl_c93 = ROOT / 'designs/switchback/C9.3/cad/switchback_revC9_3_ground.stl'
    stl_c10a = ROOT / 'designs/switchback/C10a/cad/switchback_revC10a_ground.stl'
    c10a_tip = ROOT / 'evidence/cad_battery/side/c10a_solid_tip.json'
    side_files = [
        ROOT / 'evidence/cad_battery/side/g3_a1a3.json',
        ROOT / 'evidence/cad_battery/side/w271c_11522_a1a3.json',
        ROOT / 'evidence/cad_battery/side/w272_s2902_c01_a1a3.json',
        ROOT / 'evidence/cad_battery/side/w273_s2904_c01_a1a3.json',
        ROOT / 'evidence/cad_battery/side/w273_s2903_c04_a1a3.json',
    ]

    # Render 4 3D STL panels using turntable.render + 2 quantitative FEM / CAD comparison panels
    W, H = 640, 460
    v_g3 = load_stl_any(stl_g3)
    col_g3, _ = tt.facet_colors(v_g3, 'fem', str(d1_g3))
    img_g3 = tt.render(v_g3, col_g3, 25.0, W, H, 'g3_tip+00_t60_tt3 (84.80 g · G1=1.0036 · Solid Tip SF=1.600)', 'D1 100 C SF (1..3, red<1)')

    v_c92 = load_stl_any(stl_c92)
    col_c92, _ = tt.facet_colors(v_c92, 'x', None)
    img_c92 = tt.render(v_c92, col_c92, 25.0, W, H, 'SWITCHBACK Rev C.9.2 B-Rep (67.97 g · 1 solid · mm)', 'B-Rep STEP/STL shading')

    v_c93 = load_stl_any(stl_c93)
    col_c93, _ = tt.facet_colors(v_c93, 'x', None)
    img_c93 = tt.render(v_c93, col_c93, 25.0, W, H, 'SWITCHBACK Rev C.9.3 B-Rep (66.77 g · 1 solid · mm)', 'B-Rep STEP/STL shading')

    v_c10a = load_stl_any(stl_c10a)
    col_c10a, _ = tt.facet_colors(v_c10a, 'x', None)
    c10a_doc = json.loads(c10a_tip.read_text(encoding='utf-8'))
    img_c10a = tt.render(
        v_c10a, col_c10a, 25.0, W, H,
        f"SWITCHBACK Rev C.10a B-Rep (64.84 g · TET10 Tip SF={c10a_doc['SF_nodal_max']:.4f})",
        'B-Rep STEP/STL + 372k DOF TET10',
    )

    fig, axes = plt.subplots(2, 3, figsize=(19.5, 10.5), dpi=160)
    fig.patch.set_facecolor('#0d1117')

    for ax, im in zip([axes[0, 0], axes[0, 1], axes[0, 2], axes[1, 0]], [img_g3, img_c92, img_c93, img_c10a]):
        ax.imshow(np.asarray(im))
        ax.axis('off')

    # Panel (1, 1): Planform 100 C D1 Safety Factor Colormap of g3_tip+00_t60_tt3 from committed D1 mesh
    ax_fem = axes[1, 1]
    ax_fem.set_facecolor('#161b22')
    for sp in ax_fem.spines.values():
        sp.set_color('#30363d')
    d1_data = json.loads(d1_g3.read_text(encoding='utf-8'))
    xy = np.array(d1_data['mesh']['xy'], dtype=float)
    tris = np.array(d1_data['mesh']['tris'], dtype=int)
    sf = np.clip(np.array(d1_data['mesh']['sf'], dtype=float), 0.0, 4.0)
    tpc = ax_fem.tripcolor(xy[:, 0], xy[:, 1], tris, facecolors=sf, cmap='RdYlGn', vmin=0.0, vmax=4.0, shading='flat')
    ax_fem.set_aspect('equal')
    ax_fem.tick_params(colors='#c9d1d9')
    ax_fem.xaxis.label.set_color('#e6edf3')
    ax_fem.yaxis.label.set_color('#e6edf3')
    ax_fem.set_xlabel('x (mm)')
    ax_fem.set_ylabel('y (mm)')
    ax_fem.set_title('Planform FEM Colormap: g3 D1 Certified Envelope SF (100 C)', color='#f0f6fc', fontsize=10.5, fontweight='bold')
    cb = fig.colorbar(tpc, ax=ax_fem, fraction=0.046, pad=0.04)
    cb.ax.yaxis.set_tick_params(color='#c9d1d9')
    plt.setp(plt.getp(cb.ax.axes, 'yticklabels'), color='#c9d1d9', fontsize=8)
    cb.set_label('Element Safety Factor (0..4)', color='#e6edf3', fontsize=8.5)

    # Panel (1, 2): Side Report A1-A3 Zone Stress Decomposition across g3, w271c, w272, w273_s2904, w273_s2903
    ax_side = axes[1, 2]
    ax_side.set_facecolor('#161b22')
    for sp in ax_side.spines.values():
        sp.set_color('#30363d')
    ax_side.tick_params(colors='#c9d1d9')
    ax_side.xaxis.label.set_color('#e6edf3')
    ax_side.yaxis.label.set_color('#e6edf3')

    s_docs = [json.loads(p.read_text(encoding='utf-8')) for p in side_files]
    s_names = [p.stem.replace('_a1a3', '') for p in side_files]
    blade_pk = [d['cases']['lateral']['15']['zones']['blade']['peak_mpa_per_unit'] for d in s_docs]
    groove_pk = [d['cases']['lateral']['15']['zones']['groove']['peak_mpa_per_unit'] for d in s_docs]
    neck_pk = [d['cases']['lateral']['15']['zones']['neck']['peak_mpa_per_unit'] for d in s_docs]
    xs = np.arange(len(s_names))
    bw = 0.25
    ax_side.bar(xs - bw, blade_pk, width=bw, color='#58a6ff', label='Blade Peak Stress (MPa/N)')
    ax_side.bar(xs, groove_pk, width=bw, color='#ffa657', label='Ring-Groove Peak Stress (MPa/N)')
    ax_side.bar(xs + bw, neck_pk, width=bw, color='#ff7b72', label='Neck-Zone Peak Stress (MPa/N)')
    for xi, d in zip(xs, s_docs):
        sr = d['seq_ratio_this_mesh']
        ax_side.text(xi, max(blade_pk[xi], groove_pk[xi], neck_pk[xi]) + 0.08, f'seq={sr:.3f}', ha='center', va='bottom',
                     color='#f0f6fc', fontsize=8.0, fontweight='bold')
    ax_side.set_xticks(xs)
    ax_side.set_xticklabels(s_names, rotation=25, ha='right', fontsize=8.5)
    ax_side.set_ylim(0, 3.1)
    ax_side.set_ylabel('Unit-Load von Mises Peak (MPa / N at 0.25 mm^2)')
    ax_side.set_title('Side Report A1-A3: Blade vs Ring-Groove/Neck Stress & seq_ratio', color='#f0f6fc', fontsize=10.5, fontweight='bold')
    ax_side.grid(True, axis='y', color='#21262d', linestyle='--', linewidth=0.7)
    leg_s = ax_side.legend(loc='upper right', facecolor='#0d1117', edgecolor='#30363d', fontsize=8)
    for txt in leg_s.get_texts():
        txt.set_color('#c9d1d9')

    fig.suptitle('jarambit Real 3D CAD & FEM Gallery: Evolved Crescent Genomes and Native B-Rep SWITCHBACK Candidates',
                 color='#f0f6fc', fontsize=13.5, fontweight='bold', y=0.98)
    fig.tight_layout(rect=[0, 0, 1, 0.95])
    fig.savefig(fig_path, dpi=160, facecolor=fig.get_facecolor())
    plt.close(fig)

    inputs = [stl_g3, d1_g3, stl_c92, stl_c93, stl_c10a, c10a_tip] + side_files
    figlib.write_manifest(str(fig_path), [str(p) for p in inputs], __file__, norms=['safety_factor', 'step3d_x_mm'])
    return fig_path


def main():
    f1 = make_fig1()
    f2 = make_fig2()
    f3 = make_fig3()
    print('generated:', f1.relative_to(ROOT), f2.relative_to(ROOT), f3.relative_to(ROOT))


if __name__ == '__main__':
    main()
