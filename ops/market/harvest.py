#!/usr/bin/env python3
"""Fetch public catalog evidence into ignored scratch; never execute page content."""
import argparse
import concurrent.futures
import csv
import hashlib
import html
import json
import pathlib
import re
import time
import urllib.request
from datetime import datetime, timezone

ROOT = pathlib.Path(__file__).resolve().parents[2]
DATA = ROOT / 'docs/market/2026-10-13'
SCRATCH = ROOT / '.study/market/pages'


def normalize_url(url):
    return url.strip().replace('/index.php/products/', '/products/').rstrip('/')


def page_text(raw):
    text = re.sub(r'<(script|style)\b[^>]*>.*?</\1>', ' ', raw, flags=re.S | re.I)
    text = re.sub(r'<[^>]+>', ' ', text)
    return re.sub(r'\s+', ' ', html.unescape(text)).strip()


def fetch(url):
    key = hashlib.sha256(url.encode()).hexdigest()[:20]
    target = SCRATCH / (key + '.json')
    if target.exists():
        return json.loads(target.read_text())
    start = time.monotonic()
    result = {'url': url, 'checked_at_utc': datetime.now(timezone.utc).isoformat(), 'cache_key': key}
    try:
        req = urllib.request.Request(url, headers={'User-Agent': 'Mozilla/5.0 (compatible; catalog-research/1.0)'})
        with urllib.request.urlopen(req, timeout=22) as response:
            raw = response.read(4_000_000)
            result.update(http_status=response.status, final_url=response.url,
                          content_sha256=hashlib.sha256(raw).hexdigest())
        decoded = raw.decode('utf-8', errors='replace')
        text = page_text(decoded)
        (SCRATCH / (key + '.txt')).write_text(text)
        result['page_title'] = page_text(re.search(r'<title[^>]*>(.*?)</title>', decoded, re.S|re.I).group(1)) if re.search(r'<title[^>]*>(.*?)</title>', decoded, re.S|re.I) else ''
        result['text_characters'] = len(text)
        result['has_catalog_specs'] = bool(re.search(r'blade\s*length', text, re.I))
        result['spec_contexts'] = [text[max(0,m.start()-35):m.end()+100] for m in re.finditer(r'(?:blade\s*length|cutting\s*edge|knife\s*weight|weight\s*(?:with|without|:)|blade\s*(?:steel|material))', text, re.I)][:12]
        result['status'] = 'spec_page_retrieved' if result['has_catalog_specs'] else 'page_retrieved_specs_unconfirmed'
    except Exception as exc:
        result.update(status='retrieval_failed', error=str(exc)[:220])
    result['elapsed_s'] = round(time.monotonic()-start, 2)
    target.write_text(json.dumps(result, indent=2))
    return result


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--extra', type=pathlib.Path)
    args = parser.parse_args()
    SCRATCH.mkdir(parents=True, exist_ok=True)
    urls = set()
    manifest = []
    for path in sorted((DATA/'raw').glob('*.csv')):
        rows = list(csv.DictReader(path.open(encoding='utf-8-sig', newline='')))
        manifest.append({'filename':path.name, 'sha256':hashlib.sha256(path.read_bytes()).hexdigest(), 'rows':len(rows), 'columns':list(rows[0])})
        for row in rows:
            for value in row.values():
                for url in re.findall(r'https?://[^\s|<>]+', value or ''):
                    urls.add(normalize_url(url.rstrip(';,.)')))
    if args.extra:
        urls.update(normalize_url(s) for s in args.extra.read_text().splitlines() if s.startswith('http'))
    (DATA/'input_manifest.json').write_text(json.dumps(manifest, indent=2, ensure_ascii=False)+'\n')
    print(f'{sum(m["rows"] for m in manifest)} input rows; {len(urls)} unique URLs', flush=True)
    results = []
    with concurrent.futures.ThreadPoolExecutor(max_workers=8) as pool:
        for i, result in enumerate(pool.map(fetch, sorted(urls)), 1):
            results.append(result)
            if i % 25 == 0:
                print(f'{i}/{len(urls)} retrieved; {sum(r["status"]=="spec_page_retrieved" for r in results)} spec pages', flush=True)
    # Commit outcomes/hashes, not copyrighted page bodies or narrative excerpts.
    ledger=[{k:v for k,v in r.items() if k!='spec_contexts'} for r in results]
    (DATA/'retrieval_ledger.json').write_text(json.dumps(ledger, indent=2, ensure_ascii=False)+'\n')
    print({status:sum(r['status']==status for r in results) for status in sorted({r['status'] for r in results})})


if __name__ == '__main__':
    main()
