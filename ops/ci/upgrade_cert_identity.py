#!/usr/bin/env python3
"""Rebind these unchanged committed observations after the lossless identity fix.

This is a metadata migration, not a solver run. Refuse any changed numerical source,
measurement implementation, requirement, genome or raw observation. Re-run the RS
verdict against the stronger binding and retain the original solver record verbatim.
"""
from pathlib import Path
import hashlib
import json
import os
import re
import shutil
import struct
import subprocess

ROOT=Path(__file__).resolve().parents[2]
SELECTED={'crates/crescent/src/battery.rs','crates/cli/src/bench.rs','crates/cli/src/crescent.rs'}

def sha(raw):return hashlib.sha256(raw).hexdigest()
def load(path):return json.loads(path.read_text())
def write(path,doc):path.write_text(json.dumps(doc,indent=2,sort_keys=True)+'\n')
def production(rel,raw):return raw.split(b'\n#[cfg(test)]\n')[0] if rel in SELECTED else raw

def verify_sources(provenance):
    previous=provenance['implementation_commit']
    allowed={'crates/crescent/src/certification.rs','crates/cli/src/bench.rs'}
    checked={}
    for rel,expected in provenance['model_source_sha256'].items():
        if rel in allowed:continue
        digest=sha(production(rel,(ROOT/rel).read_bytes()))
        if digest!=expected:raise ValueError(f'numerical source changed: {rel}')
        checked[rel]=digest
    def old(rel):return subprocess.check_output(['git','show',f'{previous}:{rel}'],cwd=ROOT).decode()
    rel='crates/crescent/src/certification.rs';before=old(rel);after=(ROOT/rel).read_text()
    for start,end in [('/// Vertical intersection','/// A primary native solve'),('pub fn independent_pass',None)]:
        a=before[before.index(start):before.index(end) if end else len(before)]
        b=after[after.index(start):after.index(end) if end else len(after)]
        if a!=b:raise ValueError('measurement or independent comparison implementation changed')
        checked[rel+':'+start]=sha(a.encode())
    const=r'pub const EXPORT_AREA_MM2: f64 = [^;]+;'
    if re.search(const,before)[0]!=re.search(const,after)[0]:raise ValueError('export measurement resolution changed')
    rel='crates/cli/src/bench.rs';before=old(rel);after=(ROOT/rel).read_text()
    a=before[before.index('pub fn rs_v2_eval'):before.index('        let mut j =')]
    b=after[after.index('pub fn rs_v2_eval'):after.index('        let mut j =')]
    if a!=b:raise ValueError('RS numerical evaluation or gate definitions changed')
    checked[rel+':RS_numerical_evaluation']=sha(a.encode())
    return checked

def identity(row):
    fields=row.split(',');raw=bytearray(fields[-1].encode())
    for token in fields[:-1]:raw.extend(struct.pack('<d',float(token)))
    path=ROOT/'crates/crescent/src/certification.rs'
    for rel in re.findall(r'include_str!\("([^"]+)"\)',path.read_text()):
        src=(path.parent/rel).resolve();name=str(src.relative_to(ROOT))
        raw.extend(b'\0'+production(name,src.read_bytes()))
    return sha(raw)

