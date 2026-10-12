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
    fails = []
    if not isinstance(m, (int, float)) or isinstance(m, bool):
        fails.append('mass missing')
    else:
        if m >= c['mass_cap_hard_g']:
            fails.append(f"mass {m:.2f} g >= {c['mass_cap_hard_g']:.0f} g cap")
        if not (c['mass_band_g'][0] <= m <= c['mass_band_g'][1]):
            fails.append(f"mass not in {c['mass_band_g'][0]:.0f}-{c['mass_band_g'][1]:.0f} g band")
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
    why = f" ({'; '.join(fails)})" if prom_s == 'FAIL' and fails else ''
    return f"{rs['id']}: screen {screen_s} · promotion {prom_s}{why} · human aesthetic sign-off pending · not promoted"


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
