#!/usr/bin/env python3
"""Claim checker (PR-0.28.2). Exit 1 on any violation. Author: Jepson Taylor.
1. No unscoped PASS in current public docs (README.md, docs/PROVISIONAL.md, docs/WHITEPAPER.md before Appendix A):
   a PASS token (outside `code`, link/image targets and file names) is allowed only on a line that names a
   requirement set (RS-karambit-vN) or in a table whose header row names one.
2. The verdict block between <!-- RS:BEGIN --> and <!-- RS:END --> in README.md and docs/PROVISIONAL.md must
   equal ops/ci/rs_verdicts.py output for the provisional record named in that block.
3. README's description of the default evaluator must match crates/cli/src/main.rs (JARAMBIT_FEM opt-in)."""
import os, re, subprocess, sys

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
RS = re.compile(r'RS-karambit-v\d+')
errs = []


def read(rel):
    with open(os.path.join(ROOT, rel), encoding='utf-8') as fh:
        return fh.read()


def strip_noise(line):
    line = re.sub(r'`[^`]*`', '', line)            # inline code
    line = re.sub(r'\]\([^)]*\)', ']', line)        # link / image targets
    line = re.sub(r'\S+\.(png|svg|json|csv|md|stl|step)\b', '', line)
    return line


def scan_pass(rel, text, stop=None):
    if stop and stop in text:
        text = text[:text.index(stop)]
    header_scoped = False
    in_code = False
    for i, raw in enumerate(text.splitlines(), 1):
        if raw.strip().startswith('```'):
            in_code = not in_code
            continue
        if in_code:
            continue
        s = raw.strip()
        if s.startswith('|'):
            if re.match(r'^\|[\s:|-]+\|$', s):
                continue
            if not prev_table:
                header_scoped = bool(RS.search(s))
        prev = s.startswith('|')
        line = strip_noise(raw)
        if re.search(r'\bPASS\b', line) and not RS.search(raw) and not (s.startswith('|') and header_scoped):
            errs.append(f'{rel}:{i}: unscoped PASS -> name the requirement set (e.g. RS-karambit-v1 screen): {raw.strip()[:120]}')
        globals()['prev_table'] = prev


def check_block(rel):
    t = read(rel)
    m = re.search(r'<!-- RS:BEGIN (\S+) (\S+) -->\s*\n(.*?)\n\s*<!-- RS:END -->', t, re.S)
    if not m:
        errs.append(f'{rel}: missing <!-- RS:BEGIN <index.json> <label> --> ... <!-- RS:END --> block')
        return
    idx, label, body = m.group(1), m.group(2), m.group(3).strip()
    out = subprocess.run([sys.executable, os.path.join(ROOT, 'ops', 'ci', 'rs_verdicts.py'), os.path.join(ROOT, idx), label],
                         capture_output=True, text=True)
    if out.returncode != 0:
        errs.append(f'{rel}: rs_verdicts failed: {out.stderr.strip() or out.stdout.strip()}')
        return
    want = out.stdout.strip()
    if want not in body:
        errs.append(f'{rel}: RS verdict block is stale.\n  want: {want}\n  have: {body}')


def check_default_evaluator():
    main = read('crates/cli/src/main.rs')
    opt_in = 'var("JARAMBIT_FEM").ok().as_deref() == Some("1")' in main
    readme = read('README.md')
    claims_default_on = re.search(r'plate level by default', readme) is not None
    if opt_in and claims_default_on:
        errs.append('README.md: claims plate level is the default, but crates/cli/src/main.rs makes it opt-in (JARAMBIT_FEM=1)')
    if opt_in and 'JARAMBIT_FEM=1' not in readme:
        errs.append('README.md: must document the JARAMBIT_FEM=1 opt-in for the plate-level search evaluator')


if __name__ == '__main__':
    prev_table = False
    for rel, stop in (('README.md', None), ('docs/PROVISIONAL.md', None), ('docs/WHITEPAPER.md', '## Appendix A')):
        prev_table = False
        scan_pass(rel, read(rel), stop)
    for rel in ('README.md', 'docs/PROVISIONAL.md'):
        check_block(rel)
    check_default_evaluator()
    for e in errs:
        print('ERROR:', e)
    print(f'check_claims: {len(errs)} violation(s)')
    sys.exit(1 if errs else 0)
