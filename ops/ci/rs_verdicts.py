#!/usr/bin/env python3
"""Scoped verdicts under a requirement set (PR-0.28.2). Author: Jepson Taylor.
usage: rs_verdicts.py <D1_index.json> <label>   -> prints the canonical one-line verdict used in README/PROVISIONAL.
Never prints an unscoped PASS: every verdict names the RS id and group."""
import json, os, sys
try:
    import tomllib
except ModuleNotFoundError:  # py<3.11
    tomllib = None

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


def load_rs(rs_id='RS-karambit-v1'):
    p = os.path.join(ROOT, 'requirements', f'{rs_id}.toml')
    if tomllib is None:
        raise SystemExit('python >= 3.11 required (tomllib)')
    with open(p, 'rb') as fh:
        return tomllib.load(fh)


def verdict(rec, rs):
    c = rs['constants']
    m, seq = rec.get('mass_g'), rec.get('seq_ratio')
    fails, soft = [], []
    # mass is SOFT since RS v2 (Jepson 2026-10-12): reported as a target, never a promotion failure
    if isinstance(m, (int, float)) and not isinstance(m, bool):
        if m >= c['mass_target_g']:
            soft.append(f"mass {m:.2f} g over {c['mass_target_g']:.0f} g target")
        elif m >= c['mass_stretch_g']:
            soft.append(f"mass {m:.2f} g; stretch target {c['mass_stretch_g']:.0f} g")
    else:
        soft.append('mass missing')
    if not isinstance(seq, (int, float)) or isinstance(seq, bool):
        fails.append('seq missing')
    elif seq < c['seq_target']:
        fails.append(f"seq {seq:.3f} < {c['seq_target']}")
    if (rec.get('d1') or {}).get('strict_ok') is False:
        fails.append('strict hunter lateral')
    if rec.get('twist_floor_ok') is not True:
        fails.append('twist floor')
    screen = rec.get('w20_hard_pass')
    screen_s = 'PASS' if screen is True else ('FAIL' if screen is False else 'INCOMPLETE')
    if screen is not True:
        fails.insert(0, 'screen')
    prom = rec.get('promote_eligible')
    if prom is True and fails:
        raise SystemExit(f"inconsistent record: promote_eligible true but {fails}")
    prom_s = 'PASS' if (prom is True and not fails) else 'FAIL'
    if fails:
        why = f" ({'; '.join(fails)})"
    elif prom_s == 'FAIL':
        why = ' (record promote_eligible not true; recompute under RS v2)'
    else:
        why = ''
    soft_s = f" · soft: {'; '.join(soft)} (G penalty)" if soft else ''
    return f"{rs['id']}: screen {screen_s} · promotion {prom_s}{why}{soft_s} · human aesthetic sign-off pending · not promoted"


def main():
    if len(sys.argv) != 3:
        raise SystemExit(__doc__)
    with open(sys.argv[1]) as fh:
        rows = json.load(fh)
    rec = next((r for r in rows if r.get('label') == sys.argv[2]), None)
    if rec is None:
        raise SystemExit(f'label {sys.argv[2]} not found')
    print(verdict(rec, load_rs()))


if __name__ == '__main__':
    main()
