#!/bin/bash
################################################################################
# MegaSaM Dependency Installation Script (Base Environment Only)
#
# Project: MegaSaM - Accurate, Fast and Robust Structure and Motion from
#          Casual Dynamic Videos
#
# Upstream repo: https://github.com/mega-sam/mega-sam.git
# Docs:         https://github.com/ShaneZHOU1994/mega-sam-custom/blob/main/README.md
#
# This script is designed for Vast.ai (or similar) containers where the
# **base image already provides**:
#   - Python 3.10
#   - PyTorch 2.0.1
#   - CUDA 11.8
#
# IMPORTANT:
# - This script does NOT create or activate any conda/venv.
# - All dependencies are installed directly into the **current base env**.
# - It will verify that the base env has torch==2.0.1+cu118 and fail early
#   if not.
#
# What it does:
#   1. Clone upstream MegaSaM repo with submodules into /workspace/mega-sam
#   2. Verify base env versions (Python, torch, CUDA) BEFORE installing deps
#   3. Install extra Python deps via pip (no torch/cuda/python changes)
#   4. Install torch-scatter and xformers with --no-deps to avoid touching torch
#   5. Verify versions again AFTER installs
#   6. Compile camera tracking extensions (base/setup.py)
#   7. Download Depth-Anything and RAFT checkpoints
#
# Typical usage inside container:
#   cd /workspace
#   wget <your-url>/megasam_complete_install.sh -O megasam_complete_install.sh
#   sed -i 's/\r$//' megasam_complete_install.sh
#   chmod +x megasam_complete_install.sh
#   ./megasam_complete_install.sh
################################################################################

set -e  # Exit immediately on any error

###############################################################################
# Pretty printing helpers
###############################################################################

RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

print_header() {
    echo -e "\n${BLUE}============================================================${NC}"
    echo -e "${BLUE}$1${NC}"
    echo -e "${BLUE}============================================================${NC}\n"
}

print_step() {
    echo -e "\n${YELLOW}[$1] $2${NC}\n"
}

print_success() {
    echo -e "${GREEN}✓ $1${NC}"
}

print_error() {
    echo -e "${RED}✗ $1${NC}"
}

print_info() {
    echo -e "${BLUE}ℹ $1${NC}"
}

###############################################################################
# Configuration
###############################################################################

INSTALL_DIR="/workspace/mega-sam"

print_header "MegaSaM Dependency Installation (Base Env Only)"
echo "Install dir : $INSTALL_DIR"
echo "Python exec : $(command -v python3 || command -v python || echo 'python not found')"

###############################################################################
# Step 1: Ensure base tools are available
###############################################################################

print_step "1/7" "Ensuring git/wget/curl/build-essential are available"

if command -v apt-get >/dev/null 2>&1; then
    apt-get update -qq
    apt-get install -y -qq git wget unzip curl dos2unix build-essential > /dev/null 2>&1 || true
else
    print_info "apt-get not available; assuming tools are already installed."
fi

print_success "Basic tools ready"

###############################################################################
# Step 2: Clone upstream MegaSaM repo with submodules
###############################################################################

print_step "2/7" "Cloning original MegaSaM repository with submodules"

if [ ! -d "$INSTALL_DIR" ]; then
    mkdir -p "$(dirname "$INSTALL_DIR")"
    cd "$(dirname "$INSTALL_DIR")"
    git clone --recursive https://github.com/mega-sam/mega-sam.git "$(basename "$INSTALL_DIR")"
    print_success "Repository cloned into $INSTALL_DIR"
else
    print_info "Repository already exists at $INSTALL_DIR"
    cd "$INSTALL_DIR"
    git remote -v || true
    print_info "Updating submodules"
    git submodule update --init --recursive
    print_success "Submodules updated"
fi

###############################################################################
# Helper: version check function (Python / torch / CUDA)
###############################################################################