def main():
    from ops.ci.cad_battery import build_subject
    base=ROOT/'evidence/cert_integrity';provenance=load(base/'model-provenance.json')
    checked=verify_sources(provenance);commit=subprocess.check_output(['git','rev-parse','HEAD'],cwd=ROOT,text=True).strip()
    proof={'purpose':'lossless genotype identity and stronger embedded solver binding; no numerical source or threshold change',
           'observation_implementation_commit':provenance['implementation_commit'],'identity_implementation_commit':commit,
           'unchanged_sources_and_measurement_regions':checked,'subjects':{}}
    runs=[]
    for sid in ['w283_p14_c01','w283_p10_c02']:
        folder=base/'recertified'/sid;genome=folder/f'{sid}_genome.csv';d1=load(folder/f'{sid}_D1.json')
        row=genome.read_text().splitlines()[1]
        if row!=d1['genome']:raise ValueError('lossy or changed genome; new numerical execution required')
        key=identity(row);solid_path=folder/f'{sid}_solid_tip.json';original=solid_path.read_bytes();solid=json.loads(original)
        if solid['genome_sha256']!=sha(genome.read_bytes()) or solid['d1_sha256']!=sha((folder/f'{sid}_D1.json').read_bytes()):raise ValueError('observation input mismatch')
        for suffix,field in [('solid_mesh.npz','mesh_sha256'),('skfem_raw.json','skfem_raw_sha256'),('dolfinx_raw.json','dolfinx_raw_sha256')]:
            if sha((folder/f'{sid}_{suffix}').read_bytes())!=solid[field]:raise ValueError('raw observation mismatch')
        observed=folder/f'{sid}_observed_solid_tip.json'
        if observed.exists() and observed.read_bytes()!=original:raise ValueError('identity upgrade already performed; do not overwrite the observed record')
        observed.write_bytes(original)
        old_key=solid['certificate_identity'];solid.update(certificate_identity=key,observed_certificate_identity=old_key,
            observed_record_path=str(observed.relative_to(ROOT)),observed_record_sha256=sha(original),solve_rerun=False,
            identity_upgrade='exact same genome, input D1 and numerical/measurement sources; original observations preserved')
        write(solid_path,solid)
        work=ROOT/'target/cert-integrity/lossless-bindings'/sid;work.mkdir(parents=True,exist_ok=True)
        gci=work/'gci.json';write(gci,{'certificate_identity':key,'design':sid,'solid_record':solid,
            'SF_nodal_max':{'fine':solid['stored_solid']['SF_nodal_max']}})
        write(work/'bindings.json',{key:{'certificate_identity':key,'genome':str(genome),'gci':str(gci),'gci_sha256':sha(gci.read_bytes())}})
        env={**os.environ,'OMP_NUM_THREADS':'1','OPENBLAS_NUM_THREADS':'1','MKL_NUM_THREADS':'1'}
        log=(ROOT/f'target/cert-integrity/{sid}-lossless-rs.log').open('w')
        p=subprocess.Popen([str(ROOT/'target/release/jarambit'),'rs-v2-eval','--genomes',f'{sid}={genome}',
                            '--out',str(folder),'--solid-dir',str(work)],cwd=ROOT,env=env,stdout=log,stderr=subprocess.STDOUT)
        runs.append((sid,p,log,key,old_key))
        proof['subjects'][sid]={'genome_sha256':solid['genome_sha256'],'observed_record_sha256':sha(original),
            'observed_identity':old_key,'current_identity':key,'input_d1_sha256':solid['d1_sha256']}
    for sid,p,log,key,old_key in runs:
        if p.wait()!=0:raise RuntimeError(f'RS evaluation failed: {sid}')
        log.close();folder=base/'recertified'/sid;raw=load(folder/f'{sid}.json');solid=load(folder/f'{sid}_solid_tip.json')
        if raw['certificate_identity']!=key or raw['solid_tip_sf']!=solid['stored_solid']['SF_nodal_max'] or raw['unverified']:raise ValueError('current embedded binding was not verified')
        raw['genome']=str((folder/f'{sid}_genome.csv').relative_to(ROOT));raw['solid_tip_source']=str((folder/f'{sid}_solid_tip.json').relative_to(ROOT))
        write(folder/f'{sid}.json',raw);write(folder/f'{sid}_rs.json',raw)
        for suffix in ['cad_eval','plate_gci']:
            path=folder/f'{sid}_{suffix}.json';doc=load(path);doc['observed_certificate_identity']=old_key;doc['certificate_identity']=key;write(path,doc)
        for suffix in ['rs','solid_tip','cad_eval','plate_gci']:shutil.copyfile(folder/f'{sid}_{suffix}.json',ROOT/f'evidence/rs_v2/w283_ultrarunner/{sid}_{suffix}.json')
        shutil.copyfile(folder/f'{sid}_rs.json',ROOT/f'evidence/rs_v2/{sid}.json')
        record=build_subject(sid,commit,{'analytic':'pass','gci':'pass','claims':'pass'});record['certificate_identity']=key
        write(ROOT/f'evidence/cad_battery/{sid}.json',record)
    write(base/'identity-upgrade.json',proof)
    print('Re-issued lossless bindings; original solver records, D1 inputs and raw observations retained')

if __name__=='__main__':main()
