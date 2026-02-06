# Copyright 2025 DeepMind Technologies Limited
#
# Export .npz outputs to CSV:
# - UniDepth: per-frame depth (optionally flattened row/col/depth) and fov
# - DROID: intrinsics, poses (qw,qx,qy,qz,tx,ty,tz), optional depth summary per frame

from __future__ import annotations

import argparse
import csv
from pathlib import Path
import sys

import numpy as np

# Add parent so we can use camera_tracking_scripts for rotmat2qvec if needed
_SCRIPT_DIR = Path(__file__).resolve().parent
_REPO_ROOT = _SCRIPT_DIR.parent
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))

from data_export.load_npz_utils import (
    infer_npz_format,
    load_droid_npz,
    load_unidepth_npz,
    load_unidepth_scene,
    iter_droid_npz,
)


def _rotmat2qvec(R: np.ndarray) -> np.ndarray:
    """Rotation matrix to quaternion (COLMAP order: qw, qx, qy, qz)."""
    Rxx, Ryx, Rzx, Rxy, Ryy, Rzy, Rxz, Ryz, Rzz = R.flat
    K = (
        np.array([
            [Rxx - Ryy - Rzz, 0, 0, 0],
            [Ryx + Rxy, Ryy - Rxx - Rzz, 0, 0],
            [Rzx + Rxz, Rzy + Ryz, Rzz - Rxx - Ryy, 0],
            [Ryz - Rzy, Rzx - Rxz, Rxy - Ryx, Rxx + Ryy + Rzz],
        ])
        / 3.0
    )
    eigvals, eigvecs = np.linalg.eigh(K)
    qvec = eigvecs[[3, 0, 1, 2], np.argmax(eigvals)]
    if qvec[0] < 0:
        qvec *= -1
    return qvec


def export_unidepth_frame_to_csv(
    frame_path: Path,
    out_csv: Path,
    flatten_depth: bool = False,
    depth_decimals: int = 6,
) -> None:
    """
    Export one UniDepth .npz to CSV.
    - If flatten_depth=False: one row per frame (frame_id, fov, height, width, depth_min, depth_max, depth_mean).
    - If flatten_depth=True: one row per pixel (frame_id, row, col, depth); file can be large.
    """
    frame = load_unidepth_npz(frame_path)
    depth = frame.depth
    h, w = depth.shape

    with open(out_csv, "w", newline="") as f:
        if flatten_depth:
            writer = csv.writer(f)
            writer.writerow(["frame_id", "row", "col", "depth"])
            valid = np.isfinite(depth) & (depth > 0)
            for row in range(h):
                for col in range(w):
                    if valid[row, col]:
                        writer.writerow([
                            frame.frame_id,
                            row,
                            col,
                            round(float(depth[row, col]), depth_decimals),
                        ])
        else:
            writer = csv.writer(f)
            writer.writerow([
                "frame_id", "fov", "height", "width",
                "depth_min", "depth_max", "depth_mean", "depth_median",
            ])
            valid = np.isfinite(depth) & (depth > 0)
            d = depth[valid] if np.any(valid) else np.array([0.0])
            writer.writerow([
                frame.frame_id,
                round(frame.fov, 6),
                h,
                w,
                round(float(np.min(d)), depth_decimals),
                round(float(np.max(d)), depth_decimals),
                round(float(np.mean(d)), depth_decimals),
                round(float(np.median(d)), depth_decimals),
            ])


