"""numpy-only QA metrics in finish.py (Q4/Q5/Q7/Q8/Q9 helpers)."""
import numpy as np

import finish


def test_mask_stats_clip_and_crush():
    img = np.full((100, 100, 3), 0.5)
    mask = np.zeros((100, 100)); mask[20:80, 20:80] = 1  # 3600 px
    img[20, 20:38] = 1.0      # 18 clipped product px -> 0.5 %
    img[79, 20:22] = 0.0      # 2 crushed
    img[0, 0] = 1.0           # background clip, ignored for Q4
    st = finish.mask_stats(img, mask)
    assert st['mask_px'] == 3600
    assert abs(st['clip_frac'] - 18 / 3600) < 1e-12 and abs(st['crush_frac'] - 2 / 3600) < 1e-12
    q = finish.q4_q5(st)
    assert q['Q4'] == 'FAIL' and q['Q5'] == 'PASS'
    assert finish.q4_q5(st, specular_apex=True)['Q4'] == 'FAIL'
    img[20, 20:38] = 0.99
    assert finish.q4_q5(finish.mask_stats(img, mask))['Q4'] == 'PASS'


def test_mask_stats_accepts_uint16():
    img = np.full((10, 10, 3), 65535, np.uint16)
    st = finish.mask_stats(img, np.ones((10, 10)))
    assert st['clip_frac'] == 1.0


def test_highpass_noise_and_fireflies():
    rng = np.random.default_rng(0)
    flat = np.full((64, 64), 0.4)
    assert finish.highpass_residual(flat) < 1e-12
    noisy = flat + rng.normal(0, 0.004, flat.shape)
    assert 0.005 < finish.highpass_residual(noisy) < 0.02
    ff = noisy.copy(); ff[10, 10] = 10.0; ff[40, 50] = 9.0
    assert finish.fireflies(noisy) == 0 and finish.fireflies(ff) == 2


def test_flicker_and_ssim():
    m = np.ones((8, 8))
    frames = [np.full((8, 8), v) for v in (0.5, 0.5, 0.5, 0.5)]
    assert finish.flicker(frames, m) == 0.0
    frames[1] = frames[1] * 1.02
    assert 0.005 < finish.flicker(frames, m) < 0.02
    a = np.random.default_rng(1).random((32, 32))
    assert abs(finish.ssim(a, a) - 1) < 1e-12 and finish.ssim(a, 1 - a) < 0


def test_srgb_roundtrip_and_lab_white():
    x = np.linspace(0, 1, 101)
    assert np.allclose(finish.linear_to_srgb(finish.srgb_to_linear(x)), x)
    assert np.allclose(finish.srgb_to_lab(np.array([1.0, 1.0, 1.0])), [100, 0, 0], atol=1e-3)


def test_flattest_patch_picks_flat_masked_region():
    rng = np.random.default_rng(2)
    img = rng.random((300, 300))
    img[150:260, 150:260] = 0.5            # flat area
    mask = np.zeros((300, 300)); mask[40:280, 40:280] = 1
    r, c = finish.flattest_patch(img, mask, size=96, step=8)
    assert 150 <= r and r + 96 <= 260 and 150 <= c and c + 96 <= 260
    assert finish.flattest_patch(img, np.zeros((300, 300))) is None


def test_flattest_patch_rejects_horizontal_edge():
    img = np.zeros((200, 200)); img[100:] = 1.0      # one horizontal step edge, otherwise flat
    mask = np.ones((200, 200))
    r, c = finish.flattest_patch(img, mask, size=64, step=4)
    assert r + 64 <= 100 or r >= 100
