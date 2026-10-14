#!/usr/bin/env python3
"""Check exact registered report bodies and separate scoped assertions.

Exit0 includes truthful scientific FAIL/INCOMPLETE. Integrity/scope errors exit1;
provider/admission/protocol refusal exits2 without a reusable Resolution.
--root selects document/evidence data only, never authority or a binary.
"""
import argparse
from dataclasses import dataclass, field
from pathlib import Path
import re
import sys

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
from ops.ci import rs_verdicts
from assurance.reporting import blocks, claims
from assurance.testing.contracts import ContractError

RS = re.compile(r'\bRS-[A-Za-z0-9_-]+\b')
ASSERTION = re.compile(r'(?P<rs>\bRS-[A-Za-z0-9_-]+\b):\s*(?P<fields>[^;\n|]+?)\s+(?P<outcome>PASS|FAIL|INCOMPLETE)\b\.?\s*(?=;|$|\|)')
CURRENT_HEADING = re.compile(r'^\s*#{1,6}\s+(?P<candidate>[^\s;]+)\s+(?:CURRENT(?:\s+RELEASE\s+CANDIDATE)?|RELEASE\s+CANDIDATE)(?=\s|;|$)', re.I)


@dataclass
class CheckResult:
    exit_code: int
    violations: list = field(default_factory=list)
    provider: object = None


def read(rel, root=ROOT):
    path = (Path(root) / rel).resolve()
    if not path.is_relative_to(Path(root).resolve()):
        raise claims.Refusal('document_path_escape')
    return claims.read_bounded(path).decode('utf-8', errors='strict')


def strip_noise(line):
    return next((s for _, s in blocks.editorial_lines(line)), '')


def assertion_errors(assertion, report, registration):
    """Supported syntax: RS-id: group [candidate=id] [class=id] outcome.

    group=id is also accepted. Every explicitly asserted field is compared to
    the actual provider or independently admitted caller, never to prose aliases.
    """
    tokens = assertion['fields'].split()
    fields = {}
    if tokens and '=' not in tokens[0]:
        fields['group'] = tokens.pop(0)
    for token in tokens:
        key, separator, value = token.partition('=')
        if separator != '=' or key not in {'group', 'candidate', 'class'} or not value or key in fields:
            return ['unsupported or duplicate RS assertion field']
        fields[key] = value
    errors = []
    if assertion['rs'] != report['verdict']['requirement_set']:
        errors.append('asserted requirement scope differs from admitted provider')
    if fields.get('group') != report['verdict']['group']:
        errors.append('asserted group differs from admitted provider')
    if 'candidate' in fields and fields['candidate'] != registration['candidate_id']:
        errors.append('asserted candidate differs from trusted registration')
    if 'class' in fields and fields['class'] != registration['requested_class']:
        errors.append('asserted class differs from trusted registration')
    if assertion['outcome'].lower() != report['verdict']['outcome']:
        errors.append(f"scoped {assertion['outcome']} contradicts actual {report['verdict']['group']} provider verdict")
    return errors


def scan_pass(rel, text, report, registry, parsed=(), stop=None, *, registration):
    if stop and stop in text:
        text = text[:text.index(stop)]
    errors, table_scope = [], False
    rs_id = report['verdict']['requirement_set']
    group = report['verdict']['group']
    prev_table = False
    for number, line in blocks.editorial_lines(text, parsed):
        stripped = line.strip(); in_table = stripped.startswith('|')
        if in_table and not prev_table:
            table_scope = rs_id in RS.findall(line)
        if not in_table:
            table_scope = False
        prev_table = in_table
        assertions = list(ASSERTION.finditer(line))
        table_assertion = False
        if not assertions and in_table and table_scope and re.search(r'\b(?:PASS|FAIL|INCOMPLETE)\b', line):
            # In a table scoped by its RS header, cells use the same explicit
            # group/qualifier/outcome grammar; a header cannot bless any group.
            cells = ' '.join(cell.strip() for cell in stripped.strip('|').split('|'))
            assertions = list(ASSERTION.finditer(f'{rs_id}: {cells}'))
            table_assertion = bool(assertions)
        for assertion in assertions:
            errors.extend(f'{rel}:{number}: {reason}' for reason in assertion_errors(assertion, report, registration))
        heading = CURRENT_HEADING.match(line)
        covered = assertions + ([heading] if heading else [])
        if not table_assertion and any(not any(s.start() <= token.start() and token.end() <= s.end() for s in covered)
                                       for token in re.finditer(r'\bPASS\b', line)):
            errors.append(f'{rel}:{number}: unscoped or unsupported PASS assertion')
        if heading:
            candidate = heading['candidate']
            current = registry['current_by_scope'].get(group)
            if (candidate != registration['candidate_id'] or candidate != current
                    or registry['candidates'].get(candidate) in {None, 'archived', 'superseded'}):
                errors.append(f'{rel}:{number}: stale or unregistered current candidate {candidate}')
    return errors


