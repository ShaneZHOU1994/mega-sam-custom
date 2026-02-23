# MegaSaM container for RunPod serverless (video -> camera trajectory API).
# Base: vastai/pytorch:2.0.1-cuda-11.8.0-py310 (proven with megasam_complete_install.sh).
# Install layers replicate dependencies_install/megasam_complete_install.sh.

FROM vastai/pytorch:2.0.1-cuda-11.8.0-py310

ENV DEBIAN_FRONTEND=noninteractive
ENV INSTALL_DIR=/app/mega-sam
ENV CONDA_INSTALL_DIR=/root/miniconda3
ENV PYTHON_SYSTEM=/usr/bin/python3
# Prefer vastai’s venv Python (has torch); fallback to PATH for other images
ENV PATH=/venv/main/bin:/opt/conda/bin:$PATH

# -----------------------------------------------------------------------------
# 1) System tools (script step 1)
# -----------------------------------------------------------------------------
RUN apt-get update -qq \
    && apt-get install -y -qq --no-install-recommends \
        git wget unzip curl dos2unix build-essential bzip2 \
    && rm -rf /var/lib/apt/lists/*

# -----------------------------------------------------------------------------
# 2) Copy repo (script step 3: clone replaced by COPY; submodules must be inited on host)
# -----------------------------------------------------------------------------
WORKDIR /app
COPY . mega-sam/
WORKDIR $INSTALL_DIR

# Ensure base submodule content exists: use COPY if present, else clone during build
RUN (test -d base && test -f base/setup.py) || \
    (git clone --depth 1 https://github.com/mega-sam/base.git base && test -f base/setup.py) || \
    (echo "ERROR: base missing and clone failed." && exit 1)

# -----------------------------------------------------------------------------
# 3) Miniconda + xformers into the Python that has torch (script steps 4–5)
# -----------------------------------------------------------------------------
# Discover torch site-packages (vastai/pytorch uses /venv/main; fallback to first python that has torch)
RUN for py in /venv/main/bin/python3 /opt/conda/bin/python3 /usr/bin/python3 python3; do \
      if command -v "$py" >/dev/null 2>&1 && "$py" -c "import torch" 2>/dev/null; then \
        "$py" -c "import torch; import sysconfig, sys; print(sysconfig.get_path('purelib')); print(sys.executable)" > /tmp/torch_site.txt; \
        break; \
      fi; \
    done && test -f /tmp/torch_site.txt || (echo "ERROR: no python with torch found. Tried /venv/main/bin/python3, /opt/conda/bin/python3, /usr/bin/python3, python3" && exit 1)

ARG XFORMERS_TARBALL=xformers-0.0.22.post7-py310_cu11.8.0_pyt2.0.1.tar.bz2
ARG XFORMERS_URL=https://anaconda.org/xformers/xformers/0.0.22.post7/download/linux-64/${XFORMERS_TARBALL}

RUN SYSTEM_SITE=$(head -1 /tmp/torch_site.txt) \
    && PYTHON_TORCH=$(tail -1 /tmp/torch_site.txt) \
    && wget -q https://repo.anaconda.com/miniconda/Miniconda3-latest-Linux-x86_64.sh -O /tmp/miniconda.sh \
    && bash /tmp/miniconda.sh -b -p $CONDA_INSTALL_DIR -u \
    && rm /tmp/miniconda.sh \
    && $CONDA_INSTALL_DIR/bin/conda tos accept --override-channels --channel https://repo.anaconda.com/pkgs/main \
    && $CONDA_INSTALL_DIR/bin/conda tos accept --override-channels --channel https://repo.anaconda.com/pkgs/r \
    && wget -q "$XFORMERS_URL" -O /tmp/${XFORMERS_TARBALL} \
    && $CONDA_INSTALL_DIR/bin/conda install /tmp/${XFORMERS_TARBALL} -y --prefix $CONDA_INSTALL_DIR \
    && CONDA_XFORMERS=$(find $CONDA_INSTALL_DIR -type d -path "*/site-packages/xformers" | head -1) \
    && cp -r "$CONDA_XFORMERS" "$SYSTEM_SITE/" \
    && rm -f /tmp/${XFORMERS_TARBALL} /tmp/torch_site.txt \
    && "$PYTHON_TORCH" -c "import xformers; print('xformers', xformers.__version__)"

# -----------------------------------------------------------------------------
# 4) Pip deps + setuptools for pkg_resources (script step 6) — use same python3 as torch/xformers
# -----------------------------------------------------------------------------
RUN python3 -m pip install --upgrade pip wheel \
    && python3 -m pip install "setuptools>=65.0.0,<70.0.0" \
    && python3 -c "import pkg_resources" \
    && python3 -m pip install --no-cache-dir \
        opencv-python-headless==4.9.0.80 \
        tqdm==4.67.1 \
        imageio==2.36.0 \
        einops==0.8.0 \
        scipy==1.14.1 \
        matplotlib==3.9.2 \
        wandb==0.18.7 \
        timm==1.0.7 \
        ninja==1.11.1 \
        numpy==1.26.3 \
        huggingface-hub==0.23.4 \
        kornia==0.7.4 \
        gdown \
        torch-scatter -f https://data.pyg.org/whl/torch-2.0.1+cu118.html

# -----------------------------------------------------------------------------
# 5) Camera tracking extensions (script step 7)
# -----------------------------------------------------------------------------
RUN cd base && python3 setup.py install

WORKDIR $INSTALL_DIR

# -----------------------------------------------------------------------------
# 6) Checkpoints: Depth-Anything + RAFT (script step 8). megasam_final.pth not in upstream; add via build ARG or mount.
# -----------------------------------------------------------------------------
RUN mkdir -p Depth-Anything/checkpoints cvd_opt checkpoints \
    && wget -q -O Depth-Anything/checkpoints/depth_anything_vitl14.pth \
        "https://huggingface.co/spaces/LiheYoung/Depth-Anything/resolve/main/checkpoints/depth_anything_vitl14.pth" \
    || true \
    && ( gdown "1JLdBfNpOYGpwI5YvFePLz5hWXqZXpxMR" -O cvd_opt/raft-things.pth || true )

# Optional: bake camera-tracking checkpoint if URL provided (e.g. from project page)
ARG MEGASAM_CHECKPOINT_URL=
RUN if [ -n "$MEGASAM_CHECKPOINT_URL" ]; then wget -q -O checkpoints/megasam_final.pth "$MEGASAM_CHECKPOINT_URL" || true; fi

# -----------------------------------------------------------------------------
# 7) RunPod serverless
# -----------------------------------------------------------------------------
RUN python3 -m pip install --no-cache-dir "runpod>=1.7.6"

COPY serverless/handler.py /app/handler.py
COPY serverless/entry_point.sh /app/entry_point.sh
RUN chmod +x /app/entry_point.sh

WORKDIR $INSTALL_DIR
ENV PYTHONPATH=${INSTALL_DIR}:${INSTALL_DIR}/UniDepth:${INSTALL_DIR}/Depth-Anything
ENV CUDA_VISIBLE_DEVICES=0

# Serverless worker: entry_point sets cwd and PYTHONPATH then runs handler (runpod.serverless.start)
CMD ["/bin/bash", "/app/entry_point.sh"]
