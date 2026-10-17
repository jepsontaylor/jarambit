#!/usr/bin/env python3
"""Render retained populations, never infer a population from selected winners.

Run from any directory: python3 ops/render/paper/populations.py
The point ledger records source files, CSV line numbers / JSON pointers and reductions.
All observation inputs must be git tracked. No current certification is inferred.
"""
import csv
import json
import subprocess
import sys
from collections import defaultdict
from pathlib import Path

import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import numpy as np

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT / 'ops/wave_figures'))
import figlib

OUT = ROOT / 'docs/figures/engineering_gates'
SCRIPT = Path(__file__).resolve()
INPUTS = set()
LEDGER = {}
COLORS = ['#007f86', '#e07b39', '#5667ac', '#9b4c75', '#536e45', '#657786']


def tracked(path):
    path = ROOT / path
    subprocess.run(['git', 'ls-files', '--error-unmatch', str(path.relative_to(ROOT))],
                   cwd=ROOT, check=True, stdout=subprocess.DEVNULL)
    INPUTS.add(path)
    return path


def js(path):
    return json.loads(tracked(path).read_text())


def csv_rows(path):
    with tracked(path).open() as stream:
        return list(csv.DictReader(stream))


def style():
    plt.rcParams.update({'font.family': 'DejaVu Sans', 'font.size': 9,
                         'axes.spines.top': False, 'axes.spines.right': False,
                         'axes.labelcolor': '#243641', 'text.color': '#243641',
                         'axes.titleweight': 'bold', 'grid.alpha': .2,
                         'figure.facecolor': '#faf9f5', 'axes.facecolor': '#faf9f5',
                         'savefig.facecolor': '#faf9f5'})


def save(fig, name, points):
    fig.text(.01, .008, 'HISTORICAL OBSERVATIONS • no currently certified all-gates winner',
             fontsize=8, color='#9b4c36')
    fig.tight_layout(rect=(0, .035, 1, .98))
    path = OUT / (name + '.png')
    fig.savefig(path, dpi=150)
    plt.close(fig)
    LEDGER[path.name] = points


def trajectories(pop):
    fig, axs = plt.subplots(2, 2, figsize=(10.6, 7.2))
    groups = defaultdict(list)
    for i, row in enumerate(pop):
        groups[int(row['gen'])].append((i, row))
    points = []
    gens = sorted(groups)
    stats = []
    for gen in gens:
        rows = groups[gen]
        mass = [r['mass_g'] for _, r in rows]
        fit = [r['fit'] for _, r in rows]
        s = dict(gen=gen, n=len(rows), min_mass=float(min(mass)),
                 median_mass=float(np.median(mass)), max_fit=float(max(fit)),
                 median_fit=float(np.median(fit)))
        points.append({**s, 'source': POP, 'pointers': [f'/{i}' for i, _ in rows],
                       'scope': 'fresh evaluated births, including rejected candidates; not survivor population'})
        stats.append(s)
    for ax, lo, hi, label in [(axs[0, 0], 'min_mass', 'median_mass', 'Mass (g)'),
                               (axs[0, 1], 'max_fit', 'median_fit', 'Search fitness (dimensionless)')]:
        ax.plot(gens, [s[lo] for s in stats], 'o-', color=COLORS[0], label=lo.replace('_', ' '))
        ax.plot(gens, [s[hi] for s in stats], 's--', color=COLORS[1], label=hi.replace('_', ' '))
        ax.set(xlabel='Generation', ylabel=label)
        ax.grid(); ax.legend(fontsize=8)
    axs[0, 0].set_title(f'(a) w282 • all {len(pop):,} retained fresh evaluations')
    axs[0, 1].set_title('(b) w282 • fitness includes infeasible candidates')
    paths = [('w6', 'docs/crescent/history.csv'),
             ('w13', 'docs/lattice/wave13_c6/history.csv'),
             ('w15', 'docs/lattice/wave15_c6_long/history.csv'),
             ('w16', 'docs/lattice/wave16_c6_through4/history.csv'),
             ('w272/s2902', 'evidence/rs_v2/w272_xbabe3/s2902/history.csv'),
             ('w273/s2904', 'evidence/rs_v2/w273_xbabe3/s2904/history.csv')]
    for (label, path), color in zip(paths, COLORS):
        grouped = defaultdict(list)
        for i, row in enumerate(csv_rows(path), 2):
            grouped[int(row['gen'])].append((i, row))
        xs, ms, fs = [], [], []
        for gen, rows in sorted(grouped.items()):
            # The retained mass belongs to the fitness champion, not the lightest birth.
            winner = max(rows, key=lambda ir: float(ir[1]['best_fit']))
            xs.append(gen); ms.append(float(winner[1]['best_mass_g']))
            fs.append(float(winner[1]['best_fit']))
            points.append(dict(series=label, gen=gen, mass=ms[-1], fit=fs[-1],
                               source=path, csv_line=winner[0],
                               reduction='highest best_fit among island champions; median unavailable'))
        axs[1, 0].plot(xs, ms, color=color, label=label)
        axs[1, 1].plot(xs, fs, color=color, label=label)
    axs[1, 0].set(title='(c) Earlier runs • mass of best-fitness island champion',
                   xlabel='Generation', ylabel='Mass (g)')
    axs[1, 1].set(title='(d) Earlier runs • native historical fitness scales',
                   xlabel='Generation', ylabel='Best fitness (not comparable across objectives)')
    for ax in axs[1]: ax.grid(); ax.legend(ncol=2, fontsize=7)
    save(fig, 'fig_population_trajectories', points)