def export_unidepth_scene_to_csv(
    scene_dir: Path,
    out_dir: Path,
    flatten_depth: bool = False,
    depth_decimals: int = 6,
) -> list[Path]:
    """Export all .npz in a UniDepth scene dir to CSV files. Returns list of written paths."""
    frames = load_unidepth_scene(scene_dir)
    if not frames:
        return []
    out_dir.mkdir(parents=True, exist_ok=True)
    written = []
    # Single summary CSV for the whole scene (one row per frame)
    summary_path = out_dir / "depth_summary.csv"
    with open(summary_path, "w", newline="") as f:
        writer = csv.writer(f)
        writer.writerow([
            "frame_id", "fov", "height", "width",
            "depth_min", "depth_max", "depth_mean", "depth_median",
        ])
        for fr in frames:
            d = fr.depth
            valid = np.isfinite(d) & (d > 0)
            vals = d[valid] if np.any(valid) else np.array([0.0])
            writer.writerow([
                fr.frame_id,
                round(fr.fov, 6),
                d.shape[0],
                d.shape[1],
                round(float(np.min(vals)), depth_decimals),
                round(float(np.max(vals)), depth_decimals),
                round(float(np.mean(vals)), depth_decimals),
                round(float(np.median(vals)), depth_decimals),
            ])
    written.append(summary_path)
    if flatten_depth:
        for fr in frames:
            frame_csv = out_dir / f"depth_{fr.frame_id}.csv"
            with open(frame_csv, "w", newline="") as f:
                w = csv.writer(f)
                w.writerow(["frame_id", "row", "col", "depth"])
                h, w_h = fr.depth.shape
                for r in range(h):
                    for c in range(w_h):
                        if np.isfinite(fr.depth[r, c]) and fr.depth[r, c] > 0:
                            w.writerow([fr.frame_id, r, c, round(float(fr.depth[r, c]), depth_decimals)])
            written.append(frame_csv)
    return written


def export_droid_to_csv(
    npz_path: Path,
    out_dir: Path,
    depth_summary: bool = True,
    depth_decimals: int = 6,
) -> list[Path]:
    """
    Export one *_droid.npz to CSV:
    - intrinsics.csv: camera_id, fx, fy, cx, cy (and full 3x3 if needed)
    - poses.csv: frame_id, qw, qx, qy, qz, tx, ty, tz (world-to-camera, COLMAP-style)
    - depth_summary.csv (optional): frame_id, depth_min, depth_max, depth_mean
    """
    scene = load_droid_npz(npz_path)
    out_dir = Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    written = []

    # Intrinsics
    K = scene.intrinsic
    intrinsics_path = out_dir / "intrinsics.csv"
    with open(intrinsics_path, "w", newline="") as f:
        w = csv.writer(f)
        w.writerow(["camera_id", "fx", "fy", "cx", "cy"])
        w.writerow([1, K[0, 0], K[1, 1], K[0, 2], K[1, 2]])
    written.append(intrinsics_path)

    # Poses: convert cam_c2w to world-to-camera quat + tvec
    poses_path = out_dir / "poses.csv"
    n = scene.cam_c2w.shape[0]
    with open(poses_path, "w", newline="") as f:
        w = csv.writer(f)
        w.writerow(["frame_id", "qw", "qx", "qy", "qz", "tx", "ty", "tz"])
        for i in range(n):
            c2w = scene.cam_c2w[i]
            w2c = np.linalg.inv(c2w)
            R = w2c[:3, :3]
            t = w2c[:3, 3]
            qvec = _rotmat2qvec(R)
            w.writerow([
                i,
                round(qvec[0], 8),
                round(qvec[1], 8),
                round(qvec[2], 8),
                round(qvec[3], 8),
                round(t[0], 8),
                round(t[1], 8),
                round(t[2], 8),
            ])
    written.append(poses_path)

    if depth_summary and scene.depths is not None:
        depth_path = out_dir / "depth_summary.csv"
        with open(depth_path, "w", newline="") as f:
            w = csv.writer(f)
            w.writerow(["frame_id", "depth_min", "depth_max", "depth_mean", "depth_median"])
            for i in range(n):
                d = scene.depths[i]
                valid = np.isfinite(d) & (d > 0)
                vals = d[valid] if np.any(valid) else np.array([0.0])
                w.writerow([
                    i,
                    round(float(np.min(vals)), depth_decimals),
                    round(float(np.max(vals)), depth_decimals),
                    round(float(np.mean(vals)), depth_decimals),
                    round(float(np.median(vals)), depth_decimals),
                ])
        written.append(depth_path)

    return written


