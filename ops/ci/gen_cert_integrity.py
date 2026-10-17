#!/usr/bin/env python3
"""Refresh the corrected Wave 283 engineering-paper rows from committed certificates."""
import json
from pathlib import Path
import re
import sys
ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0,str(ROOT))
from ops.ci.gen_readme import integrity_status

def render(text):
    text = re.sub(r'(?s)(<!-- GEN:CERT_INTEGRITY:BEGIN -->\n).*?(<!-- GEN:CERT_INTEGRITY:END -->)',
                  lambda m:m[1]+integrity_status()+'\n'+m[2],text)
    output=[]
    in_block=False
    for line in text.splitlines():
        if line == "<!-- GEN:CERT_INTEGRITY:BEGIN -->": in_block=True
        if in_block:
            output.append(line)
            if line == "<!-- GEN:CERT_INTEGRITY:END -->": in_block=False
            continue
        if not line.startswith('| '):output.append(line);continue
        sid=next((s for s in ['w283_p14_c01','w283_p10_c02'] if s in line),None)
        if sid is None:output.append(line);continue
        base=ROOT/'evidence/rs_v2/w283_ultrarunner'
        ev=json.loads((base/f'{sid}_cad_eval.json').read_text());em=ev['engineering_metrics'];wc=ev['weighted_cad_score']
        rs=json.loads((base/f'{sid}_rs.json').read_text());bat=json.loads((ROOT/f'evidence/cad_battery/{sid}.json').read_text())
        gf=bat['global_fitness']['G'];solid=em['solid_tip_sf_nodal_max'];seq=em['seq_ratio_cert']
        if line.startswith('| ['):
            tip=json.loads((base/f'{sid}_solid_tip.json').read_text());st=tip['stored_solid'];gci=json.loads((base/f'{sid}_plate_gci.json').read_text())
            line=f'| [`{sid}`](../evidence/cad_battery/{sid}.json) | 128-gene CSV + STEP/STL | {em["mass_g"]:.2f} | **{bat["pass_count"]}/18** | {bat["solver_run_count"]} | {sum(c["status"]=="blocked" for c in bat["cases"])} | `{solid:.4f}` (`{st["SF_skfem_nodal_max"]:.4f}` / `{tip["dolfinx_cross_check"]["SF_nodal_max"]:.4f}`) | {gci["seq_ratio_gci"]["fit_status"]} / {gci["sf_hunter_gci"]["fit_status"]} | **{seq:.4f}** | {em["seq_ratio_supported_a4"]:.4f} | {em["buckling_eigenvalue_a4"]:.2f} | **{gf:.4f}** |'
        elif '`fail`' in line or '`pass`' in line:
            line=f'| `{sid}` | `{rs["screen"]}` | **{solid:.4f}** | **{seq:.4f}** | **{rs["hm_twist_sf"]:.4f}** | **{rs["hm_spine_sf"]:.4f}** | **{rs["hm_ringback_sf"]:.4f}** | **{rs["fat_sf"]:.4f}** | **{rs["ring_bearing_w_mm"]:.2f}** | `fail` (`RS-karambit-v2`, measured export) |'
        elif 'Wave 283' in line:
            line=f'| `{sid}` | Wave 283 re-certification | `{em["mass_g"]:.3f}` / `{em["mass_3d_g"]:.3f}` | `{em["strict_lat_rob_0p0625_n"]:.1f} N` / `{em["sf_hunter_strict"]:.3f}` | `{em["twist_tipzone_sf_strict"]:.3f}` | `{seq:.3f}` | `{solid:.4f}` | `{em["seq_ratio_supported_a4"]:.3f}` | `{wc["W_CAD"]:+.4f}` | `{gf:.4f}` (`COMPLETE`) | **FAIL** (`all_hard = false`) |'
        else:
            line=f'| `{sid}` (`w283`, re-certified) | {em["t_stock_mm"]:.1f} | **{em["mass_g"]:.3f}** (`{em["mass_3d_g"]:.3f}` 3D) | {em["lat_rob_cert_n"]:.1f} | {em["spg_n_per_g"]:.3f} | **{seq:.4f}** | **{solid:.4f}** | {em["aes_score"]:.4f} | **{gf:.4f}** | Rejected: `W_CAD = {wc["W_CAD"]:+.4f}`, RS-v2 FAIL |'
        output.append(line)
    return '\n'.join(output)+'\n'

if __name__=='__main__':
    import sys
    path=ROOT/'docs/ENGINEERING_GATES_AND_EVOLUTION.md';old=path.read_text();new=render(old)
    if '--check' in sys.argv:
        if old!=new:raise SystemExit('Engineering certificate rows are stale')
    else:path.write_text(new)
