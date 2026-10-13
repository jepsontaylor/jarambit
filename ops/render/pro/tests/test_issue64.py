"""Public worker/runner regressions for the five post-merge #63 findings."""
import hashlib
import json
from pathlib import Path
import sys
import subprocess
from types import SimpleNamespace

import pytest

from ops.render.pro import jr_film
from ops.render.pro import runtime
from test_issue53 import PRO, functions, worker_env

NATIVE_RUN = subprocess.run


def test_resume_rejects_unproven_old_frames(tmp_path):
    env, calls = worker_env(tmp_path)
    env['A']['--resume'] = '1'
    for f in range(2):
        (tmp_path / f'f{f:05d}.png').write_bytes(b'old pixels')
    (tmp_path / 'anim_qa.json').write_text(json.dumps({'code': {'old': True}, 'frames': [], 'all_pass': True}))
    assert env['run_animation']() == 0
    assert len(calls) == 2
    assert all((tmp_path / f'f{f:05d}.png').read_bytes() == b'new frame' for f in range(2))


@pytest.mark.parametrize('changed', ['none', 'code', 'finish', 'material', 'state', 'film', 'spp', 'size', 'pixels', 'plate', 'missing_plate', 'bad_receipt', 'forced'])
def test_resume_requires_matching_state_and_output_hashes(tmp_path, changed):
    env, calls = worker_env(tmp_path)
    env['A']['--resume'] = '1'
    assert env['run_animation']() == 0
    calls.clear()
    if changed == 'code': env['CODE_ID'] = {'new_code': 'sha'}
    if changed == 'finish': env['FINISH'] = 'art'
    if changed == 'material': env['MATERIAL_STATE'] = {'roughness': .7}
    if changed == 'state': env['physical_state'] = lambda: ({'new': True}, 'changed-state')
    if changed == 'film':
        film = Path(env['A']['--anim']); plan = json.loads(film.read_text())
        plan['shots'][0]['start']['az'] = 90; film.write_text(json.dumps(plan))
    if changed == 'spp': env['SPP'] += 1
    if changed == 'size': env['RX'] *= 2
    if changed == 'pixels': (tmp_path / 'f00000.png').write_bytes(b'corruption')
    if changed == 'plate': (tmp_path / 'qa_sig_f00000_0001.png').write_bytes(b'corruption')
    if changed == 'missing_plate': (tmp_path / 'qa_idx_f00000_0001.png').unlink()
    if changed == 'bad_receipt':
        (tmp_path / 'f00000.png.provenance.json').write_text('broken json')
    if changed == 'forced': env['A']['--resume'] = '0'
    assert env['run_animation']() == 0
    assert len(calls) == (0 if changed == 'none' else 1 if changed in ('pixels', 'plate', 'missing_plate', 'bad_receipt') else 2)


