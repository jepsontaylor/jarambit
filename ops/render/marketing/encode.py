"""Delivery encodes.

The H.264 and H.265 paths run an explicit zscale full-range to BT.709 limited
conversion. They do not retag. +faststart is always set. WebP and GIF are
resized with zscale Lanczos. GIF uses gifski when it is on PATH and otherwise
ffmpeg palettegen with stats_mode=diff.

Production presets are slow. Tests pass a faster preset; the default stays slow.
"""
import os
import shutil
import subprocess

import numpy as np
from PIL import Image

FFMPEG = os.environ.get("JARAMBIT_FFMPEG", "ffmpeg")
FFPROBE = os.environ.get("JARAMBIT_FFPROBE", "ffprobe")
GIFSKI = os.environ.get("JARAMBIT_GIFSKI", "gifski")

# Full-range sRGB code values -> BT.709 limited. Same transfer in and out so a
# flat gray stays a flat gray and only the legal range changes.
_ZSCALE_MATRIX = (
    "rangein=full:range=limited:matrixin=709:matrix=709:"
    "transferin=709:transfer=709:primariesin=709:primaries=709:dither=none:filter=lanczos"
)


def zscale_limited(width=None, height=None, ten_bit=False) -> str:
    parts = []
    if width and height:
        parts.append(f"w={int(width)}:h={int(height)}")
    parts.append(_ZSCALE_MATRIX)
    filt = "zscale=" + ":".join(parts)
    pix = "yuv420p10le" if ten_bit else "yuv420p"
    return filt + f",format={pix}"


def _run(cmd):
    proc = subprocess.run(cmd, capture_output=True, text=True)
    if proc.returncode != 0:
        tail = (proc.stderr or proc.stdout or "")[-2000:]
        raise RuntimeError(f"command failed ({proc.returncode}): {' '.join(cmd[:8])}\n{tail}")
    return proc


def h264_cmd(src, out_path, *, width=1920, height=1080, fps=30, crf=16, preset="slow",
             sequence=False, level=None):
    cmd = [FFMPEG, "-y", "-hide_banner", "-loglevel", "error"]
    if sequence:
        cmd += ["-framerate", str(fps), "-i", src]
    else:
        cmd += ["-i", src]
    cmd += [
        "-vf", zscale_limited(width, height, ten_bit=False),
        "-c:v", "libx264", "-preset", preset, "-crf", str(crf),
        "-profile:v", "high", "-pix_fmt", "yuv420p",
        "-color_primaries", "bt709", "-color_trc", "bt709",
        "-colorspace", "bt709", "-color_range", "tv",
        "-movflags", "+faststart", "-r", str(fps),
    ]
    # Level 5.1 is the 4K compatibility tag. Small proxies stay unconstrained.
    if level is None and int(height) >= 2160:
        level = "5.1"
    if level:
        cmd += ["-level:v", str(level)]
    cmd.append(out_path)
    return cmd


def h265_cmd(src, out_path, *, width=3840, height=2160, fps=30, crf=18, preset="slow", sequence=False):
    cmd = [FFMPEG, "-y", "-hide_banner", "-loglevel", "error"]
    if sequence:
        cmd += ["-framerate", str(fps), "-i", src]
    else:
        cmd += ["-i", src]
    cmd += [
        "-vf", zscale_limited(width, height, ten_bit=True),
        "-c:v", "libx265", "-preset", preset, "-crf", str(crf),
        "-pix_fmt", "yuv420p10le", "-tag:v", "hvc1",
        "-color_primaries", "bt709", "-color_trc", "bt709",
        "-colorspace", "bt709", "-color_range", "tv",
        "-movflags", "+faststart", "-r", str(fps),
        out_path,
    ]
    return cmd


def encode_h264(src, out_path, **kwargs):
    os.makedirs(os.path.dirname(out_path) or ".", exist_ok=True)
    _run(h264_cmd(src, out_path, **kwargs))
    return out_path


def encode_h265(src, out_path, **kwargs):
    os.makedirs(os.path.dirname(out_path) or ".", exist_ok=True)
    _run(h265_cmd(src, out_path, **kwargs))
    return out_path


def encode_webp(src, out_path, *, width=1280, height=720, fps=30, quality=80, sequence=False):
    os.makedirs(os.path.dirname(out_path) or ".", exist_ok=True)
    vf = f"zscale=w={int(width)}:h={int(height)}:filter=lanczos,format=rgba"
    cmd = [FFMPEG, "-y", "-hide_banner", "-loglevel", "error"]
    if sequence:
        cmd += ["-framerate", str(fps), "-i", src]
    else:
        cmd += ["-i", src]
    cmd += [
        "-vf", vf, "-c:v", "libwebp_anim", "-quality", str(quality),
        "-loop", "0", "-pix_fmt", "yuva420p", "-r", str(fps), out_path,
    ]
    _run(cmd)
    return out_path


def gifski_bin():
    env = os.environ.get("JARAMBIT_GIFSKI")
    if env and os.path.isfile(env):
        return env
    found = shutil.which(GIFSKI)
    if found:
        return found
    home = os.path.expanduser("~/opt/gifski/bin/gifski")
    if os.path.isfile(home):
        return home
    return None


