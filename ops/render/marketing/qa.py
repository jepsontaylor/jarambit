"""QA gates Q1–Q15 (Q15: maker's-mark signature present and visible).

A missing measurement is FAIL, not a skip. Q14 stays pending until a person
sets art_review to approved. Nothing in this module writes that approval.
release_blocked is true unless Q1–Q13 and Q15 all PASS and art_review is approved.
"""
import math
import os
import sys

import numpy as np
from PIL import Image

_HERE = os.path.dirname(os.path.abspath(__file__))
if _HERE not in sys.path:
    sys.path.insert(0, _HERE)

import canon
import plan as plan_mod

SCHEMA = "jarambit.render.qa.v1"

# Delivery caps from the marketing plan.
SIZE_LIMITS = {
    "turntable_1080p_h264.mp4": 25 * 1024 * 1024,
    "turntable_2160p_h265.mp4": 60 * 1024 * 1024,
    "turntable_720p.webp": 6 * 1024 * 1024,
    "turntable_640.gif": 8 * 1024 * 1024,
    "hero_3q_1920.jpg": 600 * 1024,
}


def _record(check_id, ok, measured, threshold, detail=""):
    return {
        "id": check_id,
        "status": "PASS" if ok else "FAIL",
        "measured": measured,
        "threshold": threshold,
        "detail": detail,
    }


def _fail(check_id, detail, threshold):
    return _record(check_id, False, None, threshold, detail)


def check_q1(seconds):
    threshold = "median<=90s and p95<=150s on final_4k"
    if not seconds:
        return _fail("Q1", "no frame times", threshold)
    values = np.sort(np.asarray(seconds, float))
    median = float(np.median(values))
    p95 = float(np.percentile(values, 95))
    return _record("Q1", median <= 90.0 and p95 <= 150.0,
                   {"median_s": median, "p95_s": p95, "n": int(values.size)}, threshold)


def check_q2(wall_seconds):
    threshold = "240-frame 4K turntable wall time <= 4.5h"
    if wall_seconds is None:
        return _fail("Q2", "wall time not measured", threshold)
    limit = 4.5 * 3600.0
    return _record("Q2", float(wall_seconds) <= limit, {"wall_s": float(wall_seconds)}, threshold)


def check_q3(framing_rows):
    """framing_rows: list of {hero, margin_min, fill_worst, pass} for every shot."""
    threshold = "every frame inside the safe area, margin>=0.06, hero fill 0.62-0.78"
    if not framing_rows:
        return _fail("Q3", "no framing records", threshold)
    bad = []
    for row in framing_rows:
        margin = row.get("margin_min")
        if not row.get("pass") or margin is None or float(margin) < 0.06 - 1e-6:
            bad.append(row.get("id"))
            continue
        if row.get("hero"):
            fill = row.get("fill_worst")
            if fill is None or not (0.62 - 1e-4 <= float(fill) <= 0.78 + 1e-4):
                bad.append(row.get("id"))
    return _record("Q3", not bad, {"shots": len(framing_rows), "failed": bad}, threshold)


def _mask_pixels(display_u8, mask):
    image = np.asarray(display_u8)
    if image.ndim != 3 or image.shape[2] != 3:
        raise ValueError("display image must be HxWx3")
    sel = np.asarray(mask, bool)
    if sel.shape != image.shape[:2]:
        raise ValueError("mask shape does not match the image")
    return image[sel]


def check_q4(display_u8, mask, apex_mask=None):
    threshold = "product pixels at 255 in any channel <=0.05% (apex <=0.2%)"
    if display_u8 is None or mask is None:
        return _fail("Q4", "display image or product mask not measured", threshold)
    product = _mask_pixels(display_u8, mask)
    if product.size == 0:
        return _fail("Q4", "product mask is empty", threshold)
    clipped = np.any(product == 255, axis=-1)
    fraction = float(clipped.mean())
    apex_fraction = None
    ok = fraction <= 0.0005
    if apex_mask is not None:
        apex_px = _mask_pixels(display_u8, apex_mask)
        body = _mask_pixels(display_u8, np.asarray(mask, bool) & ~np.asarray(apex_mask, bool))
        apex_fraction = float(np.any(apex_px == 255, axis=-1).mean()) if apex_px.size else 0.0
        body_fraction = float(np.any(body == 255, axis=-1).mean()) if body.size else 0.0
        ok = body_fraction <= 0.0005 and apex_fraction <= 0.002
        fraction = body_fraction
    return _record("Q4", ok, {"clipped_fraction": fraction, "apex_fraction": apex_fraction}, threshold)


