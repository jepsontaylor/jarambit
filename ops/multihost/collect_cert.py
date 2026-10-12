#!/usr/bin/env python3
"""Collect certification.csv rows from multi-host runs and rank them (mass is SOFT; hard gates are cert_pass_all AND
twist_floor_ok_body_and_tipsub). usage: collect_cert.py WAVE host [host ...]   (or --local DIR ... to read local dirs)"""
import csv, glob, io, json, subprocess, sys

def rows_from_host(host, wave):
    cmd = f"cd ~/jarambit 2>/dev/null; for f in out/{wave}_*/certification.csv; do echo \"##$f\"; cat \"$f\"; done"
    txt = subprocess.run(['ssh', '-o', 'ConnectTimeout=5', f'ubuntu@{host}', cmd], capture_output=True, text=True).stdout
    return parse(txt, host)

def parse(txt, host):
    out = []
    for chunk in txt.split('##')[1:]:
        path, _, body = chunk.partition('\n')
        for r in csv.DictReader(io.StringIO(body)): r['run'] = path.split('/')[-2]; r['host'] = host; out.append(r)
    return out

def num(r, k):
    try: return float(r[k])
    except (KeyError, ValueError, TypeError): return float('nan')

def rank(rows):
    hard = [r for r in rows if r.get('cert_pass_all') == 'true' and r.get('twist_floor_ok_body_and_tipsub') == 'true']
    return dict(n=len(rows), n_hard=len(hard),
                best_spg=sorted(hard, key=lambda r: -num(r, 'spg_cert'))[:5],
                lightest=sorted(hard, key=lambda r: num(r, 'mass_g'))[:5])

if __name__ == '__main__':
    a = sys.argv[1:]
    if a and a[0] == '--local':
        rows = []
        for d in a[1:]:
            for f in glob.glob(f'{d}/certification.csv'): rows += parse('##' + f + '\n' + open(f).read(), 'local')
    else:
        rows = [r for h in a[1:] for r in rows_from_host(h, a[0])]
    print(json.dumps(rank(rows), indent=1))