def encode_gif_ffmpeg(src, out_path, *, width=640, height=360, fps=15, sequence=False):
    os.makedirs(os.path.dirname(out_path) or ".", exist_ok=True)
    vf = (
        f"zscale=w={int(width)}:h={int(height)}:filter=lanczos,fps={int(fps)},"
        "split[s0][s1];[s0]palettegen=stats_mode=diff[p];[s1][p]paletteuse=dither=sierra2_4a"
    )
    cmd = [FFMPEG, "-y", "-hide_banner", "-loglevel", "error"]
    if sequence:
        cmd += ["-framerate", str(fps), "-i", src]
    else:
        cmd += ["-i", src]
    cmd += ["-vf", vf, "-loop", "0", out_path]
    _run(cmd)
    return out_path


def encode_gif(frames_dir, out_path, *, width=640, height=360, fps=15, quality=80):
    """frames_dir holds PNG files in name order. gifski when installed, else ffmpeg."""
    os.makedirs(os.path.dirname(out_path) or ".", exist_ok=True)
    names = sorted(n for n in os.listdir(frames_dir) if n.lower().endswith(".png"))
    if not names:
        raise RuntimeError(f"no PNG frames in {frames_dir}")
    tool = gifski_bin()
    if tool is None:
        return _gif_from_files(names, frames_dir, out_path, width, height, fps)
    resized = _resize_pngs(frames_dir, names, width, height)
    cmd = [tool, "-o", out_path, "--fps", str(fps), "--width", str(width),
           "--quality", str(quality), "--repeat", "0", *resized]
    try:
        _run(cmd)
    except RuntimeError:
        # Some gifski builds use -W/-H and reject --width. Fall back rather than fail the delivery.
        return _gif_from_files(names, frames_dir, out_path, width, height, fps)
    return out_path


def _resize_pngs(frames_dir, names, width, height):
    out_dir = os.path.join(frames_dir, ".gifski_resized")
    os.makedirs(out_dir, exist_ok=True)
    paths = []
    for name in names:
        dest = os.path.join(out_dir, name)
        _run([
            FFMPEG, "-y", "-hide_banner", "-loglevel", "error",
            "-i", os.path.join(frames_dir, name),
            "-vf", f"zscale=w={int(width)}:h={int(height)}:filter=lanczos",
            dest,
        ])
        paths.append(dest)
    return paths


def _gif_from_files(names, frames_dir, out_path, width, height, fps):
    lst = os.path.join(frames_dir, ".gif_concat.txt")
    with open(lst, "w", encoding="utf-8") as fh:
        for name in names:
            path = os.path.join(frames_dir, name).replace("'", "'\\''")
            fh.write(f"file '{path}'\n")
            fh.write(f"duration {1.0 / float(fps):.6f}\n")
    vf = (
        f"zscale=w={int(width)}:h={int(height)}:filter=lanczos,fps={int(fps)},"
        "split[s0][s1];[s0]palettegen=stats_mode=diff[p];[s1][p]paletteuse=dither=sierra2_4a"
    )
    _run([
        FFMPEG, "-y", "-hide_banner", "-loglevel", "error",
        "-f", "concat", "-safe", "0", "-i", lst,
        "-vf", vf, "-loop", "0", out_path,
    ])
    return out_path


def write_jpeg(src_png, dest, quality=92):
    os.makedirs(os.path.dirname(dest) or ".", exist_ok=True)
    image = Image.open(src_png).convert("RGB")
    image.save(dest, format="JPEG", quality=int(quality), subsampling=0, optimize=True)
    return dest


def ffprobe(path) -> dict:
    proc = _run([
        FFPROBE, "-v", "error",
        "-show_entries",
        "stream=index,codec_name,width,height,avg_frame_rate,r_frame_rate,nb_frames,pix_fmt,"
        "color_space,color_transfer,color_primaries,color_range,profile,codec_tag_string",
        "-show_entries", "format=format_name,duration,size",
        "-of", "json", path,
    ])
    import json
    return json.loads(proc.stdout)


def moov_before_mdat(path) -> bool:
    with open(path, "rb") as fh:
        blob = fh.read()
    moov = blob.find(b"moov")
    mdat = blob.find(b"mdat")
    return moov != -1 and (mdat == -1 or moov < mdat)


def read_y_plane(path):
    """Coded 8-bit luma. The decoder is asked for yuv420p and must not expand range."""
    meta = ffprobe(path)
    video = next(item for item in meta["streams"] if "width" in item)
    width, height = int(video["width"]), int(video["height"])
    raw = subprocess.check_output([
        FFMPEG, "-v", "error", "-i", path, "-f", "rawvideo", "-pix_fmt", "yuv420p", "-",
    ])
    plane = np.frombuffer(raw, dtype=np.uint8, count=width * height).reshape(height, width)
    return plane, video


def y_band_medians(plane, bands=3):
    height = plane.shape[0]
    medians = []
    for index in range(bands):
        y0 = height * index // bands
        y1 = height * (index + 1) // bands
        medians.append(float(np.median(plane[y0:y1])))
    return medians


def write_gray_ramp(path, width=64, height=48):
    """Three horizontal bands: code 0, 128 and 255. Limited-range targets are 16, 126, 235."""
    image = Image.new("RGB", (width, height))
    pixels = image.load()
    colors = ((0, 0, 0), (128, 128, 128), (255, 255, 255))
    for y in range(height):
        color = colors[min(2, (y * 3) // height)]
        for x in range(width):
            pixels[x, y] = color
    image.save(path)
    return path


def decode_ok(path) -> bool:
    proc = subprocess.run([FFMPEG, "-v", "error", "-i", path, "-f", "null", "-"], capture_output=True, text=True)
    return proc.returncode == 0