def check_q5(display_u8, mask):
    threshold = "product pixels at 0 in every channel <=0.5%"
    if display_u8 is None or mask is None:
        return _fail("Q5", "display image or product mask not measured", threshold)
    product = _mask_pixels(display_u8, mask)
    if product.size == 0:
        return _fail("Q5", "product mask is empty", threshold)
    crushed = float(np.all(product == 0, axis=-1).mean())
    return _record("Q5", crushed <= 0.005, {"crushed_fraction": crushed}, threshold)


def delta_e2000(lab1, lab2):
    """CIEDE2000. lab channels are L*, a*, b*."""
    L1, a1, b1 = (float(v) for v in lab1)
    L2, a2, b2 = (float(v) for v in lab2)
    kL = kC = kH = 1.0
    C1 = math.hypot(a1, b1)
    C2 = math.hypot(a2, b2)
    cbar = 0.5 * (C1 + C2)
    cbar7 = cbar ** 7
    G = 0.5 * (1.0 - math.sqrt(cbar7 / (cbar7 + 25.0 ** 7)))
    a1p = (1.0 + G) * a1
    a2p = (1.0 + G) * a2
    C1p = math.hypot(a1p, b1)
    C2p = math.hypot(a2p, b2)
    h1p = math.degrees(math.atan2(b1, a1p)) % 360.0
    h2p = math.degrees(math.atan2(b2, a2p)) % 360.0
    dLp = L2 - L1
    dCp = C2p - C1p
    dhp = 0.0
    if C1p * C2p != 0.0:
        diff = h2p - h1p
        if abs(diff) <= 180.0:
            dhp = diff
        elif diff > 180.0:
            dhp = diff - 360.0
        else:
            dhp = diff + 360.0
    dHp = 2.0 * math.sqrt(C1p * C2p) * math.sin(math.radians(dhp) / 2.0)
    Lbar = 0.5 * (L1 + L2)
    Cbarp = 0.5 * (C1p + C2p)
    hsum = h1p + h2p
    if C1p * C2p == 0.0:
        Hbar = hsum
    elif abs(h1p - h2p) <= 180.0:
        Hbar = hsum / 2.0
    elif hsum < 360.0:
        Hbar = (hsum + 360.0) / 2.0
    else:
        Hbar = (hsum - 360.0) / 2.0
    T = (1.0
         - 0.17 * math.cos(math.radians(Hbar - 30.0))
         + 0.24 * math.cos(math.radians(2.0 * Hbar))
         + 0.32 * math.cos(math.radians(3.0 * Hbar + 6.0))
         - 0.20 * math.cos(math.radians(4.0 * Hbar - 63.0)))
    dtheta = 30.0 * math.exp(-((Hbar - 275.0) / 25.0) ** 2)
    Rc = 2.0 * math.sqrt(Cbarp ** 7 / (Cbarp ** 7 + 25.0 ** 7))
    Sl = 1.0 + (0.015 * (Lbar - 50.0) ** 2) / math.sqrt(20.0 + (Lbar - 50.0) ** 2)
    Sc = 1.0 + 0.045 * Cbarp
    Sh = 1.0 + 0.015 * Cbarp * T
    Rt = -math.sin(math.radians(2.0 * dtheta)) * Rc
    return math.sqrt(
        (dLp / (kL * Sl)) ** 2
        + (dCp / (kC * Sc)) ** 2
        + (dHp / (kH * Sh)) ** 2
        + Rt * (dCp / (kC * Sc)) * (dHp / (kH * Sh))
    )


