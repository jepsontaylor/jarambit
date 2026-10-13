"""Issue #53: protected regions, bounded frame memory and fail-closed rendering/delivery."""
import ast
import hashlib
import json
import os
from pathlib import Path
import runpy
import subprocess
import sys
import time
import tracemalloc
from types import SimpleNamespace

import numpy as np
import pytest

from ops.render.pro import director_gates, qa, runtime

ROOT = Path(__file__).resolve().parents[4]
PRO = ROOT / 'ops/render/pro'


@pytest.fixture(scope='module')
def shader_results(tmp_path_factory):
    out = tmp_path_factory.mktemp('protected-shaders')
    blender = Path.home() / 'opt/blender-4.2.23-linux-x64/blender'
    with (out / 'blender.log').open('w') as log:
        p = subprocess.run([str(blender), '-b', '--threads', '4', '--python-exit-code', '1',
                            '-P', str(PRO / 'tests/blender_regions.py'), '--', str(out)],
                           stdout=log, stderr=subprocess.STDOUT, timeout=180,
                           env={**os.environ, 'CUDA_VISIBLE_DEVICES': ''})
    assert p.returncode == 0, (out / 'blender.log').read_text()[-6000:]
    return json.loads((out / 'result.json').read_text())


@pytest.mark.parametrize('finish', ['art', 'flame', 'satin_blue'])
@pytest.mark.parametrize('override', [False, True])
def test_protected_regions_per_finish(shader_results, finish, override):
    row = next(r for r in shader_results['finishes'] if r['finish'] == finish and r['override'] == override)
    assert row['mark_pixel_max_diff'] < 1e-6
    assert row['antialiased_mark_pixel_max_diff'] < 1e-6
    assert row['grind_pixel_max_diff'] < 1e-6
    assert all(p['value'] == 0 and not p['linked'] for p in row['protected_inputs'].values())
    if finish == 'flame':
        assert row['body_pixel_diff'] > .01  # Finish is still active outside protected regions.


def test_frame_images_freed_on_success_and_error(shader_results):
    assert shader_results['qa_images_retained'] == 0


def frame(index=0):
    return {'frame': index, 'edge_sharpness': {'pass': True}, 'lights_pass': True,
            'sig': {'pass': True}, 'sig_mesh_pass': True, 'image': {'pass': True},
            'physical_state_sha256': f'state-{index}'}


def test_animation_receipt_streams_and_fails_closed(tmp_path):
    path = str(tmp_path / 'receipt.json')
    tracemalloc.start()
    with qa.AnimationReceipt(path, {'release_ready': False}) as receipt:
        for i in range(2000):
            receipt.add({**frame(i), 'state': {'large': 'x' * 8192}})
        assert receipt.frames == 2000
        assert not isinstance(receipt.frames, list)
    _, peak = tracemalloc.get_traced_memory(); tracemalloc.stop()
    assert peak < 2 * 1024**2  # A retained list would exceed 16 MiB.
    doc = json.loads(Path(path).read_text())
    assert len(doc['frames']) == 2000 and doc['all_pass'] and doc['render_ready']
    with qa.AnimationReceipt(path, {}) as receipt:
        pass
    doc = json.loads(Path(path).read_text())
    assert not doc['all_pass'] and not doc['render_ready']


def functions(names):
    tree = ast.parse((PRO / 'pro_hero.py').read_text())
    return compile(ast.Module(body=[n for n in tree.body if isinstance(n, ast.FunctionDef)
                                    and n.name in names], type_ignores=[]), str(PRO / 'pro_hero.py'), 'exec')