check_versions() {
    local phase="$1"
    print_info "=== VERSION CHECK (${phase}) ==="
    python3 - << 'VERCHECK'
import sys
print("Python:", sys.version.split()[0])
try:
    import torch
except Exception as e:
    print("PyTorch import FAILED:", e)
    sys.exit(1)

print("PyTorch:", torch.__version__)
print("CUDA available:", torch.cuda.is_available())
if torch.cuda.is_available():
    print("CUDA version (torch):", torch.version.cuda)
    try:
        print("GPU:", torch.cuda.get_device_name(0))
    except Exception:
        pass

required_torch = "2.0.1"
required_cuda = "11.8"

if not torch.__version__.startswith(required_torch):
    print(f"ERROR: Torch version mismatch: {torch.__version__} (expected {required_torch}).")
    sys.exit(2)

if torch.version.cuda != required_cuda:
    print(f"ERROR: CUDA version mismatch (torch.version.cuda={torch.version.cuda}, expected {required_cuda}).")
    sys.exit(3)

print("Version check OK.")
VERCHECK
}

###############################################################################
# Step 3: Pre‑dependency version check (base env must be correct)
###############################################################################

print_step "3/7" "Checking base environment versions BEFORE installing dependencies"

if ! check_versions "BEFORE DEPS" ; then
    print_error "Base environment does NOT match required versions (Python 3.10 + torch 2.0.1 + cu118)."
    print_error "Please choose a Vast.ai image with these exact versions and rerun."
    exit 1
fi

###############################################################################
# Step 4: Install extra Python dependencies into base env (no torch/cuda changes)
###############################################################################

print_step "4/7" "Installing Python dependencies in base environment (excluding torch/cuda/python)"

python3 -c "import sys; print('Using Python', sys.version)" || {
    print_error "Python is not functional in this container."
    exit 1
}

print_info "Upgrading pip/setuptools/wheel (safe)"
python3 -m pip install --upgrade pip setuptools wheel -q

print_info "Installing core packages via pip (no torch / cuda / python)"
python3 -m pip install -q \
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
    gdown

print_success "Core Python packages installed"

print_info "Installing torch-scatter for PyTorch 2.0.1 + CUDA 11.8 (no torch changes)"
python3 -m pip install -q torch-scatter -f https://data.pyg.org/whl/torch-2.0.1+cu118.html
print_success "torch-scatter installed"

print_info "Installing xformers 0.0.22.post7 for cu118 with --no-deps (so torch is untouched)"
python3 -m pip install -q xformers==0.0.22.post7 --no-deps --index-url https://download.pytorch.org/whl/cu118
print_success "xformers installed"

###############################################################################
# Step 5: Post‑dependency version check (ensure torch/cu still correct)
###############################################################################

print_step "5/7" "Re-checking base environment versions AFTER dependency installation"

if ! check_versions "AFTER DEPS" ; then
    print_error "Environment versions changed unexpectedly after dependency installation."
    exit 1
fi

###############################################################################
# Step 6: Compile camera tracking extensions (base/setup.py)
###############################################################################

print_step "6/7" "Compiling camera tracking extensions (base/setup.py)"

cd "$INSTALL_DIR/base"
python3 setup.py install

print_success "Camera tracking extensions compiled and installed"

###############################################################################
# Step 7: Download Depth-Anything and RAFT checkpoints
###############################################################################

print_step "7/7" "Downloading required checkpoints"

cd "$INSTALL_DIR"

print_info "Preparing Depth-Anything checkpoint directory"
mkdir -p "$INSTALL_DIR/Depth-Anything/checkpoints"
cd "$INSTALL_DIR/Depth-Anything/checkpoints"

