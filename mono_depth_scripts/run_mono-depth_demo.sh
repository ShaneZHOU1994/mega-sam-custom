#!/bin/bash
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


evalset=(
  upload_frames
)

DATA_DIR=DAVIS

# Ensure UniDepth package is importable
export PYTHONPATH="${PYTHONPATH}:$(pwd)/UniDepth"

for seq in ${evalset[@]}; do
  CUDA_VISIBLE_DEVICES=0 python mono_depth_scripts/run_mono_depth_pipeline.py \
    --data-dir "$DATA_DIR" \
    --scene-name "$seq" \
    --encoder vitl \
    --load-from Depth-Anything/checkpoints/depth_anything_vitl14.pth \
    --da-outdir Depth-Anything/video_visualization \
    --unidepth-outdir UniDepth/outputs
done
