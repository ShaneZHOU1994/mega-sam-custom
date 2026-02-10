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

"""Control camera trajectory data (before FBX conversion): flip axis, reverse path, swap X/Y/Z, scale.

Operates on COLMAP-format poses (world-to-camera quaternion + translation) in world space.
Supports CSV input (frame_id, qw,qx,qy,qz, tx,ty,tz) or COLMAP images.txt.
Output: CSV or COLMAP images.txt for use with run_export_fbx.

Use --swap-yz for Z-up orientation in UE5 when source has Z horizontal.
Use --scale to shrink or enlarge the camera path (e.g. 0.01 for 100x smaller).
Use --suggest-scale-from-depth [depth_summary.csv] to print a suggested --scale from scene depth.
Use --scale-from-depth [depth_summary.csv] to apply that suggested scale in this run.
"""

from __future__ import annotations

import argparse
import csv
import sys
from pathlib import Path
from typing import Iterator

import numpy as np

from data_export.colmap_to_ue import qvec2rotmat, load_poses_csv, rotmat2qvec


# Default target "scene depth" in UE (cm) when suggesting scale from depth_summary.csv
_DEFAULT_TARGET_UE_CM = 200.0


def load_depth_summary(csv_path: Path) -> list[tuple[int, float, float, float, float]]:
    """Load depth_summary.csv with columns frame_id, depth_min, depth_max, depth_mean, depth_median.

    Returns list of (frame_id, depth_min, depth_max, depth_mean, depth_median) per row.
    """
    rows = []
    with open(csv_path, newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            frame_id = int(row["frame_id"])
            depth_min = float(row["depth_min"])
            depth_max = float(row["depth_max"])
            depth_mean = float(row["depth_mean"])
            depth_median = float(row["depth_median"])
            rows.append((frame_id, depth_min, depth_max, depth_mean, depth_median))
    return rows


def suggest_scale_from_depth(
    depth_summary_path: Path,
    target_ue_cm: float = _DEFAULT_TARGET_UE_CM,
) -> tuple[float, float, float]:
    """Suggest path scale so that mean scene depth maps to target_ue_cm in UE5.

    Assumes poses and depth are in the same units (e.g. meters). After transform with
    this scale, run_export_fbx applies scale_to_cm (x100), so effective UE size is
    path_scale * 100 * depth_m = target_ue_cm  =>  path_scale = target_ue_cm / (100 * depth_m).

    Returns:
        (suggested_scale, mean_depth_m, median_depth_m) for reporting.
    """
    rows = load_depth_summary(depth_summary_path)
    if not rows:
        raise ValueError(f"No rows in depth summary: {depth_summary_path}")
    depth_means = [r[3] for r in rows]
    depth_medians = [r[4] for r in rows]
    mean_depth_m = float(np.mean(depth_means))
    median_depth_m = float(np.median(depth_medians))
    if mean_depth_m <= 0:
        raise ValueError(f"Mean depth must be positive, got {mean_depth_m}")
    suggested_scale = target_ue_cm / (100.0 * mean_depth_m)
    return suggested_scale, mean_depth_m, median_depth_m


# World-space transforms (COLMAP: X right, Y down, Z forward)
_FLIP_X = np.diag([-1.0, 1.0, 1.0])
_FLIP_Y = np.diag([1.0, -1.0, 1.0])
_FLIP_Z = np.diag([1.0, 1.0, -1.0])
_SWAP_XY = np.array([[0.0, 1.0, 0.0], [1.0, 0.0, 0.0], [0.0, 0.0, 1.0]], dtype=np.float64)
_SWAP_YZ = np.array([[1.0, 0.0, 0.0], [0.0, 0.0, 1.0], [0.0, 1.0, 0.0]], dtype=np.float64)


def _apply_transform(
    qvec: np.ndarray,
    tvec: np.ndarray,
    flip_x: bool,
    flip_y: bool,
    flip_z: bool,
    swap_xy: bool,
    swap_yz: bool,
    path_scale: float,
) -> tuple[np.ndarray, np.ndarray]:
    """Apply flip/swap/scale to one pose in COLMAP world space. Returns (qvec_new, tvec_new).
    
    For world-space transformations with matrix M:
    - Camera center: C_new = M @ C
    - Rotation (world-to-camera): R_new = M @ R @ M.T
    This ensures the camera orientation is correctly transformed in the new coordinate system.
    """
    R = qvec2rotmat(qvec)
    t = np.asarray(tvec, dtype=np.float64).reshape(3)
    # Camera center in world: C = -R^T @ t
    C = -R.T @ t

    # Apply world-space transformations: for each transformation matrix M,
    # transform both position (C_new = M @ C) and rotation (R_new = M @ R @ M.T)
    if flip_x:
        C = _FLIP_X @ C
        R = _FLIP_X @ R @ _FLIP_X.T
    if flip_y:
        C = _FLIP_Y @ C
        R = _FLIP_Y @ R @ _FLIP_Y.T
    if flip_z:
        C = _FLIP_Z @ C
        R = _FLIP_Z @ R @ _FLIP_Z.T
    if swap_xy:
        C = _SWAP_XY @ C
        R = _SWAP_XY @ R @ _SWAP_XY.T
    if swap_yz:
        C = _SWAP_YZ @ C
        R = _SWAP_YZ @ R @ _SWAP_YZ.T

    # Path scale: multiply camera center (position) by path_scale
    C = C * path_scale

    # Convert back to world-to-camera: t = -R @ C
    t_new = -R @ C
    qvec_new = rotmat2qvec(R)
    return qvec_new, t_new


def load_colmap_images(images_txt: Path) -> Iterator[tuple[int, np.ndarray, np.ndarray, int, str, str]]:
    """Load poses from COLMAP images.txt. Yields (image_id, qvec, tvec, camera_id, name, line2)."""
    with open(images_txt, "r", encoding="utf-8") as f:
        while True:
            line1 = f.readline()
            if not line1:
                break
            line1 = line1.strip()
            if not line1 or line1.startswith("#"):
                continue
            parts = line1.split()
            if len(parts) < 10:
                continue
            image_id = int(parts[0])
            qvec = np.array([float(parts[1]), float(parts[2]), float(parts[3]), float(parts[4])], dtype=np.float64)
            tvec = np.array([float(parts[5]), float(parts[6]), float(parts[7])], dtype=np.float64)
            camera_id = int(parts[8])
            name = parts[9]
            line2 = f.readline()
            if line2 is not None:
                line2 = line2.rstrip("\n\r")
            else:
                line2 = ""
            yield image_id, qvec, tvec, camera_id, name, line2


def transform_csv(
    input_csv: Path,
    output_csv: Path,
    flip_x: bool = False,
    flip_y: bool = False,
    flip_z: bool = False,
    reverse: bool = False,
    swap_xy: bool = False,
    swap_yz: bool = False,
    path_scale: float = 1.0,
) -> None:
    """Read CSV, apply transforms, write CSV."""
    rows = list(load_poses_csv(input_csv))
    if not rows:
        raise ValueError(f"No poses in {input_csv}")

    out_rows = []
    for frame_id, qvec, tvec in rows:
        q_new, t_new = _apply_transform(
            qvec, tvec, flip_x, flip_y, flip_z, swap_xy, swap_yz, path_scale
        )
        out_rows.append((frame_id, q_new, t_new))

    if reverse:
        out_rows.reverse()
        out_rows = [(i, q, t) for i, (_, q, t) in enumerate(out_rows)]

    output_csv.parent.mkdir(parents=True, exist_ok=True)
    with open(output_csv, "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(["frame_id", "qw", "qx", "qy", "qz", "tx", "ty", "tz"])
        for frame_id, q, t in out_rows:
            w.writerow([
                frame_id,
                f"{q[0]:.8f}", f"{q[1]:.8f}", f"{q[2]:.8f}", f"{q[3]:.8f}",
                f"{t[0]:.8f}", f"{t[1]:.8f}", f"{t[2]:.8f}",
            ])


def transform_colmap(
    input_images_txt: Path,
    output_images_txt: Path,
    flip_x: bool = False,
    flip_y: bool = False,
    flip_z: bool = False,
    reverse: bool = False,
    swap_xy: bool = False,
    swap_yz: bool = False,
    path_scale: float = 1.0,
) -> None:
    """Read COLMAP images.txt, apply transforms, write images.txt (poses only; copy cameras.txt separately)."""
    rows = list(load_colmap_images(input_images_txt))
    if not rows:
        raise ValueError(f"No images in {input_images_txt}")

    out_rows = []
    for image_id, qvec, tvec, camera_id, name, line2 in rows:
        q_new, t_new = _apply_transform(
            qvec, tvec, flip_x, flip_y, flip_z, swap_xy, swap_yz, path_scale
        )
        out_rows.append((image_id, q_new, t_new, camera_id, name, line2))

    if reverse:
        out_rows.reverse()
        out_rows = [(i + 1, q, t, cid, nm, l2) for i, (_, q, t, cid, nm, l2) in enumerate(out_rows)]

    output_images_txt.parent.mkdir(parents=True, exist_ok=True)
    _write_colmap_images(output_images_txt, out_rows)
    return


def _write_colmap_images(output_images_txt: Path, out_rows: list) -> None:
    """Write COLMAP images.txt from list of (image_id, q, t, camera_id, name, line2)."""
    with open(output_images_txt, "w", encoding="utf-8") as f:
        f.write("# Image list with two lines per image:\n")
        f.write("#   IMAGE_ID, QW, QX, QY, QZ, TX, TY, TZ, CAMERA_ID, NAME\n")
        f.write("#   POINTS2D[] or empty\n")
        f.write(f"# Number of images: {len(out_rows)}\n")
        for image_id, q, t, camera_id, name, line2 in out_rows:
            f.write(
                f"{image_id} {q[0]:.8f} {q[1]:.8f} {q[2]:.8f} {q[3]:.8f} "
                f"{t[0]:.8f} {t[1]:.8f} {t[2]:.8f} {camera_id} {name}\n"
            )
            f.write((line2 + "\n") if line2.strip() else "0\n")
            f.write("\n")


def colmap_to_csv(
    input_images_txt: Path,
    output_csv: Path,
    flip_x: bool = False,
    flip_y: bool = False,
    flip_z: bool = False,
    reverse: bool = False,
    swap_xy: bool = False,
    swap_yz: bool = False,
    path_scale: float = 1.0,
) -> int:
    """Read COLMAP images.txt, apply transforms, write poses CSV for run_export_fbx.

    Returns the number of poses written. Frame IDs in the CSV are 0-based consecutive.
    """
    rows = list(load_colmap_images(input_images_txt))
    if not rows:
        raise ValueError(f"No images in {input_images_txt}")

    out_rows = []
    for _image_id, qvec, tvec, _camera_id, _name, _line2 in rows:
        q_new, t_new = _apply_transform(
            qvec, tvec, flip_x, flip_y, flip_z, swap_xy, swap_yz, path_scale
        )
        out_rows.append((q_new, t_new))

    if reverse:
        out_rows.reverse()

    output_csv.parent.mkdir(parents=True, exist_ok=True)
    with open(output_csv, "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(["frame_id", "qw", "qx", "qy", "qz", "tx", "ty", "tz"])
        for frame_id, (q, t) in enumerate(out_rows):
            w.writerow([
                frame_id,
                f"{q[0]:.8f}", f"{q[1]:.8f}", f"{q[2]:.8f}", f"{q[3]:.8f}",
                f"{t[0]:.8f}", f"{t[1]:.8f}", f"{t[2]:.8f}",
            ])
    return len(out_rows)


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Transform camera trajectory (flip axis, reverse path, swap X/Y) before FBX conversion."
    )
    parser.add_argument(
        "input",
        type=Path,
        help="Input: path to poses CSV or to COLMAP images.txt (or directory containing images.txt).",
    )
    parser.add_argument(
        "output",
        type=Path,
        help="Output: path to CSV or to images.txt (or directory for COLMAP).",
    )
    parser.add_argument("--flip-x", action="store_true", help="Flip world X axis.")
    parser.add_argument("--flip-y", action="store_true", help="Flip world Y axis.")
    parser.add_argument("--flip-z", action="store_true", help="Flip world Z axis.")
    parser.add_argument("--reverse", action="store_true", help="Reverse camera path (end to begin).")
    parser.add_argument("--swap-xy", action="store_true", help="Swap X and Y axes.")
    parser.add_argument("--swap-yz", action="store_true", help="Swap Y and Z axes (e.g. for Z-up in UE).")
    parser.add_argument(
        "--scale",
        type=float,
        default=1.0,
        help="Scale camera path positions by this factor (e.g. 0.01 for 100x smaller). Default: 1.0.",
    )
    parser.add_argument(
        "--suggest-scale-from-depth",
        nargs="?",
        const="",
        metavar="depth_summary.csv",
        help="Print suggested --scale from depth_summary.csv (columns: frame_id, depth_min, depth_max, depth_mean, depth_median). If path omitted, use same dir as input with name depth_summary.csv. Then exit without transforming.",
    )
    parser.add_argument(
        "--scale-from-depth",
        nargs="?",
        const="",
        metavar="depth_summary.csv",
        help="Use suggested scale from depth_summary.csv for this run. If path omitted, use same dir as input. Overrides --scale.",
    )
    parser.add_argument(
        "--target-ue-cm",
        type=float,
        default=_DEFAULT_TARGET_UE_CM,
        help="Target scene depth in UE5 (cm) when using --suggest-scale-from-depth or --scale-from-depth. Default: 200.",
    )
    parser.add_argument(
        "--format",
        choices=["auto", "csv", "colmap"],
        default="auto",
        help="Input/output format: auto (detect from path), csv, or colmap.",
    )
    args = parser.parse_args()

    inp = Path(args.input).resolve()
    out = Path(args.output).resolve()

    # Resolve depth summary path: same dir as input if not specified
    def _depth_summary_path(optional_path: str | None) -> Path:
        if optional_path and optional_path.strip():
            p = Path(optional_path).resolve()
            if not p.is_file():
                print(f"Error: depth summary not found: {p}", file=sys.stderr)
                raise SystemExit(2)
            return p
        # Same directory as input; input may be file or dir
        if inp.is_file():
            base = inp.parent
        else:
            base = inp
        candidate = base / "depth_summary.csv"
        if not candidate.is_file():
            print(f"Error: depth_summary.csv not found at {candidate}", file=sys.stderr)
            raise SystemExit(2)
        return candidate

    if args.suggest_scale_from_depth is not None:
        depth_path = _depth_summary_path(args.suggest_scale_from_depth)
        scale_val, mean_d, median_d = suggest_scale_from_depth(depth_path, args.target_ue_cm)
        print(f"Depth summary: {depth_path}")
        print(f"  Mean depth (scene):   {mean_d:.4f} m")
        print(f"  Median depth:         {median_d:.4f} m")
        print(f"  Target in UE5:        {args.target_ue_cm} cm")
        print(f"  Suggested --scale:    {scale_val:.6f}")
        print(f"  Use:  --scale {scale_val:.6f}")
        return 0

    scale_to_use = args.scale
    if args.scale_from_depth is not None:
        depth_path = _depth_summary_path(args.scale_from_depth)
        scale_to_use, mean_d, _ = suggest_scale_from_depth(depth_path, args.target_ue_cm)
        print(f"Using scale from depth: {scale_to_use:.6f} (mean depth {mean_d:.4f} m, target {args.target_ue_cm} cm)")

    if args.format == "auto":
        if inp.suffix.lower() == ".csv":
            fmt = "csv"
        elif inp.name == "images.txt" or (inp.is_dir() and (inp / "images.txt").is_file()):
            fmt = "colmap"
        else:
            fmt = "csv" if out.suffix.lower() == ".csv" else "colmap"
    else:
        fmt = args.format

    if fmt == "csv":
        if inp.is_dir():
            inp = inp / "poses.csv"
        if not inp.is_file():
            print(f"Error: not a file: {inp}")
            return 1
        if out.is_dir():
            out = out / "poses.csv"
        transform_csv(
            inp, out,
            args.flip_x, args.flip_y, args.flip_z,
            args.reverse, args.swap_xy, args.swap_yz, scale_to_use,
        )
        print(f"Wrote {len(list(load_poses_csv(out)))} poses to {out}")
    else:
        if inp.is_dir():
            inp = inp / "images.txt"
        if not inp.is_file():
            print(f"Error: not a file: {inp}")
            return 1
        if out.is_dir():
            out = out / "images.txt"
        transform_colmap(
            inp, out,
            args.flip_x, args.flip_y, args.flip_z,
            args.reverse, args.swap_xy, args.swap_yz, scale_to_use,
        )
        print(f"Wrote COLMAP images.txt to {out} (copy cameras.txt manually if needed).")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