def check_q6(delta_e_pairs=None, y_medians=None):
    """Both the ColorChecker pairs and the gray-ramp medians are required."""
    threshold = "mean dE2000<=2 max<=4; gray-ramp Y medians 16 / 126±1 / 235"
    if delta_e_pairs is None or y_medians is None:
        return _fail("Q6", "colorchecker or gray ramp not measured", threshold)
    deltas = [delta_e2000(a, b) for a, b in delta_e_pairs]
    if not deltas:
        return _fail("Q6", "no colorchecker pairs", threshold)
    mean = float(sum(deltas) / len(deltas))
    worst = float(max(deltas))
    black, mid, white = (float(v) for v in y_medians)
    ramp_ok = black == 16.0 and abs(mid - 126.0) <= 1.0 and white == 235.0
    color_ok = mean <= 2.0 and worst <= 4.0
    return _record("Q6", ramp_ok and color_ok,
                   {"delta_e_mean": mean, "delta_e_max": worst, "y_medians": [black, mid, white]},
                   threshold)


def ssim(image_a, image_b):
    a = np.asarray(image_a, float)
    b = np.asarray(image_b, float)
    if a.shape != b.shape:
        raise ValueError("ssim inputs differ in shape")
    if a.size and max(float(np.max(a)), float(np.max(b))) <= 1.0:
        a = a * 255.0
        b = b * 255.0
    mu_a, mu_b = float(a.mean()), float(b.mean())
    var_a, var_b = float(a.var()), float(b.var())
    cov = float(((a - mu_a) * (b - mu_b)).mean())
    c1 = (0.01 * 255.0) ** 2
    c2 = (0.03 * 255.0) ** 2
    return ((2 * mu_a * mu_b + c1) * (2 * cov + c2)) / ((mu_a ** 2 + mu_b ** 2 + c1) * (var_a + var_b + c2))


def check_q7(residual, reference, denoised, body_mean=None):
    """residual is the zero-mean high-pass of the flat-body patch; its std is normalised by the
    flat-body luminance (body_mean, else the mean of the 4096-spp reference patch), never by the
    residual's own mean, which is ~0 for an unbiased high-pass."""
    threshold = "flat-body high-pass residual std <=0.6% of body luminance; SSIM vs 4096-spp reference >=0.97"
    if residual is None or reference is None or denoised is None:
        return _fail("Q7", "noise pair not measured", threshold)
    res = np.asarray(residual, float)
    body = float(body_mean) if body_mean is not None else float(np.asarray(reference, float).mean())
    if not body > 0:
        return _fail("Q7", "flat-body luminance not measured (<= 0)", threshold)
    rel = float(res.std()) / body
    score = float(ssim(reference, denoised))
    return _record("Q7", rel <= 0.006 and score >= 0.97,
                   {"residual_std_over_body": rel, "body_mean": body, "ssim": score}, threshold)


def firefly_count(image, factor=8.0):
    """Pixels brighter than factor times the 5x5 local median. image is 2-D luma."""
    luma = np.asarray(image, float)
    pad = 2
    padded = np.pad(luma, pad, mode="edge")
    # Stack the 25 shifts and take the median. Fine for the floor patches QA passes in.
    shifts = []
    for dy in range(5):
        for dx in range(5):
            shifts.append(padded[dy:dy + luma.shape[0], dx:dx + luma.shape[1]])
    local = np.median(np.stack(shifts, axis=0), axis=0)
    return int(np.sum(luma > factor * np.maximum(local, 1e-9)))


def check_q8(floor_frames):
    threshold = "floor luminance std <=0.8% of mean across frames; no pixel >8x local median"
    if not floor_frames or len(floor_frames) < 2:
        return _fail("Q8", "floor sequence not measured", threshold)
    means = np.array([float(np.asarray(frame, float).mean()) for frame in floor_frames])
    rel = float(means.std()) / (float(means.mean()) + 1e-12)
    flies = sum(firefly_count(frame) for frame in floor_frames)
    return _record("Q8", rel <= 0.008 and flies == 0,
                   {"luma_std_over_mean": rel, "fireflies": flies}, threshold)


