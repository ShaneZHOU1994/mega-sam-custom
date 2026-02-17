# Camera Intrinsics Support in FBX Export

## Overview

The FBX export pipeline now automatically reads and applies camera intrinsic parameters (focal length) from COLMAP's `cameras.txt` file. This ensures that the exported FBX contains the correct focal length, eliminating the need to manually set it in Unreal Engine 5 for every frame.

## What Changed

### Modified Files

1. **`data_export/trajectory_control.py`**
   - Added `load_colmap_camera_intrinsics()` function to parse `cameras.txt`
   - Added `get_camera_intrinsics_from_colmap()` function to extract focal length and image dimensions
   - Supports PINHOLE camera model with parameters: fx, fy, cx, cy

2. **`data_export/run_export_fbx_colmap.py`**
   - Reads camera intrinsics from `cameras.txt` in the COLMAP directory
   - Passes focal length (in pixels) and image dimensions to Blender script via command-line arguments
   - Prints camera intrinsics information during export

3. **`data_export/poses_to_fbx_blender.py`**
   - Added command-line arguments: `--focal-length-px`, `--image-width`, `--image-height`
   - Updated `_create_camera()` to accept and set focal length in millimeters
   - Converts focal length from pixels to millimeters using the formula:
     ```
     focal_mm = (focal_px × sensor_width_mm) / image_width_px
     ```
   - Default sensor width: 36mm (full frame equivalent)

## How It Works

### Focal Length and Sensor Dimension Conversion

COLMAP stores focal length in **pixels**, while Blender (and UE5) use **millimeters**. The conversion assumes a standard 36mm sensor width (full frame):

```
focal_length_mm = (focal_length_pixels × 36mm) / image_width_pixels
aspect_ratio = image_width / image_height
sensor_height_mm = sensor_width_mm / aspect_ratio
```

**Example from `marie3_colmap/cameras.txt`:**
```
1 PINHOLE 584 328 489.998810 489.353882 295.500000 166.000000
```
- Image size: 584×328 pixels
- Aspect ratio: 584/328 = 1.78
- Focal length: fx=489.998810 pixels
- Converted focal length: (489.998810 × 36) / 584 ≈ **30.2mm**
- Sensor width: **36mm**
- Sensor height: 36 / 1.78 ≈ **20.22mm**

This ensures correct FOV and aspect ratio matching between COLMAP and UE5.

### Pipeline Flow

```
COLMAP cameras.txt
    ↓ (read by trajectory_control.py)
Camera Intrinsics (fx, fy, cx, cy in pixels)
    ↓ (passed by run_export_fbx_colmap.py)
Blender Script (poses_to_fbx_blender.py)
    ↓ (convert pixels → mm, set camera.data.lens)
FBX File with Correct Focal Length
    ↓
Unreal Engine 5 (focal length automatically applied)
```

## Usage

### Basic Command (Automatic Intrinsics)

```bash
python -m data_export.run_export_fbx_colmap marie3_colmap marie3_camera.fbx --scale 0.01 --swap-yz --reverse --fps 30
```

The script will:
1. Read `marie3_colmap/cameras.txt`
2. Extract focal length (489.998810 px)
3. Convert to millimeters (~30.2mm)
4. Set focal length in Blender camera
5. Export to FBX with constant focal length

### Expected Output

```
Wrote 306 poses to C:\Users\...\Temp\colmap_poses_xyz.csv
Found camera intrinsics: PINHOLE 584x328
  Focal length: fx=489.998810, fy=489.353882
Running Blender: ... -- poses.csv marie3_camera.fbx 30
Camera intrinsics: focal_length=489.998810px, image_size=584x328
Converted to Blender: focal_length=30.21mm, sensor_width=36.00mm, sensor_height=20.22mm
Aspect ratio: 1.7805
Exported 306 camera keyframes to marie3_camera.fbx
```

### Manual Override (If cameras.txt Missing)

If `cameras.txt` is not found, the script falls back to Blender's default focal length (50mm) and prints a warning:

```
Warning: cameras.txt not found, using default focal length in Blender
```

## Verifying in Unreal Engine 5

After importing the FBX:

1. **Check the Sequencer:**
   - Open your Level Sequence
   - Expand the CineCameraActor tracks
   - Verify there is **NO** "Current Focal Length" animated track
   - If present, the focal length is constant (not keyframed)

2. **Check Camera Details:**
   - Select the CineCameraActor
   - In Details panel → Current Camera Settings
   - "Current Focal Length" should show ~30.2mm (for marie3 data)
   - "Filmback Settings" → Sensor Width: 36mm, Sensor Height: 20.22mm
   - These values should be constant across all frames
   - Aspect ratio should match your COLMAP image dimensions (1.78 for 584×328)

## Troubleshooting

### Issue: Focal length still animating in UE5

**Cause:** Blender might be exporting focal length as animated property

**Solution:** In UE5 Sequencer, delete the "Current Focal Length" track:
1. Right-click the track → Delete Track
2. Set desired focal length in camera Details panel

### Issue: Incorrect focal length value

**Cause:** Sensor width assumption (36mm) might not match your camera

**Solution:** Modify `poses_to_fbx_blender.py` line with `sensor_width_mm = 36.0` to match your actual sensor width

### Issue: cameras.txt not found

**Cause:** COLMAP directory structure issue

**Solution:** Ensure `cameras.txt` is in the same directory as `images.txt`:
```
marie3_colmap/
  ├── cameras.txt    ← Must exist
  ├── images.txt
  └── points3D.txt
```

## Technical Details

### COLMAP PINHOLE Model

```
CAMERA_ID MODEL WIDTH HEIGHT PARAMS[]
```

For PINHOLE model, PARAMS = [fx, fy, cx, cy]:
- **fx, fy**: Focal length in pixels (X and Y directions)
- **cx, cy**: Principal point (optical center) in pixels

### Blender Camera Properties

- `cam.data.lens`: Focal length in millimeters
- `cam.data.sensor_width`: Sensor width in millimeters (default: 36mm)
- `cam.data.sensor_height`: Sensor height in millimeters (calculated from aspect ratio)
- `cam.data.sensor_fit`: 'AUTO' when both dimensions specified, 'HORIZONTAL' otherwise

### FBX Export Settings

The focal length is baked into the FBX with these settings:
- `axis_forward="X"`, `axis_up="Z"` (UE5 coordinate system)
- `bake_anim=True` (bake animation)
- Focal length set as constant (not keyframed)

## Future Enhancements

Possible improvements:
1. Support for other COLMAP camera models (RADIAL, OPENCV, etc.)
2. Export distortion parameters to UE5
3. Custom sensor width via command-line argument
4. Support for per-frame varying focal length (zoom lenses)

## References

- COLMAP camera models: https://colmap.github.io/cameras.html
- Blender camera properties: https://docs.blender.org/api/current/bpy.types.Camera.html
- UE5 CineCameraActor: https://docs.unrealengine.com/5.0/en-US/cinematics-and-movie-making-in-unreal-engine/
