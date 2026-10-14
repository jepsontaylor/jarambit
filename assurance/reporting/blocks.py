"""Exact registered report blocks and editorial prose, without scientific evaluation."""
from dataclasses import dataclass
import json
import re

from assurance.testing.contracts import ContractError, strict_loads

REGISTRY_PATH = 'assurance/registry/current.v1.json'
LIMITS = {'max_bytes': 1_048_576, 'max_depth': 64, 'max_nodes': 100_000}
BEGIN = re.compile(r'<!-- RS:BEGIN assurance/registry/current\.v1\.json ([^\s<>]+) -->\Z')
END = '<!-- RS:END -->'


class BlockError(ValueError):
    pass


def canonical_body(value):
    try:
        text = json.dumps(value, sort_keys=True, ensure_ascii=False, separators=(',', ':'), allow_nan=False)
        strict_loads(text.encode('utf-8'), LIMITS)
    except (ContractError, ValueError, TypeError, UnicodeError, OverflowError) as error:
        raise BlockError(f'invalid report body: {error}') from error
    return text


@dataclass(frozen=True)
class ClaimBlock:
    claim_id: str
    body: str
    first_line: int
    last_line: int


def parse_blocks(document):
    try:
        raw = document.encode('utf-8') if type(document) is str else document
        if type(raw) is not bytes or len(raw) > LIMITS['max_bytes']:
            raise BlockError('document byte limit')
        text = raw.decode('utf-8', errors='strict')
    except UnicodeError as error:
        raise BlockError('document must be UTF8') from error
    if '\r' in text or text.startswith('\ufeff'):
        raise BlockError('registered blocks require UTF8/LF without BOM')
    lines = text.split('\n')
    blocks, seen, active = [], set(), None
    for i, line in enumerate(lines):
        start = BEGIN.fullmatch(line)
        if start:
            if active is not None:
                raise BlockError('nested RS block')
            claim_id = start.group(1)
            if claim_id in seen:
                raise BlockError('duplicate RS block')
            seen.add(claim_id)
            active = (claim_id, i)
        elif line == END:
            if active is None:
                raise BlockError('unmatched RS end')
            claim_id, first = active
            if i != first + 2:
                raise BlockError('report body must be one canonical JSON line')
            body = lines[first + 1]
            try:
                value = strict_loads(body.encode('utf-8'), LIMITS)
            except ContractError as error:
                raise BlockError(f'invalid report JSON: {error}') from error
            if type(value) is not dict or canonical_body(value) != body:
                raise BlockError('noncanonical report body')
            blocks.append(ClaimBlock(claim_id, body, first + 1, i + 1))
            active = None
        elif 'RS:BEGIN' in line or 'RS:END' in line:
            raise BlockError('invalid registry marker syntax')
    if active is not None:
        raise BlockError('unclosed RS block')
    return blocks


def check_exact_block(block, claim_id, expected):
    if block.claim_id != claim_id or block.body != canonical_body(expected):
        raise BlockError('registered claim body differs from provider report')


def write_block(claim_id, report):
    if type(claim_id) is not str or not claim_id or re.search(r'[\s<>]', claim_id):
        raise BlockError('invalid claim id')
    return f'<!-- RS:BEGIN {REGISTRY_PATH} {claim_id} -->\n{canonical_body(report)}\n{END}'


def editorial_lines(document, blocks=()):
    """Omit report bodies/fenced code; inline code and link targets are editorial."""
    covered = {i for b in blocks for i in range(b.first_line, b.last_line + 1)}
    fence = None
    for i, line in enumerate(document.splitlines(), 1):
        if i in covered:
            continue
        opening = re.match(r'^\s*(`{3,}|~{3,})', line)
        if opening:
            token = opening.group(1)
            if fence is None:
                fence = token
            elif token[0] == fence[0] and len(token) >= len(fence):
                fence = None
            continue
        if fence:
            continue
        line = re.sub(r'(`+).*?\1', '', line)
        line = re.sub(r'\]\([^)]*\)', ']', line)
        line = re.sub(r'\S+\.(?:png|svg|json|csv|md|stl|step)\b', '', line)
        yield i, line
