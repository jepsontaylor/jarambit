#!/usr/bin/env python3
"""Deterministic generator for README and White Paper page-1 hero figures.

Generates three manifest-verified figures under docs/figures/whitepaper/:
  1. fig_readme_mass_vs_wave.png:
     - Mass vs. Wave progression across w20..w27e RS-karambit-v1 screen winners
       and w274 onward 16-gate W_CAD_v2 winners, with the current record labelled.
  2. fig_why_this_matters.png:
     - Panel (a): Evolutionary Mass vs. Wave curve.
     - Panel (b): Market comparison of the current record against the commercial
       karambits in docs/market/2026-10-13/census.json.
  3. fig_w279_gate_margins.png:
     - All 16 engineering, CAD, and karambit gates for the current record:
       achieved value, threshold, and percentage reserve margin above threshold.

Every number is read from committed JSON files, and each figure writes <figure>.manifest.json
via ops/wave_figures/figlib.py, verified in CI by ops/ci/verify_figures.py.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import numpy as np

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / 'ops' / 'wave_figures'))
sys.path.insert(0, str(ROOT / 'metrics'))
import figlib  # noqa: E402
import global_metric  # noqa: E402

OUT_DIR = ROOT / 'docs' / 'figures' / 'whitepaper'


def _load_json(rel: str):
    p = ROOT / rel
    return json.loads(p.read_text(encoding='utf-8')), p


def load_wave_winners():
    """Load historical screen and all-16-gate winners from committed JSONs."""
    inputs: list[Path] = []
    w20_25_doc, p_w20_25 = _load_json('docs/wave_reports/wave20_25_winners.json')
    inputs.append(p_w20_25)

    w27_rows, p_w27 = _load_json('docs/wave27_diversity/plates/wave27_D1_index.json')
    inputs.append(p_w27)
    r_g3 = next(r for r in w27_rows if r['label'] == 'g3_tip+00_t60_tt3_D1')
    g_g3, _ = global_metric.global_G(r_g3)

    w27e_rows, p_w27e = _load_json('docs/wave27_diversity/plates_e/wave27e_D1_index.json')
    inputs.append(p_w27e)
    r_w27e = next(r for r in w27e_rows if r['label'] == 'g3t58_S05_rw-05_D1')
    g_w27e, _ = global_metric.global_G(r_w27e)

    ver_doc, p_ver = _load_json('evidence/fem_solid/verify_0.30.2.json')
    inputs.append(p_ver)
    g3_3d_mass = float(ver_doc['whole_part_mesh']['mass_g_at_4.43'])

    v1_winners = []
    for row in w20_25_doc['winners']:
        v1_winners.append({
            'wave': row['wave'],
            'label': row['label'].replace('_D1', ''),
            'mass_g': float(row['mass_g']),
            'mass_3d_g': None,
            'g1': float(row['G1']),
            'seq_ratio': float(row['seq_ratio']),
            'era': 'RS-karambit-v1 screen (seq soft)',
        })
    v1_winners.append({
        'wave': 'w27',
        'label': 'g3_tip+00_t60_tt3',
        'mass_g': float(r_g3['mass_g']),
        'mass_3d_g': g3_3d_mass,
        'g1': float(g_g3),
        'seq_ratio': float(r_g3['seq_ratio']),
        'era': 'RS-karambit-v1 screen (seq soft)',
    })
    v1_winners.append({
        'wave': 'w27e',
        'label': 'g3t58_S05_rw-05',
        'mass_g': float(r_w27e['mass_g']),
        'mass_3d_g': None,
        'g1': float(g_w27e),
        'seq_ratio': float(r_w27e['seq_ratio']),
        'era': 'RS-karambit-v1 screen (seq soft)',
    })

    wcad_specs = [
        ('w274', 'evidence/rs_v2/w274_calibrated/w274_s2905_c01_cad_eval.json', 'evidence/cad_battery/w274_s2905_c01.json'),
        ('w275', 'evidence/rs_v2/w275_ultrarunner/w275_s2909_c01_cad_eval.json', 'evidence/cad_battery/w275_s2909_c01.json'),
        ('w276', 'evidence/rs_v2/w276_ultrarunner/w276_s2913_c01_cad_eval.json', 'evidence/cad_battery/w276_s2913_c01.json'),
        ('w277', 'evidence/rs_v2/w277_ultrarunner/w277_s2919_c01_cad_eval.json', 'evidence/cad_battery/w277_s2919_c01.json'),
        ('w278', 'evidence/rs_v2/w278_ultrarunner/w278_s2922_c01_cad_eval.json', 'evidence/cad_battery/w278_s2922_c01.json'),
        ('w279', 'evidence/rs_v2/w279_ultrarunner/w279_s2928_c01_cad_eval.json', 'evidence/cad_battery/w279_s2928_c01.json'),
        ('w280', 'evidence/rs_v2/w280_ultrarunner/w280_s2931_c01_cad_eval.json', 'evidence/cad_battery/w280_s2931_c01.json'),
        ('w281', 'evidence/rs_v2/w281_ultrarunner/w281_s2932_c01_cad_eval.json', 'evidence/cad_battery/w281_s2932_c01.json'),
        ('w282', 'evidence/rs_v2/w282_ultrarunner/w282_p14_c01_cad_eval.json', 'evidence/cad_battery/w282_p14_c01.json'),
        ('w283', 'evidence/rs_v2/w283_ultrarunner/w283_p14_c01_cad_eval.json', 'evidence/cad_battery/w283_p14_c01.json'),
    ]
    wcad_winners = []
    for wtag, eval_rel, bat_rel in wcad_specs:
        ev, p_ev = _load_json(eval_rel)
        bat, p_bat = _load_json(bat_rel)
        inputs.extend([p_ev, p_bat])
        em = ev['engineering_metrics']
        if not ev['weighted_cad_score']['all_engineering_gates_pass']:
            continue
        wcad_winners.append({
            'wave': wtag,
            'label': ev['subject'],
            'mass_g': float(em['mass_g']),
            'mass_3d_g': float(em['mass_3d_g']),
            'g1': float(bat['global_fitness']['G']),
            'w_cad': float(ev['weighted_cad_score']['W_CAD']),
            'seq_ratio': float(em['seq_ratio_cert']),
            'strict_lat_n': float(em['strict_lat_rob_0p0625_n']),
            'solid_tip_sf': float(em['solid_tip_sf_nodal_max']),
            'era': 'W_CAD_v2 16/16 gates PASS (seq >= 1.20 hard)',
        })
    return v1_winners, wcad_winners, inputs


def _plot_mass_vs_wave(ax, v1_winners, wcad_winners, compact=False):
    all_pts = v1_winners + wcad_winners
    xs = np.arange(len(all_pts))
    n_v1 = len(v1_winners)

    xs_v1 = xs[:n_v1]
    ys_v1 = [p['mass_g'] for p in v1_winners]
    xs_wcad = xs[n_v1:]
    ys_wcad = [p['mass_g'] for p in wcad_winners]
    ys_wcad_3d = [p['mass_3d_g'] for p in wcad_winners]

    # Shaded regime background
    ax.axvspan(-0.5, n_v1 - 0.5, color='#1f2937', alpha=0.35, label='Waves 20–27e: RS-karambit-v1 screen (seq < 1.20 soft)')
    ax.axvspan(n_v1 - 0.5, len(all_pts) - 0.3, color='#0f291e', alpha=0.42, label='Historical waves 274–282: 16-gate screens pass (seq ≥ 1.20 hard + 3D solid tip)')

    # 80 g target line
    ax.axhline(80.0, color='#ffa657', linestyle='--', linewidth=1.4, label='Soft Mass Target (80.00 g)')

    # Bridge line between w27e and w274 (when seq >= 1.20 hard gate was activated)
    ax.plot([xs_v1[-1], xs_wcad[0]], [ys_v1[-1], ys_wcad[0]], color='#8b949e', linestyle=':', linewidth=1.5, zorder=2)

    # Plot RS-karambit-v1 screen winners
    ax.plot(xs_v1, ys_v1, '-o', color='#58a6ff', linewidth=2.2, markersize=7.5,
            markerfacecolor='#58a6ff', markeredgecolor='#f0f6fc', markeredgewidth=1.0,
            label='2.5D Raster Mass — W20–W27e Screen Winners', zorder=4)

    # Plot W_CAD_v2 16-gate winners (2.5D raster + 3D solid)
    ax.plot(xs_wcad, ys_wcad, '-s', color='#3fb950', linewidth=2.6, markersize=8.0,
            markerfacecolor='#3fb950', markeredgecolor='#f0f6fc', markeredgewidth=1.1,
            label='2.5D Raster Mass — W274–W282 All-16-Gates Winners', zorder=5)
    ax.plot(xs_wcad, ys_wcad_3d, '--D', color='#d2a8ff', linewidth=1.8, markersize=6.0,
            markerfacecolor='#d2a8ff', markeredgecolor='#0d1117', markeredgewidth=0.9,
            label=f"3D Solid STEP/STL Mass — W274–W282 ({100.0 * abs(wcad_winners[-1]['mass_g'] - wcad_winners[-1]['mass_3d_g']) / wcad_winners[-1]['mass_g']:.2f}% parity on W282)", zorder=6)

    # Highlight current record w283_p14_c01
    rec = wcad_winners[-1]
    rx = xs[-1]
    ax.scatter([rx], [rec['mass_g']], s=260, marker='*', color='#ffd33d', edgecolors='#f0f6fc', linewidths=1.3, zorder=8,
               label=f"Historical screen record: {rec['label']} ({rec['mass_g']:.3f} g / {rec['mass_3d_g']:.3f} g 3D, G1={rec['g1']:.6f})")

    # Annotate points cleanly above/below markers without touching
    pos_map = {
        'w20': (0, -16),
        'w21': (0, 12),
        'w22': (0, -16),
        'w23': (0, -16),
        'w24': (0, 12),
        'w25': (0, -17),
        'w27': (0, 13),
        'w27e': (0, -16),
        'w274': (-10, -17),
        'w275': (12, 11),
        'w276': (-8, -17),
        'w277': (10, 12),
        'w278': (10, 12),
        'w279': (-8, -16),
        'w280': (10, 12),
        'w281': (-6, 12),
        'w282': (-8, -16),
    }
    for i, p in enumerate(all_pts):
        if i == len(all_pts) - 1:
            continue
        m = p['mass_g']
        ox, oy = pos_map.get(p['wave'], (0, 12))
        lbl_txt = f"{p['mass_g']:.2f} g"
        if not compact and p['wave'] in ('w20', 'w25', 'w27', 'w274', 'w276', 'w278', 'w281', 'w282'):
            lbl_txt = f"{p['label']}\n{p['mass_g']:.2f} g"
        ax.annotate(lbl_txt, (xs[i], m), xytext=(ox, oy), textcoords='offset points',
                    ha='center', va='center', color='#e6edf3', fontsize=7.5 if compact else 8.0, fontweight='bold')

    # Prominent callout box for record w283_p14_c01 kept strictly inside axis bounds
    callout = (
        f"HISTORICAL SCREEN: {rec['label']} (Wave 282)\n"
        f"• 2.5D Raster: {rec['mass_g']:.3f} g  |  3D Solid: {rec['mass_3d_g']:.3f} g\n"
        f"• Locked G1 = {rec['g1']:.6f}  |  W_CAD = +{rec['w_cad']:.4f}\n"
        f"• strict_lat = {rec['strict_lat_n']:.1f} N  |  seq = {rec['seq_ratio']:.3f}  |  3D tip SF = {rec['solid_tip_sf']:.4f}"
    )
    ax.annotate(
        callout,
        xy=(rx, rec['mass_3d_g']),
        xytext=(5.1 if compact else 6.1, 74.15),
        color='#f0f6fc',
        fontsize=7.9 if compact else 8.6,
        fontweight='bold',
        bbox=dict(boxstyle='round,pad=0.45', facecolor='#161b22', edgecolor='#ffd33d', linewidth=1.5),
        arrowprops=dict(arrowstyle='->', color='#ffd33d', lw=1.6, connectionstyle='arc3,rad=0.12'),
        zorder=9,
    )

    ax.set_xticks(xs)
    ax.set_xticklabels([f"{p['wave'].upper()}\n({p['label'][:8]})" for p in all_pts], fontsize=7.2, rotation=20, ha='right')
    ax.set_ylabel('Finished Titanium Knife Mass (g)', fontsize=10.5, fontweight='bold')
    ax.set_xlabel('Evolutionary Wave (All-Gates Winners, W20 → W282)', fontsize=10.5, fontweight='bold')
    ax.set_ylim(73.4, 88.8)
    ax.set_xlim(-0.6, len(all_pts) - 0.2)
    ax.grid(True, color='#21262d', linestyle='--', linewidth=0.7, alpha=0.8)


def make_readme_hero_fig():
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    fig_path = OUT_DIR / 'fig_readme_mass_vs_wave.png'
    v1_winners, wcad_winners, inputs = load_wave_winners()

    plt.rcParams.update({'font.sans-serif': 'DejaVu Sans', 'font.size': 10})
    fig, ax = plt.subplots(1, 1, figsize=(14.5, 6.2), dpi=160)
    fig.patch.set_facecolor('#0d1117')
    ax.set_facecolor('#161b22')
    for sp in ax.spines.values():
        sp.set_color('#30363d')
    ax.tick_params(colors='#c9d1d9')
    ax.xaxis.label.set_color('#e6edf3')
    ax.yaxis.label.set_color('#e6edf3')
    ax.title.set_color('#f0f6fc')

    _plot_mass_vs_wave(ax, v1_winners, wcad_winners, compact=False)
    rec = wcad_winners[-1]
    ax.set_title(
        f"Historical pre-#82 model · W20 → W282 screen selection: {rec['label']} at {rec['mass_g']:.3f} g ({rec['mass_3d_g']:.3f} g 3D Solid, G1 = {rec['g1']:.6f})\nNo currently certified all-16 winner",
        fontsize=11.8, fontweight='bold', pad=12,
    )
    leg = ax.legend(loc='upper right', facecolor='#0d1117', edgecolor='#30363d', fontsize=8.2, ncol=2)
    for txt in leg.get_texts():
        txt.set_color('#c9d1d9')

    fig.tight_layout()
    fig.savefig(fig_path, dpi=160, facecolor=fig.get_facecolor())
    plt.close(fig)

    figlib.write_manifest(str(fig_path), [str(p) for p in inputs] + [__file__], __file__)
    return fig_path


def make_why_this_matters_fig():
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    fig_path = OUT_DIR / 'fig_why_this_matters.png'
    v1_winners, wcad_winners, inputs = load_wave_winners()

    census_rows, p_census = _load_json('docs/market/2026-10-13/census.json')
    market_sum, p_msum = _load_json('docs/market/2026-10-13/summary.json')
    bench_doc, p_bench = _load_json('docs/market/2026-10-13/benchmark.json')
    d1_w279, p_d1_w279 = _load_json('evidence/rs_v2/w282_ultrarunner/w282_p14_c01_D1.json')
    inputs.extend([p_census, p_msum, p_bench, p_d1_w279])

    rec = wcad_winners[-1]
    w279_blade_in = float(d1_w279['metrics']['tip_to_heel']) / 25.4
    w279_mass_g = rec['mass_g']
    w279_mass_3d_g = rec['mass_3d_g']

    plt.rcParams.update({'font.sans-serif': 'DejaVu Sans', 'font.size': 10})
    fig, (ax0, ax1) = plt.subplots(1, 2, figsize=(18.8, 6.6), dpi=160, gridspec_kw={'width_ratios': [1.12, 1.0]})
    fig.patch.set_facecolor('#0d1117')
    for ax in (ax0, ax1):
        ax.set_facecolor('#161b22')
        for sp in ax.spines.values():
            sp.set_color('#30363d')
        ax.tick_params(colors='#c9d1d9')
        ax.xaxis.label.set_color('#e6edf3')
        ax.yaxis.label.set_color('#e6edf3')
        ax.title.set_color('#f0f6fc')

    # Panel (a): Mass vs Wave curve
    _plot_mass_vs_wave(ax0, v1_winners, wcad_winners, compact=True)
    ax0.set_title('(a) Evolutionary Mass Reduction Across All-Gates Winners (W20 → W282)', fontsize=11.0, fontweight='bold', pad=10)
    leg0 = ax0.legend(loc='upper right', facecolor='#0d1117', edgecolor='#30363d', fontsize=7.4)
    for txt in leg0.get_texts():
        txt.set_color('#c9d1d9')

    # Panel (b): Market comparison (77 verified commercial karambits vs w283_p14_c01)
    plotted = [r for r in census_rows if r.get('plot_eligible') and r.get('weight_g') is not None]
    n_plotted = len(plotted)
    n_heavier_w279 = sum(1 for r in plotted if float(r['weight_g']) > w279_mass_g)
    pct_heavier_w279 = 100.0 * n_heavier_w279 / n_plotted
    median_g = float(market_sum['market_median_g'])
    pct_below_median = 100.0 * (median_g - w279_mass_g) / median_g

    fam_colors = {
        'Stainless steel': '#58a6ff',
        'Carbon / tool steel': '#ffa657',
        'PM tool steel': '#ff7b72',
        'Damascus / pattern steel': '#d2a8ff',
        'Steel, grade unspecified': '#8b949e',
        'Titanium / Ti composite': '#39d353',
        'Polymer / nonmetal': '#79c0ff',
    }
    for fam, col in fam_colors.items():
        sub = [r for r in plotted if r['material_family'] == fam]
        if not sub:
            continue
        ax1.scatter(
            [float(r['weight_g']) for r in sub],
            [float(r['blade_length_in']) for r in sub],
            c=col, s=46, alpha=0.80, edgecolors='#0d1117', linewidths=0.6,
            label=f"{fam} (n={len(sub)})", zorder=3,
        )

    # Commercial median line
    ax1.axvline(median_g, color='#ff7b72', linestyle='--', linewidth=1.4,
                label=f"Commercial Median: {median_g:.2f} g (n={n_plotted})")
    # w283 vertical line & star
    ax1.axvline(w279_mass_g, color='#ffd33d', linestyle='-', linewidth=1.5, alpha=0.85)
    ax1.scatter([w279_mass_g], [w279_blade_in], s=280, marker='*', color='#ffd33d',
                edgecolors='#f0f6fc', linewidths=1.3, zorder=8,
                label=f"Record {rec['label']}: {w279_mass_g:.3f} g ({w279_mass_3d_g:.3f} g 3D)")

    # Also plot historical g3 and B-rep RC C10a for context
    g3_pt = v1_winners[-2]
    ax1.scatter([g3_pt['mass_g']], [3.820], s=120, marker='P', color='#58a6ff',
                edgecolors='#f0f6fc', linewidths=1.0, zorder=7,
                label=f"Historical Wave 27 g3: {g3_pt['mass_g']:.2f} g")
    c10a_m = float(bench_doc['primary']['mass_g'])
    c10a_b = float(bench_doc['primary']['blade_length_in'])
    ax1.scatter([c10a_m], [c10a_b], s=115, marker='D', color='#3fb950',
                edgecolors='#f0f6fc', linewidths=1.0, zorder=7,
                label=f"SWITCHBACK C.10a RC4 (B-rep): {c10a_m:.3f} g")

    ax1.annotate(
        f"Record {rec['label']}\n"
        f"{w279_mass_g:.3f} g ({w279_mass_3d_g:.3f} g 3D)\n"
        f"• Lighter than {n_heavier_w279}/{n_plotted} ({pct_heavier_w279:.1f}%) knives\n"
        f"• {pct_below_median:.1f}% below {median_g:.2f} g median\n"
        f"• 16/16 gates PASS (G1={rec['g1']:.6f})",
        xy=(w279_mass_g, w279_blade_in),
        xytext=(52.0, 5.75),
        color='#f0f6fc',
        fontsize=8.0,
        fontweight='bold',
        bbox=dict(boxstyle='round,pad=0.45', facecolor='#161b22', edgecolor='#ffd33d', linewidth=1.4),
        arrowprops=dict(arrowstyle='->', color='#ffd33d', lw=1.5, connectionstyle='arc3,rad=0.12'),
        zorder=9,
    )

    ax1.set_title(f"(b) Market Comparison: {rec['label']} ({w279_mass_g:.3f} g) vs {n_plotted} Commercial Karambits",
                  fontsize=11.0, fontweight='bold', pad=10)
    ax1.set_xlabel('Published / Certified Knife Mass (g)', fontsize=10.5, fontweight='bold')
    ax1.set_ylabel('Blade Length (in, ≥ 3.375 in legal/utility floor)', fontsize=10.5, fontweight='bold')
    ax1.set_xlim(35, 430)
    ax1.set_ylim(3.25, 7.45)
    ax1.grid(True, color='#21262d', linestyle='--', linewidth=0.7, alpha=0.8)
    leg1 = ax1.legend(loc='upper right', facecolor='#0d1117', edgecolor='#30363d', fontsize=7.3)
    for txt in leg1.get_texts():
        txt.set_color('#c9d1d9')

    fig.suptitle(
        f"Historical pre-#82 model: selected titanium geometry at {w279_mass_g:.3f} g ({w279_mass_3d_g:.3f} g 3D) — {pct_below_median:.1f}% Below Market Median\nArchived screen observations; no currently certified all-16 winner",
        color='#f0f6fc', fontsize=12.2, fontweight='bold', y=0.98,
    )
    fig.tight_layout(rect=[0, 0, 1, 0.94])
    fig.savefig(fig_path, dpi=160, facecolor=fig.get_facecolor())
    plt.close(fig)

    figlib.write_manifest(str(fig_path), [str(p) for p in inputs] + [__file__], __file__)
    return fig_path


def make_w279_gate_margins_fig():
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    fig_path = OUT_DIR / 'fig_w279_gate_margins.png'

    ev, p_ev = _load_json('evidence/rs_v2/w282_ultrarunner/w282_p14_c01_cad_eval.json')
    d1, p_d1 = _load_json('evidence/rs_v2/w282_ultrarunner/w282_p14_c01_D1.json')
    gci, p_gci = _load_json('evidence/rs_v2/w282_ultrarunner/w282_p14_c01_plate_gci.json')
    a4, p_a4 = _load_json('evidence/rs_v2/w282_ultrarunner/w282_p14_c01_a4.json')
    st, p_st = _load_json('evidence/rs_v2/w282_ultrarunner/w282_p14_c01_solid_tip.json')
    bat, p_bat = _load_json('evidence/cad_battery/w282_p14_c01.json')
    inputs = [p_ev, p_d1, p_gci, p_a4, p_st, p_bat]

    em = ev['engineering_metrics']
    cad = ev['cad']
    ka = ev['karambit_archetype']
    mt = d1['metrics']
    gates_dict = ev['weighted_cad_score']['gates']
    assert len(gates_dict) == 16 and all(gates_dict.values()), 'Expected all 16 gates to pass'

    rel_mass_diff_pct = 100.0 * float(cad['rel_mass_diff'])
    dolfinx_err_pct = 100.0 * float(em['solid_tip_dolfinx_rel_err'])
    fine_gci_sf = float(gci['levels_fine_to_coarse'][0]['sf_hunter'])
    blade_min_in = float(ka['blade_min_in'])
    hook_drop_mm = float(ka['hook_drop_mm'])
    hausdorff_mm = float(mt['hausdorff'])
    seq_cert = float(em['seq_ratio_cert'])
    strict_lat_n = float(em['strict_lat_rob_0p0625_n'])
    cert_lat_n = float(em['lat_rob_cert_n'])
    ring_rob_n = float(em['ring_rob_cert_n'])
    tw_strict = float(em['twist_tipzone_sf_strict'])
    tw_tip = float(em['twist_tip_sf'])
    tw_body = float(em['twist_body_sf'])
    solid_tip_sf = float(em['solid_tip_sf_nodal_max'])
    a4_seq = float(a4['supported_seq_ratio'])
    a4_lam = float(a4['buckling_eigenvalue'])
    n_dof = int(st['stored_solid']['n_dof'])

    gate_rows = [
        ('1. failure_sequence_1p2 (Hand/Blade Yield Seq)', seq_cert / 1.20, f"seq = {seq_cert:.3f} ≥ 1.20 (+{100*(seq_cert/1.20 - 1):.2f}%)"),
        ('2. geometric_and_holder_gates (Blade & Sheath Box)', blade_min_in / 3.375, f"blade = {blade_min_in:.3f} in ≥ 3.375 in (+{100*(blade_min_in/3.375 - 1):.1f}%, box 199.8×99.8)"),
        ('3. cert_hunter_260n (Cert Hunter Lateral 0.25/0.125 mm²)', cert_lat_n / 260.0, f"{cert_lat_n:.1f} N ≥ 260 N (SF = {cert_lat_n/260.0:.3f}, +{100*(cert_lat_n/260.0 - 1):.1f}%)"),
        ('4. strict_hunter_260n (Strict 0.0625 mm² Hunter Lateral)', strict_lat_n / 260.0, f"{strict_lat_n:.1f} N ≥ 260 N (SF = {strict_lat_n/260.0:.4f}, +{100*(strict_lat_n/260.0 - 1):.1f}%)"),
        ('5. plate_gci_valid_3level (3-Mesh DKT+CST GCI Sequence)', fine_gci_sf / 1.00, f"3-level valid, fine SF = {fine_gci_sf:.3f} ≥ 1.00 (+{100*(fine_gci_sf - 1):.1f}%)"),
        ('6. twist_tip_submodel_strict_1p82nm (Strict 4–15 mm Tip Twist)', tw_strict / 1.00, f"SF = {tw_strict:.3f} ≥ 1.00 at 1.82 N·m (+{100*(tw_strict - 1):.1f}%)"),
        ('7. twist_tip_only_1p82nm (Cert Tip-Only Torsion 1.82 N·m)', tw_tip / 1.00, f"SF = {tw_tip:.3f} ≥ 1.00 at 1.82 N·m (+{100*(tw_tip - 1):.1f}%)"),
        ('8. solid_tip_3d_p2_1p82nm (3D P2 Solid-Tip Submodel)', solid_tip_sf / 1.00, f"SF = {solid_tip_sf:.4f} ≥ 1.00 ({n_dof:,} DOF, +{100*(solid_tip_sf - 1):.1f}%)"),
        ('9. cert_hiker_180n (Cert Hiker Lateral 180 N Floor)', cert_lat_n / 180.0, f"{cert_lat_n:.1f} N ≥ 180 N (SF = {cert_lat_n/180.0:.3f}, +{100*(cert_lat_n/180.0 - 1):.1f}%)"),
        ('10. karambit_ring_and_curved_claw (Ring & Hawkbill Claw)', hook_drop_mm / 25.0, f"hook = {hook_drop_mm:.1f} mm ≥ 25 mm (+{100*(hook_drop_mm/25.0 - 1):.1f}%, ring {ka['ring_id_mm']:.1f} mm)"),
        ('11. c6_aesthetic_floor (Rev C.6 Hausdorff & Groove)', 6.0 / hausdorff_mm, f"H = {hausdorff_mm:.3f} mm ≤ 6.0 mm ({6.0/hausdorff_mm:.2f}× margin, groove {ka['c6_ring_groove_w_mm']:.2f} mm)"),
        ('12. twist_body_1p82nm (Body Torsion r > 15 mm, 1.82 N·m)', tw_body / 1.00, f"SF = {tw_body:.3f} ≥ 1.00 (+{100*(tw_body - 1):.1f}%)"),
        ('13. side_a4_buckling_and_support (Winkler+Bore & Buckling)', a4_seq / 1.20, f"seq_a4 = {a4_seq:.3f} ≥ 1.20 (+{100*(a4_seq/1.20 - 1):.1f}%, λ_cr = {a4_lam:.2f})"),
        ('14. cad_watertight_and_single_solid (3D Solid B-Rep Parity)', 1.0 / max(rel_mass_diff_pct, 0.01), f"Δm = {rel_mass_diff_pct:.3f}% ≤ 1.00% (0 open/non-manifold edges)"),
        ('15. cert_ring_pull_1500n (Cert Ring Pull 1,500 N Floor)', ring_rob_n / 1500.0, f"{ring_rob_n:.1f} N ≥ 1,500 N (SF = {ring_rob_n/1500.0:.3f}, +{100*(ring_rob_n/1500.0 - 1):.1f}%)"),
        ('16. dolfinx_cross_check_2pct (DOLFINx vs scikit-fem Parity)', 2.0 / max(dolfinx_err_pct, 0.001), f"rel_err = {dolfinx_err_pct:.4f}% ≤ 2.00% ({2.0/max(dolfinx_err_pct, 0.001):.1f}× under cap)"),
    ]

    plt.rcParams.update({'font.sans-serif': 'DejaVu Sans', 'font.size': 9.5})
    fig, ax = plt.subplots(1, 1, figsize=(16.0, 7.8), dpi=160)
    fig.patch.set_facecolor('#0d1117')
    ax.set_facecolor('#161b22')
    for sp in ax.spines.values():
        sp.set_color('#30363d')
    ax.tick_params(colors='#c9d1d9')
    ax.xaxis.label.set_color('#e6edf3')
    ax.yaxis.label.set_color('#e6edf3')
    ax.title.set_color('#f0f6fc')

    labels = [r[0] for r in gate_rows]
    ratios = [r[1] for r in gate_rows]
    annots = [r[2] for r in gate_rows]
    y_pos = np.arange(len(gate_rows))

    disp_ratios = [min(r, 3.85) for r in ratios]
    colors = ['#3fb950' if r < 1.15 else ('#2ea043' if r < 2.0 else '#58a6ff') for r in ratios]

    bars = ax.barh(y_pos, disp_ratios, color=colors, edgecolor='#f0f6fc', linewidth=0.8, height=0.68, alpha=0.92, zorder=3)
    ax.axvline(1.0, color='#ff7b72', linestyle='--', linewidth=1.8, zorder=4, label='Hard Gate Pass Threshold (Ratio = 1.00× / 0% Reserve)')
    ax.axvspan(0.0, 1.0, color='#3d1a1f', alpha=0.32, zorder=1, label='Infeasible / Gate Reject Zone (< 1.00×)')

    for i, (bar, ratio, annot) in enumerate(zip(bars, ratios, annots)):
        x_end = bar.get_width()
        suffix = f"  [PASS: {annot}]"
        ax.text(x_end + 0.05, y_pos[i], suffix, va='center', ha='left', color='#f0f6fc', fontsize=8.4, fontweight='bold', zorder=5)

    ax.set_yticks(y_pos)
    ax.set_yticklabels(labels, fontsize=8.8, fontweight='bold')
    ax.invert_yaxis()
    ax.set_xlim(0.0, 6.75)
    ax.set_xlabel('Normalized Gate Safety Ratio (Achieved / Required Threshold; ≥ 1.00× Required to Pass)', fontsize=10.5, fontweight='bold')
    g1_val = float(bat['global_fitness']['G'])
    wcad_val = float(ev['weighted_cad_score']['W_CAD'])
    ax.set_title(
        f"Historical pre-#82 model: {ev['subject']} ({em['mass_g']:.3f} g 2.5D / {em['mass_3d_g']:.3f} g 3D Solid): All 16 Gates PASS (G1 = {g1_val:.6f}, W_CAD = +{wcad_val:.4f})\nArchived predicates; no currently certified all-16 winner",
        fontsize=11.2, fontweight='bold', pad=12,
    )
    ax.grid(True, axis='x', color='#21262d', linestyle='--', linewidth=0.7, alpha=0.8)
    leg = ax.legend(loc='upper right', facecolor='#0d1117', edgecolor='#30363d', fontsize=8.8)
    for txt in leg.get_texts():
        txt.set_color('#c9d1d9')

    fig.tight_layout()
    fig.savefig(fig_path, dpi=160, facecolor=fig.get_facecolor())
    plt.close(fig)

    figlib.write_manifest(str(fig_path), [str(p) for p in inputs] + [__file__], __file__)
    return fig_path


def _build_3d_tris_from_d1(d1_doc: dict):
    mesh = d1_doc['mesh']
    xy = np.asarray(mesh['xy'], dtype=np.float64)
    t_idx = np.asarray(mesh['tris'], dtype=np.int64)
    te = np.asarray(mesh['te'], dtype=np.float64)
    # Nodal half-thickness via averaging element thicknesses
    nodal_sum = np.zeros(len(xy), dtype=np.float64)
    nodal_cnt = np.zeros(len(xy), dtype=np.float64)
    for k in range(3):
        np.add.at(nodal_sum, t_idx[:, k], 0.5 * te)
        np.add.at(nodal_cnt, t_idx[:, k], 1.0)
    hz = nodal_sum / np.maximum(nodal_cnt, 1.0)
    verts_top = np.column_stack([xy[:, 0], xy[:, 1], hz])
    verts_bot = np.column_stack([xy[:, 0], xy[:, 1], -hz])
    tris_top = verts_top[t_idx]
    tris_bot = verts_bot[t_idx[:, [0, 2, 1]]]
    return np.concatenate([tris_top, tris_bot], axis=0), te


def make_web_studio_fig():
    """Render deterministic overview figure of the Vite+React+Three.js 3D CAD & Gate Scorecard Studio."""
    from matplotlib.collections import PolyCollection

    OUT_DIR.mkdir(parents=True, exist_ok=True)
    fig_path = OUT_DIR / 'fig_web_studio.png'

    ev, p_ev = _load_json('evidence/rs_v2/w283_ultrarunner/w283_p14_c01_cad_eval.json')
    rs, p_rs = _load_json('evidence/rs_v2/w283_p14_c01.json')
    bat, p_bat = _load_json('evidence/cad_battery/w283_p14_c01.json')
    d1, p_d1 = _load_json('evidence/rs_v2/w283_ultrarunner/w283_p14_c01_D1.json')
    p_gen = ROOT / 'evidence' / 'rs_v2' / 'w283_ultrarunner' / 'w283_p14_c01_genome.csv'
    inputs = [p_ev, p_rs, p_bat, p_d1, p_gen, ROOT / ev["cad"]["stl_path"]]

    gen_lines = p_gen.read_text(encoding='utf-8').strip().splitlines()
    gen_hdr = gen_lines[0].split(',')
    gen_val = gen_lines[1].split(',')
    edge_t_mm = float(gen_val[gen_hdr.index('edge_t')])

    from ops.render.engineering_gates_paper_figs import load_stl_any
    tris = load_stl_any(ROOT / ev['cad']['stl_path'])
    n_tris = int(ev['cad']['facets'])
    em = ev['engineering_metrics']
    wsc = ev['weighted_cad_score']
    g1_val = float(bat['global_fitness']['G'])

    plt.rcParams.update({'font.sans-serif': 'DejaVu Sans', 'font.size': 9.5})
    fig, (ax3d, ax_ui) = plt.subplots(1, 2, figsize=(17.6, 6.8), dpi=160, gridspec_kw={'width_ratios': [1.15, 1.0]})
    fig.patch.set_facecolor('#0d1117')

    # Left panel: 3D CAD Viewport isometric render of w283_p14_c01
    ax3d.set_facecolor('#161b22')
    for sp in ax3d.spines.values():
        sp.set_color('#30363d')
    v0, v1_v, v2 = tris[:, 0, :], tris[:, 1, :], tris[:, 2, :]
    normals = np.cross(v1_v - v0, v2 - v0)
    norms = np.linalg.norm(normals, axis=1, keepdims=True)
    normals = normals / np.maximum(norms, 1e-12)
    light_dir = np.array([0.38, -0.42, 0.82])
    light_dir /= np.linalg.norm(light_dir)
    intensity = np.clip(0.28 + 0.72 * np.abs(normals @ light_dir), 0.18, 1.0)
    base_rgb = np.array([0.38, 0.75, 0.98])

    # Isometric camera rotation (elev=28 deg, azim=-32 deg)
    az = np.deg2rad(-32.0)
    el = np.deg2rad(28.0)
    ca, sa = np.cos(az), np.sin(az)
    ce, se = np.cos(el), np.sin(el)
    rot_z = np.array([[ca, -sa, 0.0], [sa, ca, 0.0], [0.0, 0.0, 1.0]])
    rot_x = np.array([[1.0, 0.0, 0.0], [0.0, ce, -se], [0.0, se, ce]])
    rot = rot_x @ rot_z

    pts_rot = tris @ rot.T
    depths = pts_rot[:, :, 2].mean(axis=1)
    order = np.argsort(depths)
    polys_2d = pts_rot[order, :, :2]
    int_ord = intensity[order]
    face_colors = np.column_stack([
        np.clip(base_rgb[0] * int_ord, 0, 1),
        np.clip(base_rgb[1] * int_ord, 0, 1),
        np.clip(base_rgb[2] * int_ord, 0, 1),
        np.full(len(tris), 0.98),
    ])

    poly = PolyCollection(polys_2d, facecolors=face_colors, edgecolors='none', linewidths=0.0, zorder=3)
    ax3d.add_collection(poly)
    all_2d = polys_2d.reshape(-1, 2)
    mins, maxs = all_2d.min(axis=0), all_2d.max(axis=0)
    pad_x = 0.08 * (maxs[0] - mins[0])
    pad_y = 0.12 * (maxs[1] - mins[1])
    ax3d.set_xlim(mins[0] - pad_x, maxs[0] + pad_x)
    ax3d.set_ylim(mins[1] - pad_y, maxs[1] + pad_y)
    ax3d.set_aspect('equal', adjustable='datalim')
    ax3d.tick_params(colors='#8b949e', labelsize=8.0)
    ax3d.set_xlabel('Isometric X′ Projection (mm)', color='#c9d1d9', fontsize=9.5, fontweight='bold')
    ax3d.set_ylabel('Isometric Y′ Projection (mm)', color='#c9d1d9', fontsize=9.5, fontweight='bold')
    ax3d.grid(True, color='#21262d', linestyle='--', linewidth=0.7, alpha=0.75, zorder=1)
    ax3d.text(
        0.02, 0.96,
        f"Web Studio 3D Viewport · {ev['subject']}.stl\n"
        f"• {n_tris:,} STL triangles · 0 open / 0 non-manifold edges\n"
        f"• 3D Solid: {em['mass_3d_g']:.3f} g vs 2.5D Raster: {em['mass_g']:.3f} g (Δ={100*ev['cad']['rel_mass_diff']:.3f}%)\n"
        f"• Measured exported apex = {rs['export_measurements']['sharpness']['max_apex_mm']:.3f} mm (limit 0.20 mm)",
        transform=ax3d.transAxes, va='top', ha='left', color='#f0f6fc', fontsize=8.3, fontweight='bold',
        bbox=dict(boxstyle='round,pad=0.45', facecolor='#0d1117', edgecolor='#58a6ff', linewidth=1.3),
        zorder=6,
    )
    ax3d.set_title(
        f"(a) Web Studio 3D CAD Viewport — {ev['subject']} ({n_tris:,} STL Facets, Watertight B-Rep)",
        color='#f0f6fc', fontsize=11.0, fontweight='bold', pad=10,
    )

    # Right panel: Interactive Gate Scorecard & RS-karambit-v2 Inspector
    ax_ui.set_facecolor('#161b22')
    for sp in ax_ui.spines.values():
        sp.set_color('#30363d')
    ax_ui.set_xticks([])
    ax_ui.set_yticks([])
    ax_ui.set_xlim(0, 100)
    ax_ui.set_ylim(0, 100)
    ax_ui.set_title(
        f"(b) Committed corrected certificate — RS-v2 all_hard = {rs['all_hard']}",
        color='#f0f6fc', fontsize=11.0, fontweight='bold', pad=10,
    )

    cards = [
        ('Rejected Subject', f"{ev['subject']} (Wave 283)", '#ffd33d'),
        ('2.5D / 3D Solid Mass', f"{em['mass_g']:.3f} g / {em['mass_3d_g']:.3f} g (Δ={100*ev['cad']['rel_mass_diff']:.3f}%)", '#3fb950'),
        ('Locked Global Fitness G1', f"{g1_val:.6f} (COMPLETE)", '#d2a8ff'),
        ('Weighted CAD Score W_CAD', f"{wsc['W_CAD']:+.4f} ({sum(wsc['gates'].values())}/16 pass)", '#58a6ff'),
        ('RS-karambit-v2 Hard Gates', f"{sum(v=='pass' for v in rs['gates'].values())}/10 pass (all_hard = {rs['all_hard']})", '#ff7b72'),
        ('18-Evaluator CAD Battery', f"{bat['pass_count']} pass / {len(bat['cases'])} cases", '#79c0ff'),
    ]
    for idx_c, (k_lbl, v_lbl, col_c) in enumerate(cards):
        col_i = idx_c % 2
        row_i = idx_c // 2
        x0 = 3 + col_i * 48.5
        y0 = 82 - row_i * 14.5
        rect = plt.Rectangle((x0, y0), 45.5, 12.2, facecolor='#0d1117', edgecolor=col_c, linewidth=1.3, zorder=3)
        ax_ui.add_patch(rect)
        ax_ui.text(x0 + 2.2, y0 + 8.3, k_lbl.upper(), color='#8b949e', fontsize=7.5, fontweight='bold', zorder=4)
        ax_ui.text(x0 + 2.2, y0 + 3.0, v_lbl, color=col_c, fontsize=8.8, fontweight='bold', zorder=4)

    st = ev['export_measurements']; solid = json.loads((ROOT / rs['solid_tip_source']).read_text())['stored_solid']
    rsv2_rows = [
        ('strict_hunter_lateral', f"Strict lateral: {rs['strict_lat_rob_0p0625_n']:.1f} N / 260 N"),
        ('solid_tip_sf', f"Solid tip: SF {rs['solid_tip_sf']:.4f} / 1.0 ({solid['n_dof']:,} DOF)"),
        ('seq_hard', f"Sequence: {rs['seq_ratio']:.4f} / 1.20"),
        ('human_max', f"Human max twist / spine: {rs['hm_twist_sf']:.4f} / {rs['hm_spine_sf']:.4f}"),
        ('fatigue', f"Fatigue: {rs['fat_sf']:.4f} / 1.0"),
        ('gate_s_sharp_law', f"Actual apex: {st['sharpness']['max_apex_mm']:.3f} mm / 0.20 mm"),
        ('gate_s_tip_point_brep', f"Point monotonic 0–10 mm: {st['point']['monotonic']}"),
    ]
    for idx_r, (key, text) in enumerate(rsv2_rows):
        state = rs['gates'][key]
        col = '#3fb950' if state == 'pass' else '#ff7b72'
        ax_ui.text(3.5, 46.0-idx_r*6.2, f"{state.upper()}: {text}", color=col, fontsize=8.5, fontweight='bold')

    fig.suptitle(
        "Committed Wave 283 re-certification: exported CAD and measured gate failures",
        color='#f0f6fc', fontsize=12.2, fontweight='bold', y=0.98,
    )
    fig.tight_layout(rect=[0, 0, 1, 0.94])
    fig.savefig(fig_path, dpi=160, facecolor=fig.get_facecolor())
    plt.close(fig)

    figlib.write_manifest(str(fig_path), [str(p) for p in inputs] + [__file__], __file__)
    return fig_path


def main():
    p1 = make_readme_hero_fig()
    p2 = make_why_this_matters_fig()
    p3 = make_w279_gate_margins_fig()
    p4 = make_web_studio_fig()
    for p in (p1, p2, p3, p4):
        print('generated:', p.relative_to(ROOT))


if __name__ == '__main__':
    main()