def check_q9(frames):
    """SSIM between the seam's absolute delta and the mean consecutive absolute delta."""
    threshold = "SSIM(seam delta, mean consecutive delta) >= 0.90"
    if frames is None or len(frames) < 2:
        return _fail("Q9", "turntable frames not measured", threshold)
    seq = [np.asarray(frame, float) for frame in frames]
    deltas = [np.abs(seq[i + 1] - seq[i]) for i in range(len(seq) - 1)]
    mean_delta = np.mean(np.stack(deltas, axis=0), axis=0)
    seam = np.abs(seq[-1] - seq[0])
    score = float(ssim(seam, mean_delta))
    return _record("Q9", score >= 0.90, {"seam_ssim": score}, threshold)


def check_q10(probe, *, frame_count, faststart, decoded):
    threshold = "full decode, exact frame count, CFR, bt709, tv range, faststart"
    if not probe or not decoded:
        return _fail("Q10", "decode did not run", threshold)
    video = probe.get("video") or {}
    rate = str(video.get("r_frame_rate") or "")
    tags_ok = (
        video.get("color_space") in ("bt709",) and
        video.get("color_primaries") in ("bt709",) and
        video.get("color_transfer") in ("bt709",) and
        video.get("color_range") in ("tv", "mpeg")
    )
    count_ok = int(probe.get("frames_decoded") or -1) == int(frame_count)
    # CFR: the rational rate has no remainder against itself, and avg matches r when both exist.
    avg = str(video.get("avg_frame_rate") or rate)
    cfr = bool(rate) and rate not in ("0/0", "N/A") and avg == rate
    ok = bool(faststart) and tags_ok and count_ok and cfr and bool(decoded)
    return _record("Q10", ok, {
        "frames_decoded": probe.get("frames_decoded"),
        "r_frame_rate": rate,
        "color_space": video.get("color_space"),
        "color_range": video.get("color_range"),
        "faststart": bool(faststart),
    }, threshold)


def check_q11(sizes):
    """sizes maps filename -> byte size. Every capped delivery must be present."""
    threshold = "1080p mp4<=25MB, 4K H.265<=60MB, webp<=6MB, gif<=8MB, poster<=600KB"
    if not sizes:
        return _fail("Q11", "no delivery sizes", threshold)
    over = {}
    missing = []
    for name, limit in SIZE_LIMITS.items():
        if name not in sizes:
            missing.append(name)
            continue
        if int(sizes[name]) > limit:
            over[name] = int(sizes[name])
    return _record("Q11", not over and not missing, {"over": over, "missing": missing}, threshold)


def check_q12(plan_bytes_a, plan_bytes_b, image_a=None, image_b=None):
    threshold = "identical resolved-plan bytes; rerun mean abs diff <= 1/255"
    if plan_bytes_a is None or plan_bytes_b is None:
        return _fail("Q12", "plan bytes not measured", threshold)
    same = bytes(plan_bytes_a) == bytes(plan_bytes_b)
    diff = None
    images_ok = False  # fail closed: the rerun image pair is required for Q12
    reason = "rerun image pair not measured"
    if image_a is not None and image_b is not None:
        a = np.asarray(image_a, float)
        b = np.asarray(image_b, float)
        if a.shape != b.shape or a.size == 0:
            reason = f"rerun image shapes incompatible {a.shape} vs {b.shape}"
        else:
            reason = None
            if a.max() > 1.0 or b.max() > 1.0:
                a = a / 255.0
                b = b / 255.0
            diff = float(np.mean(np.abs(a - b)))
            images_ok = diff <= (1.0 / 255.0)
    return _record("Q12", same and images_ok,
                   {"plan_bytes_equal": same, "mean_abs": diff, "unverified": reason}, threshold)


