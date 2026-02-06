#!/bin/bash
# Run frame extraction on cloud VM so DAVIS/upload_frames is ready for
# mono_depth_scripts/run_mono-depth_demo.sh and tools/evaluate_demo.sh.
#
# Usage:
#   ./video_preprocess/run_extract_frames.sh /path/to/video.mp4 [--fps 6]
#
# Run from repo root (e.g. cd /path/to/mega-sam-custom).

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
cd "$REPO_ROOT"

if [ $# -lt 1 ]; then
  echo "Usage: $0 <video_path> [--fps FPS]"
  echo "  video_path  Path to input video (e.g. /path/to/my_video.mp4)"
  echo "  --fps FPS   Target FPS for extracted frames (default: 6)"
  echo ""
  echo "Frames are written to ./DAVIS/upload_frames/"
  exit 1
fi

VIDEO_PATH="$1"
shift
EXTRA_ARGS=("$@")

python video_preprocess/extract_frames.py "$VIDEO_PATH" "${EXTRA_ARGS[@]}"

echo "Done. Next: run mono_depth_scripts/run_mono-depth_demo.sh then tools/evaluate_demo.sh"