if [ ! -f "depth_anything_vitl14.pth" ]; then
    print_info "Downloading Depth-Anything checkpoint (~1.5 GB)..."
    if wget -q --show-progress \
        https://huggingface.co/spaces/LiheYoung/Depth-Anything/resolve/main/checkpoints/depth_anything_vitl14.pth; then
        print_success "Depth-Anything checkpoint downloaded"
    else
        print_error "Failed to download Depth-Anything checkpoint automatically."
        print_info "Please download manually from:"
        print_info "  https://huggingface.co/spaces/LiheYoung/Depth-Anything/blob/main/checkpoints/depth_anything_vitl14.pth"
        print_info "and place it at:"
        print_info "  $INSTALL_DIR/Depth-Anything/checkpoints/depth_anything_vitl14.pth"
    fi
else
    print_info "Depth-Anything checkpoint already present"
fi

print_info "Preparing RAFT checkpoint directory"
mkdir -p "$INSTALL_DIR/cvd_opt"
cd "$INSTALL_DIR/cvd_opt"

if [ ! -f "raft-things.pth" ]; then
    print_info "Downloading RAFT checkpoint (~250 MB) via gdown..."
    # RAFT checkpoint folder is documented in the official README
    if gdown "1JLdBfNpOYGpwI5YvFePLz5hWXqZXpxMR" -O raft-things.pth --quiet; then
        print_success "RAFT checkpoint downloaded"
    else
        print_error "Failed to download RAFT checkpoint automatically."
        print_info "Please download manually from the RAFT Google Drive folder and place it at:"
        print_info "  $INSTALL_DIR/cvd_opt/raft-things.pth"
    fi
else
    print_info "RAFT checkpoint already present"
fi

###############################################################################
# Final summary
###############################################################################

print_header "MegaSaM setup complete (Base Env Only)"

echo "Repository path : $INSTALL_DIR"
echo ""
echo "Checkpoints:"
if [ -f "$INSTALL_DIR/Depth-Anything/checkpoints/depth_anything_vitl14.pth" ]; then
    print_success "Depth-Anything checkpoint is present"
else
    print_error "Depth-Anything checkpoint is MISSING"
fi

if [ -f "$INSTALL_DIR/cvd_opt/raft-things.pth" ]; then
    print_success "RAFT checkpoint is present"
else
    print_error "RAFT checkpoint is MISSING"
fi

echo ""
print_info "To run MegaSaM, in this same base environment:"
echo "  cd \"$INSTALL_DIR\""
echo "  # Edit paths in mono_depth_scripts/, tools/, cvd_opt/ as needed"
echo "  ./mono_depth_scripts/run_mono-depth_demo.sh"
echo "  ./tools/evaluate_demo.sh"
echo "  ./cvd_opt/cvd_opt_demo.sh"
echo ""

#!/bin/bash
################################################################################
# MegaSaM Dependency-Only Installation Script for Vast.ai GPU Instances
#
# Project: MegaSaM - Structure and Motion from Casual Dynamic Videos
# Original Repo: https://github.com/mega-sam/mega-sam.git
# Fork Docs: https://github.com/ShaneZHOU1994/mega-sam-custom/blob/main/README.md
#
# This script assumes:
#   - You are running inside a container that ALREADY has:
#       * Python 3.10
#       * PyTorch 2.0.1
#       * CUDA 11.8
#   - You do NOT want this script to install or change Python / PyTorch / CUDA.
#
# It will:
#   1. Clone the original MegaSaM repo with submodules
#   2. Create an environment named "megasam"
#        - Prefer Conda (clone from base so versions stay identical)
#        - Fallback to Python venv with --system-site-packages
#   3. Install only the extra Python dependencies from README/environment.yml
#   4. Compile the camera tracking extensions
#   5. Download required checkpoints into the correct locations
#
# USAGE (inside your Vast.ai container, from /workspace or any writable dir):
#   wget <your-url>/megasam_complete_install.sh -O megasam_complete_install.sh
#   sed -i 's/\r$//' megasam_complete_install.sh
#   chmod +x megasam_complete_install.sh
#   ./megasam_complete_install.sh
################################################################################

