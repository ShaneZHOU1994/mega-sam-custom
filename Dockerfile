# Lightweight overlay: build on pre-built MegaSaM serverless image.
# Base image was built from Dockerfile-backup-v1 (full install on vastai/pytorch).
# We only override handler/entry and fix ENTRYPOINT so RunPod runs our worker.

FROM szhcine/fairee-megasam-serverless:test-1.4

# Override with updated handler (timing logs) and entry script
COPY serverless/handler.py /app/handler.py
COPY serverless/entry_point.sh /app/entry_point.sh
RUN chmod +x /app/entry_point.sh

WORKDIR /app/mega-sam
ENV PYTHONPATH=/app/mega-sam:/app/mega-sam/UniDepth:/app/mega-sam/Depth-Anything
ENV CUDA_VISIBLE_DEVICES=0

# ---------------------------------------------------------------------------
# Override refactored pipeline scripts in the base image.
# ---------------------------------------------------------------------------

# Frame extraction improvements (+ max-frames/max-duration/resize support)
COPY video_preprocess/extract_frames.py /app/mega-sam/video_preprocess/extract_frames.py

# Mono-depth pipeline refactor (shared image loading + faster inference)
COPY mono_depth_scripts/run_mono-depth_demo.sh /app/mega-sam/mono_depth_scripts/run_mono-depth_demo.sh
COPY mono_depth_scripts/run_mono_depth_pipeline.py /app/mega-sam/mono_depth_scripts/run_mono_depth_pipeline.py

# Depth / metric-depth inference speedups
COPY Depth-Anything/run_videos.py /app/mega-sam/Depth-Anything/run_videos.py
COPY UniDepth/scripts/demo_mega-sam.py /app/mega-sam/UniDepth/scripts/demo_mega-sam.py

# DROID parameter knobs via env vars
COPY camera_tracking_scripts/test_demo.py /app/mega-sam/camera_tracking_scripts/test_demo.py

# ---------------------------------------------------------------------------
# Bake required model checkpoints into the image to avoid runtime downloads.
# ---------------------------------------------------------------------------

# Ensure checkpoint directories exist
RUN mkdir -p Depth-Anything/checkpoints cvd_opt checkpoints

# 1) Depth-Anything ViT-L checkpoint
#    Source: https://huggingface.co/spaces/LiheYoung/Depth-Anything
RUN curl -L "https://huggingface.co/spaces/LiheYoung/Depth-Anything/resolve/main/checkpoints/depth_anything_vitl14.pth" \
    -o Depth-Anything/checkpoints/depth_anything_vitl14.pth

# 2) RAFT checkpoint for CVD optimization (only used if CVD is enabled)
#    Source folder: https://drive.google.com/drive/folders/1sWDsfuZ3Up38EUQt7-JDTT1HcGHuJgvT
#    We use gdown to download the folder and then move raft-things.pth into place.
RUN pip install --no-cache-dir gdown && \
    gdown --folder "https://drive.google.com/drive/folders/1sWDsfuZ3Up38EUQt7-JDTT1HcGHuJgvT" -O /tmp/raft && \
    if [ -f /tmp/raft/raft-things.pth ]; then mv /tmp/raft/raft-things.pth cvd_opt/raft-things.pth; fi && \
    rm -rf /tmp/raft

# 3) Pre-download UniDepthV2 weights into the image cache so first inference
#    does not spend time hitting Hugging Face.
#    (Code in exec() so no line starts with "from" - Docker parses FROM otherwise.)
RUN python - << 'EOF' && rm -rf ~/.cache/huggingface/accelerate
exec("""
from unidepth.models import UniDepthV2
print("Downloading UniDepthV2 weights into image cache...")
_ = UniDepthV2.from_pretrained(
    "lpiccinelli/unidepth-v2-vitl14",
    revision="1d0d3c52f60b5164629d279bb9a7546458e6dcc4",
)
""")
EOF

# Override base image ENTRYPOINT so our worker runs (not vastai supervisor)
ENTRYPOINT ["/bin/bash", "/app/entry_point.sh"]