def check_q13(manifest, sums_ok, source_sha256=None, hero=False):
    threshold = "source sha verified, bundle sha, toolchain, git sha, output shas, SHA256SUMS; hero outputs are not the retired g3 STL"
    if not manifest:
        return _fail("Q13", "manifest missing", threshold)
    source = manifest.get("source_cad") or {}
    outputs = manifest.get("outputs") or []
    sha = source.get("sha256") or source_sha256
    path = source.get("path") or ""
    hero_delivery = hero or any(
        plan_mod.is_hero_delivery(item.get("path"), item.get("role")) for item in outputs
    )
    if hero_delivery and (plan_mod.retired_g3(sha, path) or plan_mod.retired_g3(source_sha256, path)):
        return _fail(
            "Q13",
            "retired g3 sha256 "
            f"{plan_mod.RETIRED_G3_SHA256} is rejected for hero stills and the turntable; "
            f"use {plan_mod.HERO_MODEL} {plan_mod.HERO_STEP_SHA256}",
            threshold,
        )
    ok = (
        bool(source.get("sha256")) and bool(source.get("verified"))
        and bool(manifest.get("mesh_bundle_sha256"))
        and bool(manifest.get("toolchain"))
        and bool(manifest.get("git_sha"))
        and len(outputs) > 0
        and all(item.get("sha256") for item in outputs)
        and bool(sums_ok)
    )
    return _record("Q13", ok, {
        "source_verified": bool(source.get("verified")),
        "outputs": len(outputs),
        "sums_ok": bool(sums_ok),
        "retired_g3": False,
    }, threshold)


SIG_MIN_RATIO = 0.5      # visible ink px / expected ink px (projected bbox * ink fraction)
SIG_MIN_EXPECTED_PX = 30


def signature_rows(results):
    """Flatten worker result.json dicts into Q15 rows. A shot is 'hero' when its id starts with
    'hero' or the row says so."""
    rows = []
    for res in results or []:
        sid = res.get("shot_id")
        sig = res.get("signature") or {}
        applied = bool(sig.get("enabled")) and bool((sig.get("material") or {}).get("applied"))
        for fr in res.get("frames") or []:
            rows.append({"shot": sid, "frame": fr.get("index"), "hero": str(sid or "").startswith("hero"),
                         "applied": applied, **(fr.get("signature") or {})})
        if not res.get("frames"):
            rows.append({"shot": sid, "frame": None, "hero": False, "applied": applied})
    return rows


def check_q15(rows):
    """Every shot carries the signature overlay; in hero stills it must face the camera, be in
    frame and be at least SIG_MIN_RATIO visible (fails on missing or unexpected occlusion)."""
    threshold = {"applied_every_shot": True, "hero_min_visible_ratio": SIG_MIN_RATIO,
                 "hero_min_expected_px": SIG_MIN_EXPECTED_PX}
    if not rows:
        return _fail("Q15", "no signature measurements", threshold)
    bad = []
    for r in rows:
        if not r.get("applied"):
            bad.append({"shot": r.get("shot"), "frame": r.get("frame"), "why": "signature not applied"})
            continue
        if not r.get("hero"):
            continue
        if not r.get("facing") or not r.get("in_frame"):
            bad.append({"shot": r["shot"], "frame": r["frame"], "why": "hero still: mark faces away/out of frame"})
        elif (r.get("expected_px") or 0) < SIG_MIN_EXPECTED_PX:
            bad.append({"shot": r["shot"], "frame": r["frame"], "why": f"hero still: mark too small ({r.get('expected_px')} px)"})
        elif r.get("visible_px") is None or (r.get("visible_ratio") or 0) < SIG_MIN_RATIO:
            bad.append({"shot": r["shot"], "frame": r["frame"], "why": f"hero still: mark occluded/missing (ratio {r.get('visible_ratio')})"})
    return _record("Q15", not bad, {"rows": len(rows), "violations": bad[:20]}, threshold)