def check_document(document, context=None, *, rel='document.md', stop=None):
    try:
        context = context if context is not None else rs_verdicts.admitted_context()
        claim_id = context.caller.data['pin']['registration']['claim_id']
        expected = context.report_for(claim_id)
        provider = context.last_resolution
        registration = context.caller.verify_current()['pin']['registration']
        registry = context.registry()
    except rs_verdicts.RequestedScopeError as error:
        return CheckResult(1, list(error.reasons), context.last_resolution)
    except (claims.Refusal, ContractError, OSError, UnicodeError, TypeError, KeyError, ValueError) as error:
        return CheckResult(2, [str(error)], None)
    try:
        text = document.decode('utf-8') if type(document) is bytes else document
        parsed = blocks.parse_blocks(text)
        if len(parsed) != 1:
            raise blocks.BlockError('exactly one registered report block required')
        blocks.check_exact_block(parsed[0], claim_id, expected)
        errors = scan_pass(rel, text, expected, registry, parsed, stop, registration=registration)
        return CheckResult(1 if errors else 0, errors, provider)
    except (blocks.BlockError, UnicodeError, TypeError, ValueError) as error:
        return CheckResult(1, [str(error)], provider)


def check_block(rel, context=None, root=ROOT):
    return check_document(read(rel, root), context, rel=rel)


def check_default_evaluator(root=ROOT):
    main = read('crates/cli/src/main.rs', root)
    opt_in = 'var("JARAMBIT_FEM").ok().as_deref() == Some("1")' in main
    readme = read('README.md', root)
    errors = []
    if opt_in and re.search(r'plate level by default', readme):
        errors.append('README.md: plate level is opt-in (JARAMBIT_FEM=1)')
    if opt_in and 'JARAMBIT_FEM=1' not in readme:
        errors.append('README.md: must document the JARAMBIT_FEM=1 opt-in')
    return errors


def check_root(root=ROOT, context=None):
    context = context if context is not None else rs_verdicts.admitted_context()
    root = Path(root).resolve()
    if (root / 'document.md').is_file():
        return check_document(read('document.md', root), context)
    results = [check_document(read(rel, root), context, rel=rel, stop=stop) for rel, stop in [('README.md', None), ('docs/PROVISIONAL.md', None), ('docs/WHITEPAPER.md', '## Appendix A')]]
    errors = [e for r in results for e in r.violations] + check_default_evaluator(root)
    code = 2 if any(r.exit_code == 2 for r in results) else (1 if errors else 0)
    return CheckResult(code, errors, [r.provider for r in results])


def main(argv=None, *, context=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--root', type=Path, default=ROOT)
    args = parser.parse_args(argv)
    try:
        result = check_root(args.root, context)
    except (claims.Refusal, ContractError, OSError, UnicodeError, ValueError, TypeError, KeyError) as error:
        result = CheckResult(2, [str(error)])
    for error in result.violations:
        print('ERROR:', error)
    print(f'check_claims: {len(result.violations)} violation(s)')
    return result.exit_code


if __name__ == '__main__':
    raise SystemExit(main())
