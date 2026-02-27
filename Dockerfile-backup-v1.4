# Lightweight overlay: build on pre-built MegaSaM serverless image.
# Base image was built from Dockerfile-backup-v1 (full install on vastai/pytorch).
# We only override handler/entry and fix ENTRYPOINT so RunPod runs our worker.

FROM szhcine/fairee-megasam-serverless:test-1.0

# Override with updated handler (timing logs) and entry script
COPY serverless/handler.py /app/handler.py
COPY serverless/entry_point.sh /app/entry_point.sh
RUN chmod +x /app/entry_point.sh

WORKDIR /app/mega-sam
ENV PYTHONPATH=/app/mega-sam:/app/mega-sam/UniDepth:/app/mega-sam/Depth-Anything
ENV CUDA_VISIBLE_DEVICES=0

# Override base image ENTRYPOINT so our worker runs (not vastai supervisor)
ENTRYPOINT ["/bin/bash", "/app/entry_point.sh"]
