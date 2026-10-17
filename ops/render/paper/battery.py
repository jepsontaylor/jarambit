#!/usr/bin/env python3
"""Current 23-by-18 battery matrix and actual frozen assurance inventory.

Statuses are observations about their own case scope. A solver_run pass is not
automatically a strength pass. Run: python3 ops/render/paper/battery.py
"""
import json
import subprocess
import sys
from collections import Counter
from pathlib import Path

import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from matplotlib.colors import ListedColormap
import numpy as np

ROOT=Path(__file__).resolve().parents[3]
sys.path.insert(0,str(ROOT/'ops/wave_figures'))
import figlib


def main():
    out=ROOT/'docs/figures/engineering_gates';out.mkdir(parents=True,exist_ok=True)
    manifest=ROOT/'evidence/cad_battery/manifest.json';inventory=json.loads(manifest.read_text())
    subjects=inventory['subjects'];case_ids=inventory['case_ids']
    assert len(subjects)==23 and len(case_ids)==18
    statuses=['pass','fail','blocked','incomplete'];symbols=['P','F','B','I']
    colors=['#a5c9b0','#e8a89a','#cbd1d6','#efd39a']
    paths=[ROOT/'evidence/cad_battery'/f'{s}.json' for s in subjects]
    data=[];points=[];totals=Counter()
    for subject,path in zip(subjects,paths):
        subprocess.run(['git','ls-files','--error-unmatch',str(path.relative_to(ROOT))],cwd=ROOT,check=True,stdout=subprocess.DEVNULL)
        doc=json.loads(path.read_text());cases={c['id']:(i,c) for i,c in enumerate(doc['cases'])}
        assert set(cases)==set(case_ids) and len(doc['cases'])==18
        row=[]
        for cid in case_ids:
            i,c=cases[cid];st=c['status'];assert st in statuses
            row.append(statuses.index(st));totals[st]+=1
            points.append(dict(subject=subject,case=cid,status=st,kind=c['kind'],source=str(path.relative_to(ROOT)),pointer=f'/cases/{i}/status'))
        data.append(row)
    plt.rcParams.update({'font.family':'DejaVu Sans','font.size':8})
    fig,ax=plt.subplots(figsize=(10.6,7.8),facecolor='#faf9f5')
    ax.imshow(data,cmap=ListedColormap(colors),vmin=-.5,vmax=3.5,aspect='auto')
    ax.set_xticks(range(18),case_ids,rotation=55,ha='right',fontsize=7)
    ax.set_yticks(range(23),subjects,fontsize=8)
    for i,row in enumerate(data):
        for j,n in enumerate(row):ax.text(j,i,symbols[n],ha='center',va='center',fontsize=7,color='#243641')
    ax.set_title('23 subjects × 18 evaluators = 414 recorded cells\nP pass · F fail · B blocked · I incomplete; case scope controls the meaning of pass',fontsize=12,pad=15)
    fig.text(.01,.01,'Historical records plus corrected w283 failures • no currently certified all-gates winner',fontsize=8,color='#9b4c36')
    fig.tight_layout(rect=(0,.03,1,1));figure=out/'fig_battery_23.png';fig.savefig(figure,dpi=150);plt.close(fig)
    ledger=out/'battery_points.json';ledger.write_text(json.dumps({'schema':1,'totals':dict(totals),'cells':points},indent=1,sort_keys=True)+'\n')
    figlib.write_manifest(str(figure),paths+[manifest,ledger,Path(__file__).resolve()],str(Path(__file__).resolve()),extra={'command':'python3 ops/render/paper/battery.py','case_status_totals':dict(totals),'denominator':414})
    catalog=ROOT/'docs/v1/science/tests/TEST_CASE_CATALOG.json';cases=json.loads(catalog.read_text())['cases']
    counts=Counter(c['work_unit'] for c in cases);states=Counter(c['status'] for c in cases)
    summary=out/'assurance_inventory.json';summary.write_text(json.dumps({'schema':1,'source':str(catalog.relative_to(ROOT)),
        'sha256':figlib.sha256_file(str(catalog)),'groups':dict(sorted(counts.items())),
        'catalog_recorded_statuses':dict(sorted(states.items())),
        'scope':'Frozen catalog metadata; these are not fresh executions, control receipts, physical validation or gate coverage.'},indent=1,sort_keys=True)+'\n')
    print('battery:',dict(totals),'catalog groups:',sum(counts.values()))


if __name__=='__main__':main()