def main():
    parser = argparse.ArgumentParser(
        description="Export .npz (UniDepth or DROID) to CSV.",
        formatter_class=argparse.ArgumentDefaultsHelpFormatter,
    )
    parser.add_argument(
        "input",
        type=Path,
        help="Path to a single .npz file, or directory containing .npz (UniDepth: scene dir; DROID: dir of *_droid.npz).",
    )
    parser.add_argument(
        "-o", "--output",
        type=Path,
        default=None,
        help="Output directory (or single CSV for one UniDepth .npz). Default: same as input with _csv suffix or next to file.",
    )
    parser.add_argument(
        "--format",
        choices=("auto", "unidepth", "droid"),
        default="auto",
        help="Force format; auto infers from file contents.",
    )
    parser.add_argument(
        "--flatten-depth",
        action="store_true",
        help="For UniDepth: write one row per pixel (frame_id, row, col, depth). Can be large.",
    )
    parser.add_argument(
        "--no-depth-summary",
        action="store_true",
        help="For DROID: skip depth_summary.csv.",
    )
    parser.add_argument(
        "--decimals",
        type=int,
        default=6,
        help="Decimal places for float columns.",
    )
    args = parser.parse_args()

    input_path = args.input.resolve()
    if not input_path.exists():
        print(f"Error: input does not exist: {input_path}", file=sys.stderr)
        sys.exit(1)

    if input_path.is_file():
        fmt = args.format
        if fmt == "auto":
            fmt = infer_npz_format(input_path)
            if fmt is None:
                print("Error: could not infer .npz format. Use --format unidepth or droid.", file=sys.stderr)
                sys.exit(1)
        if fmt == "unidepth":
            if args.output and args.output.suffix.lower() == ".csv":
                out = args.output
            else:
                out_dir = args.output or (input_path.parent / f"{input_path.stem}_csv")
                out_dir = Path(out_dir)
                out_dir.mkdir(parents=True, exist_ok=True)
                out = out_dir / "depth_summary.csv"
            export_unidepth_frame_to_csv(
                input_path,
                out,
                flatten_depth=args.flatten_depth,
                depth_decimals=args.decimals,
            )
            print(f"Wrote: {out}")
            if args.flatten_depth and (args.output is None or not args.output.suffix.lower() == ".csv"):
                out_dir = out.parent
                frame = load_unidepth_npz(input_path)
                frame_csv = out_dir / f"depth_{frame.frame_id}.csv"
                export_unidepth_frame_to_csv(
                    input_path,
                    frame_csv,
                    flatten_depth=True,
                    depth_decimals=args.decimals,
                )
                print(f"Wrote: {frame_csv}")
        else:
            out_dir = args.output or (input_path.parent / f"{input_path.stem.replace('_droid', '')}_csv")
            paths = export_droid_to_csv(
                input_path,
                out_dir,
                depth_summary=not args.no_depth_summary,
                depth_decimals=args.decimals,
            )
            for p in paths:
                print(f"Wrote: {p}")
        return

    # Directory
    if args.format == "droid" or (args.format == "auto" and any(input_path.glob("*_droid.npz"))):
        out_base = args.output or (input_path / "csv_export")
        out_base = Path(out_base)
        for scene_name, scene in iter_droid_npz(input_path):
            out_dir = out_base / scene_name
            paths = export_droid_to_csv(
                input_path / f"{scene_name}_droid.npz",
                out_dir,
                depth_summary=not args.no_depth_summary,
                depth_decimals=args.decimals,
            )
            for p in paths:
                print(f"Wrote: {p}")
        return

    # UniDepth scene directory (many .npz per scene)
    out_dir = args.output or (input_path.parent / f"{input_path.name}_csv")
    paths = export_unidepth_scene_to_csv(
        input_path,
        Path(out_dir),
        flatten_depth=args.flatten_depth,
        depth_decimals=args.decimals,
    )
    for p in paths:
        print(f"Wrote: {p}")


if __name__ == "__main__":
    main()
