#!/usr/bin/env python3
"""Run Blender with bounded CPU/memory, then bind each output to exact inputs.

python3 ops/render/blender/render_paper.py [--scene hero_oblique] [--samples 48]
"""
import argparse
import hashlib
import json
import os
import subprocess
import sys
from pathlib import Path
import PIL
from PIL import Image, ImageDraw, ImageFont

ROOT=Path(__file__).resolve().parents[3]
sys.path.insert(0,str(ROOT/'ops/wave_figures'))
import figlib


def main():
    p=argparse.ArgumentParser();p.add_argument('--scene');p.add_argument('--samples',type=int,default=48);args=p.parse_args()
    script=ROOT/'ops/render/blender/paper_scenes.py'
    # Read the declarative scene dictionary without importing Blender in the host interpreter.
    import ast
    tree=ast.parse(script.read_text())
    scenes=next(ast.literal_eval(n.value) for n in tree.body if isinstance(n,ast.Assign) and any(isinstance(t,ast.Name) and t.id=='SCENES' for t in n.targets))
    names=[args.scene] if args.scene else list(scenes)
    if any(n not in scenes for n in names):p.error('unknown scene')
    evidence=ROOT/'evidence/evolve_certifiable/manifest.json'
    proof=json.loads(evidence.read_text())['automatic']
    artifacts=proof['artifacts']
    board=json.loads((ROOT/artifacts['leaderboard']).read_text())
    score=json.loads((ROOT/artifacts['scorecard']).read_text())
    rs=json.loads((ROOT/artifacts['rs']).read_text())
    # This atlas illustrates an assessed failure, never a placeholder winner.
    assert board['champion'] is None and board['qualified_count']==0
    assert not score['weighted_cad_score']['all_engineering_gates_pass'] and not rs['all_hard']
    inputs=[evidence]+[ROOT/artifacts[k] for k in ['stl','d1','scorecard','rs','leaderboard','step_check']]
    for path in inputs:subprocess.run(['git','ls-files','--error-unmatch',str(path.relative_to(ROOT))],cwd=ROOT,check=True,stdout=subprocess.DEVNULL)
    blender=os.environ.get('BLENDER', 'blender')
    version=subprocess.check_output([blender,'--version'],text=True).splitlines()[0]
    font=Path('/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf')
    out=ROOT/'docs/figures/whitepaper/blender';out.mkdir(parents=True,exist_ok=True)
    logdir=ROOT/'target/paper/blender';logdir.mkdir(parents=True,exist_ok=True)
    for name in names:
        figure=out/(name+'.webp');raw=logdir/(name+'.png')
        cmd=['nice','-n','10',str(Path.home()/'bin/memcap'),'32G','--',blender,'-b','-t','4','-P',str(script),'--','--scene',name,'--output',str(raw),'--samples',str(args.samples)]
        with (logdir/(name+'.log')).open('w') as log:subprocess.run(cmd,cwd=ROOT,stdout=log,stderr=subprocess.STDOUT,check=True)
        captions=json.loads(raw.with_suffix('.labels.json').read_text())
        with Image.open(raw) as source:
            im=source.convert('RGB');draw=ImageDraw.Draw(im);scale=im.width/.285
            for caption in captions:
                face=ImageFont.truetype(str(font),round(caption['size']*scale*1.25))
                draw.text((im.width/2+caption['x']*scale,im.height/2-caption['y']*scale),
                          caption['text'],font=face,fill=tuple(caption['rgb']),anchor='ls')
            im.save(figure,format='WEBP',quality=92,method=6)
        figlib.write_manifest(str(figure),inputs+[script,Path(__file__).resolve()],str(script),
            extra={
                'scene':name,'command':f'python3 ops/render/blender/render_paper.py --scene {name} --samples {args.samples}',
                'blender':version,'engine':'Cycles CPU','threads':4,'samples':args.samples,'denoise':True,
                'typography':'Pillow publication overlay after Cycles; fixed image coordinates, independent of depth of field',
                'pillow':PIL.__version__,'captions':captions,
                'font':str(font),'font_sha256':hashlib.sha256(font.read_bytes()).hexdigest(),
                'encoding':'WebP quality 92, method 6; unlabelled Cycles PNG and caption JSON retained under target/paper/blender',
                'geometry_frame_sha256':hashlib.sha256(raw.read_bytes()).hexdigest(),
                'subject':proof['label'],'certificate_identity':proof['certificate_identity'],
                'geometry':'Exact committed automatic-assessment STL; no remodeled geometry; section scene clips at z=0',
                'status':'Assessed example, not qualified; no certified all-16 winner; champion=null',
                'gate_verdict':score['weighted_cad_score']['gates'].get(name),
                'rs_v2_all_hard':rs['all_hard'],'qualified_count':board['qualified_count'],
                'field':'Retained D1 design-load plate envelope, not a new solve or a solid stress field' if scenes[name][2] in ('lateral','pull','sequence') else 'No stress field; illustrative finish / fixture / load annotations',
                'field_scale':{'units':'MPa','min':0,'max':828,'clip':True,'colors_at_equal_intervals':[[.04,.08,.35],[0,.45,.7],[.08,.7,.6],[.95,.8,.12],[.8,.08,.05]]} if scenes[name][2] in ('lateral','pull','sequence') else None,
                'finish':'Illustrative titanium/anodized shader; no structural or coating qualification',
            })
        print(name,figure.stat().st_size,flush=True)


if __name__=='__main__':main()
