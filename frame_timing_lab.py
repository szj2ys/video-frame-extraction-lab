#!/usr/bin/env python3
"""Create an original three-frame clip and verify what a frame-extraction command saves."""
import argparse
import datetime
import hashlib
import json
from pathlib import Path
import re
import shutil
import struct
import subprocess


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--ffmpeg", default="ffmpeg", help="FFmpeg executable path")
    parser.add_argument("--out", required=True, type=Path, help="A NEW output directory; never overwrites an existing directory")
    args = parser.parse_args()
    ffmpeg = shutil.which(args.ffmpeg) or (str(Path(args.ffmpeg).resolve()) if Path(args.ffmpeg).is_file() else None)
    if not ffmpeg:
        parser.error("FFmpeg was not found. Supply --ffmpeg with its executable path.")
    out = args.out.resolve()
    out.mkdir(parents=True, exist_ok=False)
    commands = []

    def run(name, parts):
        p = subprocess.run([ffmpeg, "-hide_banner", "-nostdin", "-y", *parts], cwd=out, capture_output=True)
        (out / (name + ".log")).write_bytes(p.stderr)
        commands.append({"name": name, "argv": ["ffmpeg", "-hide_banner", "-nostdin", "-y", *parts], "exit_code": p.returncode})
        if p.returncode:
            raise RuntimeError(f"{name} failed; see {out / (name + '.log')}")
        return p

    # PPM is deliberately simple: these pixels, filenames and fixture are original.
    for n, rgb in enumerate(((255, 0, 0), (0, 255, 0), (0, 0, 255))):
        (out / f"source-{n:02d}.ppm").write_bytes(b"P6\n320 180\n255\n" + bytes(rgb) * (320 * 180))
    run("encode", ["-framerate", "1", "-i", "source-%02d.ppm", "-c:v", "libx264", "-pix_fmt", "yuv420p", "-crf", "18", "-movflags", "+faststart", "three-frames.mp4"])
    timing = run("timestamps", ["-i", "three-frames.mp4", "-map", "0:v:0", "-an", "-vf", "showinfo", "-f", "null", "-"]).stderr.decode("utf-8", "replace")
    pts = [float(x) for x in re.findall(r"\bn:\s*\d+\s+pts:\s*-?\d+\s+pts_time:([\d.eE+-]+)", timing)]
    duration = re.search(r"Duration:\s*(\d+):(\d+):([\d.]+)", timing)
    if not duration:
        raise AssertionError("No duration found in FFmpeg's fixture inspection")
    duration_s = int(duration[1]) * 3600 + int(duration[2]) * 60 + float(duration[3])
    run("add-longer-audio", ["-i", "three-frames.mp4", "-f", "lavfi", "-i", "anullsrc=r=48000:cl=mono", "-map", "0:v:0", "-map", "1:a:0", "-c:v", "copy", "-c:a", "aac", "-t", "5", "longer-audio.mp4"])
    audio_timing = run("longer-audio-timestamps", ["-i", "longer-audio.mp4", "-map", "0:v:0", "-an", "-vf", "showinfo", "-f", "null", "-"]).stderr.decode("utf-8", "replace")
    audio_pts = [float(x) for x in re.findall(r"\bn:\s*\d+\s+pts:\s*-?\d+\s+pts_time:([\d.eE+-]+)", audio_timing)]
    audio_duration = re.search(r"Duration:\s*(\d+):(\d+):([\d.]+)", audio_timing)
    if not audio_duration:
        raise AssertionError("No duration found for the longer-audio fixture")
    audio_duration_s = int(audio_duration[1]) * 3600 + int(audio_duration[2]) * 60 + float(audio_duration[3])
    run("extract-last", ["-i", "three-frames.mp4", "-map", "0:v:0", "-an", "-fps_mode", "passthrough", "-update", "1", "last.png"])
    run("extract-index-one", ["-i", "three-frames.mp4", "-map", "0:v:0", "-an", "-vf", r"select=eq(n\,1)", "-frames:v", "1", "-fps_mode", "passthrough", "-update", "1", "index-one.png"])
    run("seek-at-duration", ["-ss", "3", "-i", "three-frames.mp4", "-map", "0:v:0", "-an", "-frames:v", "1", "-update", "1", "at-duration.png"])

    def inspect_png(name):
        data = (out / name).read_bytes()
        if data[:8] != b"\x89PNG\r\n\x1a\n":
            raise AssertionError(f"{name} is not PNG")
        width, height = struct.unpack(">II", data[16:24])
        raw = run("decode-" + name, ["-i", name, "-f", "rawvideo", "-pix_fmt", "rgb24", "pipe:1"]).stdout
        offset = ((height // 2) * width + width // 2) * 3
        rgb = list(raw[offset:offset + 3])
        if len(raw) != width * height * 3:
            raise AssertionError(f"Unexpected pixel count in {name}")
        return {"file": name, "dimensions": [width, height], "center_rgb": rgb, "bytes": len(data), "sha256": hashlib.sha256(data).hexdigest()}

    last, middle = inspect_png("last.png"), inspect_png("index-one.png")
    checks = {
        "three_presentation_timestamps": pts == [0.0, 1.0, 2.0],
        "duration_three_seconds": duration_s == 3.0,
        "last_is_blue": last["center_rgb"][2] > 240 and max(last["center_rgb"][:2]) < 10,
        "index_one_is_green": middle["center_rgb"][1] > 240 and max(middle["center_rgb"][0], middle["center_rgb"][2]) < 10,
        "seek_at_end_created_no_png": not (out / "at-duration.png").exists(),
        "png_dimensions_match": last["dimensions"] == middle["dimensions"] == [320, 180],
        "longer_audio_duration_five_seconds": audio_duration_s == 5.0,
        "longer_audio_same_video_timestamps": audio_pts == [0.0, 1.0, 2.0],
    }
    version = subprocess.run([ffmpeg, "-version"], capture_output=True, text=True, check=True).stdout.splitlines()[0]
    result = {"checked_utc": datetime.datetime.now(datetime.timezone.utc).isoformat(), "ffmpeg_version": version, "fixture": {"file": "three-frames.mp4", "sha256": hashlib.sha256((out / "three-frames.mp4").read_bytes()).hexdigest(), "duration_seconds": duration_s, "presentation_timestamps_seconds": pts, "frame_colors_in_order": ["red", "green", "blue"], "original_synthetic_media": True}, "longer_audio_fixture": {"file": "longer-audio.mp4", "sha256": hashlib.sha256((out / "longer-audio.mp4").read_bytes()).hexdigest(), "duration_seconds": audio_duration_s, "presentation_timestamps_seconds": audio_pts}, "last_frame": last, "index_one_frame": middle, "checks": checks, "commands": commands, "not_covered": ["variable-frame-rate media", "HDR/color-managed workflows", "rotation metadata", "other codecs/builds", "corrupt input", "network services"]}
    (out / "result.json").write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"result": str(out / "result.json"), "checks": checks}))
    if not all(checks.values()):
        raise SystemExit(1)


if __name__ == "__main__":
    main()
