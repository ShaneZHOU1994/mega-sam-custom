"""Pre-download DINOv2 (ViT-L/14) into torch hub cache (used at Docker build time)."""
import torch

print("Downloading DINOv2 (vitl14) into torch hub cache...")
# Same repo and model as Depth-Anything/dpt.py uses; default encoder is vitl.
_ = torch.hub.load("facebookresearch/dinov2", "dinov2_vitl14")
print("Done.")
