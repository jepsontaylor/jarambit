#!/usr/bin/env python3
"""Show the difference between numerical agreement and passing a physical gate."""
import json
import subprocess
import sys
from pathlib import Path

import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import numpy as np

ROOT=Path(__file__).resolve().parents[3]
sys.path.insert(0,str(ROOT/'ops/wave_figures'))
import figlib


def main():
    inputs=[];points=[]
    def read(path):
        subprocess.run(['git','ls-files','--error-unmatch',path],cwd=ROOT,check=True,stdout=subprocess.DEVNULL)
        inputs.append(ROOT/path);return json.loads((ROOT/path).read_text())
    plt.rcParams.update({'font.family':'DejaVu Sans','font.size':9,'axes.spines.top':False,'axes.spines.right':False})
    fig,axs=plt.subplots(2,2,figsize=(10.6,7),facecolor='#faf9f5')
    for ax in axs.flat:ax.set_facecolor('#faf9f5');ax.grid(axis='y',alpha=.2)
    path='evidence/fem_solid/verify_0.30.2.json';analytic=read(path)['analytic']
    errs=[100*r['rel_err'] for r in analytic]
    axs[0,0].bar(['Square-bar torsion','Kirsch / Heywood'],errs,color='#007f86',width=.5)
    axs[0,0].axhline(1,color='#be4c41',ls='--',label='Recorded 1% bar')
    axs[0,0].set(title='(a) Archived analytic verification',ylabel='Relative error (%)',ylim=(0,1.18));axs[0,0].legend(fontsize=8)
    for i,r in enumerate(analytic):points.append(dict(panel='a',source=path,pointer=f'/analytic/{i}/rel_err',value_percent=errs[i],reduction='100 × recorded relative error'))
    path='evidence/fem_solid/gci/g3_tip+00_t60_tt3_gci.json';levels=read(path)['levels']
    axs[0,1].plot([r['n_dof'] for r in levels],[r['SF_nodal_max'] for r in levels],'o-',color='#5667ac')
    axs[0,1].set_xscale('log');axs[0,1].set(title='(b) Historical g3 refinement observations',xlabel='DOFs (log scale)',ylabel='Nodal-maximum SF')
    axs[0,1].text(.03,.08,'Saved values; no new GCI admission',transform=axs[0,1].transAxes,fontsize=8,color='#9b4c36')
    for i,r in enumerate(levels):points.append(dict(panel='b',source=path,pointer=f'/levels/{i}',dof=r['n_dof'],SF=r['SF_nodal_max']))
    labels=[];primary=[];independent=[];lateral=[]
    for subject in ['w283_p14_c01','w283_p10_c02']:
        path=f'evidence/rs_v2/w283_ultrarunner/{subject}_solid_tip.json';d=read(path)
        primary.append(d['stored_solid']['SF_skfem_nodal_max']);independent.append(d['dolfinx_cross_check']['SF_nodal_max']);labels.append(subject.replace('w283_',''))
        points.append(dict(panel='c',source=path,pointers=['/stored_solid/SF_skfem_nodal_max','/dolfinx_cross_check/SF_nodal_max'],skfem_SF=primary[-1],dolfinx_SF=independent[-1]))
        path=f'evidence/rs_v2/w283_ultrarunner/{subject}_rs.json';d=read(path);lateral.append(d['strict_lat_rob_0p0625_n'])
        points.append(dict(panel='d',source=path,pointer='/strict_lat_rob_0p0625_n',value_N=lateral[-1]))
    x=np.arange(2);axs[1,0].bar(x-.16,primary,.3,label='scikit-fem P2',color='#007f86');axs[1,0].bar(x+.16,independent,.3,label='DOLFINx 0.9',color='#5667ac')
    axs[1,0].axhline(1,color='#be4c41',ls='--');axs[1,0].set_xticks(x,labels)
    axs[1,0].set(title='(c) Corrected w283 • agreement, strength failure',ylabel='Fine solid-tip SF',ylim=(0,1.2));axs[1,0].legend(fontsize=8)
    axs[1,1].bar(labels,lateral,color='#be4c41',width=.5);axs[1,1].axhline(260,color='#243641',ls='--',label='Unchanged 260 N floor')
    axs[1,1].set(title='(d) Corrected w283 • strict lateral failure',ylabel='Capacity (N)',ylim=(0,290));axs[1,1].legend(fontsize=8)
    for i,v in enumerate(lateral):axs[1,1].text(i,v+5,f'{v:.3f} N',ha='center',fontsize=8)
    fig.text(.01,.01,'Archived numerical checks and corrected rejected candidates • no new solves • no currently certified all-gates winner',fontsize=8,color='#9b4c36')
    fig.tight_layout(rect=(0,.035,1,1));out=ROOT/'docs/figures/engineering_gates';figure=out/'fig_verification_and_retraction.png';fig.savefig(figure,dpi=150);plt.close(fig)
    ledger=out/'verification_points.json';ledger.write_text(json.dumps({'schema':1,'points':points},indent=1,sort_keys=True)+'\n')
    figlib.write_manifest(str(figure),inputs+[ledger,Path(__file__).resolve()],str(Path(__file__).resolve()),extra={'command':'python3 ops/render/paper/verification.py','scope':'Archived validation observations, not fresh execution; corrected failures on fixed physical kernel'})
    print(figure.relative_to(ROOT))


if __name__=='__main__':main()