set -e  # Exit immediately on error

###############################################################################
# Color helpers
###############################################################################

RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

print_header() {
    echo -e "\n${BLUE}============================================================${NC}"
    echo -e "${BLUE}$1${NC}"
    echo -e "${BLUE}============================================================${NC}\n"
}

print_step() {
    echo -e "\n${YELLOW}[$1] $2${NC}\n"
}

print_success() {
    echo -e "${GREEN}✓ $1${NC}"
}

print_error() {
    echo -e "${RED}✗ $1${NC}"
}

print_info() {
    echo -e "${BLUE}ℹ $1${NC}"
}

###############################################################################
# Configuration
###############################################################################

# Where to clone the original upstream repo
INSTALL_DIR="/workspace/mega-sam"

# Environment name requested
ENV_NAME="megasam"

# If using venv, this is the directory path
VENV_DIR="/workspace/${ENV_NAME}"

print_header "MegaSaM Dependency Installation (no PyTorch/CUDA/Python changes)"
echo "Install dir : $INSTALL_DIR"
echo "Env name    : $ENV_NAME"
echo "Venv dir    : $VENV_DIR"

###############################################################################
# Step 1: Basic tools (no Python / CUDA changes)
###############################################################################

print_step "1/7" "Ensuring basic system tools are available (git, wget, unzip, curl)"

if command -v apt-get >/dev/null 2>&1; then
    apt-get update -qq
    apt-get install -y -qq git wget unzip curl dos2unix build-essential > /dev/null 2>&1 || true
else
    print_info "apt-get not available; assuming git/wget/curl are already installed."
fi

print_success "Basic tools checked"

###############################################################################
# Step 2: Clone original MegaSaM repository
###############################################################################

print_step "2/7" "Cloning original MegaSaM repository with submodules"

if [ ! -d "$INSTALL_DIR" ]; then
    mkdir -p "$(dirname "$INSTALL_DIR")"
    cd "$(dirname "$INSTALL_DIR")"
    git clone --recursive https://github.com/mega-sam/mega-sam.git "$(basename "$INSTALL_DIR")"
    print_success "Repository cloned into $INSTALL_DIR"
else
    print_info "Repository already exists at $INSTALL_DIR"
    cd "$INSTALL_DIR"
    git remote -v || true
    print_info "Updating submodules"
    git submodule update --init --recursive
    print_success "Submodules updated"
fi

###############################################################################
# Step 3: Create 'megasam' environment (conda preferred, venv fallback)
###############################################################################

print_step "3/7" "Creating 'megasam' environment without touching PyTorch/CUDA/Python versions"

ENV_TYPE=""
ENV_ACTIVATE_CMD=""

if command -v conda >/dev/null 2>&1; then
    print_info "Conda detected. Creating conda env '$ENV_NAME' by cloning 'base' to preserve versions."

    # Remove old env if it exists
    conda env remove -n "$ENV_NAME" -y >/dev/null 2>&1 || true

    # Clone base environment (this reuses existing Python / PyTorch / CUDA versions)
    conda create -n "$ENV_NAME" --clone base -y

    ENV_TYPE="conda"
    ENV_ACTIVATE_CMD="conda activate $ENV_NAME"
    print_success "Conda env '$ENV_NAME' created by cloning 'base'"
else
    print_info "Conda NOT detected. Falling back to Python venv with system site-packages."

    # Use the existing Python 3.10 in the container
    if ! command -v python3 >/dev/null 2>&1; then
        print_error "python3 not found. Please ensure Python 3.10 is installed in the container."
        exit 1
    fi

    # Remove existing venv if present
    if [ -d "$VENV_DIR" ]; then
        print_info "Removing existing venv at $VENV_DIR"
        rm -rf "$VENV_DIR"
    fi

    python3 -m venv --system-site-packages "$VENV_DIR"

    ENV_TYPE="venv"
    ENV_ACTIVATE_CMD="source \"$VENV_DIR/bin/activate\""
    print_success "Python venv created at $VENV_DIR (inherits system site-packages)"
