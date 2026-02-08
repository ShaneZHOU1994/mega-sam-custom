# Copyright 2025 DeepMind Technologies Limited
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#    http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.
# ==============================================================================

"""Launcher: run Blender in background to export poses CSV to FBX for UE5.

Finds Blender (PATH, BLENDER_EXE, or common Windows paths) and runs:
  blender --background --python data_export/poses_to_fbx_blender.py -- <args>

Usage (from repo root):
  python -m data_export.run_export_fbx plaza_csv/poses.csv plaza_camera.fbx [--fps 30]
  python -m data_export.run_export_fbx plaza_csv/poses.csv plaza_camera.fbx --no-scale-to-cm
"""

from __future__ import annotations

import argparse
import os
import shutil
import subprocess
import sys
from pathlib import Path

_SCRIPT_DIR = Path(__file__).resolve().parent
_REPO_ROOT = _SCRIPT_DIR.parent
_BLENDER_SCRIPT = _SCRIPT_DIR / "poses_to_fbx_blender.py"


def _find_blender() -> str | None:
    """Return path to Blender executable, or None if not found."""
    # 1. Environment variable
    exe = os.environ.get("BLENDER_EXE")
    if exe and Path(exe).is_file():
        return exe
    # 2. On PATH
    exe = shutil.which("blender")
    if exe:
        return exe
    # 3. Common Windows paths (Blender 3.x / 4.x)
    if sys.platform == "win32":
        program_files = os.environ.get("ProgramFiles", "C:\\Program Files")
        foundation = Path(program_files) / "Blender Foundation"
        if foundation.is_dir():
            for sub in sorted(foundation.iterdir(), reverse=True):
                candidate = sub / "blender.exe"
                if candidate.is_file():
                    return str(candidate)
    return None


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Export poses CSV to FBX camera animation for Unreal Engine 5 (uses Blender)."
    )
    parser.add_argument(
        "poses_csv",
        type=Path,
        help="Path to poses CSV (frame_id, qw, qx, qy, qz, tx, ty, tz).",
    )
    parser.add_argument(
        "output_fbx",
        type=Path,
        help="Output FBX file path.",
    )
    parser.add_argument(
        "--fps",
        type=float,
        default=30.0,
        help="Frames per second for timeline (default: 30).",
    )
    parser.add_argument(
        "--scale-to-cm",
        action="store_true",
        default=True,
        help="Scale positions to centimeters for UE (default: True).",
    )
    parser.add_argument(
        "--no-scale-to-cm",
        action="store_false",
        dest="scale_to_cm",
        help="Keep positions in meters.",
    )
    args = parser.parse_args()

    blender_exe = _find_blender()
    if not blender_exe:
        print(
            "Blender not found. Install Blender or set BLENDER_EXE to the blender executable path.\n"
            "Example (Windows, run in cmd with admin if needed):\n"
            '  set BLENDER_EXE="C:\\Program Files\\Blender Foundation\\Blender 4.2\\blender.exe"'
        )
        return 1

    poses_csv = Path(args.poses_csv).resolve()
    output_fbx = Path(args.output_fbx).resolve()
    if not poses_csv.is_file():
        print(f"Error: poses CSV not found: {poses_csv}")
        return 1

    script_path = _BLENDER_SCRIPT.resolve()
    if not script_path.is_file():
        print(f"Error: Blender script not found: {script_path}")
        return 1

    cmd = [
        blender_exe,
        "--background",
        "--python", str(script_path),
        "--",
        str(poses_csv),
        str(output_fbx),
        str(args.fps),
    ]
    if not args.scale_to_cm:
        cmd.append("--no-scale-to-cm")

    print(f"Running: {blender_exe} --background --python ... -- {poses_csv} {output_fbx} {args.fps}")
    result = subprocess.run(cmd, cwd=str(_REPO_ROOT))
    return result.returncode


if __name__ == "__main__":
    sys.exit(main())
