# Video preprocess: extract frames for demo

## On cloud VM

1. Copy your video to the VM (or have it at a path on the VM).
2. From repo root, run:

```bash
./video_preprocess/run_extract_frames.sh /path/to/your_video.mp4
```

Optional FPS (default 6):

```bash
./video_preprocess/run_extract_frames.sh /path/to/your_video.mp4 --fps 8
```

3. Frames are written to `./DAVIS/upload_frames/`. Then run:

```bash
./mono_depth_scripts/run_mono-depth_demo.sh
./tools/evaluate_demo.sh
```

## Run extraction locally

From repo root:

```bash
python video_preprocess/extract_frames.py path/to/video.mp4 [--fps 6]
```

Frames go to `./DAVIS/upload_frames/`.

## Upload local `DAVIS/upload_frames` to cloud VM

If you extracted frames locally and want to push them to the VM, use one of the following. Replace `USER`, `HOST`, and `REMOTE_REPO` with your VM user, hostname/IP, and repo path on the VM.

**Using `scp` (Windows cmd or PowerShell):**

```cmd
scp -r DAVIS\upload_frames USER@HOST:REMOTE_REPO/DAVIS/
```

Example:

```cmd
scp -r DAVIS\upload_frames myuser@myvm.example.com:~/mega-sam-custom/DAVIS/
```

**Using `rsync` (if available, e.g. WSL or Git Bash):**

```bash
rsync -avz DAVIS/upload_frames/ USER@HOST:REMOTE_REPO/DAVIS/upload_frames/
```

Example:

```bash
rsync -avz DAVIS/upload_frames/ myuser@myvm.example.com:~/mega-sam-custom/DAVIS/upload_frames/
```

Then on the VM, run `./mono_depth_scripts/run_mono-depth_demo.sh` and `./tools/evaluate_demo.sh` as above.
