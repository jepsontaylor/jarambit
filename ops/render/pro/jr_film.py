#!/usr/bin/env python3
"""jr-film: one command from a committed design folder to a delivered, manifest-stamped film.

  jr-film --design designs/switchback/C10a --work DIR          # explicit design
  jr-film --latest designs/switchback --work DIR               # newest RC folder (default family)
  jr-film ... --plan                                           # validate + print the plan, render nothing (CI/PR mode)

Stages (each is skipped when its outputs exist AND carry the same manifest sha; --force STAGE redoes one):
  manifest  design_manifest.py: README gates + SHA256SUMS + STEP sha + mass + gate JSON + FEM store -> design_manifest.json
  ingest    marketing/ingest.py STEP -> mesh bundle (re-used only if the bundle's source sha == manifest STEP sha)
  prep      prep.py (flat-seam weld + seam QA must pass)
  fem       fem_asset.py: solver tet mesh + per-tet von Mises -> render-space surface npz (sha + centroid checks)
  film      pro_hero.py --anim (the photoreal cut)
  sci       the data turntable re-rendered as solver tet mesh and von Mises field (registered: same camera/spin)
  assemble  cross-fade photoreal / mesh / field, typewriter data card, weight badge on EVERY frame, per-frame text QA
  encode    PNG sequence -> FFV1 master (.mkv), H.265 preview, H.264 chat copy (< chat_mp4_max_mb)
Any missing input, sha mismatch, failed QA gate or empty stage output exits non-zero. Nothing is ever placeholdered."""
import argparse, hashlib, json, os, shutil, subprocess, sys, time
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[2]


def die(msg):
    print(f'jr-film: FAIL: {msg}', file=sys.stderr); raise SystemExit(2)


def need(c, msg):
    if not c: die(msg)


def sha256(p):
    h = hashlib.sha256()
    with open(p, 'rb') as f:
        for b in iter(lambda: f.read(1 << 20), b''): h.update(b)
    return h.hexdigest()


def run(cmd, log, cwd=HERE, env=None):
    print('  $', ' '.join(map(str, cmd)), '>', log, flush=True)
    with open(log, 'w') as lf:
        r = subprocess.run(list(map(str, cmd)), cwd=cwd, stdout=lf, stderr=subprocess.STDOUT, env=env)
    if r.returncode != 0:
        tail = Path(log).read_text(errors='replace').splitlines()[-15:]
        die(f'{cmd[0]} exited {r.returncode}; see {log}\n    ' + '\n    '.join(tail))


class Stamp:
    """<work>/.stages/<stage>.json records the manifest sha a stage was built for."""
    def __init__(self, work, msha, force):
        self.d = Path(work) / '.stages'; self.d.mkdir(parents=True, exist_ok=True); self.msha = msha; self.force = set(force)

    def done(self, st, outputs):
        p = self.d / f'{st}.json'
        if st in self.force or not p.is_file(): return False
        rec = json.loads(p.read_text())
        return rec.get('manifest_sha256') == self.msha and all(Path(o).exists() for o in outputs)

    def mark(self, st, outputs, **extra):
        for o in outputs: need(Path(o).exists(), f'stage {st} produced no {o}')
        (self.d / f'{st}.json').write_text(json.dumps({'manifest_sha256': self.msha, 'outputs': list(map(str, outputs)),
                                                        'utc': time.strftime('%Y-%m-%dT%H:%M:%SZ', time.gmtime()), **extra}, indent=1))


def blender():
    b = os.environ.get('JR_BLENDER') or shutil.which('blender') or os.path.expanduser('~/opt/blender-4.2.23-linux-x64/blender')
    need(os.path.isfile(b), f'Blender not found ({b}); set JR_BLENDER'); return b


def memcap():
    m = os.environ.get('JR_MEMCAP') or shutil.which('memcap') or os.path.expanduser('~/bin/memcap')
    need(os.path.isfile(m), f'memcap not found ({m}); runtime.ensure_memcap refuses uncapped renders (#55)'); return [m]


