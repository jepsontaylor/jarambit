#!/usr/bin/env python3
"""Render the #87 historical failure snapshot, never a new certificate.

All observations must match HEAD blobs and the original host capture hashes.
The ledger retains JSON pointers and explicit reductions for every plotted value.
"""
import hashlib
import json
from pathlib import Path
import subprocess
import sys

import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import numpy as np

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT / 'ops/wave_figures'))
import figlib

SNAPSHOT = 'evidence/evolution_plateau/2026-10-17'
WAVES = [('xbabe2', 'w298', True), ('xbabe3', 'w401c3', True),
         ('xbabe2', 'w300', False), ('xbabe3', 'w402c3', False)]
COLORS = ['#007f86', '#7252a2', '#b77b26', '#ad4e43']


def main():
    inputs = set()
    documents = {}
    points = []

    def read(name):
        if name not in documents:
            raw = (ROOT / name).read_bytes()
            committed = subprocess.check_output(['git', 'show', 'HEAD:' + name], cwd=ROOT)
            if raw != committed:
                raise ValueError('Observation differs from committed HEAD: ' + name)
            inputs.add(ROOT / name)
            documents[name] = json.loads(raw)
        return documents[name]

    def point(source, pointer, value, **context):
        points.append(dict(source=source, pointer=pointer, value=value, **context))
        return value

    # Verify the complete captured file inventory, including files not plotted.
    for host in ['xbabe2', 'xbabe3']:
        manifest = read(f'{SNAPSHOT}/{host}/snapshot_manifest.json')
        for entry in manifest['files']:
            name = f'{SNAPSHOT}/{host}/' + entry['path']
            raw = (ROOT / name).read_bytes()
            if raw != subprocess.check_output(['git', 'show', 'HEAD:' + name], cwd=ROOT):
                raise ValueError('Capture differs from HEAD: ' + name)
            if len(raw) != entry['bytes'] or hashlib.sha256(raw).hexdigest() != entry['sha256']:
                raise ValueError('Capture hash mismatch: ' + name)
            inputs.add(ROOT / name)

    rounds, assessments, summaries = [], [], []
    for host, wave, complete in WAVES:
        folder = ROOT / SNAPSHOT / host / 'out' / wave
        prefix = str(folder.relative_to(ROOT))
        for file in sorted(folder.glob('round_*_screen.json')):
            source = str(file.relative_to(ROOT))
            screen = read(source)
            birth_source = source.replace('_screen.json', '_births.json')
            birth = read(birth_source)
            rnd = point(birth_source, '/round', birth['round'], wave=wave, metric='round')
            n = point(birth_source, '/genomes', len(birth['genomes']), reduction='array length', wave=wave, metric='births')
            eligible = point(source, '', len(screen), reduction='array length', wave=wave, metric='rankable')
            deficit = point(source, '/0/screen_deficit', screen[0]['screen_deficit'], wave=wave, metric='best coarse deficit')
            pointers = [f'/genomes/{i}/row' for i in range(n)]
            unique = len({r['row'] for r in birth['genomes']})
            points.append(dict(source=birth_source, pointers=pointers, reduction='distinct values', value=unique, wave=wave, metric='distinct CSV rows'))
            families = {}
            for family in ['p10', 'p14', 'control']:
                count = sum(r['family'] == family for r in birth['genomes'])
                points.append(dict(source=birth_source, pointers=[f'/genomes/{i}/family' for i in range(n)],
                                   reduction='count equal', equals=family, value=count, wave=wave, metric='birth family'))
                families[family] = count
            rounds.append(dict(wave=wave, round=rnd, complete=complete, n=n, eligible=eligible,
                               unique=unique, deficit=deficit, families=families))
        scores = sorted(folder.glob('by-content/*/*/*_master_scorecard.json'))
        for file in scores:
            source = str(file.relative_to(ROOT)); score = read(source)
            rs_source = source.replace('_master_scorecard.json', '_rs.json'); rs = read(rs_source)
            if score['weighted_cad_score']['all_engineering_gates_pass'] or rs['all_hard']:
                raise ValueError('This failure-snapshot plot requires reassessment of its scope')
            metrics = {}
            for name in ['mass_g', 'solid_tip_sf', 'hm_twist_sf', 'hm_spine_sf', 'fat_sf', 'twist_tipzone_sf_strict']:
                metrics[name] = point(rs_source, '/' + name, rs[name], wave=wave, subject=rs['label'], metric=name)
            metrics['strict_hunter_sf'] = point(source, '/engineering_metrics/sf_hunter_strict',
                score['engineering_metrics']['sf_hunter_strict'], wave=wave, subject=rs['label'], metric='strict_hunter_sf')
            assessments.append(dict(wave=wave, **metrics))
        summaries.append(dict(wave=wave, snapshot='final leaderboard' if complete else 'partial capture',
                              captured_assessments=len(scores), scorecards=[str(f.relative_to(ROOT)) for f in scores]))
        if complete:
            board_source = prefix + '/leaderboard.json'; board = read(board_source)
            for key in ['assessed_count', 'qualified_count', 'champion', 'unverified']:
                point(board_source, '/' + key, board[key], wave=wave, metric=key)
            if board['assessed_count'] != len(scores) or board['qualified_count'] != 0 or board['champion'] is not None or board['unverified']:
                raise ValueError('Final leaderboard does not match captured failed assessments')

    plt.rcParams.update({'font.family':'DejaVu Sans', 'font.size':9,
        'axes.spines.top':False, 'axes.spines.right':False, 'grid.alpha':.2,
        'figure.facecolor':'#faf9f5', 'axes.facecolor':'#faf9f5', 'savefig.facecolor':'#faf9f5'})
    fig, axs = plt.subplots(2, 2, figsize=(11.5, 8.5))
    for (host, wave, complete), color in zip(WAVES, COLORS):
        series = [r for r in rounds if r['wave'] == wave]
        axs[0, 0].plot([r['round'] + 1 for r in series], [r['deficit'] for r in series],
            'o-' if complete else 'x', color=color, label=wave + ('' if complete else ' (partial)'))
        selected = [a for a in assessments if a['wave'] == wave]
        if selected:
            axs[0, 1].scatter([a['mass_g'] for a in selected], [a['solid_tip_sf'] for a in selected],
                color=color, marker='o' if complete else 'x', label=wave + ('' if complete else '*'), s=38, alpha=.85)
    axs[0, 0].set(title='(a) Best coarse shortfall by proposal round', xlabel='Round (stored index + 1)', ylabel='Shortfall sum D (lower is better)', xticks=[1, 2, 3])
    axs[0, 0].legend(fontsize=8); axs[0, 0].grid()
    axs[0, 1].axhline(1, ls='--', color='#ad4e43', label='Unchanged SF = 1 floor')
    axs[0, 1].set(title='(b) Retained independent assessments', xlabel='Raster mass (g)', ylabel='Solid-tip SF', ylim=(.60, 1.04))
    axs[0, 1].legend(fontsize=8, loc='upper right'); axs[0, 1].grid()
    axs[0, 1].text(.04, .45, 'Selected failures; not a population sample\nSnapshot omits raw solver/mesh sidecars', transform=axs[0, 1].transAxes, fontsize=8)

    x = np.arange(len(rounds)); bottom = np.zeros(len(rounds))
    for family, color in [('p10', '#007f86'), ('p14', '#7252a2'), ('control', '#b77b26')]:
        values = [r['families'][family] for r in rounds]
        axs[1, 0].bar(x, values, bottom=bottom, color=color, label=family); bottom += values
    for i, r in enumerate(rounds):
        axs[1, 0].text(i, r['n'] + 2, f"{r['unique']}/{r['n']}", ha='center', fontsize=8)
    axs[1, 0].set_xticks(x, [r['wave'] + ('*' if not r['complete'] else '') + '\nr' + str(r['round'] + 1) for r in rounds], fontsize=8)
    axs[1, 0].set(title='(c) Birth-family loss; labels = distinct rows / births', ylabel='Generated birth instances', ylim=(0, 116))
    axs[1, 0].legend(ncol=3, fontsize=8); axs[1, 0].grid(axis='y')
    metric_names = [('hm_twist_sf', 'Human twist'), ('hm_spine_sf', 'Human spine'),
        ('fat_sf', 'Fatigue'), ('twist_tipzone_sf_strict', 'Strict tip twist'),
        ('solid_tip_sf', 'Solid tip'), ('strict_hunter_sf', 'Strict lateral')]
    for i, (key, label) in enumerate(metric_names):
        values = [a[key] for a in assessments]
        axs[1, 1].plot([min(values), max(values)], [i, i], color='#a9b5b8', lw=3)
        axs[1, 1].scatter(values, i + np.linspace(-.15, .15, len(values)), s=22,
            c=[COLORS[next(j for j, w in enumerate(WAVES) if w[1] == a['wave'])] for a in assessments], zorder=3)
    axs[1, 1].axvline(1, ls='--', color='#ad4e43')
    axs[1, 1].set_yticks(range(len(metric_names)), [v for _, v in metric_names], fontsize=8)
    axs[1, 1].set(title=f'(d) Physical deficits across all {len(assessments)} retained assessments', xlabel='SF (each stated floor = 1); vertical offsets are layout', xlim=(0, 1.05))
    axs[1, 1].grid(axis='x')
    fig.suptitle('Historical plateau snapshot · captured 17 October 2026, 08:02 UTC\nNo qualified design; partial captures marked *; source/model identities remain separate', fontsize=12)
    fig.text(.01, .012, 'Raw JSON observations only · coarse rank is not certification · family labels are not genotype distances · no new solves', fontsize=8, color='#9b4c36')
    fig.tight_layout(rect=(0, .035, 1, .98), h_pad=2.2, w_pad=2)
    out = ROOT / 'docs/figures/engineering_gates'; out.mkdir(parents=True, exist_ok=True)
    figure = out / 'fig_plateau_history.png'; fig.savefig(figure, dpi=145); plt.close(fig)
    ledger = out / 'plateau_points.json'
    ledger.write_text(json.dumps({'schema':1, 'scope':'Historical diagnostic capture, not current certificates or fresh solves',
        'snapshot':SNAPSHOT, 'waves':summaries, 'points':points}, indent=1, sort_keys=True) + '\n')
    inputs.update([Path(__file__).resolve(), ledger, ROOT / SNAPSHOT / 'summarize.py', ROOT / 'requirements/RS-karambit-v2.toml'])
    figlib.write_manifest(str(figure), sorted(inputs), str(Path(__file__).resolve()), extra={
        'command':'python3 ops/render/paper/plateau.py', 'point_ledger':str(ledger.relative_to(ROOT)),
        'scope':'Historical failures, no re-certification; raw solver/export sidecars are not captured',
        'runtime':{'matplotlib':matplotlib.__version__, 'numpy':np.__version__}})
    print(f'{len(rounds)} captured rounds; {len(assessments)} failed assessments; {len(points)} traced observations')


if __name__ == '__main__':
    main()
