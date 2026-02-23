# RunPod Serverless Handler for MegaSaM

- **handler.py** – RunPod serverless entry: receives video (URL or base64), runs the full MegaSaM pipeline (extract frames → mono-depth → camera tracking → CVD), returns trajectory/pose paths and optional CSV.
- **entry_point.sh** – Sets `WORKDIR` and `PYTHONPATH` then runs `handler.py`. The Dockerfile `CMD` runs this script so the container starts the RunPod worker.

## Input (`event.input`)

- `video_url` (optional): URL of an MP4 file.
- `video_base64` (optional): base64-encoded MP4.
- `fps` (optional): target FPS for frame extraction (default `6`).

## Output

- `trajectory_npz_path`: path to `upload_frames_droid.npz` (camera tracking).
- `cvd_npz_path`: path to `upload_frames_sgd_cvd_hr.npz` (consistent depth).
- `poses_csv_path` / `poses_csv_content`: if CSV export runs.
- `error`: message if the pipeline failed.

## Checkpoint

Camera tracking requires **checkpoints/megasam_final.pth**. The Dockerfile does not download it. Either:

1. Build with `--build-arg MEGASAM_CHECKPOINT_URL=<url>` if you have a direct download URL, or  
2. Copy the file into the image in a custom build step, or  
3. Use RunPod [model caching](https://docs.runpod.io/serverless/endpoints/model-caching) and mount it at runtime.

Without this checkpoint, the handler returns a clear error.