fi

echo ""
print_info "To activate later, run:"
echo "  $ENV_ACTIVATE_CMD"

###############################################################################
# Step 4: Activate env and install Python dependencies (except PyTorch/CUDA/Python)
###############################################################################

print_step "4/7" "Activating environment and installing extra Python dependencies"

if [ "$ENV_TYPE" = "conda" ]; then
    # shellcheck disable=SC1091
    source "$(conda info --base)/etc/profile.d/conda.sh"
    eval "$ENV_ACTIVATE_CMD"
else
    # venv
    # shellcheck disable=SC1090
    eval "$ENV_ACTIVATE_CMD"
fi

python -c "import sys; print('Using Python', sys.version)" || {
    print_error "Python not working inside the environment."
    exit 1
}

print_info "=== VERSION CHECK BEFORE DEP INSTALLS ==="
python - << 'PRECHECK'
import sys
print("Python:", sys.version.split()[0])
try:
    import torch
    print("PyTorch:", torch.__version__)
    print("CUDA available:", torch.cuda.is_available())
    if torch.cuda.is_available():
        print("CUDA version (torch):", torch.version.cuda)
        try:
            print("GPU:", torch.cuda.get_device_name(0))
        except Exception:
            pass
except Exception as e:
    print("PyTorch not importable yet:", e)
PRECHECK

print_info "Installing core packages via pip (no torch / cuda / python)"

pip install --upgrade pip setuptools wheel -q

pip install -q \
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
    gdown

print_success "Core Python packages installed"

print_info "Installing torch-scatter for PyTorch 2.0.1 + CUDA 11.8"
pip install -q torch-scatter -f https://data.pyg.org/whl/torch-2.0.1+cu118.html
print_success "torch-scatter installed"

print_info "Installing xformers 0.0.22.post7 for cu118 (NO torch reinstall, using --no-deps)"
pip install -q xformers==0.0.22.post7 --no-deps --index-url https://download.pytorch.org/whl/cu118
print_success "xformers installed"

print_info "=== VERSION CHECK AFTER xformers INSTALL ==="
python - << 'POSTCHECK'
import sys
print("Python:", sys.version.split()[0])
try:
    import torch
    print("PyTorch:", torch.__version__)
    print("CUDA available:", torch.cuda.is_available())
    if torch.cuda.is_available():
        print("CUDA version (torch):", torch.version.cuda)
        try:
            print("GPU:", torch.cuda.get_device_name(0))
        except Exception:
            pass
except Exception as e:
    print("PyTorch not importable:", e)
POSTCHECK

###############################################################################
# Step 5: Quick verification of PyTorch / CUDA / key deps
###############################################################################

print_step "5/7" "Verifying that PyTorch 2.0.1 + CUDA 11.8 are available in this env"

python - << 'PYCHECK'
import sys

def fail(msg: str) -> None:
    print(msg)
    sys.exit(1)

try:
    import torch
except Exception as e:
    fail(f"ERROR: Could not import torch inside env: {e}")

print("Python:", sys.version.split()[0])
print("PyTorch:", torch.__version__)

if not torch.__version__.startswith("2.0.1"):
    fail(f"ERROR: Torch version mismatch: {torch.__version__} (expected 2.0.1). "
         "Ensure your base container matches MegaSaM requirements.")

print("CUDA available:", torch.cuda.is_available())
if torch.cuda.is_available():
    print("CUDA version (torch):", torch.version.cuda)
    print("GPU:", torch.cuda.get_device_name(0))

for name in ["torch_scatter", "xformers"]:
    try:
        __import__(name)
        print(f"{name}: OK")
    except Exception as e:
        fail(f"ERROR: {name} import failed: {e}")

print("Environment verification passed.")
PYCHECK

