"""Image shading-seam QA for broad flats (complements prep.py flat_seam_qa on the mesh).

A seam (split normals / tangent pole / patch boundary) on a flat shows as a long, straight, low-contrast
luminance step. On the part interior (lit metal, eroded away from silhouette/holes) with the dark ink
excluded, we take the horizontal and vertical luminance derivative after a light blur, project it along
columns / rows, and look for a narrow ridge that stands out from its neighbourhood:
    score = max_c |P(c) - median_w(P)(c)| / (MAD of P + floor)
A real seam gives one sharp, long ridge; smooth shading gradients and the brushed texture do not.
python3 seamqa.py IMAGE.png [--limit 6.0] [--json out.json]"""
import json, sys, warnings
warnings.simplefilter('ignore', RuntimeWarning)
import numpy as np
import cv2


def seam_score(img_path, limit=6.0, part_thr=0.08, ink_thr=0.06, erode_px=0.012, min_len_frac=0.5):
    im = cv2.imread(img_path, cv2.IMREAD_UNCHANGED).astype(np.float32)
    im /= 65535.0 if im.max() > 255 else 255.0
    L = im[..., :3] @ np.array([0.0722, 0.7152, 0.2126], np.float32) if im.ndim == 3 else im
    h, w = L.shape
    k = max(3, int(erode_px * w) | 1)
    part = (L > part_thr).astype(np.uint8)
    part = cv2.morphologyEx(part, cv2.MORPH_CLOSE, np.ones((k, k), np.uint8))   # fill ink strokes
    ink = ((L < ink_thr) & (part > 0)).astype(np.uint8)
    interior = cv2.erode(part, np.ones((2 * k, 2 * k), np.uint8)) & (1 - cv2.dilate(ink, np.ones((k, k), np.uint8)))
    interior &= ((L > part_thr) & (L < 0.9)).astype(np.uint8)
    # ROI: the flat that carries the mark (ink bbox, grown 35 %), i.e. the region a viewer actually reads
    n_, lab, st, _ = cv2.connectedComponentsWithStats(ink, 8)
    strokes = np.zeros_like(ink)
    for j in range(1, n_):   # ink strokes are thin (low fill of their bbox); holes / gaps are solid blobs
        x_, y_, w_, h_, a_ = st[j]
        if a_ > 50 and a_ / float(w_ * h_) < 0.35: strokes[lab == j] = 1
    ys, xs = np.where(strokes > 0)
    if len(ys) > 200:
        y0, y1, x0, x1 = ys.min(), ys.max(), xs.min(), xs.max(); gy, gx = int(0.35 * (y1 - y0)), int(0.05 * (x1 - x0))
        roi = np.zeros_like(interior); roi[max(0, y0 - gy):y1 + gy, max(0, x0 - gx):x1 + gx] = 1
        interior &= roi
    out_roi = int(interior.sum())
    Lb = cv2.GaussianBlur(L, (0, 0), 1.5)
    out = {'image': img_path, 'interior_frac': round(float(interior.mean()), 4), 'roi_px': out_roi}
    worst = 0.0
    W = 41
    for axis, name in ((1, 'vertical_seam'), (0, 'horizontal_seam')):
        ks = (W, 1) if axis == 1 else (1, W)                        # window along the profile direction
        ok = cv2.erode(interior, np.ones(ks[::-1], np.uint8)) > 0   # whole window on the flat interior
        res = Lb - cv2.blur(Lb, ks)                                 # local residual (linear shading cancels)
        cnt = ok.sum(axis=0 if axis == 1 else 1)
        P = (res * ok).sum(axis=0 if axis == 1 else 1) / np.maximum(cnt, 1)
        valid = cnt >= max(30, min_len_frac * cnt.max())
        if valid.sum() < 50:
            out[name] = {'score': 0.0, 'note': 'too little flat'}; continue
        Pv = np.where(valid, P, 0.0); mad = float(np.median(np.abs(Pv[valid]))) + 1e-4
        sc = np.abs(Pv) / mad * (np.abs(Pv) > 0.0008); i_ = int(np.argmax(sc))
        top = [int(t) for t in np.argsort(-sc)[:40]]; peaks = []
        for t in top:
            if all(abs(t - q) > 8 for q in peaks): peaks.append(t)
        out[name + '_peaks'] = [[t, round(float(sc[t]), 1), round(float(Pv[t]), 5)] for t in peaks[:4]]
        out[name] = {'score': round(float(sc[i_]), 2), 'at_px': i_, 'ridge': round(float(Pv[i_]), 5), 'mad': round(mad, 5), 'n_lines': int(valid.sum())}
        worst = max(worst, float(sc[i_]))
    out.update(score=round(worst, 2), limit=limit, **{'pass': worst <= limit})
    return out


if __name__ == '__main__':
    a = sys.argv[1:]
    lim = float(a[a.index('--limit') + 1]) if '--limit' in a else 6.0
    r = seam_score(a[0], lim)
    if '--json' in a:
        json.dump(r, open(a[a.index('--json') + 1], 'w'), indent=1)
    print(json.dumps(r))
    sys.exit(0 if r['pass'] else 1)