def diversity(pop):
    rows = csv_rows(CSV_POP)
    header = list(rows[0]); genes = header[header.index('cp00'):header.index('material')]
    matrix = np.array([[float(r[k]) for k in genes] for r in rows])
    span = np.ptp(matrix, axis=0)
    active = span > 0
    normalized = matrix[:, active] / span[active]
    fig, axs = plt.subplots(1, 3, figsize=(10.6, 3.8)); points = []
    gens = sorted({int(r['gen']) for r in rows})
    for gen in gens:
        ii = [i for i, r in enumerate(rows) if int(r['gen']) == gen]
        x = normalized[ii]
        # Mean squared pairwise RMS distance, evaluated without sampling.
        n = len(x)
        d = float(np.sqrt(2 * n / (n - 1) * np.var(x, axis=0).mean())) if n > 1 else None
        relief = [float(rows[i]['relief_frac']) for i in ii]
        nov = [float(rows[i]['novelty']) for i in ii]
        p = dict(gen=gen, n=n, genotype_rms=d, active_genes=int(active.sum()),
                 relief_q25=float(np.percentile(relief, 25)), relief_q75=float(np.percentile(relief, 75)),
                 novelty_median=float(np.median(nov)), source=CSV_POP,
                 csv_lines=[i + 2 for i in ii],
                 normalization='each varying gene divided by its range over this retained run; material excluded')
        points.append(p)
    axs[0].plot(gens, [p['genotype_rms'] for p in points], 'o-', color=COLORS[0])
    axs[0].set(title='(a) w282 • genotype spread', ylabel='Pairwise RMS distance', xlabel='Generation')
    axs[1].fill_between(gens, [p['relief_q25'] for p in points], [p['relief_q75'] for p in points], color=COLORS[0], alpha=.3)
    axs[1].set(title='(b) Relief descriptor projection', ylabel='Material-removal fraction • IQR', xlabel='Generation')
    axs[2].plot(gens, [p['novelty_median'] for p in points], 'o-', color=COLORS[2])
    axs[2].set(title='(c) Recorded novelty', ylabel='Median k-nearest-neighbor distance', xlabel='Generation')
    for ax in axs: ax.grid()
    save(fig, 'fig_population_diversity', points)