def worker_env(tmp_path):
    film = tmp_path / 'film.json'
    film.write_text(json.dumps({'fps': 30, 'shots': [{'name': 'fixture', 'frames': [0, 2],
                      'common': {'sig_side': 'front'}, 'start': {}, 'end': {}}]}))
    calls = []
    r = SimpleNamespace(image_settings=SimpleNamespace())
    scene = SimpleNamespace(render=r, frame_set=lambda n: None)
    image = SimpleNamespace(save_render=lambda p, scene: None)
    env = dict(A={'--anim': str(film)}, CFG={'shots': [{'name': 'fixture', 'sig_side': 'front'}], 'flame': {}},
               json=json, os=os, time=time, np=np, hashlib=hashlib, Q=qa, BASE_LIGHTS={}, OUT=str(tmp_path),
               PREP=str(tmp_path), r=r, sc=scene, reset_lights=lambda: None, place_camera=lambda s: .1,
               aim_mirror_lights=lambda s: None, clear_lights=lambda: [], qa_lights=lambda: {'pass': True},
               qa_sig_frame=lambda side: {'pass': True}, physical_state=lambda: ({}, 'same-state'),
               mesh_qa={'front': {'pass': True}, 'back': {'pass': True}},
               FINISH='flame', FILM_PATH=True, RES='4k', CODE_ID={}, MATERIAL_STATE={},
               MAN={'edge_qa': {'pass': True}, 'source': {}},
               fo=SimpleNamespace(file_slots=[SimpleNamespace(), SimpleNamespace()]),
               bpy=SimpleNamespace(data=SimpleNamespace(images={'Render Result': image}), app=SimpleNamespace(version_string='test'),
                                   ops=SimpleNamespace(render=SimpleNamespace(render=lambda **kw: calls.append(kw)))),
               frame_qa_image=lambda p, f: {'pass': True},
               image_pixels=lambda p, raw=False: np.full((4, 4, 4), .5 if 'qa_idx_' in p else .02),
               cd=SimpleNamespace(lens=85, dof=SimpleNamespace(use_dof=False)),
               cam=SimpleNamespace(location=[0, 0, 0], rotation_euler=[0, 0, 0]),
               SPP=1, RX=4, RY=4, LOOK={'agx_look': 'Standard', 'exposure': 0},
               sha=lambda p: 'fixture-sha', light_rec=[])
    exec(functions({'lerp_shot', 'run_animation', 'run_stills'}), env)
    return env, calls


@pytest.mark.parametrize('kind', ['edge', 'missing_edge', 'lights', 'signature', 'mesh', 'image', 'image_error', 'valid'])
@pytest.mark.parametrize('animation', [True, False])
def test_worker_gate_failures_block_render_or_delivery(tmp_path, kind, animation):
    env, calls = worker_env(tmp_path)
    if kind == 'edge': env['MAN']['edge_qa']['pass'] = False
    if kind == 'missing_edge': env['MAN'].pop('edge_qa')
    if kind == 'lights': env['qa_lights'] = lambda: {'pass': False}
    if kind == 'signature': env['qa_sig_frame'] = lambda side: {'pass': False}
    if kind == 'mesh': env['mesh_qa'] = {}
    if kind == 'image': env['frame_qa_image'] = lambda p, f: {'pass': False}
    if kind == 'image_error':
        def broken(p, f): raise ValueError('missing image')
        env['frame_qa_image'] = broken
    rc = env['run_animation' if animation else 'run_stills']()
    assert rc == (0 if kind == 'valid' else 1)
    expected = (2 if animation else 1) if kind == 'valid' else int(kind in ('image', 'image_error'))
    assert len(calls) == expected
    path = tmp_path / ('anim_qa.json' if animation else 'fixture_4k_flame.qa.json')
    receipt = json.loads(path.read_text())
    assert receipt['all_pass'] == (kind == 'valid')
    if animation:
        assert receipt['render_ready'] == (kind == 'valid')
        assert receipt['release_ready'] is False
    else:
        assert (receipt['status'] == 'RENDERED') == (kind == 'valid')