@pytest.fixture
def film_runner(tmp_path, monkeypatch):
    here = tmp_path / 'pro'; here.mkdir()
    work = tmp_path / 'work'
    monkeypatch.setattr(jr_film, 'HERE', here)
    recipe = dict(res='hd', size=[1920, 1080], fps=30, finish='satin_blue', film='film.json',
                  spp={'film': 64, 'sci': 24}, sig_mask='sig.png', art=str(here / 'art.png'),
                  prep_config='prep.json', sci_gain=1.5, sci_glint=.35, sci_wire_rgb=[.2,.5,1],
                  sci_wire_px=.7, chat_mp4_max_mb=24)
    for name in ('sig.png', 'art.png'):
        (here / name).write_bytes(b'fixture')
    (here / 'prep.json').write_text('{}')
    (here / 'shots.json').write_text(json.dumps({'resolutions': {'hd': [1920,1080], 'low': [64,36]}}))
    (here / 'film.json').write_text(json.dumps({'fps': 30, 'title': 'fixture', 'shots': [
        {'name': 'fixture', 'frames': [0,3], 'common': {'science': True, 'sci_case': 'V3'}, 'start': {}, 'end': {}}],
        'science_range': [0,3], 'science_timeline_s': {}}))
    (here / 'recipe.json').write_text(json.dumps(recipe))
    font = here / 'fonts'; font.mkdir()
    (font / 'Inter-VariableFont_opsz,wght.ttf').write_bytes(b'font fixture')
    man = dict(manifest_sha256='manifest-sha', stamp='fixture', label='candidate', badge='badge', mass_g=64.841,
               Sy_MPa=828, design_dir=str(tmp_path / 'design'), step={'sha256':'step-sha','path':'hero.step'},
               fem={'mesh': {'sha256':'mesh-sha'}}, science=[dict(gate='V3', test='pry', load={'value':1,'unit':'N'},
                    peak_vm_MPa=500, SF=1.6, verdict='unverified', fem={'sha256':'field-sha'})])
    calls = []; admitted = []
    monkeypatch.setattr(jr_film, 'ensure_memcap', lambda **kw: admitted.append(kw) or 3, raising=False)
    monkeypatch.setattr(jr_film, 'blender', lambda: '/blender')
    def run(cmd, log, **kw):
        cmd = list(map(str, cmd)); calls.append(cmd)
        assert admitted, 'jr-film must admit/cap its parent before launching any child'
        script = next((Path(x).name for x in cmd if x.endswith('.py')), None)
        def write(path, value):
            path = Path(path); path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(json.dumps(value))
        if script == 'design_manifest.py': write(work / 'design_manifest.json', man)
        elif script == 'ingest.py':
            write(work / 'mesh/bundle.json', {'source': {'sha256':'step-sha'}})
            write(work / 'mesh/regions.json', {})
        elif script == 'prep.py':
            write(work / 'prep/prep.json', {'source':{'sha256':'step-sha'},
                  'normal_repair':{'flat_seam_qa':{'pass':True}}, 'edge_qa':{'pass':True}})
        elif script == 'fem_asset.py': write(work / 'fem_surface.npz', {})
        elif script == 'pro_hero.py':
            out = Path(cmd[cmd.index('--out')+1]); write(out / 'anim_qa.json', {'all_pass':True,'render_ready':True,'run':len(calls)})
            for f in range(3): write(out / f'f{f:05d}.png', {'run':len(calls)})
        elif script == 'assemble_film.py': write(cmd[-3], {'text_qa_pass':True,'frames':3})
        elif cmd[0] == 'ffmpeg' and cmd[-1] != '/dev/null':
            Path(cmd[-1]).write_bytes(b'encoded fixture')
    monkeypatch.setattr(jr_film, 'run', run)
    monkeypatch.setattr(jr_film.subprocess, 'run', lambda *a, **kw: SimpleNamespace(stdout='3', returncode=0))
    def invoke(*args):
        monkeypatch.setattr(sys, 'argv', ['jr-film','--design','designs/switchback/C10a','--fem-store','fixture',
                                         '--work',str(work),'--recipe',str(here / 'recipe.json'),*args])
        jr_film.main()
    return SimpleNamespace(invoke=invoke, calls=calls, here=here, work=work, admitted=admitted)


@pytest.mark.parametrize('changed', ['none','overrides','film','prep','art','signature','font'])
def test_public_film_runner_invalidates_effective_inputs(film_runner, changed):
    F = film_runner
    F.invoke(); F.calls.clear()
    if changed in ('film', 'prep'):
        p = F.here / f'{changed}.json'; doc = json.loads(p.read_text()); doc['changed'] = True; p.write_text(json.dumps(doc))
    if changed in ('art','signature','font'):
        p = F.here / {'art':'art.png','signature':'sig.png','font':'fonts/Inter-VariableFont_opsz,wght.ttf'}[changed]
        p.write_bytes(b'new input')
    F.invoke(*(['--res','low','--spp-scale','0.25'] if changed == 'overrides' else []))
    renders = [c for c in F.calls if any(x.endswith('/pro_hero.py') for x in c)]
    assert len(renders) == (0 if changed == 'none' else 3)
    assemblies = [c for c in F.calls if any(x.endswith('/assemble_film.py') for x in c)]
    assert len(assemblies) == (0 if changed == 'none' else 1)
    if changed == 'overrides':
        assert renders[0][renders[0].index('--res')+1] == 'low'
        assert renders[0][renders[0].index('--spp')+1] == '16'
        resolved = json.loads(Path(assemblies[0][-5]).read_text())
        assert resolved['res'] == 'low' and resolved['size'] == [64,36] and resolved['spp']['film'] == 16


def test_forced_film_rerenders_frames_and_downstream(film_runner):
    F = film_runner; F.invoke(); F.calls.clear(); F.invoke('--force','film')
    render = next(c for c in F.calls if any(x.endswith('/pro_hero.py') for x in c))
    assert render[render.index('--resume')+1] == '0'
    assert any(any(x.endswith('/assemble_film.py') for x in c) for c in F.calls)


