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

"""Export camera pose CSV to FBX for Unreal Engine 5 (run inside Blender).

Usage (from repo root, with Blender on PATH):
  blender --background --python data_export/poses_to_fbx_blender.py -- \\
    plaza_csv/poses.csv plaza_camera.fbx 30

Or use run_export_fbx.py which finds Blender and invokes this script.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

# Add repo root so we can import data_export.colmap_to_ue when run by Blender
_SCRIPT_DIR = Path(__file__).resolve().parent
_REPO_ROOT = _SCRIPT_DIR.parent
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))

import numpy as np

# bpy is only available when this script is run inside Blender
try:
    import bpy
except ImportError:
    print("This script must be run inside Blender: blender --background --python ...")
    sys.exit(1)

from data_export.colmap_to_ue import (
    colmap_pose_to_ue,
    load_poses_csv,
    rotation_matrix_to_euler_xyz_rad,
)


def _parse_args() -> argparse.Namespace:
    # Blender passes its own argv; our args come after "--"
    if "--" in sys.argv:
        argv = sys.argv[sys.argv.index("--") + 1:]
    else:
        argv = []
    parser = argparse.ArgumentParser(
        description="Export poses CSV to FBX camera animation for UE5 (run inside Blender)."
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
        "fps",
        type=float,
        nargs="?",
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
    return parser.parse_args(argv)


def _clear_scene() -> None:
    """Remove default objects so we start clean."""
    bpy.ops.object.select_all(action="SELECT")
    bpy.ops.object.delete(use_global=False)


# Blender camera default: local -Y = forward. UE export: we want that to be UE +X (forward).
# IMPORTANT: The FBX exporter with axis_forward="X", axis_up="Z" handles the coordinate conversion.
# We need to set the camera orientation in Blender's world space such that when exported,
# it matches the UE5 orientation.
# 
# Blender world: X=right, Y=forward, Z=up
# UE5 world: X=forward, Y=right, Z=up
# So: Blender Y = UE5 X, Blender X = UE5 Y, Blender Z = UE5 Z
_UE_TO_BLENDER_WORLD = np.array([
    [0.0, 1.0, 0.0],   # Blender X (right) = UE5 Y (right)
    [1.0, 0.0, 0.0],   # Blender Y (forward) = UE5 X (forward)
    [0.0, 0.0, 1.0],   # Blender Z (up) = UE5 Z (up)
], dtype=np.float64)


def _create_camera(name: str = "Camera") -> bpy.types.Object:
    """Create a camera (default Blender orientation: looks along -Y)."""
    bpy.ops.object.camera_add()
    cam = bpy.context.active_object
    cam.name = name
    return cam


def _set_keyframes(
    cam: bpy.types.Object,
    poses: list[tuple[int, np.ndarray, np.ndarray]],
    fps: float,
    scale_to_cm: bool,
) -> None:
    """Set camera location and rotation keyframes from COLMAP poses."""
    scene = bpy.context.scene
    scene.render.fps = int(round(fps))
    for frame_id, qvec, tvec in poses:
        frame = int(frame_id)
        pos_ue, R_ue = colmap_pose_to_ue(qvec, tvec, scale_to_cm=scale_to_cm)
        
        # Transform from UE5 world coordinates to Blender world coordinates
        # UE5: X=forward, Y=right, Z=up
        # Blender: X=right, Y=forward, Z=up
        # Position: simple axis swap
        pos_blender = np.array([pos_ue[1], pos_ue[0], pos_ue[2]], dtype=np.float64)
        
        # Rotation: similarity transformation for coordinate change
        R_blender = _UE_TO_BLENDER_WORLD @ R_ue @ _UE_TO_BLENDER_WORLD.T
        
        # CRITICAL: Blender camera convention
        # R_ue is camera-to-world where columns are [forward | right | up] in UE5
        # After coordinate transform, R_blender columns are [right | forward | up] in Blender world
        # BUT: Blender camera's LOCAL axes are [right | up | backward]
        # Blender camera looks along LOCAL -Z, which is the NEGATIVE of the 3rd column
        #
        # We need R_blender where:
        #   Column 0 = camera's right in world
        #   Column 1 = camera's up in world  
        #   Column 2 = camera's BACKWARD in world (camera looks along -column2)
        #
        # Current R_blender = [right | forward | up]
        # We need:           [right | up | -forward]
        #
        # Solution: Swap columns 1 and 2, and negate the new column 2
        R_blender_corrected = np.column_stack([
            R_blender[:, 0],   # right stays
            R_blender[:, 2],   # up (was column 2)
            -R_blender[:, 1],  # backward = -forward (was column 1)
        ])
        R_blender = R_blender_corrected
        
        euler_rad = rotation_matrix_to_euler_xyz_rad(R_blender)
        # Timeline frame: 1-based in Blender UI, we use frame_id + 1 for clarity
        scene.frame_set(frame + 1)
        cam.location = (float(pos_blender[0]), float(pos_blender[1]), float(pos_blender[2]))
        cam.rotation_euler = (float(euler_rad[0]), float(euler_rad[1]), float(euler_rad[2]))
        cam.keyframe_insert(data_path="location", frame=frame + 1)
        cam.keyframe_insert(data_path="rotation_euler", frame=frame + 1)
    # Set scene frame range
    scene.frame_start = 1
    scene.frame_end = len(poses) + 1


def _export_fbx(output_path: Path) -> None:
    """Export scene to FBX with Unreal-friendly axes (Forward X, Up Z)."""
    output_path = Path(output_path).resolve()
    output_path.parent.mkdir(parents=True, exist_ok=True)
    bpy.ops.export_scene.fbx(
        filepath=str(output_path),
        use_selection=False,
        global_scale=1.0,
        apply_unit_scale=True,
        apply_scale_options="FBX_SCALE_NONE",
        axis_forward="X",
        axis_up="Z",
        bake_anim=True,
        bake_anim_use_all_bones=False,
        bake_anim_use_nla_strips=False,
        bake_anim_use_all_actions=False,
        bake_anim_force_startend_keying=True,
        bake_anim_simplify_factor=0.0,
        path_mode="AUTO",
        embed_textures=False,
    )


def main() -> int:
    args = _parse_args()
    poses_csv = Path(args.poses_csv).resolve()
    output_fbx = Path(args.output_fbx).resolve()

    if not poses_csv.is_file():
        print(f"Error: poses CSV not found: {poses_csv}")
        return 1

    poses = list(load_poses_csv(poses_csv))
    if not poses:
        print("Error: no poses in CSV")
        return 1

    _clear_scene()
    cam = _create_camera(name="CineCameraActor")
    _set_keyframes(cam, poses, args.fps, args.scale_to_cm)
    _export_fbx(output_fbx)

    print(f"Exported {len(poses)} camera keyframes to {output_fbx}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
