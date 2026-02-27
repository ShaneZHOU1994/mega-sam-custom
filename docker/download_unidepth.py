"""Pre-download UniDepthV2 weights into image cache (used at Docker build time)."""
from unidepth.models import UniDepthV2

print("Downloading UniDepthV2 weights into image cache...")
_ = UniDepthV2.from_pretrained(
    "lpiccinelli/unidepth-v2-vitl14",
    revision="1d0d3c52f60b5164629d279bb9a7546458e6dcc4",
)
