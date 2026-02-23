"""
RunPod serverless handler: video (URL or base64) -> MegaSaM pipeline -> same results as complete_workflow_cmd.txt.

Input (event["input"]):
  - video_url: str (optional) – URL of MP4 to download
  - video_base64: str (optional) – base64-encoded MP4
  - fps: float (optional) – target FPS for frame extraction (default 30, as in workflow)

Output:
  - trajectory_npz_path: outputs/upload_frames_droid.npz
  - cvd_npz_path: outputs/upload_frames_sgd_cvd_hr.npz
  - colmap_*: COLMAP text model (cameras.txt, images.txt, points3D.txt; no images/ folder)
  - error: str (if pipeline failed)

Pipeline (strictly replicates complete_workflow_cmd.txt):
  1. ./video_preprocess/run_extract_frames.sh <video> --fps <fps>   -> DAVIS/upload_frames
  2. ./mono_depth_scripts/run_mono-depth_demo.sh
  3. ./tools/evaluate_demo.sh                                        -> outputs/upload_frames_droid.npz
  4. ./cvd_opt/cvd_opt_demo.sh                                       -> outputs/upload_frames_sgd_cvd_hr.npz
  5. python -m data_export.export_colmap ... -o ... --no-images      -> cameras.txt, images.txt, points3D.txt
"""

import base64
import os
import subprocess
import sys
import tempfile
from pathlib import Path

# RunPod SDK
import runpod

INSTALL_DIR = Path("/app/mega-sam")
SCENE_NAME = "upload_frames"
CKPT_MEGASAM = INSTALL_DIR / "checkpoints" / "megasam_final.pth"


def _run(cmd, cwd=None, env=None):
    cwd = cwd or str(INSTALL_DIR)
    env = env or os.environ
    pythonpath = f"{INSTALL_DIR}:{INSTALL_DIR}/UniDepth:{INSTALL_DIR}/Depth-Anything"
    env = {**env, "PYTHONPATH": pythonpath, "CUDA_VISIBLE_DEVICES": "0"}
    return subprocess.run(
        cmd,
        cwd=cwd,
        env=env,
        capture_output=True,
        text=True,
        timeout=3600,
    )


def _ensure_video_file(input_data):
    """Return path to video file from input (video_url or video_base64)."""
    video_path = input_data.get("video_path")
    if video_path and os.path.isfile(video_path):
        return video_path

    video_url = input_data.get("video_url")
    if video_url:
        out = tempfile.NamedTemporaryFile(suffix=".mp4", delete=False)
        out.close()
        r = subprocess.run(
            ["wget", "-q", "-O", out.name, video_url],
            capture_output=True,
            text=True,
            timeout=600,
        )
        if r.returncode != 0:
            raise RuntimeError(f"Failed to download video: {r.stderr}")
        return out.name

    video_b64 = input_data.get("video_base64")
    if video_b64:
        out = tempfile.NamedTemporaryFile(suffix=".mp4", delete=False)
        out.close()
        with open(out.name, "wb") as f:
            f.write(base64.b64decode(video_b64))
        return out.name

    raise ValueError("Provide one of: video_url, video_base64, or video_path (existing file)")


def run_pipeline(video_path: str, fps: float = 30.0):
    """Run full MegaSaM pipeline; replicates complete_workflow_cmd.txt step-by-step."""
    if not CKPT_MEGASAM.exists():
        raise FileNotFoundError(
            f"Camera tracking checkpoint missing: {CKPT_MEGASAM}. "
            "Add checkpoints/megasam_final.pth to the image or use RunPod model cache."
        )

    os.chdir(INSTALL_DIR)
    frames_dir = INSTALL_DIR / "DAVIS" / SCENE_NAME
    frames_dir.mkdir(parents=True, exist_ok=True)
    # Clear previous frames
    for f in frames_dir.glob("*"):
        f.unlink()

    # 1) Extract frames (run_extract_frames.sh)
    r = _run(["bash", "video_preprocess/run_extract_frames.sh", video_path, "--fps", str(fps)])
    if r.returncode != 0:
        raise RuntimeError(f"run_extract_frames.sh failed: {r.stderr or r.stdout}")

    # 2) Mono-depth (run_mono-depth_demo.sh)
    r = _run(["bash", "mono_depth_scripts/run_mono-depth_demo.sh"])
    if r.returncode != 0:
        raise RuntimeError(f"run_mono-depth_demo.sh failed: {r.stderr or r.stdout}")

    # 3) Camera tracking (evaluate_demo.sh)
    r = _run(["bash", "tools/evaluate_demo.sh"])
    if r.returncode != 0:
        raise RuntimeError(f"evaluate_demo.sh failed: {r.stderr or r.stdout}")

    # 4) CVD opt (cvd_opt_demo.sh)
    r = _run(["bash", "cvd_opt/cvd_opt_demo.sh"])
    if r.returncode != 0:
        raise RuntimeError(f"cvd_opt_demo.sh failed: {r.stderr or r.stdout}")

    # 5) Output paths
    droid_npz = INSTALL_DIR / "outputs" / f"{SCENE_NAME}_droid.npz"
    cvd_npz = INSTALL_DIR / "outputs" / f"{SCENE_NAME}_sgd_cvd_hr.npz"

    result = {
        "trajectory_npz_path": str(droid_npz) if droid_npz.exists() else None,
        "cvd_npz_path": str(cvd_npz) if cvd_npz.exists() else None,
    }

    # 6) Export npz to COLMAP format (three txt files only; no image frame folder)
    colmap_dir = INSTALL_DIR / "outputs" / f"colmap_{SCENE_NAME}"
    r = _run([
        sys.executable, "-m", "data_export.export_colmap",
        str(droid_npz), "-o", str(colmap_dir), "--no-images",
    ])
    if r.returncode == 0:
        cameras_txt = colmap_dir / "cameras.txt"
        images_txt = colmap_dir / "images.txt"
        points3d_txt = colmap_dir / "points3D.txt"
        result["colmap_cameras_txt_path"] = str(cameras_txt) if cameras_txt.exists() else None
        result["colmap_images_txt_path"] = str(images_txt) if images_txt.exists() else None
        result["colmap_points3d_txt_path"] = str(points3d_txt) if points3d_txt.exists() else None
        if images_txt.exists():
            result["colmap_images_txt_content"] = images_txt.read_text()
    else:
        result["colmap_export_error"] = r.stderr or r.stdout or "export_colmap failed"

    return result


def handler(event):
    """RunPod serverless handler entry."""
    try:
        input_data = event.get("input", {})
        fps = float(input_data.get("fps", 30.0))
        video_path = _ensure_video_file(input_data)
        try:
            out = run_pipeline(video_path, fps=fps)
            return out
        finally:
            if video_path.startswith(tempfile.gettempdir()):
                try:
                    os.unlink(video_path)
                except Exception:
                    pass
    except Exception as e:
        return {"error": str(e)}


if __name__ == "__main__":
    runpod.serverless.start({"handler": handler})
