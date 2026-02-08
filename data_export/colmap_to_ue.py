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

"""Convert COLMAP camera poses (world-to-camera) to Unreal Engine 5 coordinates.

COLMAP: right-handed, X right, Y down, Z forward (into scene).
UE5:    left-handed, X forward, Y right, Z up.

Poses are converted to UE5 camera-to-world: position and rotation matrix.
"""

from __future__ import annotations

import csv
from pathlib import Path
from typing import Iterator

import numpy as np


# COLMAP → UE5 axis remap: UE forward = Colmap Z, UE right = Colmap X, UE up = -Colmap Y
# So P_ue = M @ P_colmap with rows = UE X,Y,Z in Colmap components:
_COLMAP_TO_UE_AXIS = np.array([
    [0.0, 0.0, 1.0],   # UE X (forward)  = Colmap Z
    [1.0, 0.0, 0.0],   # UE Y (right)    = Colmap X
    [0.0, -1.0, 0.0],  # UE Z (up)        = -Colmap Y
], dtype=np.float64)


def qvec2rotmat(qvec: np.ndarray) -> np.ndarray:
    """Quaternion (qw, qx, qy, qz) to 3x3 rotation matrix (COLMAP convention)."""
    qw, qx, qy, qz = float(qvec[0]), float(qvec[1]), float(qvec[2]), float(qvec[3])
    return np.array([
        [
            1 - 2 * qy * qy - 2 * qz * qz,
            2 * qx * qy - 2 * qw * qz,
            2 * qz * qx + 2 * qw * qy,
        ],
        [
            2 * qx * qy + 2 * qw * qz,
            1 - 2 * qx * qx - 2 * qz * qz,
            2 * qy * qz - 2 * qw * qx,
        ],
        [
            2 * qz * qx - 2 * qw * qy,
            2 * qy * qz + 2 * qw * qx,
            1 - 2 * qx * qx - 2 * qy * qy,
        ],
    ], dtype=np.float64)


def colmap_pose_to_ue(
    qvec: np.ndarray,
    tvec: np.ndarray,
    scale_to_cm: bool = True,
) -> tuple[np.ndarray, np.ndarray]:
    """Convert one COLMAP pose (world-to-camera) to UE5 camera-to-world.

    Args:
        qvec: Quaternion (qw, qx, qy, qz) world-to-camera rotation.
        tvec: Translation (tx, ty, tz) world-to-camera.
        scale_to_cm: If True, scale position to centimeters (UE default).

    Returns:
        position_ue: (3,) camera position in UE5 world (X forward, Y right, Z up).
        rotation_ue: (3, 3) camera-to-world rotation matrix in UE5.
    """
    R_w2c = qvec2rotmat(qvec)
    t_w2c = np.asarray(tvec, dtype=np.float64).reshape(3)
    # Camera center in world (COLMAP): C = -R^T @ t
    camera_center_colmap = -R_w2c.T @ t_w2c
    # Camera-to-world rotation: R_c2w = R^T
    R_c2w_colmap = R_w2c.T
    # Apply axis remap to UE5
    position_ue = _COLMAP_TO_UE_AXIS @ camera_center_colmap
    rotation_ue = _COLMAP_TO_UE_AXIS @ R_c2w_colmap
    if scale_to_cm:
        position_ue = position_ue * 100.0
    return position_ue, rotation_ue


def rotation_matrix_to_euler_xyz_rad(R: np.ndarray) -> np.ndarray:
    """Convert 3x3 rotation matrix to Euler XYZ (radians). Used for Blender."""
    sy = np.sqrt(R[0, 0] ** 2 + R[1, 0] ** 2)
    if sy > 1e-6:
        x = np.arctan2(R[2, 1], R[2, 2])
        y = np.arctan2(-R[2, 0], sy)
        z = np.arctan2(R[1, 0], R[0, 0])
    else:
        x = np.arctan2(-R[1, 2], R[1, 1])
        y = np.arctan2(-R[2, 0], sy)
        z = 0.0
    return np.array([x, y, z], dtype=np.float64)


def load_poses_csv(csv_path: Path) -> Iterator[tuple[int, np.ndarray, np.ndarray]]:
    """Load poses from a CSV with columns: frame_id, qw, qx, qy, qz, tx, ty, tz.

    Yields:
        (frame_id, qvec, tvec) for each row.
    """
    csv_path = Path(csv_path)
    with open(csv_path, newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            frame_id = int(row["frame_id"])
            qvec = np.array([
                float(row["qw"]), float(row["qx"]), float(row["qy"]), float(row["qz"])
            ], dtype=np.float64)
            tvec = np.array([
                float(row["tx"]), float(row["ty"]), float(row["tz"])
            ], dtype=np.float64)
            yield frame_id, qvec, tvec


def export_ue_poses_csv(
    poses_csv_path: Path,
    output_csv_path: Path,
    scale_to_cm: bool = True,
) -> None:
    """Convert COLMAP-style poses CSV to UE5-style CSV (frame_id, px, py, pz, roll_deg, pitch_deg, yaw_deg).

    Useful for verification or for tools that read UE poses directly.
    Euler angles are in degrees, XYZ order (roll=X, pitch=Y, yaw=Z) in UE convention.
    """
    with open(output_csv_path, "w", newline="", encoding="utf-8") as out:
        writer = csv.writer(out)
        writer.writerow(["frame_id", "px", "py", "pz", "roll_deg", "pitch_deg", "yaw_deg"])
        for frame_id, qvec, tvec in load_poses_csv(poses_csv_path):
            pos_ue, R_ue = colmap_pose_to_ue(qvec, tvec, scale_to_cm=scale_to_cm)
            euler_rad = rotation_matrix_to_euler_xyz_rad(R_ue)
            euler_deg = np.degrees(euler_rad)
            writer.writerow([
                frame_id,
                f"{pos_ue[0]:.6f}", f"{pos_ue[1]:.6f}", f"{pos_ue[2]:.6f}",
                f"{euler_deg[0]:.6f}", f"{euler_deg[1]:.6f}", f"{euler_deg[2]:.6f}",
            ])
