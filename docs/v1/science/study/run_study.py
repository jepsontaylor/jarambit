#!/usr/bin/env python3
"""Read-only science study: run existing tests and isolated reporting probes."""
import hashlib
import importlib.util
import json
import math
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import time
from types import SimpleNamespace

ROOT = Path('/home/ubuntu/jarambit/.agent/worktrees/codex-science-v1-plan')
OUT = ROOT / '.agent/science-v1-study'
OUT.mkdir(parents=True, exist_ok=True)
EXPECTED = '97af59cf14299af583b344aeaefb4594d089465a'


def command(args, name, timeout=1200, extra=None):
    env = dict(os.environ)
    env.update(extra or {})
    t = time.time()
    with (OUT / (name + '.log')).open('w') as log:
        p = subprocess.run(args, cwd=ROOT, env=env, stdout=log,
                           stderr=subprocess.STDOUT, timeout=timeout)
    return dict(name=name, command=args, returncode=p.returncode,
                elapsed_s=round(time.time()-t, 3), log=name+'.log')


def load(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def sanitize(x):
    if isinstance(x, float) and not math.isfinite(x):
        return repr(x)
    if isinstance(x, dict):
        return {k: sanitize(v) for k, v in x.items()}
    if isinstance(x, list):
        return [sanitize(v) for v in x]
    return x


def probes():
    g = load('study_gci', ROOT/'fem_solid/gci.py')
    rows=[]
    for case, values in [('second_order', (100.5,102,108,2)),
                         ('divergent_monotone',(10,12,13,2)),
                         ('zero_observed_order',(10,11,12,2)),
                         ('fine_pair_plateau',(10,10,100,2)),
                         ('oscillatory',(100,100.1,99.9,2)),
                         ('nonfinite',(float('nan'),101,104,2)),
                         ('zero_reference',(0,1,3,2)),
                         ('invalid_ratio',(100,101,104,1))]:
        row=dict(id=case, input=list(values))
        try:
            result=g.gci(*values)
            row.update(result=result, threshold_comparison_passes=result['gci_fine']<=.03)
        except Exception as e:
            row['exception']=type(e).__name__+': '+str(e)
        rows.append(row)
    with tempfile.TemporaryDirectory(prefix='jarambit-science-report-') as tmp:
        r=Path(tmp)
        (r/'fem_solid').mkdir()
        (r/'evidence/fem_solid/gci').mkdir(parents=True)
        (r/'docs/calibration').mkdir(parents=True)
        shutil.copy2(ROOT/'fem_solid/gci_report.py',r/'fem_solid/gci_report.py')
        p=subprocess.run([sys.executable,str(r/'fem_solid/gci_report.py')],capture_output=True,text=True)
        rows.append(dict(id='empty_inventory_report',returncode=p.returncode,
                         result_line=next((ln for ln in p.stdout.splitlines() if ln.startswith('Result:')),None)))
    c=load('study_claims',ROOT/'ops/ci/check_claims.py')
    canonical='RS-karambit-v1: screen FAIL · promotion FAIL · not promoted'
    c.read=lambda _: '<!-- RS:BEGIN fake.json fixture -->\n'+canonical+'\nRS-karambit-v1: promotion PASS; approved for release\n<!-- RS:END -->'
    c.subprocess=SimpleNamespace(run=lambda *a,**k:SimpleNamespace(returncode=0,stdout=canonical+'\n',stderr=''))
    c.errs=[]
    c.check_block('synthetic-README.md')
    rows.append(dict(id='contradictory_verdict_block',errors=c.errs,local_checker_accepted=not c.errs,
                     scope='Isolated check_block contract; not a demonstrated complete CI bypass'))
    (OUT/'probes.json').write_text(json.dumps(sanitize(rows),indent=2,allow_nan=False)+'\n')
    return rows


def main():
    sha=subprocess.check_output(['git','rev-parse','HEAD'],cwd=ROOT,text=True).strip()
    if sha != EXPECTED:
        raise SystemExit('Frozen study checkout changed')
    env=dict(source_commit=sha,host=os.uname().nodename,python=sys.version,
             affinity=sorted(os.sched_getaffinity(0)),
             selected_env={k:os.environ.get(k) for k in ['CARGO_BUILD_JOBS','CARGO_TARGET_DIR','JARAMBIT_MAX_THREADS','OPENBLAS_NUM_THREADS','OMP_NUM_THREADS','XDG_RUNTIME_DIR','DBUS_SESSION_BUS_ADDRESS']},
             requirements_sha256=hashlib.sha256((ROOT/'requirements/RS-karambit-v2.toml').read_bytes()).hexdigest())
    (OUT/'environment.json').write_text(json.dumps(env,indent=2)+'\n')
    probes()
    runs=[]
    steps=[([sys.executable,'-m','unittest','discover','-s','fem_solid/tests','-v'],'solid_fast'),
           ([sys.executable,'-m','unittest','discover','-s','metrics/tests','-t','.','-v'],'metric_contract'),
           ([sys.executable,'ops/ci/check_claims.py'],'claims_baseline'),
           ([str(Path.home()/'.cargo/bin/cargo'),'test','--release','--workspace'],'rust_workspace'),
           ([str(Path.home()/'.cargo/bin/cargo'),'build','--release','-p','jarambit'],'cli_build')]
    for args,name in steps:
        try:
            result=command(args,name)
        except Exception as e:
            result=dict(name=name,error=type(e).__name__+': '+str(e))
        runs.append(result)
        (OUT/'progress.json').write_text(json.dumps(runs,indent=2)+'\n')
    binary=Path(os.environ['CARGO_TARGET_DIR'])/'release/jarambit'
    if binary.is_file() and runs[-1].get('returncode') == 0:
        result=command([str(binary),'crescent-d1','--genomes','w14c03=docs/d1/wave15_16_collect/wave14_c03_genome.csv','--threads','2','--out',str(OUT/'d1')], 'd1_recompute', extra={'D1_PLATES':'1'})
        runs.append(result)
        if result.get('returncode') == 0:
            for script,name in [('ops/ci/d1_smoke.py','d1_known_negative'),('ops/ci/check_json_strict.py','d1_strict_json')]:
                runs.append(command([sys.executable,script,str(OUT/'d1')],name))
    receipt=dict(schema='jarambit.science.study.v1',source_commit=sha,
                 status='completed',purpose='Planning baseline; no physical validation or full solid solver rerun',
                 runs=runs,probes='probes.json',environment='environment.json')
    (OUT/'receipt.json').write_text(json.dumps(receipt,indent=2,allow_nan=False)+'\n')
    (OUT/'DONE').write_text('study completed\n')


if __name__=='__main__':
    main()
