"""Fail-closed pro gates and an O(1)-memory animation receipt writer."""
import json
import os


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