def archive_spread():
    """Compare only the retained archive, without calling it the full population."""
    paths=subprocess.check_output(['git','ls-files','*qd_archive.csv'],cwd=ROOT,text=True).splitlines()
    series=[];points=[]
    for path in paths:
        rows=csv_rows(path)
        if not rows or 'relief_frac' not in rows[0]:
            continue  # The early archive lacks this descriptor; no value is imputed.
        wave=re_wave(path)
        label=wave+(('/'+Path(path).parent.name) if 's290' in path else '')
        mass=[float(r['mass_g']) for r in rows];relief=[float(r['relief_frac']) for r in rows]
        series.append((int(wave[1:]),label,mass,relief,path))
        for i,r in enumerate(rows,2):
            points.append(dict(series=label,source=path,csv_line=i,mass_g=float(r['mass_g']),
                               relief_frac=float(r['relief_frac']),id=int(r['id']),
                               scope='retained final MAP-Elites archive; selected niches, not all births'))
    series.sort(key=lambda v:(v[0],v[1]))
    fig,axs=plt.subplots(2,1,figsize=(10.6,5.5))
    for ax,index,ylabel in [(axs[0],2,'Archive mass (g)'),(axs[1],3,'Archive relief fraction')]:
        for j,row in enumerate(series):
            q=np.percentile(row[index],[0,25,50,75,100])
            ax.plot([j,j],[q[0],q[4]],color='#a3afb5',lw=1)
            ax.plot([j,j],[q[1],q[3]],color=COLORS[0],lw=5)
            ax.scatter(j,q[2],color=COLORS[1],s=18,zorder=3)
        ax.set(ylabel=ylabel);ax.set_xticks(range(len(series)),[r[1]+f'\nn={len(r[2])}' for r in series],fontsize=7)
        ax.grid(axis='y')
    axs[0].set_title('Historical archive descriptor spread • median, IQR and retained range\nSeparate runs / objectives; selected niches are not population samples',fontsize=11)
    save(fig,'fig_archive_descriptor_spread',points)


def re_wave(path):
    import re
    return 'w'+re.search(r'(?:wave|/w)(\d+)',path).group(1)


def gate_rates(pop, evals):
    gates = list(evals[0][1]['weighted_cad_score']['gates'])
    grouped = defaultdict(list)
    for path, doc in evals:
        wave = int(doc['subject'].split('_')[0][1:])
        grouped[wave].append((path, doc))
    waves = sorted(grouped)
    matrix = []; points = []
    for gate in gates:
        line = []
        for wave in waves:
            present = [(p, d['weighted_cad_score']['gates'][gate]) for p, d in grouped[wave]
                       if gate in d['weighted_cad_score']['gates']]
            rate = sum(v is True for _, v in present) / len(present)
            line.append(rate)
            points.append(dict(wave=wave, gate=gate, n=len(present), pass_rate=rate,
                               observations=[{'source':p, 'pointer':'/weighted_cad_score/gates/'+gate, 'value':v} for p,v in present],
                               scope='selected retained evaluations, not a population pass rate'))
        matrix.append(line)
    fig, ax = plt.subplots(figsize=(10.6, 6.3))
    ax.imshow(matrix, cmap='RdYlGn', vmin=0, vmax=1, aspect='auto')
    ax.set_yticks(range(len(gates)), [g.replace('_', ' ') for g in gates], fontsize=8)
    ax.set_xticks(range(len(waves)), [f'w{w}\nn={len(grouped[w])}' for w in waves], fontsize=8)
    for i, line in enumerate(matrix):
        for j, v in enumerate(line): ax.text(j, i, f'{v:.0%}', ha='center', va='center', fontsize=7)
    ax.set_title('All 16 gates across retained candidate scorecards • selected sample only\nw283 is re-certified/rejected; historical w274–w282 scores retain their original model', fontsize=10)
    save(fig, 'fig_gate_pass_rates', points)
    # Population rates are separately plotted only where every birth has the observation.
    predicates = {'Aesthetic': lambda r:r['aes_pass'], 'Geometry':lambda r:not r['rejects'],
                  'Lateral ≥180 N':lambda r:(r.get('lat_rob') or 0)>=180,
                  'Lateral ≥260 N':lambda r:(r.get('lat_rob') or 0)>=260,
                  'Ring ≥1500 N':lambda r:(r.get('ring_rob') or 0)>=1500,
                  'Sequence ≥1.2':lambda r:(r.get('seq_ratio') or 0)>=1.2,
                  'Tip-zone SF ≥1':lambda r:(r.get('twist_tipzone_sf') or 0)>=1}
    fig, ax = plt.subplots(figsize=(10.6, 3.8)); points=[]
    for k, (name, pred) in enumerate(predicates.items()):
        xs=[]; ys=[]
        for gen in sorted({r['gen'] for r in pop}):
            indices=[i for i,r in enumerate(pop) if r['gen']==gen]
            # Missing FEM counts as not demonstrated. This is a screening rate, never certification.
            vals=[bool(pred(pop[i])) for i in indices]
            xs.append(gen);ys.append(sum(vals)/len(vals))
            points.append(dict(series=name,gen=gen,n=len(vals),passed=sum(vals),rate=ys[-1],source=POP,
                               pointers=[f'/{i}' for i in indices],scope='search mesh; missing solves count as not demonstrated'))
        ax.plot(xs,ys,label=name,color=COLORS[k%len(COLORS)],linestyle='--' if k>=6 else '-')
    ax.set(title='w282 population screening • every retained fresh evaluation',xlabel='Generation',ylabel='Fraction demonstrating screen condition',ylim=(-.02,1.02))
    ax.grid();ax.legend(ncol=3,fontsize=8)
    save(fig,'fig_population_screen_rates',points)


