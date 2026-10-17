#!/usr/bin/env python3
"""Plot the committed #84 proof, including its failed qualification.

This is one retained round, not a multi-wave record or a post-merge new solve.
Every plotted observation carries a committed file and JSON pointer in the ledger.
"""
import json
import subprocess
import sys
from pathlib import Path

import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import numpy as np

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT / 'ops/wave_figures'))
import figlib

OUT = ROOT / 'docs/figures/engineering_gates'
INPUTS = set()
POINTS = []


def read(name):
    path = ROOT / name
    subprocess.run(['git', 'ls-files', '--error-unmatch', name], cwd=ROOT,
                   check=True, stdout=subprocess.DEVNULL)
    INPUTS.add(path)
    return json.loads(path.read_text())


def observation(name, pointer, value, **context):
    POINTS.append(dict(source=name, pointer=pointer, value=value, **context))
    return value


def main():
    proof_path = 'evidence/evolve_certifiable/manifest.json'
    proof = read(proof_path)['automatic']
    paths = proof['artifacts']
    births_path = 'evidence/evolve_certifiable/automatic/round_00_births.json'
    screen_path = 'evidence/evolve_certifiable/automatic/round_00_screen.json'
    births = read(births_path)
    screen = read(screen_path)
    board = read(paths['leaderboard'])
    score = read(paths['scorecard'])
    primary = read(paths['skfem_raw'])
    independent = read(paths['dolfinx_raw'])
    assert board['qualified_count'] == 0 and board['champion'] is None
    assert len(screen) == len(births['genomes']) == 7
    assert sorted(r['certificate_identity'] for r in screen) == sorted(
        r['certificate_identity'] for r in births['genomes'])
    POINTS.append(dict(source=births_path,
                       pointers=[f'/genomes/{i}/certificate_identity' for i in range(len(births['genomes']))],
                       reduction='distinct content identities', value=len({r['certificate_identity'] for r in births['genomes']})))
    observation(paths['leaderboard'], '/champion', board['champion'], panel='b annotation')

    plt.rcParams.update({'font.family':'DejaVu Sans', 'font.size':9,
                         'axes.spines.top':False, 'axes.spines.right':False,
                         'figure.facecolor':'#faf9f5', 'axes.facecolor':'#faf9f5',
                         'text.color':'#243641', 'axes.labelcolor':'#243641',
                         'savefig.facecolor':'#faf9f5'})
    fig, axs = plt.subplots(2, 2, figsize=(12, 9),
                            gridspec_kw={'height_ratios':[1, 1.8]})
    masses = []
    deficit_axis = axs[0, 0].twiny()
    for i, row in enumerate(screen):
        mass = observation(screen_path, f'/{i}/mass_g', row['mass_g'],
                           panel='a', label=row['label'])
        deficit = observation(screen_path, f'/{i}/screen_deficit', row['screen_deficit'],
                              panel='a', label=row['label'])
        masses.append(mass)
        selected = row['certificate_identity'] == proof['certificate_identity']
        axs[0, 0].scatter(mass, i, s=85 if selected else 35,
                          marker='*' if selected else 'o',
                          color='#bf4b36' if selected else '#007f86', zorder=3)
        deficit_axis.scatter(deficit, i, marker='x', color='#b57837', s=30)
    median = float(np.median(masses))
    axs[0, 0].axvline(median, color='#657786', ls='--', lw=1)
    POINTS.append(dict(panel='a', source=screen_path,
                       pointers=[f'/{i}/mass_g' for i in range(len(screen))],
                       reduction='median of seven retained screen instances', value=median))
    axs[0, 0].set_title('(a) Seven screen instances / six genomes', pad=34)
    axs[0, 0].set(xlabel=f'Mass (g), dots / dashed median {median:.3f} g',
                   ylim=(6.6, -.6), xlim=(81.8, 83.25))
    axs[0, 0].set_yticks(range(len(screen)), [r['label'].rsplit('_', 1)[-1]
                           + (' *' if r['certificate_identity']==proof['certificate_identity'] else '')
                           for r in screen], fontsize=8)
    deficit_axis.set(xlabel='Shortfall sum, crosses (lower is better)', xlim=(2.9, 4))
    deficit_axis.xaxis.label.set_color('#9b642e')
    axs[0, 0].grid(alpha=.2)

    counts = [len(births['genomes']), len(screen), board['assessed_count'],
              len(board['unverified']), board['qualified_count']]
    for source, pointer, value in zip(
            [births_path, screen_path] + [paths['leaderboard']] * 3,
            ['/genomes', '', '/assessed_count', '/unverified', '/qualified_count'], counts):
        observation(source, pointer, value, panel='b',
                    reduction='array length' if pointer in ['/genomes', '', '/unverified'] else 'identity')
    ax = axs[0, 1]
    ax.bar(range(5), counts, color=['#aab9b8', '#007f86', '#5667ac', '#c58a55', '#bf4b36'])
    ax.set_xticks(range(5), ['Births', 'Screened', 'Assessed', 'Unverified', 'Qualified'], fontsize=8)
    for i, value in enumerate(counts):ax.text(i, value+.12, str(value), ha='center')
    ax.set(title='(b) Completion does not imply qualification', ylabel='Retained instances', ylim=(0, 8))
    ax.text(.98, .91, 'champion = null', transform=ax.transAxes, ha='right', color='#bf4b36')

    gates = score['weighted_cad_score']['gates']
    ordered = [
        'cad_watertight_and_single_solid', 'geometric_and_holder_gates',
        'karambit_ring_and_curved_claw', 'c6_aesthetic_floor',
        'cert_hiker_180n', 'cert_hunter_260n', 'strict_hunter_260n',
        'cert_ring_pull_1500n', 'twist_body_1p82nm', 'twist_tip_only_1p82nm',
        'twist_tip_submodel_strict_1p82nm', 'solid_tip_3d_p2_1p82nm',
        'side_a4_buckling_and_support', 'failure_sequence_1p2',
        'plate_gci_valid_3level', 'dolfinx_cross_check_2pct']
    assert set(ordered) == set(gates)
    ax = axs[1, 0]
    for i, key in enumerate(ordered):
        val = observation(paths['scorecard'], '/weighted_cad_score/gates/'+key,
                          gates[key], panel='c')
        ax.text(.01, i, f'{i+1:02d}  '+key, va='center', fontsize=7.5)
        ax.text(.98, i, 'PASS' if val else 'FAIL', ha='right', va='center',
                weight='bold', color='#007f86' if val else '#bf4b36', fontsize=8)
    for boundary in [1.5, 3.5, 11.5, 12.5, 13.5]:
        ax.axhline(boundary, color='#cdd5d3', lw=.6)
    ax.set(xlim=(0, 1), ylim=(15.8, -.8), title='(c) Actual W_CAD_v2 predicates: 10/16')
    ax.axis('off')

    m = score['engineering_metrics']
    metrics = [('Strict lateral / 260 N', 'strict_lat_rob_0p0625_n', 260),
               ('Tip twist / required SF', 'twist_tip_sf', 1),
               ('Strict tip twist / required SF', 'twist_tipzone_sf_strict', 1),
               ('Solid-tip / required SF', 'solid_tip_sf_nodal_max', 1),
               ('Sequence / 1.20', 'seq_ratio_cert', 1.2),
               ('L7 fatigue / required SF', 'fat_sf_l7', 1)]
    ax = axs[1, 1]
    for i, (label, key, floor) in enumerate(metrics):
        value = observation(paths['scorecard'], '/engineering_metrics/'+key, m[key],
                            panel='d', divisor=floor, plotted_ratio=m[key]/floor)
        ax.barh(i, value/floor, color='#007f86' if value >= floor else '#bf4b36', height=.55)
        ax.text(value/floor+.025, i, f'{value/floor:.3f}', va='center', fontsize=8)
    ax.axvline(1, ls='--', lw=1, color='#243641')
    ax.set_yticks(range(len(metrics)), [r[0] for r in metrics], fontsize=8)
    ax.set(ylim=(6.3, -.8), xlim=(0, 1.48), xlabel='Observed / required (≥ 1)',
           title='(d) Selected physical margins; fatigue is RS-v2')
    sf_primary = observation(paths['skfem_raw'], '/solid/SF_solid_nodal_max',
                             primary['solid']['SF_solid_nodal_max'], panel='d annotation')
    observation(paths['dolfinx_raw'], '/SF_nodal_max', independent['SF_nodal_max'], panel='d annotation')
    ax.text(.02, .02, f"Same-mesh solid SF: skfem {sf_primary:.4f}, "
            f"DOLFINx {independent['SF_nodal_max']:.4f}\nAgreement verifies the comparison; both SFs fail strength.",
            transform=ax.transAxes, fontsize=8, color='#bf4b36')
    fig.suptitle('Committed automatic-assessment proof / no certified winner', weight='bold', fontsize=14)
    fig.text(.02, .015, 'One pre-merge proof committed with #84; not a post-merge evolution wave. '
             'Historical w282 trajectories are reported separately.', fontsize=9, color='#9b4c36')
    fig.tight_layout(rect=(0, .04, 1, .96), w_pad=2.5, h_pad=2)
    OUT.mkdir(parents=True, exist_ok=True)
    output = OUT/'fig_certifiable_pipeline.png'
    fig.savefig(output, dpi=150)
    plt.close(fig)
    ledger = OUT/'certifiable_points.json'
    ledger.write_text(json.dumps({'schema':1, 'scope':'Retained #84 proof; no new solve or qualified winner',
        'missing':'Only one round and one independent assessment; no post-merge winner, population fitness series or full-population 16-gate rates.',
        'points':POINTS}, indent=1, sort_keys=True)+'\n')
    figlib.write_manifest(str(output), sorted(INPUTS)+[Path(__file__).resolve(), ledger], __file__,
                          extra={'point_ledger':str(ledger.relative_to(ROOT)),
                                 'runtime':{'numpy':np.__version__, 'matplotlib':matplotlib.__version__},
                                 'status':'No qualified winner; champion=null',
                                 'command':'python3 ops/render/paper/certifiable.py'})
    print(output.relative_to(ROOT), len(POINTS), 'traced observations')


if __name__ == '__main__':main()