def test_public_encoders_use_admitted_threads_and_parent_scope(film_runner):
    F = film_runner; F.invoke()
    encoders = [c for c in F.calls if c[0] == 'ffmpeg']
    assert len(encoders) == 4
    for c in encoders:
        assert c[c.index('-threads')+1] == '3'
        assert c[c.index('-filter_threads')+1] == '3'
        assert c[c.index('-filter_complex_threads')+1] == '3'
        assert c[c.index('-c:v')+2:c.index('-c:v')+4] == ['-threads','3']
    h265 = next(c for c in encoders if 'libx265' in c)
    assert h265[h265.index('-x265-params')+1] == 'pools=none:frame-threads=3:wpp=0'


def test_inter_font_checksum_manifest():
    font = PRO / 'fonts/Inter-VariableFont_opsz,wght.ttf'
    expected = '0be2399ea925f1f83ff974764761da9860ec50742ed29a5d4c1ffd0c5c7ac3a8'
    assert hashlib.sha256(font.read_bytes()).hexdigest() == expected
    assert f'{expected}  {font.name}' in (font.parent / 'SHA256SUMS').read_text().splitlines()


def test_signature_rejects_dielectric_override():
    env = {'CFG': {'protected': {'mark': {'metallic': 0}}}}
    exec(functions({'protect_signature'}), env)
    with pytest.raises(ValueError, match='must remain bare metal'):
        env['protect_signature'](None, None, None, None)


def test_jr_film_refuses_failed_admission_before_children(film_runner, monkeypatch):
    def refuse(**kw): raise RuntimeError('insufficient free memory')
    monkeypatch.setattr(jr_film, 'ensure_memcap', refuse)
    with pytest.raises(RuntimeError, match='insufficient free memory'):
        film_runner.invoke()
    assert not film_runner.calls


def test_failed_frame_qa_cannot_seed_resume_cache(tmp_path):
    env, calls = worker_env(tmp_path)
    env['A']['--resume'] = '1'
    env['frame_qa_image'] = lambda p, f: {'pass': False}
    assert env['run_animation']() == 1
    assert not (tmp_path / 'f00000.png.provenance.json').exists()
    calls.clear(); env['frame_qa_image'] = lambda p, f: {'pass': True}
    assert env['run_animation']() == 0 and len(calls) == 2


def test_real_encoders_roundtrip_under_memcap(film_runner, monkeypatch):
    from PIL import Image
    F = film_runner
    cap = [str(Path.home() / 'bin/memcap'), '32G', '--']
    fake_run = jr_film.run
    def run(cmd, log, **kw):
        cmd = list(map(str, cmd))
        if cmd[0] == 'ffmpeg':
            p = NATIVE_RUN([*cap, *cmd], capture_output=True, text=True)
            assert p.returncode == 0, p.stderr
        else:
            fake_run(cmd, log, **kw)
            if any(x.endswith('/assemble_film.py') for x in cmd):
                seq = Path(cmd[-4]); seq.mkdir(parents=True, exist_ok=True)
                for f in range(3): Image.new('RGB', (64,36), (40+f*20,70,90)).save(seq / f'f{f:05d}.png')
    monkeypatch.setattr(jr_film, 'run', run)
    monkeypatch.setattr(jr_film.subprocess, 'run', NATIVE_RUN)
    F.invoke('--res','low')
    for p in (F.work / 'final').glob('*.*'):
        if p.suffix not in ('.mp4','.mkv'): continue
        result = NATIVE_RUN([*cap,'ffmpeg','-v','error','-threads','3','-i',str(p),'-f','null','-'], capture_output=True)
        assert result.returncode == 0, result.stderr


def test_real_runtime_guard_verifies_pipeline_scope():
    code = ('import json; from ops.render.pro import runtime; '
            'workers = runtime.ensure_memcap(); '
            'print(json.dumps({"workers": workers, "limits": runtime.scope_limits()}))')
    p = NATIVE_RUN([sys.executable, '-c', code], cwd=PRO.parents[2], capture_output=True, text=True)
    assert p.returncode == 0, p.stderr
    rec = json.loads(p.stdout)
    assert 1 <= rec['workers'] <= runtime.MAX_THREADS
    assert any(limit <= runtime.MEMCAP and swap == '0' for limit, _, swap in rec['limits'])
