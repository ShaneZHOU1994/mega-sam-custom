# Copyright 2025 DeepMind Technologies Limited
#
# Export DROID *_droid.npz to COLMAP-importable format:
# - cameras.txt, images.txt (text format)
# - Optional: write RGB frames to images/ so COLMAP can use them
#
# Only camera tracking outputs (*_droid.npz) contain poses; UniDepth .npz do not.
# Use this script on outputs from tools/evaluate_demo.sh (e.g. outputs/swing_droid.npz).

from __future__ import annotations

import argparse
import sys
from pathlib import Path

import numpy as np

_SCRIPT_DIR = Path(__file__).resolve().parent
_REPO_ROOT = _SCRIPT_DIR.parent
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))

from data_export.load_npz_utils import load_droid_npz


def rotmat2qvec(R: np.ndarray) -> np.ndarray:
    """Rotation matrix to quaternion (COLMAP: qw, qx, qy, qz)."""
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


def write_colmap_cameras(
    path: Path,
    camera_id: int,
    model: str,
    width: int,
    height: int,
    fx: float,
    fy: float,
    cx: float,
    cy: float,
) -> None:
    """Write COLMAP cameras.txt (one camera). PINHOLE has 4 params: fx, fy, cx, cy."""
    with open(path, "w") as f:
        f.write("# Camera list with one line of data per camera:\n")
        f.write("#   CAMERA_ID, MODEL, WIDTH, HEIGHT, PARAMS[]\n")
        f.write("# Number of cameras: 1\n")
        f.write(f"{camera_id} {model} {width} {height} {fx:.6f} {fy:.6f} {cx:.6f} {cy:.6f}\n")


def write_colmap_images(
    path: Path,
    image_names: list[str],
    qvecs: list[np.ndarray],
    tvecs: list[np.ndarray],
    camera_id: int = 1,
) -> None:
    """
    Write COLMAP images.txt.
    Each image: line1 = IMAGE_ID QW QX QY QZ TX TY TZ CAMERA_ID NAME
                line2 = 2D points (x y point3D_id repeated); use empty line if no points.
    COLMAP uses world-to-camera: R, t so that x_cam = R @ x_world + t.
    """
    with open(path, "w") as f:
        f.write("# Image list with two lines of data per image:\n")
        f.write("#   IMAGE_ID, QW, QX, QY, QZ, TX, TY, TZ, CAMERA_ID, NAME\n")
        f.write("#   POINTS2D[] as (X, Y, POINT3D_ID)\n")
        f.write(f"# Number of images: {len(image_names)}\n")
        for i, (name, qvec, tvec) in enumerate(zip(image_names, qvecs, tvecs)):
            image_id = i + 1
            f.write(
                f"{image_id} {qvec[0]:.8f} {qvec[1]:.8f} {qvec[2]:.8f} {qvec[3]:.8f} "
                f"{tvec[0]:.8f} {tvec[1]:.8f} {tvec[2]:.8f} {camera_id} {name}\n"
            )
            # No 2D observations: empty second line (COLMAP allows this)
            f.write("\n")


def write_images_to_dir(images: np.ndarray, out_dir: Path, name_fmt: str = "frame_{:06d}.jpg") -> list[str]:
    """Write (N,H,W,3) uint8 RGB to disk. Returns list of image names."""
    try:
        import cv2
    except ImportError:
        raise ImportError("OpenCV (cv2) is required to write images. Install with: pip install opencv-python")
    out_dir.mkdir(parents=True, exist_ok=True)
    names = []
    for i in range(images.shape[0]):
        name = name_fmt.format(i)
        p = out_dir / name
        # COLMAP expects BGR for JPEG; our arrays are RGB
        bgr = images[i][:, :, ::-1].copy()
        cv2.imwrite(str(p), bgr)
        names.append(name)
    return names


