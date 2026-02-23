#!/bin/bash
# RunPod serverless worker entry point.
# Sets working directory and PYTHONPATH then starts the RunPod handler (handler.py).
# CMD in Dockerfile runs this script; handler.py calls runpod.serverless.start() to listen for requests.

set -e
cd /app/mega-sam
export PYTHONPATH=/app/mega-sam:/app/mega-sam/UniDepth:/app/mega-sam/Depth-Anything
exec python3 -u /app/handler.py
