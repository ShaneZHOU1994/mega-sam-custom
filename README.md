# MegaSaM

<!-- # 🚧 This repository is still not done and being uploaded, please stand by. 🚧  -->

[Project Page](https://mega-sam.github.io/index.html) | [Paper](https://arxiv.org/abs/2412.04463)

This code accompanies the paper

**MegaSam: Accurate, Fast and Robust Casual Structure and Motion from Casual
Dynamic Videos** \
Zhengqi Li, Richard Tucker, Forrester Cole, Qianqian Wang, Linyi Jin, Vickie Ye,
Angjoo Kanazawa, Aleksander Holynski, Noah Snavely

*This is not an officially supported Google product.*

## Clone

Make sure to clone the repository with the submodules by using:
`git clone --recursive git@github.com:mega-sam/mega-sam.git`

## Instructions for installing dependencies

### Python Environment

The following codebase was successfully run with Python 3.10, CUDA11.8, and
Pytorch2.0.1. We suggest installing the library in a virtual environment such as
Anaconda.

1.  To install main libraries, run: \
    `conda env create -f environment.yml`

2.  To install xformers for UniDepth model, follow the instructions from
    https://github.com/facebookresearch/xformers. If you encounter any
    installation issue, we suggest installing it from a prebuilt file. For
    example, for Python 3.10+Cuda11.8+Pytorch2.0.1, run: \
    `wget https://anaconda.org/xformers/xformers/0.0.22.post7/download/linux-64/xformers-0.0.22.post7-py310_cu11.8.0_pyt2.0.1.tar.bz2`

    `conda install xformers-0.0.22.post7-py310_cu11.8.0_pyt2.0.1.tar.bz2`

3.  Compile the extensions for the camera tracking module: \
    `cd base; python setup.py install`

### Downloading pretrained checkpoints

1.  Download [DepthAnything checkpoint](https://huggingface.co/spaces/LiheYoung/Depth-Anything/blob/main/checkpoints/depth_anything_vitl14.pth) to
    mega-sam/Depth-Anything/checkpoints/depth_anything_vitl14.pth

2.  Download and include [RAFT checkpoint](https://drive.google.com/drive/folders/1sWDsfuZ3Up38EUQt7-JDTT1HcGHuJgvT) at mega-sam/cvd_opt/raft-things.pth

### Running MegaSaM on Sintel

1.  Download and unzip [Sintel data](https://drive.google.com/file/d/1bSGX7JY73M3HzMS6xsJizRkPH-NQLPOf/view?usp=sharing)

2.  Precompute mono-depth (Please modify img-path in the script):
    `./mono_depth_scripts/run_mono-depth_sintel.sh`

3.  Run camera tracking (Please modify DATA_PATH in the script. Adding
    argument --opt_focal to enable focal length optimization):
    `./tools/evaluate_sintel.sh`

4.  Running consistent video depth optimization given estimated cameras (Please
    modify datapath in the script): `./cvd_opt/cvd_opt_sintel.sh`

5.  Evaluate camera poses and depths: \
    `python ./evaluations_poses/evaluate_sintel.py`

    `python ./evaluations_depth/evaluate_depth_ours_sintel.py`

### Running MegaSaM on DyCheck

1.  Download [Dycheck data](https://drive.google.com/drive/folders/1BHzjHo58nGAMvKMo_AS0_SwU2tJagXXx?usp=sharing)

2.  Precompute mono-depth (Please modify img-path in the script):
    `./mono_depth_scripts/run_mono-depth_dycheck.sh`

3.  Running camera tracking (Please modify DATA_PATH in the script. Add
    argument --opt_focal to enable focal length optimization):
    `./tools/evaluate_dycheck.sh`

4.  Running consistent video depth optimization given estimated cameras (Please
    modify datapath in the script):
    `./cvd_opt/cvd_opt_dycheck.sh`

5.  Evaluate camera poses and depths: \
    `python ./evaluations_poses/evaluate_dycheck.py`

    `python ./evaluations_depth/evaluate_depth_ours_dycheck.py`

### Running MegaSaM on in-the-wild video, for example from DAVIS videos

1.  Download example [DAVIS data](https://drive.google.com/file/d/1y5XItnTTgZJqRSOpG48v1FuHvPgaAvw8/view?usp=sharing)

2.  Precompute mono-depth (Please modify img-path in the script):
    `./mono_depth_scripts/run_mono-depth_demo.sh`

3.  Running camera tracking (Please modify DATA_PATH in the script. Add
    argument --opt_focal to enable focal length optimization):
    `./tools/evaluate_demo.sh`

4.  Running consistent video depth optimization given estimated cameras (Please
    modify datapath in the script):
    `./cvd_opt/cvd_opt_demo.sh`

### Downloading output files from a remote instance (e.g. vast.ai)

After running `run_mono-depth_demo.sh` and `evaluate_demo.sh` on a remote VM, outputs live under the repo root (e.g. `/workspace/mega-sam` on vast.ai):

| Source | Remote path (under repo root) |
|--------|-------------------------------|
| Mono-depth (Depth-Anything) | `Depth-Anything/video_visualization/<seq>/` (e.g. `swing`, `breakdance-flare`) |
| Mono-depth (UniDepth) | `UniDepth/outputs/<seq>/` (per-frame `.npz`) |
| Camera tracking (evaluate_demo) | `outputs/<scene>_droid.npz` (e.g. `outputs/swing_droid.npz`, `outputs/breakdance-flare_droid.npz`) |
| CVD depth (cvd_opt_demo) | `outputs/<scene>_sgd_cvd_hr.npz` (e.g. `outputs/upload_frames_sgd_cvd_hr.npz`) |

**Where to get SSH host and port (vast.ai)**  
1. Open [vast.ai console](https://cloud.vast.ai/) → your instance.  
2. Click the **SSH** button (or SSH icon) on the instance card.  
3. The popup shows the exact SSH command, e.g. `ssh -p 20544 root@142.214.185.187`.  
   - **Port** = the number after `-p` (e.g. `20544`). Use this port only — do not use a port from a browser URL (e.g. Jupyter).  
   - **Host** = the IP or hostname after `root@` (e.g. `142.214.185.187`). Use only the host; **do not** put `https://` or `:port` or a path in the host.  
4. For SCP, the remote path is **after** a colon: `root@HOST:/workspace/mega-sam/outputs` (no `https`, no port in the host part).

If you get **"Connection closed"**: (a) Use the port from the SSH popup, not from the instance URL. (b) Add your SSH public key to the instance (instance card → add key / SSH interface). (c) Ensure your private key is the one vast.ai has the public key for (e.g. `ssh -P PORT -i C:\Users\You\.ssh\id_ed25519 root@HOST`).

**Download with SCP** (run in **cmd** or PowerShell on your Windows machine; use the **host** and **port** from the vast.ai SSH popup as above):

Replace `PORT` and `HOST` with the values from the SSH popup (e.g. `PORT=20544`, `HOST=142.214.185.187`). Remote repo root is `/workspace/mega-sam`:

```cmd
scp -P PORT -r root@HOST:/workspace/mega-sam/outputs .
scp -P PORT -r root@HOST:/workspace/mega-sam/UniDepth/outputs ./UniDepth_outputs
scp -P PORT -r root@HOST:/workspace/mega-sam/Depth-Anything/video_visualization ./Depth-Anything_video_visualization
```

If you use a specific key: `scp -P PORT -i C:\Users\YourName\.ssh\id_ed25519 -r root@HOST:/workspace/mega-sam/outputs .`

**Download with rsync** (if you have rsync; same `PORT` and `HOST`):

```cmd
rsync -avz -e "ssh -p PORT" root@HOST:/workspace/mega-sam/outputs/ ./outputs/
rsync -avz -e "ssh -p PORT" root@HOST:/workspace/mega-sam/UniDepth/outputs/ ./UniDepth_outputs/
rsync -avz -e "ssh -p PORT" root@HOST:/workspace/mega-sam/Depth-Anything/video_visualization/ ./Depth-Anything_video_visualization/
```

Run these from the directory where you want the folders (e.g. your local `mega-sam-custom` clone). For vast.ai, use the SSH command from the instance page (host, port, and key); typically `USER` is `root` and `HOST` is something like `ssh.vast.ai` or the instance’s direct IP.

### Contact

For any questions related to our paper, please send email to zl548@cornell.edu.


### Bibtex

```
@inproceedings{li2025megasam,
  title     = {{MegaSaM: Accurate, Fast and Robust Structure and Motion from Casual Dynamic Videos}},
  author    = {Li, Zhengqi and Tucker, Richard and Cole, Forrester and Wang, Qianqian and Jin, Linyi and Ye, Vickie and Kanazawa, Angjoo and Holynski, Aleksander and Snavely, Noah},
  booktitle = {Proceedings of the IEEE/CVF Conference on Computer Vision and Pattern Recognition},
  year      = {2025}
}
```

### Copyright

Copyright 2025 Google LLC  

All software is licensed under the Apache License, Version 2.0 (Apache 2.0); you may not use this file except in compliance with the Apache 2.0 license. You may obtain a copy of the Apache 2.0 license at: https://www.apache.org/licenses/LICENSE-2.0

All other materials are licensed under the Creative Commons Attribution 4.0 International License (CC-BY). You may obtain a copy of the CC-BY license at: https://creativecommons.org/licenses/by/4.0/legalcode

Unless required by applicable law or agreed to in writing, all software and materials distributed here under the Apache 2.0 or CC-BY licenses are distributed on an "AS IS" BASIS, WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied. See the licenses for the specific language governing permissions and limitations under those licenses.

This is not an official Google product.

