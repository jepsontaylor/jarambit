"""Fail-closed pro gates and an O(1)-memory animation receipt writer."""
import json
import os
import hashlib
from pathlib import Path


def file_sha256(path):
    h = hashlib.sha256()
    with open(path, 'rb') as f:
        for block in iter(lambda: f.read(1 << 20), b''): h.update(block)
    return h.hexdigest()


class FrameCache:
    """One small receipt per frame; reuse requires matching inputs, state and all plate bytes."""
    def __init__(self, provenance):
        self.key = hashlib.sha256(json.dumps(provenance, sort_keys=True).encode()).hexdigest()

    def matches(self, png, state, outputs):
        try:
            rec = json.loads(Path(png + '.provenance.json').read_text())
            return (rec.get('render_provenance_sha256') == self.key
                    and rec.get('physical_state_sha256') == state
                    and rec.get('outputs') == {Path(p).name: file_sha256(p) for p in outputs}
                    and all(Path(p).stat().st_size > 0 for p in outputs))
        except (OSError, ValueError, AttributeError):
            return False

    def mark(self, png, state, outputs):
        rec = {'render_provenance_sha256': self.key, 'physical_state_sha256': state,
               'outputs': {Path(p).name: file_sha256(p) for p in outputs}}
        path = png + '.provenance.json'
        with open(path + '.partial', 'w') as f:
            json.dump(rec, f); f.flush(); os.fsync(f.fileno())
        os.replace(path + '.partial', path)


def passed(check):
    return isinstance(check, dict) and check.get('pass') is True and 'error' not in check


def pre_render_pass(edge, lights, signature, mesh):
    return (passed(edge) and passed(lights) and passed(signature) and isinstance(mesh, dict)
            and all(passed(mesh.get(side)) for side in ('front', 'back')))


def frame_pass(frame, *, dry=False):
    return (passed(frame.get('edge_sharpness')) and frame.get('lights_pass') is True
            and passed(frame.get('sig')) and frame.get('sig_mesh_pass') is True
            and (dry or passed(frame.get('image'))))


def still_pass(qa):
    return (pre_render_pass(qa.get('edge_sharpness'), qa.get('lights'),
                            qa.get('signature_frame'), qa.get('signature_mesh'))
            and passed(qa.get('clipping')) and passed(qa.get('image')))


class AnimationReceipt:
    """Write each frame immediately; keep only a count and aggregate gate state in RAM."""
    def __init__(self, path, header, *, dry=False):
        self.path, self.header, self.dry = path, header, dry
        self.frames = 0
        self.all_pass = True

    def __enter__(self):
        self.file = open(self.path + '.partial', 'w')
        self.file.write(json.dumps({**self.header, 'dry': self.dry})[:-1] + ', "frames": [')
        return self

    def add(self, frame):
        if self.frames:
            self.file.write(',\n')
        json.dump(frame, self.file)
        self.frames += 1
        self.all_pass = self.all_pass and frame_pass(frame, dry=self.dry)

    def __exit__(self, kind, value, traceback):
        self.all_pass = bool(self.all_pass and self.frames and kind is None)
        ready = self.all_pass and not self.header.get('fault')
        self.file.write('], "all_pass": ' + json.dumps(self.all_pass)
                        + ', "render_ready": ' + json.dumps(ready) + '}\n')
        self.file.flush()
        os.fsync(self.file.fileno())
        self.file.close()
        os.replace(self.path + '.partial', self.path)
