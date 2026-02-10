# Camera Pose Conversion Fix - Complete Documentation

## Overview

This document explains the mathematical principles behind the camera pose conversion from COLMAP/CSV format to Blender/UE5 FBX format, the bugs that were fixed, and how to use the corrected code.

## Table of Contents

1. [Mathematical Principles](#mathematical-principles)
2. [Bugs Fixed](#bugs-fixed)
3. [Usage Guide](#usage-guide)
4. [Verification](#verification)

---

## Mathematical Principles

### Coordinate Systems

Three different coordinate systems are involved in the conversion:

#### COLMAP Coordinate System
- **World coordinates**: X=right, Y=down, Z=forward
- **Camera convention**: Camera looks along **+Z** axis (forward)
- **Pose representation**: World-to-camera (w2c)
  - Quaternion: `(qw, qx, qy, qz)`
  - Translation: `(tx, ty, tz)`
  - Camera center: `C = -R_w2c^T @ t_w2c`

#### UE5 Coordinate System
- **World coordinates**: X=forward, Y=right, Z=up (left-handed)
- **Camera convention**: Camera looks along **+X** axis (forward)
- **Pose representation**: Camera-to-world (c2w)

#### Blender Coordinate System
- **World coordinates**: X=right, Y=forward, Z=up (right-handed)
- **Camera convention**: Camera looks along **-Z** axis (backward in local space)
- **Rotation matrix format**: `R = [right | up | backward]`
  - Camera viewing direction: `-R[:, 2]` (negative of 3rd column)

### Coordinate Transformation Formula

When transforming a rotation matrix between coordinate systems using transformation matrix `M`:

**Similarity Transformation:**
```
R_new = M @ R_old @ M^T
```

This is **NOT** simple matrix multiplication `R @ M` or `M @ R`.

**Why?** A rotation matrix represents how to rotate vectors. When you change coordinate systems:
1. A vector `v` in old coords becomes `M @ v` in new coords
2. The rotation must satisfy: `M @ (R @ v) = R_new @ (M @ v)`
3. Solving: `R_new = M @ R @ M^(-1)`
4. For orthogonal M: `M^(-1) = M^T`

### Camera Rotation Matrix Interpretation

A camera-to-world rotation matrix has columns representing camera's local axes in world coordinates:

```
R_c2w = [right_world | up_world | forward_world]  (for COLMAP/UE5)
R_c2w = [right_world | up_world | backward_world] (for Blender)
```

The camera's viewing direction depends on the convention:
- **COLMAP/UE5**: Camera looks along **+forward** (3rd column for COLMAP, 1st column for UE5)
- **Blender**: Camera looks along **-backward** = **+forward** (negative of 3rd column)

---

## Bugs Fixed

### Bug 1: Incorrect World-Space Rotation Transformation

**Location:** `data_export/trajectory_control.py`, function `_apply_transform()`

**The Problem:**
When applying world-space transformations (axis flips/swaps), the code was using:
```python
# WRONG
R = R @ M  # Right multiplication
```

**The Fix:**
```python
# CORRECT
R = M @ R @ M.T  # Similarity transformation
```

**Impact:** This bug affected all trajectory transformations (`--flip-x`, `--flip-y`, `--flip-z`, `--swap-xy`, `--swap-yz`, `--scale`). It caused rotation matrices to be corrupted, resulting in discontinuous camera trajectories.

---

### Bug 2: Incomplete COLMAP to UE5 Axis Conversion

**Location:** `data_export/colmap_to_ue.py`, function `colmap_pose_to_ue()`

**The Problem:**
The axis remapping from COLMAP to UE5 was incomplete:
```python
# WRONG
rotation_ue = _COLMAP_TO_UE_AXIS @ R_c2w_colmap
```

**The Fix:**
```python
# CORRECT
rotation_ue = _COLMAP_TO_UE_AXIS @ R_c2w_colmap @ _COLMAP_TO_UE_AXIS.T
```

**Impact:** This bug caused camera orientations to be incorrect in UE5 coordinate space, contributing to the discontinuous appearance of trajectories.

---

### Bug 3: Incorrect Blender Camera Orientation

**Location:** `data_export/poses_to_fbx_blender.py`, function `_set_keyframes()`

**The Problem:**
The conversion from UE5 to Blender was not accounting for Blender's camera convention. After coordinate transformation, the rotation matrix had the format:
```python
R_blender = [right | forward | up]  # Wrong format for Blender camera
```

But Blender camera needs:
```python
R_blender = [right | up | backward]  # Correct format
```

Where the camera looks along `-backward` direction.

**The Fix:**
```python
# After UE5 to Blender world coordinate transformation
R_blender = _UE_TO_BLENDER_WORLD @ R_ue @ _UE_TO_BLENDER_WORLD.T

# Rearrange columns to match Blender camera convention
R_blender_corrected = np.column_stack([
    R_blender[:, 0],   # right (unchanged)
    R_blender[:, 2],   # up (was column 2)
    -R_blender[:, 1],  # backward = -forward (was column 1)
])
```

**Impact:** This was the critical bug causing cameras to face the wrong direction. Before the fix, cameras were looking perpendicular to the path instead of along it.

---

## Usage Guide

### Prerequisites

- Python 3.8+
- NumPy
- Blender (on PATH or set `BLENDER_EXE` environment variable)

### Export from CSV

**Basic usage:**
```bash
python -m data_export.run_export_fbx <poses.csv> <output.fbx> [--fps FPS]
```

**Example:**
```bash
python -m data_export.run_export_fbx plaza_10s_csv/poses.csv plaza_camera.fbx --fps 30
```

**CSV Format:**
```csv
frame_id,qw,qx,qy,qz,tx,ty,tz
0,1.0,-0.00002,-0.00006,0.000001,0.00014,0.00001,0.00016
1,1.0,-0.00003,-0.00005,-0.000005,0.00016,-0.000002,0.00028
...
```

Where:
- `qw, qx, qy, qz`: Quaternion (COLMAP convention: world-to-camera)
- `tx, ty, tz`: Translation (COLMAP convention: world-to-camera)

### Export from COLMAP

**Basic usage:**
```bash
python -m data_export.run_export_fbx_colmap <colmap_dir> <output.fbx> [options]
```

**Example:**
```bash
python -m data_export.run_export_fbx_colmap plaza_10s_colmap plaza_camera.fbx --fps 30
```

**With transformations:**
```bash
python -m data_export.run_export_fbx_colmap plaza_10s_colmap plaza_camera.fbx \
    --scale 0.01 --swap-yz --reverse --fps 30
```

**Options:**
- `--scale FACTOR`: Scale camera path positions (e.g., `0.01` for 100x smaller)
- `--flip-x`, `--flip-y`, `--flip-z`: Flip world axes
- `--swap-xy`, `--swap-yz`: Swap axes
- `--reverse`: Reverse camera path (end to beginning)
- `--fps FPS`: Frame rate (default: 30)
- `--scale-to-cm`: Scale positions to centimeters for UE5 (default: True)
- `--no-scale-to-cm`: Keep positions in meters

### Trajectory Transformation (Optional)

Transform trajectory data before FBX export:

```bash
python -m data_export.trajectory_control <input> <output> [options]
```

**Example:**
```bash
# Transform CSV
python -m data_export.trajectory_control plaza_csv/poses.csv plaza_csv/poses_transformed.csv \
    --swap-yz --scale 0.01 --reverse

# Then export to FBX
python -m data_export.run_export_fbx plaza_csv/poses_transformed.csv plaza_camera.fbx --fps 30
```

**Input formats:**
- CSV file: `poses.csv`
- COLMAP directory: `colmap_dir/` (containing `images.txt`)
- COLMAP file: `colmap_dir/images.txt`

**Output formats:**
- CSV file: `output.csv`
- COLMAP directory: `output_dir/` (will create `images.txt`)
- COLMAP file: `output_dir/images.txt`

---

## Verification

### Import in Blender

1. Open Blender
2. File → Import → FBX
3. Select the exported `.fbx` file
4. Select the camera object
5. Press **Space** to play animation

**Expected results:**
- ✅ Camera moves smoothly along path (no jumps or discontinuities)
- ✅ Camera looks forward (along movement direction, matching COLMAP visualization)
- ✅ Camera orientation changes naturally at each frame
- ✅ Smooth, continuous motion matching the original video

### Import in Unreal Engine 5

1. In UE5 Content Browser, right-click → Import
2. Select the exported `.fbx` file
3. Import settings:
   - **Import as Skeletal**: No
   - **Import Animations**: Yes
   - **Animation Length**: Exported Frame Range
   - **Frame Rate**: Match your export FPS
4. Drag the imported camera into your level
5. In Sequencer, add the camera and its animation track
6. Play the sequence

**Expected results:**
- ✅ Camera path matches Blender preview
- ✅ Camera orientation correct in UE5 viewport
- ✅ Smooth camera motion for cinematics

### Troubleshooting

**Issue: Camera still facing wrong direction**
- Verify you regenerated FBX **after** applying all fixes
- Check file timestamp to ensure it's the latest version
- Try reimporting in Blender with default import settings

**Issue: Camera trajectory discontinuous**
- Check source data quality (COLMAP/DROID estimation)
- Verify CSV format matches expected format
- Run trajectory analysis: `python -m data_export.analyze_camera_direction <poses.csv>`

**Issue: Blender not found**
- Install Blender or set `BLENDER_EXE` environment variable:
  ```bash
  export BLENDER_EXE="/path/to/blender"  # Linux/Mac
  set BLENDER_EXE=C:\Path\To\blender.exe  # Windows
  ```

---

## Technical Details

### Complete Conversion Pipeline

```
COLMAP Camera Pose (world-to-camera)
  ├─ Quaternion: (qw, qx, qy, qz)
  ├─ Translation: (tx, ty, tz)
  └─ Camera center: C = -R_w2c^T @ t_w2c

↓ Convert to camera-to-world
  R_c2w_colmap = R_w2c^T

↓ Apply COLMAP to UE5 axis transformation
  position_ue = M_colmap_to_ue @ C
  rotation_ue = M_colmap_to_ue @ R_c2w_colmap @ M_colmap_to_ue^T

↓ Apply UE5 to Blender world transformation
  position_blender = [pos_ue[1], pos_ue[0], pos_ue[2]]
  R_temp = M_ue_to_blender @ R_ue @ M_ue_to_blender^T

↓ Rearrange for Blender camera convention
  R_blender = [R_temp[:, 0], R_temp[:, 2], -R_temp[:, 1]]
  (Columns: [right | up | backward])

↓ Convert to Euler angles
  euler_xyz = rotation_matrix_to_euler_xyz(R_blender)

↓ Export to FBX via Blender
  - Set camera location and rotation_euler
  - Export with axis_forward="X", axis_up="Z"
```

### Transformation Matrices

**COLMAP to UE5:**
```python
_COLMAP_TO_UE_AXIS = np.array([
    [0.0, 0.0, 1.0],   # UE X (forward)  = COLMAP Z
    [1.0, 0.0, 0.0],   # UE Y (right)    = COLMAP X
    [0.0, -1.0, 0.0],  # UE Z (up)       = -COLMAP Y
])
```

**UE5 to Blender World:**
```python
_UE_TO_BLENDER_WORLD = np.array([
    [0.0, 1.0, 0.0],   # Blender X (right)   = UE5 Y
    [1.0, 0.0, 0.0],   # Blender Y (forward) = UE5 X
    [0.0, 0.0, 1.0],   # Blender Z (up)      = UE5 Z
])
```

### Files Modified

1. **`data_export/trajectory_control.py`**
   - Fixed `_apply_transform()` to use similarity transformation
   - Affects: `--flip-x/y/z`, `--swap-xy/yz`, `--scale`

2. **`data_export/colmap_to_ue.py`**
   - Fixed `colmap_pose_to_ue()` to complete axis transformation
   - Affects: All COLMAP to UE5 conversions

3. **`data_export/poses_to_fbx_blender.py`**
   - Fixed `_set_keyframes()` to correctly handle Blender camera convention
   - Affects: Final FBX export orientation

---

## Summary

The camera pose conversion from COLMAP/CSV to Blender/UE5 FBX format required fixing three critical bugs:

1. **Similarity transformation** for world-space coordinate changes
2. **Complete axis remapping** from COLMAP to UE5
3. **Correct camera convention handling** for Blender's camera orientation

All fixes are based on rigorous mathematical principles of rotation matrix transformations and coordinate system conversions. The corrected code now faithfully preserves camera orientation from the source data through the entire conversion pipeline.

**Result:** Camera trajectories exported to FBX now display correctly in both Blender and Unreal Engine 5, with smooth motion and accurate orientation matching the original COLMAP visualization.

---

## References

- COLMAP format: https://colmap.github.io/format.html
- Rotation matrix transformations: Linear algebra similarity transformations
- Blender FBX export: https://docs.blender.org/manual/en/latest/addons/import_export/scene_fbx.html
- Unreal Engine camera import: https://docs.unrealengine.com/5.0/en-US/importing-fbx-content-into-unreal-engine/

---

**Last Updated:** February 2026  
**Version:** 1.0 (All bugs fixed and verified)
