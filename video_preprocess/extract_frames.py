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
    parser.add_argument(
        "--max-frames",
        type=int,
        default=None,
        help="Optional hard cap on the number of frames to write.",
    )
    parser.add_argument(
        "--max-duration-sec",
        type=float,
        default=None,
        help="Optional maximum duration (in seconds) to process from the start of the video.",
    )
    parser.add_argument(
        "--resize-long-dim",
        type=int,
        default=None,
        help=(
            "If set, downscale frames so that the longer image side is at most this many "
            "pixels (aspect ratio preserved)."
        ),
    )
    args = parser.parse_args()

    if args.fps <= 0:
        print("Error: --fps must be > 0.", file=sys.stderr)
        return 1

    video_path = args.video.resolve()
    if not video_path.is_file():
        print(f"Error: video file not found: {video_path}", file=sys.stderr)
        return 1

    out_dir = args.out_dir
    if out_dir is None:
        out_dir = Path("DAVIS") / "upload_frames"
    out_dir = out_dir.resolve()
    out_dir.mkdir(parents=True, exist_ok=True)

    cap = cv2.VideoCapture(str(video_path))
    if not cap.isOpened():
        print(f"Error: could not open video: {video_path}", file=sys.stderr)
        return 1

    video_fps = cap.get(cv2.CAP_PROP_FPS)
    if video_fps <= 0:
        video_fps = 30.0
    total_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
    duration_sec = total_frames / video_fps if total_frames else 0.0

    dt_video = 1.0 / video_fps
    dt_target = 1.0 / args.fps

    # Sequentially decode frames and pick those whose timestamp crosses the next target time.
    written = 0
    frame_idx = 0
    next_save_time = 0.0

    while True:
        ret, frame = cap.read()
        if not ret:
            break

        t_sec = frame_idx * dt_video
        if args.max_duration_sec is not None and t_sec > args.max_duration_sec:
            break

        if t_sec + 1e-9 >= next_save_time:
            frame_to_write = frame
            if args.resize_long_dim is not None and args.resize_long_dim > 0:
                h, w = frame.shape[:2]
                long_dim = max(h, w)
                if long_dim > args.resize_long_dim:
                    if h >= w:
                        new_h = args.resize_long_dim
                        new_w = int(round(w * args.resize_long_dim / float(h)))
                    else:
                        new_w = args.resize_long_dim
                        new_h = int(round(h * args.resize_long_dim / float(w)))
                    frame_to_write = cv2.resize(
                        frame, (new_w, new_h), interpolation=cv2.INTER_AREA
                    )

            out_path = out_dir / f"{written:05d}.jpg"
            cv2.imwrite(str(out_path), frame_to_write)
            written += 1
            next_save_time += dt_target

            if args.max_frames is not None and written >= args.max_frames:
                break

        frame_idx += 1

    cap.release()
    print(
        f"Wrote {written} frames to {out_dir} (target FPS={args.fps}, "
        f"video_fps={video_fps:.2f}, duration={duration_sec:.2f}s)."
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
