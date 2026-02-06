#!/usr/bin/env python3
"""
Extract video frames at a given FPS and save to DAVIS/upload_frames.
Use output with run_mono-depth_demo.sh and tools/evaluate_demo.sh.
"""

import argparse
import sys
from pathlib import Path

try:
    import cv2
except ImportError:
    raise ImportError(
        "OpenCV (cv2) is required. Install with: pip install opencv-python"
    )


def main():
    parser = argparse.ArgumentParser(
        description="Extract video frames at given FPS into DAVIS/upload_frames."
    )
    parser.add_argument(
        "video",
        type=Path,
        help="Path to input video file.",
    )
    parser.add_argument(
        "--fps",
        type=float,
        default=6.0,
        help="Target FPS for extracted frames (default: 6).",
    )
    parser.add_argument(
        "--out-dir",
        type=Path,
        default=None,
        help="Output directory (default: ./DAVIS/upload_frames).",
    )
    args = parser.parse_args()

    video_path = args.video.resolve()
    if not video_path.is_file():
        print(f"Error: video file not found: {video_path}", file=sys.stderr)
        sys.exit(1)

    out_dir = args.out_dir
    if out_dir is None:
        out_dir = Path("DAVIS") / "upload_frames"
    out_dir = out_dir.resolve()
    out_dir.mkdir(parents=True, exist_ok=True)

    cap = cv2.VideoCapture(str(video_path))
    if not cap.isOpened():
        print(f"Error: could not open video: {video_path}", file=sys.stderr)
        sys.exit(1)

    video_fps = cap.get(cv2.CAP_PROP_FPS)
    if video_fps <= 0:
        video_fps = 30.0
    total_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
    duration_sec = total_frames / video_fps if total_frames else 0
    num_out = max(1, int(round(duration_sec * args.fps)))

    written = 0
    for i in range(num_out):
        t_sec = i / args.fps
        frame_idx = min(int(t_sec * video_fps), total_frames - 1) if total_frames else 0
        cap.set(cv2.CAP_PROP_POS_FRAMES, frame_idx)
        ret, frame = cap.read()
        if not ret:
            break
        out_path = out_dir / f"{written:05d}.jpg"
        cv2.imwrite(str(out_path), frame)
        written += 1

    cap.release()
    print(f"Wrote {written} frames to {out_dir} (target FPS={args.fps}).")
    return 0


if __name__ == "__main__":
    sys.exit(main())
