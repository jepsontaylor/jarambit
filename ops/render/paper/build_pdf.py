#!/usr/bin/env python3
"""Build the two existing papers with Pandoc/LuaLaTeX into lane-local target/paper.

Requires pandoc, texlive-luatex/latex-extra, fonts-texgyre, Pillow.
No PDF binary is committed. Every build writes source/output hashes and tool versions.
"""
import argparse
import hashlib
import json
import os
import re
import subprocess
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import quote

from PIL import Image

ROOT=Path(__file__).resolve().parents[3]
HERE=Path(__file__).resolve().parent


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def build(name):
    out=ROOT/'target/paper';out.mkdir(parents=True,exist_ok=True)
    source=ROOT/'docs'/f'{name}.md';text=source.read_text();inputs={str(source.relative_to(ROOT)):sha(source)}
    head=subprocess.check_output(['git','rev-parse','HEAD'],cwd=ROOT,text=True).strip()
    epoch=int(subprocess.check_output(['git','show','-s','--format=%ct',head],cwd=ROOT,text=True))
    version_path=ROOT/'docs/VERSION';version=version_path.read_text().strip()
    if not re.fullmatch(r'[0-9A-Za-z.-]+',version):raise ValueError('invalid version')
    inputs['docs/VERSION']=sha(version_path)
    version_header=out/'version.tex';version_header.write_text('\\newcommand{\\PaperVersion}{'+version+'}\n')
    title=text.splitlines()[0].removeprefix('# ')
    text=text.split('\n',1)[1].replace('**Jepson Taylor**\n','',1)
    if name=='WHITEPAPER':
        text=text.split('## Appendix A — prior draft')[0]
        text+='\n## Historical source archive\n\nThe prior draft remains in `docs/WHITEPAPER.md`, Appendix A, for traceability. It is excluded from this publication rendering because its earlier model and requirements are historical.\n'
    def image(match):
        path=(source.parent/match.group(2)).resolve()
        if not path.is_file():raise FileNotFoundError(path)
        inputs[str(path.relative_to(ROOT))]=sha(path)
        manifest=Path(str(path)+'.manifest.json')
        if manifest.is_file():inputs[str(manifest.relative_to(ROOT))]=sha(manifest)
        if path.suffix=='.webp':
            png=out/'images'/(path.stem+'-'+sha(path)[:12]+'.png');png.parent.mkdir(exist_ok=True)
            with Image.open(path) as im:im.convert('RGB').save(png)
            path=png
        return f'![{match.group(1)}]({path})'
    text=re.sub(r'!\[([^\]]*)\]\(([^)]+)\)',image,text)
    def link(match):
        target=match.group(2)
        if '://' in target or target.startswith('#'):return match.group(0)
        path,sep,fragment=target.partition('#');local=(source.parent/path).resolve()
        relative=local.relative_to(ROOT)
        kind='tree' if local.is_dir() else 'blob'
        url=f'https://github.com/neverhuman/jarambit/{kind}/{head}/{quote(str(relative),safe="/")}'
        return f'[{match.group(1)}]({url}{sep}{fragment})'
    text=re.sub(r'(?<!!)\[([^\]]+)\]\(([^)]+)\)',link,text)
    staged=out/f'{name}.md';staged.write_text(text)
    pdf=out/f'{name}.pdf'
    # The source already supplies captions; inline placement keeps them with their image.
    cmd=['pandoc',str(staged),'--from=markdown+tex_math_dollars-implicit_figures','--pdf-engine=lualatex',
         '--resource-path',str(ROOT/'docs'),'-V','documentclass=article','-V','fontsize=10pt',
         '-V','geometry:margin=22mm','-V','mainfont=TeX Gyre Pagella',
         '-V','sansfont=TeX Gyre Heros','-V','monofont=DejaVu Sans Mono',
         '-V','colorlinks=true','--metadata',f'title={title}','--metadata','author=Jepson Taylor',
         '--metadata','date='+datetime.fromtimestamp(epoch,timezone.utc).strftime('%d %B %Y')+f' · Version {version} (corrected certification)',
         '--standalone','--lua-filter',str(HERE/'publication.lua'),
         '--include-in-header',str(version_header),'--include-in-header',str(HERE/'header.tex'),'-o',str(pdf)]
    env=dict(os.environ,TEXMFOUTPUT=str(out),SOURCE_DATE_EPOCH=str(epoch))
    with (out/f'{name}.build.log').open('w') as log:
        run=subprocess.run(['nice','-n','10']+cmd,cwd=ROOT,env=env,stdout=log,stderr=subprocess.STDOUT)
    if run.returncode:raise RuntimeError(f'PDF build failed; see {out/name}.build.log')
    for path in [Path(__file__).resolve(),HERE/'publication.lua',HERE/'header.tex']:
        inputs[str(path.relative_to(ROOT))]=sha(path)
    record={'schema':1,'source_commit':head,'source':str(source.relative_to(ROOT)),'source_sha256':sha(source),
            'inputs':inputs,'output':str(pdf.relative_to(ROOT)),'output_sha256':sha(pdf),
            'pandoc':subprocess.check_output(['pandoc','--version'],text=True).splitlines()[0],
            'latex':subprocess.check_output(['lualatex','--version'],text=True).splitlines()[0],
            'command':cmd,'scope':'Publication render only; no new engineering solves or certification'}
    (out/f'{name}.pdf.manifest.json').write_text(json.dumps(record,indent=1,sort_keys=True)+'\n')
    print(pdf.relative_to(ROOT),pdf.stat().st_size,flush=True)


def main():
    p=argparse.ArgumentParser();p.add_argument('--document',choices=['WHITEPAPER','ENGINEERING_GATES_AND_EVOLUTION']);args=p.parse_args()
    for name in [args.document] if args.document else ['WHITEPAPER','ENGINEERING_GATES_AND_EVOLUTION']:build(name)


if __name__=='__main__':main()
