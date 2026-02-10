# Copyright 2025 DeepMind Technologies Limited
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use it except in compliance with the License.
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

"""COLMAP → (optional transform) → FBX for UE5 camera pose/path import.

Reads COLMAP images.txt (and optionally cameras.txt; points3D.txt not used for camera path),
applies optional scale/axis flips/swaps/reverse, converts to poses CSV, then runs Blender
to export FBX for Unreal Engine 5 CineCameraActor.

Usage (from repo root):
  python -m data_export.run_export_fbx_colmap plaza_10s_colmap plaza_camera.fbx
  python -m data_export.run_export_fbx_colmap plaza_10s_colmap plaza_camera.fbx --scale 0.01 --swap-yz --reverse
  python -m data_export.run_export_fbx_colmap plaza_10s_colmap/images.txt plaza_camera.fbx --csv out/poses.csv
"""

from __future__ import annotations

import argparse
import os
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

_SCRIPT_DIR = Path(__file__).resolve().parent
_REPO_ROOT = _SCRIPT_DIR.parent
_BLENDER_SCRIPT = _SCRIPT_DIR / "poses_to_fbx_blender.py"


def _find_blender() -> str | None:
    """Return path to Blender executable, or None if not found."""
    exe = os.environ.get("BLENDER_EXE")
    if exe and Path(exe).is_file():
        return exe
    exe = shutil.which("blender")
    if exe:
        return exe
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
        description="COLMAP images.txt → (optional transform) → FBX for UE5 camera path."
    )
    parser.add_argument(
        "colmap_input",
        type=Path,
        help="COLMAP directory (containing images.txt) or path to images.txt.",
    )
    parser.add_argument(
        "output_fbx",
        type=Path,
        help="Output FBX file path.",
    )
    parser.add_argument(
        "--csv",
        type=Path,
        default=None,
        metavar="PATH",
        help="Save intermediate poses CSV to this path (default: temp file, deleted after).",
    )
    parser.add_argument(
        "--scale",
        type=float,
        default=1.0,
        help="Scale camera path positions (e.g. 0.01 for 100x smaller). Default: 1.0.",
    )
    parser.add_argument("--flip-x", action="store_true", help="Flip world X axis.")
    parser.add_argument("--flip-y", action="store_true", help="Flip world Y axis.")
    parser.add_argument("--flip-z", action="store_true", help="Flip world Z axis.")
    parser.add_argument("--swap-xy", action="store_true", help="Swap X and Y axes.")
    parser.add_argument(
        "--swap-yz",
        action="store_true",
        help="Swap Y and Z axes (e.g. for Z-up in UE when source has Z horizontal).",
    )
    parser.add_argument(
        "--reverse",
        action="store_true",
        help="Reverse camera path (end to begin).",
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

    colmap_input = Path(args.colmap_input).resolve()
    if colmap_input.is_dir():
        images_txt = colmap_input / "images.txt"
    else:
        images_txt = colmap_input
    if not images_txt.is_file():
        print(f"Error: COLMAP images.txt not found: {images_txt}")
        return 1

    output_fbx = Path(args.output_fbx).resolve()
    output_fbx.parent.mkdir(parents=True, exist_ok=True)

    from data_export.trajectory_control import colmap_to_csv

    use_temp = args.csv is None
    if use_temp:
        fd, csv_path = tempfile.mkstemp(suffix=".csv", prefix="colmap_poses_")
        csv_path = Path(csv_path)
        os.close(fd)
    else:
        csv_path = Path(args.csv).resolve()
        csv_path.parent.mkdir(parents=True, exist_ok=True)

    try:
        n_poses = colmap_to_csv(
            images_txt,
            csv_path,
            flip_x=args.flip_x,
            flip_y=args.flip_y,
            flip_z=args.flip_z,
            reverse=args.reverse,
            swap_xy=args.swap_xy,
            swap_yz=args.swap_yz,
            path_scale=args.scale,
        )
        print(f"Wrote {n_poses} poses to {csv_path}")

        blender_exe = _find_blender()
        if not blender_exe:
            print(
                "Blender not found. Install Blender or set BLENDER_EXE.\n"
                "Intermediate CSV saved; you can run FBX export manually:\n"
                f"  python -m data_export.run_export_fbx {csv_path} {output_fbx}"
            )
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
            str(csv_path),
            str(output_fbx),
            str(args.fps),
        ]
        if not args.scale_to_cm:
            cmd.append("--no-scale-to-cm")

        print(f"Running Blender: ... -- {csv_path} {output_fbx} {args.fps}")
        result = subprocess.run(cmd, cwd=str(_REPO_ROOT))
        if result.returncode != 0:
            return result.returncode
        print(f"Exported {n_poses} camera keyframes to {output_fbx}")
        return 0
    finally:
        if use_temp and csv_path.is_file():
            try:
                csv_path.unlink()
            except OSError:
                pass


if __name__ == "__main__":
    sys.exit(main())