print_success "Environment verification succeeded"

###############################################################################
# Step 6: Compile camera tracking extensions
###############################################################################

print_step "6/7" "Compiling camera tracking extensions (base/setup.py)"

cd "$INSTALL_DIR/base"
python setup.py install

print_success "Camera tracking extensions compiled and installed"

###############################################################################
# Step 7: Download checkpoints (Depth-Anything + RAFT)
###############################################################################

print_step "7/7" "Downloading required checkpoints"

cd "$INSTALL_DIR"

print_info "Preparing Depth-Anything checkpoint directory"
mkdir -p "$INSTALL_DIR/Depth-Anything/checkpoints"
cd "$INSTALL_DIR/Depth-Anything/checkpoints"

if [ ! -f "depth_anything_vitl14.pth" ]; then
    print_info "Downloading Depth-Anything checkpoint (~1.5 GB)..."
    if wget -q --show-progress \
        https://huggingface.co/spaces/LiheYoung/Depth-Anything/resolve/main/checkpoints/depth_anything_vitl14.pth; then
        print_success "Depth-Anything checkpoint downloaded"
    else
        print_error "Failed to download Depth-Anything checkpoint automatically."
        print_info "Please download manually from:"
        print_info "  https://huggingface.co/spaces/LiheYoung/Depth-Anything/blob/main/checkpoints/depth_anything_vitl14.pth"
        print_info "and place it at:"
        print_info "  $INSTALL_DIR/Depth-Anything/checkpoints/depth_anything_vitl14.pth"
    fi
else
    print_info "Depth-Anything checkpoint already present"
fi

print_info "Preparing RAFT checkpoint directory"
mkdir -p "$INSTALL_DIR/cvd_opt"
cd "$INSTALL_DIR/cvd_opt"

if [ ! -f "raft-things.pth" ]; then
    print_info "Downloading RAFT checkpoint (~250 MB) via gdown..."
    # Official link in README: https://drive.google.com/drive/folders/1sWDsfuZ3Up38EUQt7-JDTT1HcGHuJgvT
    # The file ID used here is the same as in the previous installer.
    if gdown "1JLdBfNpOYGpwI5YvFePLz5hWXqZXpxMR" -O raft-things.pth --quiet; then
        print_success "RAFT checkpoint downloaded"
    else
        print_error "Failed to download RAFT checkpoint automatically."
        print_info "Please download manually from the RAFT Google Drive folder and place it at:"
        print_info "  $INSTALL_DIR/cvd_opt/raft-things.pth"
    fi
else
    print_info "RAFT checkpoint already present"
fi

###############################################################################
# Final summary
###############################################################################

print_header "MegaSaM setup complete (dependencies only)"

echo "Repository path : $INSTALL_DIR"
echo "Env type        : $ENV_TYPE"
echo "Activate with   :"
echo "  $ENV_ACTIVATE_CMD"
echo ""
echo "Checkpoints:"
if [ -f "$INSTALL_DIR/Depth-Anything/checkpoints/depth_anything_vitl14.pth" ]; then
    print_success "Depth-Anything checkpoint is present"
else
    print_error "Depth-Anything checkpoint is MISSING"
fi

if [ -f "$INSTALL_DIR/cvd_opt/raft-things.pth" ]; then
    print_success "RAFT checkpoint is present"
else
    print_error "RAFT checkpoint is MISSING"
fi

echo ""
print_info "Next typical steps (inside the container):"
echo "  1) $ENV_ACTIVATE_CMD"
echo "  2) cd \"$INSTALL_DIR\""
echo "  3) Edit paths in scripts under mono_depth_scripts/, tools/, cvd_opt/ as needed"
echo "  4) Run, for example:"
echo "       ./mono_depth_scripts/run_mono-depth_demo.sh"
echo "       ./tools/evaluate_demo.sh"
echo "       ./cvd_opt/cvd_opt_demo.sh"
echo ""

