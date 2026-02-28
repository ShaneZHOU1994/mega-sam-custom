#!/usr/bin/env python3
"""
Run Depth-Anything and UniDepth on the same frame sequence in a single process.

This shares image loading across both models while preserving the existing
output layout used by camera_tracking_scripts/test_demo.py:

- Depth-Anything outputs: Depth-Anything/video_visualization/<scene>/*.npy
- UniDepth outputs:       UniDepth/outputs/<scene>/*.npz
"""

import argparse
import glob
import os
from pathlib import Path
from contextlib import nullcontext

import cv2
import numpy as np
import torch
import torch.nn.functional as F
from torchvision.transforms import Compose
from tqdm import tqdm

from depth_anything.dpt import DPT_DINOv2
from depth_anything.util.transform import NormalizeImage, PrepareForNet, Resize
from unidepth.models import UniDepthV2


LONG_DIM = 640


def build_depth_anything(encoder: str, weights_path: Path, localhub: bool, device: torch.device):
    assert encoder in ["vits", "vitb", "vitl"]
    if encoder == "vits":
        depth_anything = DPT_DINOv2(
            encoder="vits",
            features=64,
            out_channels=[48, 96, 192, 384],
            localhub=localhub,
        )
    elif encoder == "vitb":
        depth_anything = DPT_DINOv2(
            encoder="vitb",
            features=128,
            out_channels=[96, 192, 384, 768],
            localhub=localhub,
        )
    else:
        depth_anything = DPT_DINOv2(
            encoder="vitl",
            features=256,
            out_channels=[256, 512, 1024, 1024],
            localhub=localhub,
        )

    depth_anything.to(device)
    state = torch.load(str(weights_path), map_location="cpu")
    depth_anything.load_state_dict(state, strict=True)
    depth_anything.eval()

    transform = Compose(
        [
            Resize(
                width=768,
                height=768,
                resize_target=False,
                keep_aspect_ratio=True,
                ensure_multiple_of=14,
                resize_method="upper_bound",
                image_interpolation_method=cv2.INTER_CUBIC,
            ),
            NormalizeImage(mean=[0.485, 0.456, 0.406], std=[0.229, 0.224, 0.225]),
            PrepareForNet(),
        ]
    )
    return depth_anything, transform


def build_unidepth(device: torch.device) -> torch.nn.Module:
    model = UniDepthV2.from_pretrained(
        "lpiccinelli/unidepth-v2-vitl14",
        revision="1d0d3c52f60b5164629d279bb9a7546458e6dcc4",
    )
    model = model.to(device)
    model.eval()
    return model


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Run Depth-Anything and UniDepth on a scene, sharing image loading."
    )
    parser.add_argument(
        "--data-dir",
        type=str,
        default="DAVIS",
        help="Root directory containing scene frames (default: DAVIS).",
    )
    parser.add_argument(
        "--scene-name",
        type=str,
        required=True,
        help="Scene name (subdirectory under --data-dir, e.g. upload_frames).",
    )
    parser.add_argument(
        "--encoder",
        type=str,
        default="vitl",
        choices=["vits", "vitb", "vitl"],
        help="Depth-Anything encoder type.",
    )
    parser.add_argument(
        "--load-from",
        type=str,
        required=True,
        help="Path to Depth-Anything checkpoint (.pth).",
    )
    parser.add_argument(
        "--localhub",
        action="store_true",
        default=False,
        help="Use local hub for Depth-Anything weights.",
    )
    parser.add_argument(
        "--da-outdir",
        type=str,
        default="Depth-Anything/video_visualization",
        help="Base output directory for Depth-Anything .npy files.",
    )
    parser.add_argument(
        "--unidepth-outdir",
        type=str,
        default="UniDepth/outputs",
        help="Base output directory for UniDepth .npz files.",
    )

    args = parser.parse_args()

    device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
    torch.backends.cudnn.benchmark = True

    data_dir = Path(args.data_dir)
    img_dir = data_dir / args.scene_name
    if not img_dir.is_dir():
        print(f"Error: image directory not found: {img_dir}")
        return 1

    img_paths = sorted(glob.glob(str(img_dir / "*.png")))
    img_paths += sorted(glob.glob(str(img_dir / "*.jpg")))
    if not img_paths:
        print(f"Error: no frames found in {img_dir} (expected .png or .jpg).")
        return 1

    da_scene_out = Path(args.da_outdir) / args.scene_name
    uni_scene_out = Path(args.unidepth_outdir) / args.scene_name
    da_scene_out.mkdir(parents=True, exist_ok=True)
    uni_scene_out.mkdir(parents=True, exist_ok=True)

    depth_anything, da_transform = build_depth_anything(
        args.encoder, Path(args.load_from), args.localhub, device
    )
    unidepth = build_unidepth(device)

    use_amp = device.type == "cuda"
    # torch.cuda.amp.autocast() does not take device_type (only torch.amp.autocast in newer PyTorch does)
    amp_ctx = (
        (lambda: torch.cuda.amp.autocast(dtype=torch.float16)) if use_amp
        else nullcontext()
    )

    with torch.inference_mode():
        for img_path in tqdm(img_paths):
            img_path = Path(img_path)
            bgr = cv2.imread(str(img_path))
            if bgr is None:
                continue

            # Depth-Anything branch (monocular disparity)
            image_rgb = cv2.cvtColor(bgr, cv2.COLOR_BGR2RGB) / 255.0
            h, w = image_rgb.shape[:2]
            da_input = da_transform({"image": image_rgb})["image"]
            da_input = torch.from_numpy(da_input).unsqueeze(0).to(device)

            with amp_ctx():
                da_depth = depth_anything(da_input)

            da_depth = F.interpolate(
                da_depth[None], (h, w), mode="bilinear", align_corners=False
            )[0, 0]
            da_depth_npy = np.float32(da_depth.cpu().numpy())
            np.save(da_scene_out / f"{img_path.stem}.npy", da_depth_npy)

            # UniDepth branch (metric depth + FOV)
            rgb = bgr[..., ::-1]
            if rgb.shape[1] > rgb.shape[0]:
                final_w, final_h = LONG_DIM, int(
                    round(LONG_DIM * rgb.shape[0] / rgb.shape[1])
                )
            else:
                final_w, final_h = (
                    int(round(LONG_DIM * rgb.shape[1] / rgb.shape[0])),
                    LONG_DIM,
                )
            rgb_resized = cv2.resize(
                rgb, (final_w, final_h), cv2.INTER_AREA
            )

            rgb_torch = torch.from_numpy(rgb_resized).permute(2, 0, 1).to(device)
            predictions = unidepth.infer(rgb_torch)
            fov_ = np.rad2deg(
                2
                * np.arctan(
                    predictions["depth"].shape[-1]
                    / (2 * predictions["intrinsics"][0, 0, 0].cpu().numpy())
                )
            )
            depth_uni = predictions["depth"][0, 0].cpu().numpy().astype(np.float32)
            np.savez(
                uni_scene_out / f"{img_path.stem}.npz",
                depth=depth_uni,
                fov=fov_,
            )

    return 0


if __name__ == "__main__":
    raise SystemExit(main())