def pareto(evals):
    fig, axs = plt.subplots(1,2,figsize=(10.6,4.4)); points=[]
    for path, doc in evals:
        m=doc['engineering_metrics'];wave=int(doc['subject'].split('_')[0][1:])
        margin=min(m['strict_lat_rob_0p0625_n']/260, m['seq_ratio_cert']/1.2,
                   m['twist_tipzone_sf_strict'],m['solid_tip_sf_nodal_max'])-1
        g=doc['global_fitness_G1']['G']
        color='#be4c41' if wave>=283 else plt.cm.viridis((wave-274)/9)
        for ax,y in [(axs[0],margin),(axs[1],g)]:
            ax.scatter(m['mass_g'],y,color=color,s=45,marker='x' if wave>=283 else 'o')
        if doc['subject'].endswith('c01'):
            for ax,y in [(axs[0],margin),(axs[1],g)]:ax.annotate(str(wave),(m['mass_g'],y),xytext=(4,4),textcoords='offset points',fontsize=7)
        points.append(dict(subject=doc['subject'],mass_g=m['mass_g'],minimum_margin=margin,G1=g,source=path,
                           pointers=['/engineering_metrics','/global_fitness_G1/G'],
                           reduction='min(strict_lateral/260, cert_sequence/1.2, strict_tip_twist_SF, solid_tip_SF)-1; subset of gates only'))
    axs[0].axhline(0,color='#be4c41',ls='--',lw=1)
    axs[0].set(title='(a) Mass versus limiting structural margin',ylabel='Minimum margin of four stated metrics')
    axs[1].set(title='(b) Mass versus locked G1',ylabel='G1 (dimensionless)')
    for ax in axs:ax.set_xlabel('Raster mass (g)');ax.grid()
    fig.suptitle('Selected-candidate progression • historical models; w283 correction shown in red',fontsize=11)
    save(fig,'fig_pareto_history',points)


