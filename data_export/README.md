# Data export: .npz → CSV and COLMAP

Postprocess and export outputs from:

- **Mono-depth (UniDepth)** — `mono_depth_scripts/run_mono-depth_demo.sh` → per-frame `.npz` in `UniDepth/outputs/<scene>/`
- **Camera tracking (evaluate_demo)** — `tools/evaluate_demo.sh` → `outputs/<scene>_droid.npz`

## .npz formats

| Source | Path pattern | Contents |
|--------|----------------|----------|
| UniDepth | `UniDepth/outputs/<scene>/*.npz` | Per frame: `depth` (H×W float32), `fov` (scalar) |
| DROID | `outputs/<scene>_droid.npz` | One file: `images` (N,H,W,3), `depths` (N,H,W), `intrinsic` (3×3), `cam_c2w` (N,4,4) |

## Loading .npz in Python

```python
import numpy as np
from data_export.load_npz_utils import load_any_npz, load_unidepth_npz, load_droid_npz

# Auto-detect and load
data = load_any_npz("path/to/file.npz")

# Or by format
frame = load_unidepth_npz("UniDepth/outputs/swing/00000.npz")
# frame.depth, frame.fov, frame.frame_id

scene = load_droid_npz("outputs/swing_droid.npz")
# scene.images, scene.depths, scene.intrinsic, scene.cam_c2w, scene.scene_name
```

## Export to CSV

**Script:** `python -m data_export.export_csv` (or `python data_export/export_csv.py`)

- **UniDepth**  
  - Summary: one row per frame — `frame_id`, `fov`, `height`, `width`, `depth_min`, `depth_max`, `depth_mean`, `depth_median`.  
  - Optional: `--flatten-depth` → one row per pixel (`frame_id`, `row`, `col`, `depth`).

- **DROID**  
  - `intrinsics.csv`: `camera_id`, `fx`, `fy`, `cx`, `cy`  
  - `poses.csv`: `frame_id`, `qw`, `qx`, `qy`, `qz`, `tx`, `ty`, `tz` (world-to-camera)  
  - `depth_summary.csv`: per-frame depth stats (optional; use `--no-depth-summary` to skip)

**Examples:**

```bash
# Single UniDepth .npz → CSV
python -m data_export.export_csv UniDepth/outputs/swing/00000.npz -o swing_frame0.csv

# Whole UniDepth scene dir → summary + optional per-pixel CSVs
python -m data_export.export_csv UniDepth/outputs/swing -o swing_csv
python -m data_export.export_csv UniDepth/outputs/swing -o swing_csv --flatten-depth

# Single DROID .npz → CSV
python -m data_export.export_csv outputs/swing_droid.npz -o swing_csv

# Directory of *_droid.npz → one CSV set per scene
python -m data_export.export_csv outputs -o outputs/csv_export
```

## Export to COLMAP

**Script:** `python -m data_export.export_colmap` (or `python data_export/export_colmap.py`)

Only **DROID** outputs have poses; UniDepth .npz do not.

Writes COLMAP **text** model in the output directory:

- `cameras.txt` — one PINHOLE camera (fx, fy, cx, cy)
- `images.txt` — per-image pose (qw, qx, qy, qz, tx, ty, tz) and image name
- `points3D.txt` — empty (no 3D points)
- `images/` — RGB frames (optional; use `--no-images` to skip)

**Examples:**

```bash
# Single scene
python -m data_export.export_colmap outputs/swing_droid.npz -o swing_colmap

# All *_droid.npz in a directory
python -m data_export.export_colmap outputs -o colmap_export

# Only cameras.txt + images.txt (no image files written)
python -m data_export.export_colmap outputs/swing_droid.npz -o swing_colmap --no-images
```

**Using in COLMAP:**  
Point COLMAP’s “sparse model” (or “Import model”) to the output directory and choose **text** format. Image paths in `images.txt` are relative to that directory (e.g. `images/frame_000000.jpg`).

## Trajectory control (before FBX)

Transform camera trajectory data (flip axis, reverse path, swap X/Y/Z) on CSV or COLMAP input:

- **Script:** `python -m data_export.trajectory_control <input> <output> [--flip-x] [--flip-y] [--flip-z] [--reverse] [--swap-xy] [--swap-yz] [--scale]`
- **Input:** Path to poses CSV or COLMAP `images.txt` (or directory containing it).
- **Output:** Path to CSV or `images.txt` (or directory). Use `--format csv` or `--format colmap` to force format; otherwise auto-detected from path.
- **Options:** `--flip-x`, `--flip-y`, `--flip-z` (flip world axis), `--reverse` (end→begin), `--swap-xy`, `--swap-yz`, `--scale` (path scale factor).

**Important:** Transformation fixes applied (Feb 2025) - world-space rotation transformations now use correct similarity transformation formula.

Example: reverse path and write CSV, then export FBX:  
`python -m data_export.trajectory_control plaza_csv/poses.csv plaza_csv/poses_reversed.csv --reverse`  
`python -m data_export.run_export_fbx plaza_csv/poses_reversed.csv plaza_camera_reversed.fbx`

### Debug and Analysis Tools

**Analyze trajectory continuity:**
```bash
python -m data_export.debug_trajectory plaza_csv/poses.csv --max-frames 50
```
Shows frame-by-frame position/rotation changes and flags large jumps.

**Compare two trajectories:**
```bash
python -m data_export.compare_trajectories poses1.csv poses2.csv --max-frames 20
```
Shows differences between two trajectory files.

**Test transformation correctness:**
```bash
python -m data_export.test_transformation_fix
```
Runs comprehensive tests to verify transformations preserve trajectory continuity.

## Export to FBX for Unreal Engine 5 (Camera Poses)

Convert poses CSV (COLMAP convention) to an FBX camera animation for import into **Unreal Engine 5.5**.

- **Launcher (CSV):** `python -m data_export.run_export_fbx <poses.csv> <output.fbx> [--fps 30]`
- **Launcher (COLMAP):** `python -m data_export.run_export_fbx_colmap <colmap_dir_or_images.txt> <output.fbx>` — reads COLMAP `images.txt`, applies optional transform (scale, flip, swap, reverse), then exports FBX. Example:  
  `python -m data_export.run_export_fbx_colmap plaza_10s_colmap plaza_camera.fbx --scale 0.01 --swap-yz --reverse`
- **Conversion utilities:** `data_export.colmap_to_ue` — `load_poses_csv()`, `colmap_pose_to_ue()`, `rotmat2qvec()`, `export_ue_poses_csv()`
- **Full instructions:** See **[UE5_CAMERA_IMPORT.md](UE5_CAMERA_IMPORT.md)** in this folder (prerequisites, step-by-step UE5 import, troubleshooting).

**Requirements:** Python 3.8+, NumPy, and **Blender** (on PATH or set `BLENDER_EXE`).

## Requirements

- Python 3.8+
- NumPy  
- For writing RGB frames in COLMAP export: `opencv-python` (`pip install opencv-python`)

Run from the **repository root** so `data_export` and repo root are on `PYTHONPATH`, or set `PYTHONPATH` accordingly.