def check_q14(art_review):
    # Never promoted here. pending is not a FAIL of the metric; it blocks release separately.
    status = "PASS" if art_review == "approved" else "PENDING"
    return {
        "id": "Q14",
        "status": status,
        "measured": {"art_review": art_review or "pending"},
        "threshold": "human sign-off; never auto-approved",
        "detail": "pending until a person records approved",
    }


def evaluate(measurements):
    """measurements supplies whatever has been measured. Missing keys FAIL closed."""
    m = measurements or {}
    checks = [
        check_q1(m.get("seconds")),
        check_q2(m.get("wall_seconds")),
        check_q3(m.get("framing")),
        check_q4(m.get("display"), m.get("mask"), m.get("apex_mask")),
        check_q5(m.get("display"), m.get("mask")),
        check_q6(m.get("delta_e_pairs"), m.get("y_medians")),
        check_q7(m.get("residual"), m.get("reference"), m.get("denoised"), m.get("body_mean")),
        check_q8(m.get("floor_frames")),
        check_q9(m.get("loop_frames")),
        check_q10(m.get("probe"), frame_count=m.get("frame_count") or 0,
                  faststart=m.get("faststart"), decoded=m.get("decoded")),
        check_q11(m.get("sizes")),
        check_q12(m.get("plan_bytes_a"), m.get("plan_bytes_b"), m.get("image_a"), m.get("image_b")),
        check_q13(
            m.get("manifest"),
            m.get("sums_ok"),
            source_sha256=m.get("source_sha256") or (m.get("source_cad") or {}).get("sha256"),
            hero=any(row.get("hero") for row in (m.get("framing") or [])),
        ),
        check_q15(m.get("signature")),
        check_q14(m.get("art_review")),
    ]
    failed = [item["id"] for item in checks if item["status"] == "FAIL"]
    art = m.get("art_review") or "pending"
    release_blocked = bool(failed) or art != "approved"
    reasons = list(failed)
    if art != "approved":
        reasons.append("art_review")
    return {
        "schema": SCHEMA,
        "art_review": art,
        "checks": checks,
        "failed": failed,
        "release_blocked": release_blocked,
        "release_blocked_reasons": reasons,
    }


def write_qa(path, report):
    canon.atomic_write_json(path, report)
    return path


def framing_rows(plan):
    """Q3 rows from a resolved plan. A margin list uses its minimum."""
    rows = []
    for shot in (plan or {}).get("shots") or []:
        framing = shot.get("framing") or {}
        margin = framing.get("per_frame_margin_min")
        if isinstance(margin, (list, tuple)):
            margin = min(margin) if margin else None
        rows.append({
            "id": shot.get("id"),
            "hero": bool(shot.get("hero")),
            "margin_min": margin,
            "fill_worst": framing.get("fill_worst"),
            "pass": bool(framing.get("pass")),
        })
    return rows


def seconds_from_receipts(receipts):
    """Render seconds recorded by the worker. Missing seconds are left out."""
    values = []
    for receipt in receipts or []:
        frame = receipt.get("frame") or {}
        if frame.get("seconds") is None:
            continue
        values.append(float(frame["seconds"]))
    return values


def contact_sheet(image_paths, out_path, columns=4, thumb=320):
    """Montage of delivery stills. Returns the path, or None when there is nothing to show."""
    paths = [path for path in image_paths if path and os.path.isfile(path)]
    if not paths:
        return None
    thumbs = []
    for path in paths:
        image = Image.open(path).convert("RGB")
        image.thumbnail((thumb, thumb))
        thumbs.append(image)
    columns = max(1, min(columns, len(thumbs)))
    rows = (len(thumbs) + columns - 1) // columns
    cell_w = max(image.width for image in thumbs)
    cell_h = max(image.height for image in thumbs)
    sheet = Image.new("RGB", (columns * cell_w, rows * cell_h), (20, 22, 24))
    for index, image in enumerate(thumbs):
        x = (index % columns) * cell_w
        y = (index // columns) * cell_h
        sheet.paste(image, (x, y))
    os.makedirs(os.path.dirname(out_path) or ".", exist_ok=True)
    sheet.save(out_path)
    return out_path
