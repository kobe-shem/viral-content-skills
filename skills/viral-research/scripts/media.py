#!/usr/bin/env python3
"""Prepare inspectable evidence from an existing local video. Python 3.9+, ffmpeg."""
import argparse
import hashlib
import json
import math
from pathlib import Path
import shutil
import subprocess
import sys


def run(args):
    result = subprocess.run(args, capture_output=True, text=True)
    if result.returncode:
        raise ValueError(result.stderr[-3000:] or "Media command failed")
    return result


def sha256(path):
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def inspect(path):
    if not shutil.which("ffprobe"):
        raise ValueError("ffprobe is required on PATH")
    data = json.loads(run(["ffprobe", "-v", "error", "-show_format", "-show_streams", "-of", "json", str(path)]).stdout)
    streams = data.get("streams", [])
    video = next((s for s in streams if s.get("codec_type") == "video"), None)
    if not video:
        raise ValueError("Source has no video stream")
    raw_duration = data.get("format", {}).get("duration")
    if raw_duration in (None, ""):
        raw_duration = video.get("duration")
    try:
        duration = float(raw_duration)
    except (TypeError, ValueError):
        raise ValueError("Source duration is unavailable or invalid")
    if not math.isfinite(duration) or duration <= 0:
        raise ValueError("Source duration is unavailable or invalid")
    return {
        "duration_seconds": duration,
        "width": video.get("width"), "height": video.get("height"),
        "average_frame_rate": video.get("avg_frame_rate"),
        "nominal_frame_rate": video.get("r_frame_rate"),
        "audio_present": any(s.get("codec_type") == "audio" for s in streams),
        "probe": data,
    }


def schedule(duration, interval, max_frames=None):
    # Dense opening plus explicit full-duration samples. Does not claim every cut.
    if not math.isfinite(duration) or duration <= 0 or not math.isfinite(interval) or interval <= 0:
        raise ValueError("Duration and interval must be positive finite numbers")
    regular_count = math.ceil(duration / interval)
    if max_frames is not None and regular_count > max_frames:
        raise ValueError("Frame budget exceeded. Increase interval/max-frames deliberately or study a documented excerpt.")
    times = {0.0, 0.25, 0.5, 1.0, 1.5, 2.0, 3.0, 5.0}
    times.update(i * interval for i in range(regular_count))
    times.add(max(0.0, duration - 0.1))
    rounded = {round(t, 4) for t in times if t < duration}
    if max_frames is not None and len(rounded) > max_frames:
        raise ValueError("Frame budget exceeded. Increase interval/max-frames deliberately or study a documented excerpt.")
    return sorted(rounded)


def prepare(path, output, interval=2.0, max_frames=360):
    if not path.is_file():
        raise ValueError("Source must be an existing local video")
    if not math.isfinite(interval) or interval <= 0 or max_frames < 1:
        raise ValueError("Use a positive interval and max-frames")
    if output.exists():
        raise ValueError("Output already exists; choose a new evidence version")
    if not shutil.which("ffmpeg"):
        raise ValueError("ffmpeg is required on PATH")
    info = inspect(path)
    times = schedule(info["duration_seconds"], interval, max_frames)
    output.mkdir(parents=True)
    frames_dir = output / "frames"
    frames_dir.mkdir()
    manifest = {
        "schema_version": "1.0", "status": "preparing",
        "source_path": str(path.resolve()), "source_sha256": sha256(path),
        "duration_seconds": info["duration_seconds"], "width": info["width"], "height": info["height"],
        "average_frame_rate": info["average_frame_rate"], "nominal_frame_rate": info["nominal_frame_rate"],
        "audio_present": info["audio_present"], "frame_interval_seconds": interval,
        "coverage": {"visual": "sampled_frames_unreviewed", "speech": "not_transcribed", "audio": "unreviewed", "continuous_video": "unreviewed"},
        "frames": [], "warnings": ["Sampled frames can miss transitions, motion and brief text. Extract additional timecodes around suspected events.", "Transcript and audio extraction do not establish a listening review. Scene labels require observation."]
    }
    manifest_path = output / "media-manifest.json"
    def save():
        manifest_path.write_text(json.dumps(manifest, indent=2) + "\n")
    save()
    (output / "ffprobe.json").write_text(json.dumps(info["probe"], indent=2) + "\n")
    try:
        for index, seconds in enumerate(times):
            name = "frame-{:04d}-{:010.4f}s.jpg".format(index, seconds)
            frame = frames_dir / name
            run(["ffmpeg", "-v", "error", "-i", str(path), "-ss", str(seconds), "-frames:v", "1", "-vf", "scale=640:-2", "-q:v", "3", str(frame)])
            if not frame.is_file() or frame.stat().st_size == 0:
                manifest["warnings"].append("No decoded frame at {} seconds".format(seconds))
                continue
            manifest["frames"].append({"requested_time_seconds": seconds, "path": "frames/" + name, "sha256": sha256(frame), "timing_note": "Requested seek position; not a frame-accurate cut boundary."})
        if info["audio_present"]:
            run(["ffmpeg", "-v", "error", "-i", str(path), "-vn", "-ac", "1", "-ar", "16000", "-c:a", "pcm_s16le", str(output / "audio.wav")])
            manifest["audio_path"] = "audio.wav"
            manifest["audio_sha256"] = sha256(output / "audio.wav")
        manifest["status"] = "prepared"
        save()
    except Exception as exc:
        manifest["status"] = "failed_partial_evidence"
        manifest["failure"] = str(exc)
        save()
        raise
    return manifest


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="command", required=True)
    probe = sub.add_parser("probe")
    probe.add_argument("source", type=Path)
    prep = sub.add_parser("prepare")
    prep.add_argument("source", type=Path)
    prep.add_argument("--out", type=Path, required=True)
    prep.add_argument("--interval", type=float, default=2.0)
    prep.add_argument("--max-frames", type=int, default=360)
    args = parser.parse_args()
    try:
        result = inspect(args.source) if args.command == "probe" else prepare(args.source, args.out, args.interval, args.max_frames)
        print(json.dumps(result, indent=2))
    except (ValueError, OSError, json.JSONDecodeError) as exc:
        print("Error: " + str(exc), file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