@pytest.mark.parametrize('case', ['false_normal', 'false_shard', 'hash_drift', 'empty', 'duplicate', 'missing', 'fault_passes', 'fault_crash', 'valid'])
def test_director_requires_complete_normal_runs_and_expected_faults(tmp_path, monkeypatch, case):
    film = tmp_path / 'film.json'
    film.write_text(json.dumps({'shots': [{'frames': [0, 111]}]}))
    monkeypatch.setattr(runtime, 'ensure_memcap', lambda: 4)
    monkeypatch.setattr(runtime, 'safe_workers', lambda: 4)
    def fake_run(cmd, **kw):
        requested = [int(x) for x in cmd[cmd.index('--frames')+1].split(',')]
        name = cmd[cmd.index('--receipt')+1]
        dest = Path(cmd[cmd.index('--out')+1]) / name
        fault = cmd[cmd.index('--fault')+1] if '--fault' in cmd else None
        if case == 'missing' or case == 'fault_crash' and fault:
            return SimpleNamespace(returncode=1)
        rows = [frame(i) for i in requested]
        ok, rc = True, 0
        if case == 'false_normal' and name == 'contiguous.json' or case == 'false_shard' and name.startswith('shard'):
            ok = False; rows[0]['lights_pass'] = False
        if case == 'empty' and name == 'contiguous.json': rows = []
        if case == 'duplicate' and name == 'contiguous.json': rows = [frame(requested[0])] * len(requested)
        if case == 'hash_drift' and name.startswith('shard'): rows[0]['physical_state_sha256'] = 'drift'
        if fault and case != 'fault_passes':
            rows = rows[:1]; ok, rc = False, 1
            rows[0]['lights_pass' if fault == 'light_in_frame' else 'sig_mesh_pass'] = False
        dest.write_text(json.dumps({'frames': rows, 'fault': fault, 'all_pass': ok, 'render_ready': ok}))
        return SimpleNamespace(returncode=rc)
    monkeypatch.setattr(director_gates.subprocess, 'run', fake_run)
    assert director_gates.main(['unused-prep', str(film), str(tmp_path)]) == (0 if case == 'valid' else 1)
    assert json.loads((tmp_path / 'director_gates.json').read_text())['all_pass'] == (case == 'valid')


@pytest.mark.parametrize('kind', ['edge', 'missing_edge', 'image', 'clipping', 'signature', 'lights', 'mesh', 'aggregate', 'missing_aggregate', 'empty'])
def test_delivery_refuses_any_failed_or_missing_gate_before_writing(tmp_path, monkeypatch, kind):
    src, dst = tmp_path / 'src', tmp_path / 'delivery'
    src.mkdir()
    receipt = {'status': 'RENDERED', 'all_pass': True, 'edge_sharpness': {'pass': True}, 'image': {'pass': True},
               'clipping': {'pass': True}, 'signature_frame': {'pass': True}, 'lights': {'pass': True},
               'signature_mesh': {'front': {'pass': True}, 'back': {'pass': True}}}
    if kind == 'missing_edge': receipt.pop('edge_sharpness')
    elif kind == 'missing_aggregate': receipt.pop('all_pass')
    elif kind == 'aggregate': receipt['all_pass'] = False
    elif kind == 'mesh': receipt['signature_mesh'] = {}
    elif kind != 'empty': receipt[{'edge': 'edge_sharpness', 'signature': 'signature_frame'}.get(kind, kind)]['pass'] = False
    if kind != 'empty': (src / 'still.qa.json').write_text(json.dumps(receipt))
    monkeypatch.setattr(runtime, 'ensure_memcap', lambda: 4)
    monkeypatch.setitem(sys.modules, 'runtime', runtime)
    monkeypatch.setitem(sys.modules, 'qa', qa)
    monkeypatch.setattr(sys, 'argv', [str(PRO / 'deliver.py'), str(src), str(dst)])
    with pytest.raises(SystemExit):
        runpy.run_path(str(PRO / 'deliver.py'), run_name='__main__')
    assert not dst.exists()


def test_safe_workers_uses_free_memory_and_hard_ceiling(monkeypatch):
    monkeypatch.setattr(os, 'sched_getaffinity', lambda pid: set(range(64)))
    assert runtime.safe_workers(64, free_bytes=10*runtime.GIB, per_worker_bytes=runtime.GIB) == 6
    assert runtime.safe_workers(64, free_bytes=1000*runtime.GIB) == 16
    with pytest.raises(RuntimeError, match='insufficient free memory'):
        runtime.safe_workers(free_bytes=2*runtime.GIB)
    with pytest.raises(RuntimeError, match='insufficient free memory'):
        runtime.safe_workers(free_bytes=1000*runtime.GIB, fixed_bytes=33*runtime.GIB)


