# Import Camera Poses into Unreal Engine 5.5

This guide describes how to convert camera pose data (CSV or COLMAP format) into an FBX camera animation and import it into **Unreal Engine 5.5** for viewing in a virtual environment.

## Pipeline Overview

```
poses.csv (COLMAP convention)  →  colmap_to_ue  →  FBX (camera + keyframes)  →  UE5 Sequencer
```

1. **Conversion**: COLMAP world-to-camera (right-handed, X right / Y down / Z forward) → UE5 camera-to-world (left-handed, X forward / Y right / Z up).
2. **Export**: A Python script run inside **Blender** (headless) creates one camera with keyframes and exports FBX with Unreal-friendly axes (Forward X, Up Z).
3. **Import**: In UE5 Sequencer, add a Cine Camera Actor and import the FBX to apply the animation.

---

## Prerequisites

- **Python 3.8+** (with NumPy) for conversion and launcher.
- **Blender 3.x or 4.x** installed and either:
  - On your system **PATH**, or
  - Path set in environment variable **`BLENDER_EXE`** (e.g. `C:\Program Files\Blender Foundation\Blender 4.2\blender.exe`).
- **Unreal Engine 5.5** (or 5.x) with a level and optional virtual environment asset.

---

## Data Formats

### Input: Poses CSV

Your poses CSV (e.g. from `data_export/export_csv` or DROID pipeline) must have columns:

| Column   | Description                          |
|----------|--------------------------------------|
| `frame_id` | Integer frame index (0, 1, 2, …)   |
| `qw`, `qx`, `qy`, `qz` | Quaternion (world-to-camera)     |
| `tx`, `ty`, `tz`       | Translation (world-to-camera)    |

Example: `plaza_csv/poses.csv`

### Input: COLMAP (alternative)

If you only have COLMAP text model (`images.txt`, `cameras.txt`), you can either:

- Export poses to CSV using your pipeline, or
- Use `colmap_read_model.py` to read `images.txt` and feed the same (qw, qx, qy, qz, tx, ty, tz) into the conversion. The conversion script in this folder expects **CSV**; for COLMAP-only you’d write a small script that reads COLMAP and calls `colmap_pose_to_ue()` per image.

---

## Step 1: Convert Poses to UE5 and Export FBX

### Option A: Launcher script (recommended)

From the **repository root** (so `data_export` and repo root are on `PYTHONPATH`):

```bash
# Default: 30 fps, positions scaled to centimeters for UE
python -m data_export.run_export_fbx plaza_csv/poses.csv plaza_camera.fbx

# Custom fps (e.g. match source video)
python -m data_export.run_export_fbx plaza_csv/poses.csv plaza_camera.fbx --fps 24

# Keep positions in meters (no scale to cm)
python -m data_export.run_export_fbx plaza_csv/poses.csv plaza_camera.fbx --no-scale-to-cm
```

**Windows (cmd, run with appropriate privileges if needed):**

```cmd
cd /d D:\PyProjects\mega-sam-custom
python -m data_export.run_export_fbx plaza_csv/poses.csv plaza_camera.fbx --fps 30
```

The launcher finds Blender (PATH or `BLENDER_EXE`), runs it in the background with `poses_to_fbx_blender.py`, and writes `plaza_camera.fbx` (or the path you give).

### Option B: Run Blender manually

If Blender is on PATH:

```bash
blender --background --python data_export/poses_to_fbx_blender.py -- plaza_csv/poses.csv plaza_camera.fbx 30
```

Arguments after `--`: `poses_csv`, `output_fbx`, `fps` (optional, default 30). Add `--no-scale-to-cm` to keep positions in meters.

### Option C: Export UE-style poses to CSV (no FBX)

To only convert COLMAP → UE5 and write a CSV (e.g. for verification or other tools):

```python
from pathlib import Path
from data_export.colmap_to_ue import export_ue_poses_csv

export_ue_poses_csv(
    Path("plaza_csv/poses.csv"),
    Path("plaza_csv/poses_ue.csv"),
    scale_to_cm=True,
)
```

Output columns: `frame_id`, `px`, `py`, `pz`, `roll_deg`, `pitch_deg`, `yaw_deg` (UE convention).

---

## Step 2: Import FBX into Unreal Engine 5.5

1. **Open your project** and the level where you want the camera path (e.g. with your virtual environment asset).

2. **Open or create a Level Sequence**  
   - **Cinematics** → **Level Sequence** → create or open existing.

3. **Add a Cine Camera Actor**  
   - In the Sequencer toolbar: **+ Track** → **Add Cine Camera** (or place a **Cine Camera Actor** in the level and add it to the sequence).  
   - Ensure the camera has a clear name (e.g. `CineCameraActor_0`); you may bind the FBX to it by name.

4. **Import the FBX**  
   - In Sequencer: **File** → **Import** → **FBX** (or equivalent in your UE version).  
   - Select the exported FBX (e.g. `plaza_camera.fbx`).  
   - In the import dialog:
     - Map the **FBX camera** to the **Cine Camera Actor** you added.
     - Set **Frame Rate** to match the export (e.g. 30 if you used `--fps 30`).
   - Confirm import; the camera’s **Transform** track should be filled with keyframes.

5. **Playback**  
   - Play the sequence; the view should follow the trajectory from your source video.  
   - Optionally enable **Lock Viewport to Camera** so the editor view follows the camera.

6. **FOV (optional)**  
   - If you have intrinsics (e.g. `plaza_csv/intrinsics.csv` or COLMAP `cameras.txt`), set the Cine Camera’s **Focal Length** or **Field of View** in UE to match the original video so framing matches.

---

## Scripts Reference

| Script / module              | Purpose |
|-----------------------------|--------|
| `colmap_to_ue.py`           | COLMAP → UE5 coordinate conversion; `load_poses_csv()`, `colmap_pose_to_ue()`, `export_ue_poses_csv()`. |
| `poses_to_fbx_blender.py`   | Run **inside Blender** (`blender --background --python ...`): reads CSV, creates camera keyframes, exports FBX (Forward X, Up Z). |
| `run_export_fbx.py`         | Launcher: finds Blender, runs `poses_to_fbx_blender.py` with your CSV and output FBX path. |

---

## Coordinate System Summary

- **COLMAP**: Right-handed. X right, Y down, Z forward (into scene). Poses are **world-to-camera** (R, t).
- **UE5**: Left-handed. X forward, Y right, Z up. We output **camera-to-world** position and rotation.
- **Conversion**: Camera center in world (COLMAP) = `-R^T @ t`. Axis remap: UE forward = Colmap Z, UE right = Colmap X, UE up = -Colmap Y. Positions are optionally scaled by 100 (meters → centimeters) for UE’s default unit.

---

## Troubleshooting

- **Blender not found**  
  - Install Blender and add it to PATH, or set `BLENDER_EXE` to the full path of `blender.exe`.

- **FBX import in UE does not create a camera**  
  - UE typically imports **animation** onto an existing camera. Add a Cine Camera in the sequence first, then import the FBX and assign it to that camera.

- **Camera pointing wrong direction**  
  - The scripts convert COLMAP (camera looks along +Z) to UE (camera looks along +X). If your source used a different convention, the conversion in `colmap_to_ue.py` may need to be adjusted.

- **Scale looks wrong in UE**  
  - Use `--scale-to-cm` (default) if your CSV/COLMAP is in **meters**; use `--no-scale-to-cm` if your data is already in centimeters or you want to scale in UE.

- **FPS / timing**  
  - Export with `--fps` matching your source video (e.g. 30 or 24). Set the same frame rate in the UE FBX import dialog so the sequence length and timing match.
