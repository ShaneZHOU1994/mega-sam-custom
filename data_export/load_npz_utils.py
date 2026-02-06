# Copyright 2025 DeepMind Technologies Limited
#
# Utilities to load .npz outputs from mono-depth (UniDepth) and camera tracking (evaluate_demo).
# See README in this folder for formats and usage.

from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Iterator

import numpy as np


# -----------------------------------------------------------------------------
# Format detection and loaders
# -----------------------------------------------------------------------------

def is_unidepth_npz(data: dict[str, Any]) -> bool:
    """UniDepth per-frame .npz: keys 'depth' (H,W), 'fov' (scalar)."""
    return "depth" in data and "fov" in data and "cam_c2w" not in data


def is_droid_npz(data: dict[str, Any]) -> bool:
    """Camera tracking *_droid.npz: keys 'images', 'depths', 'intrinsic', 'cam_c2w'."""
    return all(
        k in data
        for k in ("images", "depths", "intrinsic", "cam_c2w")
    )


def load_npz(path: str | Path) -> np.lib.npyio.NpzFile:
    """Load a single .npz file (lazy arrays)."""
    return np.load(path, allow_pickle=False)


def infer_npz_format(path: str | Path) -> str | None:
    """Infer format from file: 'unidepth' | 'droid' | None."""
    with load_npz(path) as z:
        keys = set(z.files)
    if "depth" in keys and "fov" in keys and "cam_c2w" not in keys:
        return "unidepth"
    if all(k in keys for k in ("images", "depths", "intrinsic", "cam_c2w")):
        return "droid"
    return None


# -----------------------------------------------------------------------------
# UniDepth (per-frame) data
# -----------------------------------------------------------------------------

@dataclass
class UniDepthFrame:
    """Single frame from UniDepth output: depth map + fov."""
    depth: np.ndarray   # (H, W) float32
    fov: float         # degrees
    frame_id: str      # e.g. filename stem "00000"


def load_unidepth_npz(path: str | Path) -> UniDepthFrame:
    """Load one UniDepth per-frame .npz."""
    path = Path(path)
    with load_npz(path) as z:
        depth = np.asarray(z["depth"], dtype=np.float32)
        fov = float(np.asarray(z["fov"]).flat[0])
    return UniDepthFrame(depth=depth, fov=fov, frame_id=path.stem)


def load_unidepth_scene(dir_path: str | Path) -> list[UniDepthFrame]:
    """Load all .npz in a directory (one scene from UniDepth/outputs/<scene>/)."""
    dir_path = Path(dir_path)
    frames = []
    for p in sorted(dir_path.glob("*.npz")):
        frames.append(load_unidepth_npz(p))
    return frames


# -----------------------------------------------------------------------------
# DROID / camera-tracking (single .npz per scene) data
# -----------------------------------------------------------------------------

@dataclass
class DroidScene:
    """Single scene from evaluate_demo: outputs/<scene>_droid.npz."""
    images: np.ndarray    # (N, H, W, 3) uint8 RGB
    depths: np.ndarray    # (N, H, W) float32
    intrinsic: np.ndarray # (3, 3) K
    cam_c2w: np.ndarray   # (N, 4, 4) camera-to-world
    scene_name: str       # e.g. "swing", "breakdance-flare"


def load_droid_npz(path: str | Path, scene_name: str | None = None) -> DroidScene:
    """Load one *_droid.npz file."""
    path = Path(path)
    if scene_name is None:
        scene_name = path.stem.replace("_droid", "")
    with load_npz(path) as z:
        images = np.asarray(z["images"], dtype=np.uint8)
        depths = np.asarray(z["depths"], dtype=np.float32)
        intrinsic = np.asarray(z["intrinsic"], dtype=np.float64)
        cam_c2w = np.asarray(z["cam_c2w"], dtype=np.float64)
    return DroidScene(
        images=images,
        depths=depths,
        intrinsic=intrinsic,
        cam_c2w=cam_c2w,
        scene_name=scene_name,
    )


def iter_droid_npz(dir_path: str | Path) -> Iterator[tuple[str, DroidScene]]:
    """Yield (scene_name, DroidScene) for every *_droid.npz in directory."""
    dir_path = Path(dir_path)
    for p in sorted(dir_path.glob("*_droid.npz")):
        scene_name = p.stem.replace("_droid", "")
        yield scene_name, load_droid_npz(p, scene_name=scene_name)


# -----------------------------------------------------------------------------
# Generic loader (auto-detect)
# -----------------------------------------------------------------------------

def load_any_npz(path: str | Path):
    """Load .npz and return either UniDepthFrame or DroidScene. Raises if unknown."""
    fmt = infer_npz_format(path)
    if fmt == "unidepth":
        return load_unidepth_npz(path)
    if fmt == "droid":
        return load_droid_npz(path)
    raise ValueError(
        f"Unknown .npz format: {path}. Expected UniDepth (depth, fov) or DROID (images, depths, intrinsic, cam_c2w)."
    )