def main():
    ap = argparse.ArgumentParser(prog='jr-film', description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    g = ap.add_mutually_exclusive_group()
    g.add_argument('--design', help='designs/<family>/<rev> folder')
    g.add_argument('--latest', nargs='?', const='designs/switchback', help='family dir; picks the newest RC (default)')
    ap.add_argument('--recipe', default=str(HERE / 'autofilm_satin.json'))
    ap.add_argument('--fem-store', default=os.environ.get('JR_FEM_STORE'), help='solver results dir (or $JR_FEM_STORE)')
    ap.add_argument('--work', required=True, help='scratch dir for this design (large)')
    ap.add_argument('--deliver', help='copy finals here')
    ap.add_argument('--plan', action='store_true', help='validate inputs and print the plan; render nothing')
    ap.add_argument('--force', action='append', default=[])
    ap.add_argument('--until', help='stop after this stage')
    ap.add_argument('--res', help='override recipe res key (e.g. low for a preview)'); ap.add_argument('--spp-scale', type=float, default=1.0)
    a = ap.parse_args()
    need(a.fem_store, '--fem-store (or $JR_FEM_STORE) is required: the solver output is the source of every stress pixel')
    R = json.loads(Path(a.recipe).read_text())
    if a.res:
        R['res'] = a.res; R['size'] = json.loads((HERE / 'shots.json').read_text())['resolutions'][a.res]
    R['spp'] = {k: max(1, int(round(v * a.spp_scale))) for k, v in R['spp'].items()}
    work = Path(a.work).expanduser(); work.mkdir(parents=True, exist_ok=True)
    logs = work / 'logs'; logs.mkdir(exist_ok=True)
    py = sys.executable

    # ---- manifest
    dm = work / 'design_manifest.json'
    src = ['--latest', str(REPO / (a.latest or 'designs/switchback'))] if not a.design else [str(REPO / a.design if not os.path.isabs(a.design) else a.design)]
    run([py, HERE / 'design_manifest.py', *src, '--fem-store', a.fem_store, '--out', dm], logs / 'manifest.log')
    man = json.loads(dm.read_text()); msha = man['manifest_sha256']; stamp = man['stamp']
    for k in ('label', 'badge', 'stamp', 'Sy_MPa', 'science', 'step', 'design_dir'):
        need(k in man, f'manifest lacks {k}')
    need(man['science'], 'manifest has no science shots (gate table / fem_cases mismatch)')
    # stage key = manifest + recipe + signature/art inputs: a new mark or recipe rebuilds prep and everything after
    # (code-only changes: use --force <stage>)
    key = hashlib.sha256((msha + Path(a.recipe).read_text() + sha256(HERE / R['sig_mask']) + sha256(os.path.expanduser(R['art']))).encode()).hexdigest()
    S = Stamp(work, key, a.force)
    film_plan = json.loads((HERE / R['film']).read_text())
    sci_shots = [s_ for s_ in film_plan['shots'] if s_['common'].get('science')]
    for s_ in sci_shots:
        need(any(m['gate'] == s_['common']['sci_case'] for m in man['science']), f"film shot {s_['name']} wants {s_['common']['sci_case']}, absent from the manifest")
    need('science_range' in film_plan and 'science_timeline_s' in film_plan, 'film JSON lacks science_range / science_timeline_s')
    plan = {'design': man['design_dir'], 'stamp': stamp, 'label': man['label'], 'badge': f"{man['mass_g']:.1f} g · {man['label']}",
            'science': [f"{s['gate']} {s['test']} {s['load']['value']:g} {s['load']['unit']} · PEAK {s['peak_vm_MPa']:.0f} MPa · SF {s['SF']} {s['verdict']}" for s in man['science']],
            'film_frames': film_plan['shots'][-1]['frames'][1], 'work': str(work)}
    print(json.dumps(plan, indent=1, ensure_ascii=False))
    if a.plan: return
    stop = lambda st: a.until == st

    # ---- ingest
    mesh = work / 'mesh'; bundle = mesh / 'bundle.json'
    if not (bundle.is_file() and json.loads(bundle.read_text())['source']['sha256'] == man['step']['sha256']):
        run([py, REPO / 'ops/render/marketing/ingest.py', Path(man['design_dir']) / man['step']['path'], '--out', mesh, '--units', 'mm',
             '--expected-sha256', man['step']['sha256']], logs / 'ingest.log', cwd=REPO / 'ops/render/marketing')
    need(json.loads(bundle.read_text())['source']['sha256'] == man['step']['sha256'], 'mesh bundle is not from the manifest STEP')
    if stop('ingest'): return

    # ---- prep
    prep = work / 'prep'
    if not S.done('prep', [prep / 'prep.json']):
        run([py, HERE / 'prep.py', mesh, prep, os.path.expanduser(R['art']), HERE / R['sig_mask'], HERE / R['prep_config']], logs / 'prep.log')
        if not (prep / 'regions.json').is_file(): shutil.copy(mesh / 'regions.json', prep / 'regions.json')
        pj = json.loads((prep / 'prep.json').read_text())
        need(pj['source']['sha256'] == man['step']['sha256'], 'prep is not from the manifest STEP')
        need(pj.get('normal_repair', {}).get('flat_seam_qa', {}).get('pass'), 'prep flat-seam QA did not pass')
        need((pj.get('edge_qa') or {}).get('pass'), 'prep edge-width gate did not pass')
        S.mark('prep', [prep / 'prep.json'])
    if stop('prep'): return

    # ---- fem
    fem = work / 'fem_surface.npz'
    if not S.done('fem', [fem]):
        run([py, HERE / 'fem_asset.py', a.fem_store, bundle, dm, fem], logs / 'fem.log'); S.mark('fem', [fem])
    if stop('fem'): return

    B = [*memcap(), blender(), '-b', '-P', HERE / 'pro_hero.py', '--']
    base = ['--prep', prep, '--res', R['res'], '--finish', R['finish']]
    # ---- film
    film = work / 'film'
    nfr = film_plan['shots'][-1]['frames'][1]
    if not S.done('film', [film / 'anim_qa.json']):
        run([*B, *base, '--out', film, '--spp', R['spp']['film'], '--anim', HERE / R['film'], '--step', 1], logs / 'film.log')
        S.mark('film', [film / 'anim_qa.json'])
    got = len(list(film.glob('f[0-9]*.png'))); need(got == nfr, f'film has {got} frames, plan says {nfr}')
    if stop('film'): return

    # ---- science passes: the SAME animation (camera, 3x360 deg turntable) re-rendered as solver mesh and as von Mises
    a0, b0 = film_plan['science_range']; rng = f'{a0}:{b0}'
    sci_dirs = {m: work / f'sci_{m}' for m in ('wire', 'heat')}
    for m, dr in sci_dirs.items():
        if not S.done(f'sci_{m}', [dr / 'anim_qa.json']):
            run([*B, *base, '--out', dr, '--spp', R['spp']['sci'], '--anim', HERE / R['film'], '--frame_range', rng,
                 '--sci', fem, '--sci_case', sci_shots[0]['common']['sci_case'], '--sci_mode', m, '--sci_vmax', man['Sy_MPa'],
                 '--sci_gain', R['sci_gain'], '--sci_glint', R['sci_glint'], '--sci_wire_rgb', json.dumps(R['sci_wire_rgb']),
                 '--sci_wire_px', R['sci_wire_px']], logs / f'sci_{m}.log')
            S.mark(f'sci_{m}', [dr / 'anim_qa.json'])
        got = len(list(dr.glob('f[0-9]*.png'))); need(got == b0 - a0, f'sci_{m}: {got} frames, expected {b0 - a0}')
    if stop('sci'): return

    # ---- assemble + encode
    final = work / 'final'; seq = final / f'{stamp}_seq'
    if not S.done('assemble', [final / f'{stamp}_assembly.json']):
        run([py, HERE / 'assemble_film.py', film, sci_dirs['wire'], sci_dirs['heat'], dm, HERE / R['film'], a.recipe, seq, final / f'{stamp}_assembly.json', '--size', f'{R["size"][0]}x{R["size"][1]}'], logs / 'assemble.log')
        S.mark('assemble', [final / f'{stamp}_assembly.json'])
    asm = json.loads((final / f'{stamp}_assembly.json').read_text()); need(asm['text_qa_pass'], 'text QA failed')
    W, H = R['size']; fps = R['fps']; fin = R['finish']
    mkv = final / f'{stamp}_{fin}_{W}x{H}_ffv1.mkv'; h265 = final / f'{stamp}_{fin}_{W}x{H}_h265.mp4'; chat = final / f'{stamp}_{fin}_chat.mp4'
    if not S.done('encode', [mkv, h265, chat]):
        inp = ['-framerate', fps, '-i', seq / 'f%05d.png']
        ff = lambda *x: run(['ffmpeg', '-y', '-loglevel', 'error', *x], logs / 'encode.log')
        ff(*inp, '-c:v', 'ffv1', '-level', 3, '-g', 1, '-slicecrc', 1, '-pix_fmt', 'rgb48le', mkv)
        ff(*inp, '-c:v', 'libx265', '-preset', 'slow', '-crf', 12, '-pix_fmt', 'yuv420p10le', '-tag:v', 'hvc1', '-movflags', '+faststart', h265)
        dur = asm['frames'] / fps; kbps = int(R['chat_mp4_max_mb'] * 8e3 * 0.92 / dur)
        for crf_pass in (1, 2):
            ff(*inp, '-c:v', 'libx264', '-preset', 'slow', '-b:v', f'{kbps}k', '-pass', crf_pass, '-passlogfile', work / 'x264pass',
               '-pix_fmt', 'yuv420p', '-movflags', '+faststart', *(['-f', 'mp4', '/dev/null'] if crf_pass == 1 else [chat]))
        need(chat.stat().st_size < R['chat_mp4_max_mb'] * 1e6, f'chat copy {chat.stat().st_size/1e6:.1f} MB over budget')
        S.mark('encode', [mkv, h265, chat])
    for p in (mkv, h265, chat):
        n = int(subprocess.run(['ffprobe', '-v', 'error', '-count_frames', '-select_streams', 'v:0', '-show_entries', 'stream=nb_read_frames',
                                '-of', 'csv=p=0', p], capture_output=True, text=True).stdout.strip() or 0)
        need(n == asm['frames'], f'{p.name}: {n} frames, expected {asm["frames"]}')
    receipt = {'schema': 'jarambit.render.pro.autofilm_receipt.v1', 'manifest_sha256': msha, 'stamp': stamp, 'label': man['label'],
               'frames': asm['frames'], 'fps': fps, 'text_qa_pass': asm['text_qa_pass'],
               'outputs': {p.name: {'bytes': p.stat().st_size, 'sha256': sha256(p)} for p in (mkv, h265, chat)},
               'sequence': str(seq), 'release_ready': False, 'note': 'design candidate, not certified'}
    rp = final / f'{stamp}_receipt.json'; rp.write_text(json.dumps(receipt, indent=1, ensure_ascii=False))
    if a.deliver:
        d = Path(a.deliver); d.mkdir(parents=True, exist_ok=True)
        for p in (h265, chat, rp, dm, final / f'{stamp}_assembly.json'): shutil.copy(p, d)
    print('JR_FILM_DONE', rp)


if __name__ == '__main__':
    main()
