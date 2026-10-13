"""zscale full-to-limited roundtrip. A missing ffmpeg fails the test; it is not skipped."""
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

import encode

PIPE = ROOT / "pipeline.py"


def test_ffmpeg_is_required():
    proc = subprocess.run(
        [sys.executable, str(PIPE), "doctor", "--require", "ffmpeg,zscale,libx264,libx265,libwebp"],
        capture_output=True, text=True,
    )
    assert proc.returncode == 0, proc.stderr


def test_gray_ramp_y_medians_and_tags(tmp_path):
    png = tmp_path / "ramp.png"
    encode.write_gray_ramp(str(png), width=64, height=48)
    out = tmp_path / "ramp.mp4"
    encode.encode_h264(str(png), str(out), width=64, height=48, fps=1, preset="veryfast", crf=16)
    plane, video = encode.read_y_plane(str(out))
    black, mid, white = encode.y_band_medians(plane, 3)
    assert black == 16.0
    assert abs(mid - 126.0) <= 1.0
    assert white == 235.0
    assert video["color_space"] == "bt709"
    assert video["color_primaries"] == "bt709"
    assert video["color_transfer"] == "bt709"
    assert video["color_range"] == "tv"
    assert video["pix_fmt"] == "yuv420p"
    assert encode.moov_before_mdat(str(out))
    assert encode.decode_ok(str(out))


def test_production_h264_command_is_explicit():
    cmd = encode.h264_cmd("in.png", "out.mp4", width=1920, height=1080, fps=30)
    text = " ".join(cmd)
    assert "zscale=" in text
    assert "rangein=full" in text and "range=limited" in text
    assert "matrix=709" in text
    assert "+faststart" in text
    assert "libx264" in cmd
    assert "slow" in cmd
    assert "16" in cmd  # CRF
    assert "bt709" in cmd
    assert "tv" in cmd


def test_h265_tags_and_webp_and_gif(tmp_path):
    png = tmp_path / "frame.png"
    encode.write_gray_ramp(str(png), width=32, height=32)
    h265 = tmp_path / "tiny.mp4"
    encode.encode_h265(str(png), str(h265), width=32, height=32, fps=1, preset="ultrafast", crf=28)
    meta = encode.ffprobe(str(h265))
    video = next(item for item in meta["streams"] if "width" in item)
    assert video["pix_fmt"] == "yuv420p10le"
    assert video["codec_tag_string"].lower() in ("hvc1", "hev1")
    assert encode.moov_before_mdat(str(h265))
    assert encode.decode_ok(str(h265))

    frames = tmp_path / "frames"
    frames.mkdir()
    for index in range(4):
        encode.write_gray_ramp(str(frames / f"f{index}.png"), width=32, height=32)
    webp = tmp_path / "loop.webp"
    encode.encode_webp(str(frames / "f0.png"), str(webp), width=32, height=32, fps=10, sequence=False)
    assert webp.stat().st_size > 0
    assert encode.decode_ok(str(webp))

    gif = tmp_path / "loop.gif"
    encode.encode_gif(str(frames), str(gif), width=32, height=32, fps=10, quality=80)
    assert gif.stat().st_size > 0
    assert encode.decode_ok(str(gif))


def test_four_k_h264_sets_level():
    cmd = encode.h264_cmd("f%04d.png", "out.mp4", width=3840, height=2160, sequence=True, crf=18)
    assert "5.1" in cmd
    assert "libx264" in cmd