def export_droid_to_colmap(
    npz_path: Path,
    out_dir: Path,
    write_frames: bool = True,
    image_format: str = "jpg",
) -> tuple[Path, Path, list[Path]]:
    """
    Export one *_droid.npz to COLMAP sparse model (cameras.txt, images.txt).
    Optionally write RGB frames to out_dir/images/.
    Returns (cameras_path, images_path, list of written paths).
    """
    out_dir = Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)

    scene = load_droid_npz(npz_path)
    K = scene.intrinsic
    cam_c2w = scene.cam_c2w
    n = cam_c2w.shape[0]
    h, w = scene.images.shape[1], scene.images.shape[2]

    # Camera: PINHOLE with fx, fy, cx, cy
    cameras_path = out_dir / "cameras.txt"
    write_colmap_cameras(
        cameras_path,
        camera_id=1,
        model="PINHOLE",
        width=w,
        height=h,
        fx=float(K[0, 0]),
        fy=float(K[1, 1]),
        cx=float(K[0, 2]),
        cy=float(K[1, 2]),
    )

    # Image names: either from written files or synthetic
    if write_frames:
        images_subdir = out_dir / "images"
        name_fmt = f"frame_{{:06d}}.{image_format}"
        image_names = write_images_to_dir(scene.images, images_subdir, name_fmt=name_fmt)
    else:
        image_names = [f"frame_{i:06d}.jpg" for i in range(n)]

    # World-to-camera pose per frame
    qvecs = []
    tvecs = []
    for i in range(n):
        w2c = np.linalg.inv(cam_c2w[i])
        R = w2c[:3, :3]
        t = w2c[:3, 3]
        qvecs.append(rotmat2qvec(R))
        tvecs.append(t)

    images_path = out_dir / "images.txt"
    write_colmap_images(images_path, image_names, qvecs, tvecs, camera_id=1)

    # Empty points3D.txt so COLMAP can load the model (no 3D points from DROID)
    points3d_path = out_dir / "points3D.txt"
    with open(points3d_path, "w") as f:
        f.write("# 3D point list with one line of data per point:\n")
        f.write("#   POINT3D_ID, X, Y, Z, R, G, B, ERROR, TRACK[] as (IMAGE_ID, POINT2D_IDX)\n")
        f.write("# Number of points: 0\n")

    written = [cameras_path, images_path, points3d_path]
    if write_frames:
        written.extend([out_dir / "images" / name for name in image_names])
    return cameras_path, images_path, written


def main():
    parser = argparse.ArgumentParser(
        description="Export DROID *_droid.npz to COLMAP cameras.txt + images.txt (and optionally write RGB frames).",
        formatter_class=argparse.ArgumentDefaultsHelpFormatter,
    )
    parser.add_argument(
        "input",
        type=Path,
        help="Path to a *_droid.npz file or directory containing *_droid.npz (e.g. outputs/).",
    )
    parser.add_argument(
        "-o", "--output",
        type=Path,
        default=None,
        help="Output directory for COLMAP model (cameras.txt, images.txt) and optional images/.",
    )
    parser.add_argument(
        "--no-images",
        action="store_true",
        help="Do not write RGB frames to images/ (only cameras.txt and images.txt).",
    )
    parser.add_argument(
        "--image-format",
        choices=("jpg", "png"),
        default="jpg",
        help="Format for written frames.",
    )
    args = parser.parse_args()

    input_path = args.input.resolve()
    if not input_path.exists():
        print(f"Error: input does not exist: {input_path}", file=sys.stderr)
        sys.exit(1)

    if input_path.is_file():
        npz_list = [input_path]
        out_base = args.output or (input_path.parent / f"{input_path.stem.replace('_droid', '')}_colmap")
    else:
        npz_list = sorted(input_path.glob("*_droid.npz"))
        if not npz_list:
            print("Error: no *_droid.npz files found in directory.", file=sys.stderr)
            sys.exit(1)
        out_base = args.output or (input_path / "colmap_export")

    for npz_path in npz_list:
        scene_name = npz_path.stem.replace("_droid", "")
        out_dir = Path(out_base) / scene_name if len(npz_list) > 1 else Path(out_base)
        try:
            export_droid_to_colmap(
                npz_path,
                out_dir,
                write_frames=not args.no_images,
                image_format=args.image_format,
            )
        except Exception as e:
            print(f"Error exporting {npz_path}: {e}", file=sys.stderr)
            sys.exit(1)
        print("COLMAP export written to:", out_dir)
        print("  cameras.txt, images.txt")
        if not args.no_images:
            print("  images/ (RGB frames)")
    print("\nTo use in COLMAP: set sparse model path to the output directory (text format).")


if __name__ == "__main__":
    main()
