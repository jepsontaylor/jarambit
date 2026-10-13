"""Preset consistency: every shot resolves to an existing rig, every region has a finish, HDRIs are pinned."""
import json
import os

import pytest

from conftest import MKT

P = os.path.join(MKT, 'presets')
LABELS = ['body', 'bevel', 'edge_apex', 'serration', 'ring', 'pad', 'spine']


def load(n):
    return json.load(open(os.path.join(P, n)))


def test_finish_covers_all_regions():
    f = load('finish_ti64.json')
    assert f['appearance_assumed'] is True
    assert set(f['default_assignment']) == set(LABELS)
    for lab, name in f['default_assignment'].items():
        assert name in f['finishes'], (lab, name)
    assert f['accent_finish'] in f['finishes']
    m = f['metal']
    assert all(0 < x < 1 for x in m['base_color_lin'] + m['f82_tint'])
    for name, s in f['finishes'].items():
        assert 0 < s['roughness'] < 1 and 0 <= s.get('anisotropy', 0) <= 1, name
        if 'thin_film_nm' in s:
            assert 150 <= s['thin_film_nm'] <= 350


@pytest.mark.parametrize('rig', ['rig_studio_softbox.json', 'rig_dark_strip.json', 'rig_product_white.json'])
def test_rig_schema(rig):
    r = load(rig)
    assert r['schema'] == 'jarambit.render.rig.v1'
    for L in r['lights']:
        assert L.get('type', 'AREA') in ('AREA', 'POINT', 'SPOT', 'CARD')
        assert ('az' in L and 'el' in L) or L.get('aim') == 'mirror'
        if L.get('aim') == 'mirror':
            assert L['region'] in LABELS
    h = r['world'].get('hdri')
    if h:
        assert len(h['sha256']) == 64 and h['source']
    assert r['backdrop']['type'] in ('sweep', 'plane', 'none')


def test_dark_rig_flags_artistic_visibility():
    assert load('rig_dark_strip.json')['world']['glossy_only'] is True


def test_shots_reference_existing_presets():
    s = load('shots_default.json')
    ids = [x['id'] for x in s['stills'] + s['turntables']]
    assert len(ids) == len(set(ids))
    assert {'hero_3q', 'profile_flat', 'spine_top', 'edge_macro', 'ring_detail', 'dark_hero', 'white_ecom',
            'flat_lay'} <= set(ids)
    for x in s['stills'] + s['turntables']:
        assert os.path.isfile(os.path.join(P, x['rig'] + '.json')), x['rig']
        assert x['camera']['focal_mm'] > 0
    for t in s['turntables']:
        assert t['frames'] == 240 and t['fps'] == 30 and t['loop']


def test_no_combat_framing_in_presets():
    bad = ('combat', 'tactical', 'weapon', 'fight', 'kill', 'attack')
    for n in os.listdir(P):
        txt = open(os.path.join(P, n)).read().lower()
        assert not any(b in txt for b in bad), n