def test_uncapped_entry_refuses_missing_memcap(monkeypatch):
    monkeypatch.setattr(runtime, 'available_memory', lambda: 100*runtime.GIB)
    monkeypatch.setattr(runtime, 'scope_limits', lambda: [])
    monkeypatch.setattr(runtime.shutil, 'which', lambda name: None)
    monkeypatch.setattr(Path, 'is_file', lambda path: False)
    monkeypatch.setattr(os, 'nice', lambda n: None)
    with pytest.raises(RuntimeError, match='memcap is required'):
        runtime.ensure_memcap()


@pytest.mark.parametrize('prefix,late,applied', [([], True, False), (['--threads', '0'], False, False),
    (['--threads', '128', '--python-exit-code', '1'], False, False),
    (['--threads', '2', '--python-exit-code', '1'], True, False),
    (['--threads', '2', '--python-exit-code', '1'], False, True)])
def test_blender_limits_precede_script_and_preserve_script_arguments(prefix, late, applied):
    original = ['/blender', '-b', *prefix, '-P', '/hero.py',
                *(['--threads', '128', '--python-exit-code', '0'] if late else []),
                '--', '--cfg', 'shots.json', '--threads', '900']
    command, ready, workers = runtime.blender_command(original, 4)
    assert ready is applied and 1 <= workers <= 4
    assert command[1:5] == ['--threads', str(workers), '--python-exit-code', '1']
    assert command.index('--threads') < command.index('-P')
    assert command[command.index('--'):] == original[original.index('--'):]
    assert command[:command.index('--')].count('--threads') == 1


def test_already_capped_blender_reexecs_if_native_flags_are_late(monkeypatch):
    monkeypatch.setattr(runtime, 'available_memory', lambda: 100*runtime.GIB)
    monkeypatch.setattr(runtime, 'scope_limits', lambda: [(runtime.MEMCAP, 30*runtime.GIB, '0')])
    monkeypatch.setattr(Path, 'read_bytes', lambda p: b'/blender\0-b\0-P\0/hero.py\0--\0--prep\0mesh\0')
    monkeypatch.setattr(os, 'nice', lambda n: None)
    commands = []
    def capture(file, argv):
        commands.append(argv)
        raise RuntimeError('captured native exec')
    monkeypatch.setattr(os, 'execv', capture)
    with pytest.raises(RuntimeError, match='captured native exec'):
        runtime.ensure_memcap(blender=True)
    assert commands[0][1] == '--threads' and commands[0].index('--python-exit-code') < commands[0].index('-P')


def test_director_rejects_malformed_and_incomplete_fault_receipts():
    assert not director_gates.normal_pass({'frames': [None], 'all_pass': True, 'render_ready': True}, [0], 0)
    assert not director_gates.normal_pass([], [0], 0)
    false_receipt = {'fault': 'light_in_frame', 'all_pass': False, 'render_ready': False,
                     'frames': [{'frame': 0, 'edge_sharpness': {'pass': True}, 'lights_pass': False}]}
    assert not director_gates.fault_pass(false_receipt, [0], 1, 'light_in_frame')


@pytest.mark.parametrize('swap', ['0', 'max'])
def test_entry_guard_verifies_real_cap_not_environment(monkeypatch, swap):
    monkeypatch.setenv('JARAMBIT_PRO_CAPPED', '1')
    monkeypatch.setattr(runtime, 'available_memory', lambda: 100*runtime.GIB)
    monkeypatch.setattr(runtime, 'scope_limits', lambda: [(runtime.MEMCAP, 30*runtime.GIB, swap)])
    monkeypatch.setattr(runtime.shutil, 'which', lambda name: '/host/bin/memcap')
    monkeypatch.setattr(os, 'nice', lambda n: None)
    commands = []
    def capture(file, argv):
        commands.append(argv)
        raise RuntimeError('captured exec')
    monkeypatch.setattr(os, 'execv', capture)
    if swap == '0':
        assert runtime.ensure_memcap() >= 1
        assert not commands
    else:
        with pytest.raises(RuntimeError, match='captured exec'):
            runtime.ensure_memcap()
        assert commands[0][:3] == ['/host/bin/memcap', '32G', '--']
