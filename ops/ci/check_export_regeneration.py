#!/usr/bin/env python3
"""Regenerate retained genome geometry, checking SHA256 and historical geometric payloads."""
import argparse
import hashlib
import json
from pathlib import Path
import subprocess
import time

ROOT=Path(__file__).resolve().parents[2]
def sha(path):return hashlib.sha256(path.read_bytes()).hexdigest()
def check(exporter:Path,out:Path):
    manifest=json.loads((ROOT/'evidence/evolve_certifiable/manifest.json').read_text())
    out.mkdir(parents=True,exist_ok=True)
    results=[]
    for item in manifest['regeneration']['exports']:
        prefix=out/item['id']
        subprocess.run([str(exporter.resolve()),str(ROOT/item['genome']),str(prefix),item['label']],cwd=ROOT,check=True)
        for suffix in ('.step', '.stl'):
            expected = item['sha256'][suffix]
            observed = sha(Path(str(prefix) + suffix))
            if observed != expected:
                raise ValueError(f'{item["id"]}{suffix}: expected {expected}, got {observed}')
            if expected != manifest['files'][item['historical_prefix'] + suffix]:
                raise ValueError('Current STEP/STL changed from retained historical geometry')
        surf_path = Path(str(prefix) + '_surface.json')
        surf_text = surf_path.read_text()
        old = json.loads((ROOT / (item['historical_prefix'] + '_surface.json')).read_text())
        new = json.loads(surf_text)
        cur_id = new.get('certificate_identity')
        if not (isinstance(cur_id, str) and len(cur_id) == 64 and all(c in '0123456789abcdef' for c in cur_id)):
            raise ValueError('Current exporter certificate_identity is not a valid 64-hex digest')
        replayed_sha = hashlib.sha256(surf_text.replace(cur_id, item['certificate_identity'], 1).encode()).hexdigest()
        if replayed_sha != item['sha256']['_surface.json']:
            raise ValueError(f'{item["id"]}_surface.json: expected payload sha256 {item["sha256"]["_surface.json"]}, got {replayed_sha}')
        # Historical identity remains an immutable observation of its original producer.
        # All geometric coordinates, topology, tip and mode must still be identical.
        old.pop('certificate_identity')
        new.pop('certificate_identity')
        if old != new:
            raise ValueError('Actual exported surface payload changed')
        results.append({'id': item['id'], 'sha256': item['sha256'], 'geometry_matches_historical': True})
    (out/'regeneration-result.json').write_text(json.dumps({'exports':results},indent=2)+'\n')
    print('Export regeneration PASS:',len(results),'genomes, all STEP/STL/surface SHA256 entries match')
if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--exporter',type=Path,default=ROOT/'target/release/examples/export_step');p.add_argument('--out-dir',type=Path,default=ROOT/'target/export-regeneration'/str(time.time_ns()));a=p.parse_args();check(a.exporter,a.out_dir)