def lineage(pop):
    # Retained search champions and actual controlled-probe winners are separate lineages.
    index={r['id']:r for r in pop}
    certified=csv_rows('evidence/rs_v2/w282_ultrarunner/search/certification.csv')
    passing=[r for r in certified if r['cert_pass_all']=='true']
    champion=min(passing,key=lambda r:float(r['mass_g']))
    chosen=int(champion['id']); nodes=set()
    def ancestors(i):
        if i in nodes:return
        nodes.add(i)
        for parent in index[i]['parents']:
            if parent not in index:raise ValueError(f'missing ancestor {parent}')
            ancestors(parent)
    ancestors(chosen)
    fig,axs=plt.subplots(1,2,figsize=(10.6,5.2)); positions={};points=[]
    bygen=defaultdict(list)
    for i in sorted(nodes):bygen[index[i]['gen']].append(i)
    for gen,ids in bygen.items():
        for k,i in enumerate(ids):positions[i]=(gen,k-(len(ids)-1)/2)
    for i,(x,y) in positions.items():
        row=index[i]
        for parent in row['parents']:
            axs[0].annotate('',xy=(x,y),xytext=positions[parent],arrowprops={'arrowstyle':'->','color':'#acb5bb','lw':.6})
        axs[0].scatter(x,y,s=55 if i==chosen else 18,color=COLORS[1] if i==chosen else COLORS[0],zorder=3)
        if i==chosen or not row['parents']:axs[0].annotate(str(i),(x,y),xytext=(2,5),textcoords='offset points',fontsize=7)
        points.append(dict(id=i,gen=row['gen'],parents=row['parents'],op=row['op'],source=POP,pointer=f'/{pop.index(row)}'))
    axs[0].set(title=f'(a) Ancestry of retained search passer {chosen}\n{champion["mass_g"]} g; distinct from the lighter probe winners',xlabel='Generation',ylabel='Layout position (not a descriptor)')
    axs[0].set_yticks([])
    probes=js('evidence/rs_v2/w282_ultrarunner/controlled_probes.json')
    wanted=[('p10','w282_p10_c02'),('p14','w282_p14_c01')]
    for k,(label,subject) in enumerate(wanted):
        pi=next(i for i,r in enumerate(probes) if r['label']==label);row=probes[pi]
        parent=Path(row['parent']).stem.replace('_genome','')
        axs[1].text(.02,.78-k*.43,parent,fontsize=9,bbox=dict(boxstyle='round,pad=.6',fc='#e2eae8',ec='none'))
        axs[1].annotate('',xy=(.47,.61-k*.43),xytext=(.12,.73-k*.43),arrowprops=dict(arrowstyle='->',color=COLORS[0]))
        axs[1].text(.48,.59-k*.43,subject+'\n'+', '.join(f'{a}={b}' for a,b in row['patch'].items()),fontsize=8,
                    bbox=dict(boxstyle='round,pad=.6',fc='#fae8d9',ec='none'))
        points.append(dict(subject=subject,parent=row['parent'],patch=row['patch'],source='evidence/rs_v2/w282_ultrarunner/controlled_probes.json',pointer=f'/{pi}'))
    axs[1].set(title='(b) Named w282 record / reserve peer\nDirect probes of w281; separate from search ancestry',xlim=(0,1),ylim=(0,1));axs[1].axis('off')
    save(fig,'fig_winner_lineage',points)


POP='evidence/rs_v2/w282_ultrarunner/search/all_evals.json'
CSV_POP='evidence/rs_v2/w282_ultrarunner/search/all_evals.csv'


def main():
    OUT.mkdir(parents=True,exist_ok=True);style()
    pop=js(POP)
    if len({r['id'] for r in pop})!=len(pop):raise ValueError('duplicate birth IDs')
    evals=[]
    paths=subprocess.check_output(['git','ls-files','evidence/rs_v2/*/*_cad_eval.json'],cwd=ROOT,text=True).splitlines()
    for path in paths:
        doc=js(path)
        if 274<=int(doc['subject'].split('_')[0][1:])<=283:evals.append((path,doc))
    trajectories(pop);diversity(pop);archive_spread();gate_rates(pop,evals);pareto(evals);lineage(pop)
    ledger=OUT/'population_points.json'
    ledger.write_text(json.dumps({'schema':1,'scope':'Historical retained data; no new certification',
        'missing':'No population medians or full-population 16-gate rates for waves retaining only elites; no committed w284-w29x population in this snapshot.',
        'figures':LEDGER},indent=1,sort_keys=True)+'\n')
    for name in LEDGER:
        figlib.write_manifest(str(OUT/name),sorted(INPUTS)+[SCRIPT,ledger],str(SCRIPT),extra={
            'point_ledger':str(ledger.relative_to(ROOT)),
            'runtime':{'numpy':np.__version__,'matplotlib':matplotlib.__version__},
            'status':'Historical or corrected failure; never current qualification',
            'command':'python3 ops/render/paper/populations.py'})
    print(f'{len(LEDGER)} figures; {len(pop)} fresh evaluations; point ledger {ledger.relative_to(ROOT)}')


if __name__=='__main__':main()
