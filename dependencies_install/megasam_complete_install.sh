#!/bin/bash
################################################################################
# MegaSaM Complete Installation Script for Vast.ai (Base Python Only)
#
# Project: MegaSaM - Accurate, Fast and Robust Structure and Motion from
#          Casual Dynamic Videos
#
# Fork repo: https://github.com/ShaneZHOU1994/mega-sam-custom.git
# Docs:      https://github.com/ShaneZHOU1994/mega-sam-custom/blob/main/README.md
#
# Base Image: vastai/pytorch:2.0.1-cuda-11.8.0-py310
#
# This script uses the BASE IMAGE's existing Python/PyTorch/CUDA setup:
#   - Python 3.10 (system Python)
#   - PyTorch 2.0.1 + CUDA 11.8 (already installed)
#   - Only installs xformers using conda method (per README)
#   - Does NOT create a conda environment (avoids reinstalling everything)
#
# This script:
#   1. Installs Miniconda (only for conda command to install xformers)
#   2. Clones fork repo with submodules
#   3. Installs xformers using conda method into conda base, then copies to system Python
#   4. Installs other Python dependencies via pip into system Python
#   5. Compiles camera tracking extensions using system Python
#   6. Downloads required checkpoints
#
# Usage:
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
REPO_URL="https://github.com/ShaneZHOU1994/mega-sam-custom.git"
CONDA_INSTALL_DIR="/root/miniconda3"
XFORMERS_TARBALL="xformers-0.0.22.post7-py310_cu11.8.0_pyt2.0.1.tar.bz2"
XFORMERS_URL="https://anaconda.org/xformers/xformers/0.0.22.post7/download/linux-64/${XFORMERS_TARBALL}"

print_header "MegaSaM Installation Script (Using Base Image Python)"
echo "Install dir      : $INSTALL_DIR"
echo "Repository      : $REPO_URL"
echo "Using Python     : $(command -v python3 || command -v python)"
echo "Conda install    : $CONDA_INSTALL_DIR (for xformers only)"

###############################################################################
# Step 1: Install basic system tools
###############################################################################

print_step "1/7" "Installing basic system tools"

if command -v apt-get >/dev/null 2>&1; then
    apt-get update -qq
    apt-get install -y -qq git wget unzip curl dos2unix build-essential bzip2 > /dev/null 2>&1 || true
else
    print_info "apt-get not available; assuming tools are already installed."
fi

print_success "Basic tools ready"

###############################################################################
# Step 2: Verify base Python/PyTorch setup
###############################################################################

print_step "2/7" "Verifying base Python/PyTorch setup"

# Determine Python command
if command -v python3 >/dev/null 2>&1; then
    PYTHON_CMD="python3"
elif command -v python >/dev/null 2>&1; then
    PYTHON_CMD="python"
else
    print_error "Python not found. Please ensure Python 3.10 is installed."
    exit 1
fi

print_info "Using Python: $PYTHON_CMD ($($PYTHON_CMD --version))"

# Verify PyTorch is installed
print_info "Checking PyTorch installation..."
$PYTHON_CMD - << 'PYCHECK'
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
    
    # Verify versions match requirements
    if not torch.__version__.startswith("2.0.1"):
        print(f"WARNING: PyTorch version {torch.__version__} may not match required 2.0.1")
    if torch.version.cuda != "11.8":
        print(f"WARNING: CUDA version {torch.version.cuda} may not match required 11.8")
except ImportError as e:
    print(f"ERROR: PyTorch not found: {e}")
    sys.exit(1)
PYCHECK

if [ $? -ne 0 ]; then
    print_error "PyTorch verification failed. Base image should have PyTorch 2.0.1 + CUDA 11.8."
    exit 1
fi

print_success "Base Python/PyTorch setup verified"

###############################################################################
# Step 3: Clone fork repository with submodules
###############################################################################

print_step "3/7" "Cloning fork repository with submodules"

if [ ! -d "$INSTALL_DIR" ]; then
    mkdir -p "$(dirname "$INSTALL_DIR")"
    cd "$(dirname "$INSTALL_DIR")"
    print_info "Cloning $REPO_URL..."
    git clone --recursive "$REPO_URL" "$(basename "$INSTALL_DIR")"
    print_success "Repository cloned into $INSTALL_DIR"
else
    print_info "Repository already exists at $INSTALL_DIR"
    cd "$INSTALL_DIR"
    git remote -v || true
    print_info "Updating submodules..."
    git submodule update --init --recursive
    print_success "Submodules updated"
fi

cd "$INSTALL_DIR"

###############################################################################
# Step 4: Install Miniconda (only for xformers installation)
###############################################################################

print_step "4/7" "Installing Miniconda (for xformers conda install only)"

if command -v conda >/dev/null 2>&1; then
    print_info "Conda already installed at: $(command -v conda)"
    CONDA_BASE=$(conda info --base 2>/dev/null || echo "$CONDA_INSTALL_DIR")
    print_success "Using existing conda at: $CONDA_BASE"
else
    print_info "Downloading Miniconda installer..."
    MINICONDA_INSTALLER="/tmp/miniconda.sh"
    wget -q https://repo.anaconda.com/miniconda/Miniconda3-latest-Linux-x86_64.sh -O "$MINICONDA_INSTALLER"
    
    print_info "Installing Miniconda to $CONDA_INSTALL_DIR..."
    bash "$MINICONDA_INSTALLER" -b -p "$CONDA_INSTALL_DIR" -u
    
    # Initialize conda
    "$CONDA_INSTALL_DIR/bin/conda" init bash >/dev/null 2>&1 || true
    
    print_success "Miniconda installed successfully"
    rm -f "$MINICONDA_INSTALLER"
fi

# Ensure conda is in PATH
if ! command -v conda >/dev/null 2>&1; then
    export PATH="$CONDA_INSTALL_DIR/bin:$PATH"
fi

# Initialize conda for this session
if [ -f "$CONDA_INSTALL_DIR/etc/profile.d/conda.sh" ]; then
    source "$CONDA_INSTALL_DIR/etc/profile.d/conda.sh"
fi

# Accept Anaconda Terms of Service
print_info "Accepting Anaconda Terms of Service for default channels..."
conda tos accept --override-channels --channel https://repo.anaconda.com/pkgs/main || true
conda tos accept --override-channels --channel https://repo.anaconda.com/pkgs/r || true

conda --version
print_success "Conda is ready (for xformers installation only)"

###############################################################################
# Step 5: Install xformers using conda method (per README)
###############################################################################

print_step "5/7" "Installing xformers using conda method (per README)"

# Check if xformers is already installed in system Python
if $PYTHON_CMD -c "import xformers" 2>/dev/null; then
    XFORMERS_VERSION=$($PYTHON_CMD -c "import xformers; print(xformers.__version__)" 2>/dev/null)
    print_info "xformers already installed in system Python: $XFORMERS_VERSION"
    print_success "xformers is ready"
else
    # Download xformers tarball
    XFORMERS_DOWNLOAD_PATH="/tmp/${XFORMERS_TARBALL}"
    if [ ! -f "$XFORMERS_DOWNLOAD_PATH" ]; then
        print_info "Downloading xformers prebuilt package..."
        wget -q --show-progress "$XFORMERS_URL" -O "$XFORMERS_DOWNLOAD_PATH"
        print_success "xformers tarball downloaded"
    else
        print_info "xformers tarball already exists, reusing..."
    fi
    
    # Install xformers into conda base environment first (per README)
    print_info "Installing xformers into conda base environment (per README)..."
    conda install "$XFORMERS_DOWNLOAD_PATH" -y --prefix "$CONDA_INSTALL_DIR"
    
    # Get system Python site-packages directory (ensure we use the actual system Python, not conda's)
    # Temporarily remove conda from PATH to ensure we get the right site-packages
    OLD_PATH="$PATH"
    export PATH=$(echo "$PATH" | tr ':' '\n' | grep -v "$CONDA_INSTALL_DIR" | tr '\n' ':' | sed 's/:$//')
    
    SYSTEM_SITE_PACKAGES=$($PYTHON_CMD -c "import sys; import site; print([p for p in site.getsitepackages() if 'conda' not in p.lower()][0] if any('conda' not in p.lower() for p in site.getsitepackages()) else site.getsitepackages()[0])" 2>/dev/null || \
                          $PYTHON_CMD -c "import sysconfig; print(sysconfig.get_path('purelib'))" 2>/dev/null || \
                          $PYTHON_CMD -c "import sys; print(sys.path[-1])" 2>/dev/null)
    
    export PATH="$OLD_PATH"
    
    # Fallback: try to infer from Python executable path
    if [ -z "$SYSTEM_SITE_PACKAGES" ] || [[ "$SYSTEM_SITE_PACKAGES" == *"conda"* ]]; then
        PYTHON_BIN_DIR=$(dirname "$($PYTHON_CMD -c 'import sys; print(sys.executable)')")
        if [[ "$PYTHON_BIN_DIR" == *"/venv/"* ]]; then
            # It's a venv, site-packages is typically ../lib/pythonX.X/site-packages
            SYSTEM_SITE_PACKAGES=$(dirname "$PYTHON_BIN_DIR")/lib/python$($PYTHON_CMD -c 'import sys; print(".".join(map(str, sys.version_info[:2])))')/site-packages
        elif [[ "$PYTHON_BIN_DIR" == *"/usr/"* ]]; then
            SYSTEM_SITE_PACKAGES="/usr/local/lib/python$($PYTHON_CMD -c 'import sys; print(".".join(map(str, sys.version_info[:2])))')/site-packages"
        else
            SYSTEM_SITE_PACKAGES="$PYTHON_BIN_DIR/../lib/python$($PYTHON_CMD -c 'import sys; print(".".join(map(str, sys.version_info[:2])))')/site-packages"
        fi
        SYSTEM_SITE_PACKAGES=$(readlink -f "$SYSTEM_SITE_PACKAGES" 2>/dev/null || echo "$SYSTEM_SITE_PACKAGES")
    fi
    
    print_info "System Python site-packages: $SYSTEM_SITE_PACKAGES"
    
    # Ensure directory exists
    mkdir -p "$SYSTEM_SITE_PACKAGES" || {
        print_error "Cannot create or access system Python site-packages directory"
        exit 1
    }
    
    # Install xformers into conda base environment first (per README)
    print_info "Installing xformers into conda base environment (per README)..."
    conda install "$XFORMERS_DOWNLOAD_PATH" -y --prefix "$CONDA_INSTALL_DIR"
    
    # Find xformers installation in conda
    # Conda installs packages to: $CONDA_INSTALL_DIR/lib/python3.X/site-packages/ or $CONDA_INSTALL_DIR/pkgs/package-name/lib/python3.X/site-packages/
    CONDA_XFORMERS_PATH=$(find "$CONDA_INSTALL_DIR" -name "xformers" -type d -path "*/site-packages/xformers" 2>/dev/null | grep -v "__pycache__" | grep -v ".pyc" | head -1)
    
    # If not found, check pkgs directory (conda package cache) - this is where conda extracts packages
    if [ -z "$CONDA_XFORMERS_PATH" ]; then
        print_info "Checking conda package cache..."
        CONDA_XFORMERS_PATH=$(find "$CONDA_INSTALL_DIR/pkgs" -name "xformers" -type d -path "*/site-packages/xformers" 2>/dev/null | head -1)
    fi
    
    # Also check if it was installed to conda's base lib
    if [ -z "$CONDA_XFORMERS_PATH" ]; then
        for pyver in python3.10 python3.11 python3.12 python3.13; do
            if [ -d "$CONDA_INSTALL_DIR/lib/$pyver/site-packages/xformers" ]; then
                CONDA_XFORMERS_PATH="$CONDA_INSTALL_DIR/lib/$pyver/site-packages/xformers"
                break
            fi
        done
    fi
    
    if [ -n "$CONDA_XFORMERS_PATH" ]; then
        print_info "Found xformers in conda at: $CONDA_XFORMERS_PATH"
        
        # Copy xformers to system Python site-packages
        print_info "Copying xformers to system Python site-packages..."
        if cp -r "$CONDA_XFORMERS_PATH" "$SYSTEM_SITE_PACKAGES/"; then
            print_success "xformers copied successfully"
            
            # Verify copy succeeded
            if [ ! -d "$SYSTEM_SITE_PACKAGES/xformers" ]; then
                print_error "Copy verification failed - xformers directory not found"
                CONDA_XFORMERS_PATH=""
            else
                # Also copy any xformers-related .so files from conda lib
                CONDA_LIB_DIR=$(dirname "$CONDA_XFORMERS_PATH" | xargs dirname)
                if [ -d "$CONDA_LIB_DIR" ]; then
                    print_info "Copying xformers shared libraries..."
                    find "$CONDA_LIB_DIR" -name "*xformers*.so*" -type f 2>/dev/null | while read -r lib_file; do
                        cp "$lib_file" "$SYSTEM_SITE_PACKAGES/" 2>/dev/null || true
                    done
                fi
            fi
        else
            print_error "Failed to copy xformers to system Python"
            print_info "Trying alternative: extracting from tarball..."
            CONDA_XFORMERS_PATH=""
        fi
    fi
    
    # If copying failed or xformers not found, extract from tarball
    if [ -z "$CONDA_XFORMERS_PATH" ] || ! $PYTHON_CMD -c "import xformers" 2>/dev/null; then
        print_info "Extracting xformers from conda tarball..."
        EXTRACT_DIR="/tmp/xformers_extract"
        mkdir -p "$EXTRACT_DIR"
        cd "$EXTRACT_DIR"
        tar -xjf "$XFORMERS_DOWNLOAD_PATH"
        
        # Conda package structure: info/, lib/python3.10/site-packages/xformers/
        PKG_DIR=$(find . -type d -path "*/lib/python*/site-packages" | head -1)
        if [ -n "$PKG_DIR" ] && [ -d "$PKG_DIR/xformers" ]; then
            print_info "Found xformers package in extracted tarball at: $PKG_DIR/xformers"
            # Manual copy is more reliable than pip install for conda packages
            print_info "Copying xformers from extracted package..."
            cp -r "$PKG_DIR/xformers" "$SYSTEM_SITE_PACKAGES/" || {
                print_error "Failed to copy xformers from extracted package"
                exit 1
            }
        else
            print_error "Could not find xformers package in extracted tarball"
            print_info "Tarball contents:"
            ls -la "$EXTRACT_DIR" || true
            exit 1
        fi
        
        cd - >/dev/null
        rm -rf "$EXTRACT_DIR"
    fi
    
    # Verify xformers installation in system Python
    # IMPORTANT: Remove conda from PATH to ensure we use system Python
    print_info "Verifying xformers installation in system Python..."
    
    # Save current directory
    ORIG_DIR=$(pwd)
    
    # Temporarily remove conda from PATH to get correct Python
    OLD_PATH="$PATH"
    export PATH=$(echo "$PATH" | tr ':' '\n' | grep -v "$CONDA_INSTALL_DIR" | tr '\n' ':' | sed 's/:$//')
    
    # Get absolute path to system Python (avoid conda's Python)
    # Use command -v with clean PATH to find the right Python
    ABS_PYTHON_CMD=$(command -v "$PYTHON_CMD" 2>/dev/null || echo "$PYTHON_CMD")
    
    # If it's still relative or contains conda, try to resolve it
    if [[ "$ABS_PYTHON_CMD" != /* ]] || [[ "$ABS_PYTHON_CMD" == *"conda"* ]]; then
        # Try to get it from Python itself (but with clean PATH)
        ABS_PYTHON_CMD=$($PYTHON_CMD -c "import sys; print(sys.executable)" 2>/dev/null || echo "$PYTHON_CMD")
    fi
    
    # Final fallback: resolve relative path
    if [[ "$ABS_PYTHON_CMD" != /* ]]; then
        ABS_PYTHON_CMD=$(cd "$ORIG_DIR" && command -v "$PYTHON_CMD" 2>/dev/null || echo "$PYTHON_CMD")
    fi
    
    # Ensure it's an absolute path
    if [[ "$ABS_PYTHON_CMD" != /* ]]; then
        # Last resort: construct from known locations
        if [ -f "/venv/main/bin/python3" ]; then
            ABS_PYTHON_CMD="/venv/main/bin/python3"
        elif [ -f "/usr/bin/python3" ]; then
            ABS_PYTHON_CMD="/usr/bin/python3"
        else
            ABS_PYTHON_CMD="$PYTHON_CMD"
        fi
    fi
    
    # Verify the Python executable exists
    if [ ! -f "$ABS_PYTHON_CMD" ]; then
        print_error "Cannot find Python executable: $ABS_PYTHON_CMD"
        print_info "Trying to locate Python..."
        which python3 || which python || print_error "Python not found in PATH"
        export PATH="$OLD_PATH"
        exit 1
    fi
    
    print_info "Using Python: $ABS_PYTHON_CMD"
    
    # Verify xformers is in the correct location
    if [ ! -d "$SYSTEM_SITE_PACKAGES/xformers" ]; then
        print_error "xformers directory not found at $SYSTEM_SITE_PACKAGES/xformers"
        cd "$ORIG_DIR"
        export PATH="$OLD_PATH"
        exit 1
    fi
    
    # Test import with explicit path priority
    cd "$ORIG_DIR"
    $ABS_PYTHON_CMD - << PYVERIFY
import sys
import os

# Ensure our site-packages is first in path
target_path = '$SYSTEM_SITE_PACKAGES'
if target_path not in sys.path:
    sys.path.insert(0, target_path)

# Remove any conda paths that might interfere
sys.path = [p for p in sys.path if 'conda' not in p.lower() or p == target_path]

# Verify we can import xformers
try:
    import xformers
    xformers_path = os.path.dirname(xformers.__file__)
    print(f'✓ xformers {xformers.__version__} verified')
    print(f'  Location: {xformers_path}')
    
    # Verify it's from our target location
    if target_path in xformers_path:
        print(f'✓ xformers is correctly installed in system Python')
    else:
        print(f'⚠ Warning: xformers imported from {xformers_path}, not {target_path}')
except Exception as e:
    print(f'✗ xformers import failed: {e}')
    print(f'  Python executable: {sys.executable}')
    print(f'  Python path (first 3): {":".join(sys.path[:3])}')
    print(f'  Target path exists: {os.path.exists(target_path + "/xformers/__init__.py")}')
    sys.exit(1)
PYVERIFY
    
    VERIFY_EXIT_CODE=$?
    cd "$ORIG_DIR"
    export PATH="$OLD_PATH"
    
    if [ $VERIFY_EXIT_CODE -ne 0 ]; then
        print_error "xformers verification failed"
        exit 1
    fi
    
    print_success "xformers installed successfully in system Python"
    
    # Clean up tarball
    rm -f "$XFORMERS_DOWNLOAD_PATH"
fi

# xformers verification already completed above - no need for duplicate check

###############################################################################
# Step 6: Install additional Python dependencies (into system Python)
###############################################################################

print_step "6/7" "Installing additional Python dependencies (system Python)"

# Remove conda from PATH to ensure we use system Python's pip
OLD_PATH_PIP="$PATH"
export PATH=$(echo "$PATH" | tr ':' '\n' | grep -v "$CONDA_INSTALL_DIR" | tr '\n' ':' | sed 's/:$//')

# Get absolute path to system Python
SYSTEM_PYTHON_ABS=$($PYTHON_CMD -c "import sys; print(sys.executable)" 2>/dev/null)
if [[ "$SYSTEM_PYTHON_ABS" == *"conda"* ]] || [ -z "$SYSTEM_PYTHON_ABS" ]; then
    SYSTEM_PYTHON_ABS=$(command -v "$PYTHON_CMD" 2>/dev/null || echo "$PYTHON_CMD")
fi

# Fallback to known locations
if [[ "$SYSTEM_PYTHON_ABS" != /* ]] || [[ "$SYSTEM_PYTHON_ABS" == *"conda"* ]]; then
    if [ -f "/venv/main/bin/python3" ]; then
        SYSTEM_PYTHON_ABS="/venv/main/bin/python3"
    elif [ -f "/usr/bin/python3" ]; then
        SYSTEM_PYTHON_ABS="/usr/bin/python3"
    else
        SYSTEM_PYTHON_ABS="$PYTHON_CMD"
    fi
fi

print_info "Using system Python: $SYSTEM_PYTHON_ABS"
print_info "Python version: $($SYSTEM_PYTHON_ABS --version)"

print_info "Upgrading pip, setuptools, wheel..."
$SYSTEM_PYTHON_ABS -m pip install --upgrade pip wheel 2>&1 | grep -v "WARNING: Running pip as the 'root' user" || true

# Ensure pkg_resources is available (required for torch.utils.cpp_extension)
# This is critical for compiling CUDA extensions with PyTorch
print_info "Verifying pkg_resources availability..."

# First check if it's already available
if $SYSTEM_PYTHON_ABS -c "import pkg_resources" 2>/dev/null; then
    print_success "pkg_resources is already available"
else
    print_info "pkg_resources not found, installing setuptools with pkg_resources support..."
    
    # Try multiple methods to ensure pkg_resources is installed
    
    # Method 1: Install setuptools < 70.0.0 (versions that include pkg_resources)
    print_info "Method 1: Installing setuptools < 70.0.0..."
    $SYSTEM_PYTHON_ABS -m pip install --upgrade --force-reinstall "setuptools>=65.0.0,<70.0.0" 2>&1 | grep -v "WARNING: Running pip as the 'root' user" || true
    
    if $SYSTEM_PYTHON_ABS -c "import pkg_resources" 2>/dev/null; then
        print_success "pkg_resources installed successfully (Method 1)"
    else
        # Method 2: Try installing setuptools without version constraint
        print_info "Method 1 failed. Method 2: Force reinstalling latest setuptools..."
        $SYSTEM_PYTHON_ABS -m pip install --upgrade --force-reinstall setuptools 2>&1 | grep -v "WARNING: Running pip as the 'root' user" || true
        
        if $SYSTEM_PYTHON_ABS -c "import pkg_resources" 2>/dev/null; then
            print_success "pkg_resources installed successfully (Method 2)"
        else
            # Method 3: Install specific known-good version
            print_info "Method 2 failed. Method 3: Installing setuptools 69.5.1..."
            $SYSTEM_PYTHON_ABS -m pip install --upgrade --force-reinstall "setuptools==69.5.1" 2>&1 | grep -v "WARNING: Running pip as the 'root' user" || true
            
            if $SYSTEM_PYTHON_ABS -c "import pkg_resources" 2>/dev/null; then
                print_success "pkg_resources installed successfully (Method 3)"
            else
                # Method 4: Last resort - try to install from system packages
                print_info "Method 3 failed. Method 4: Checking system packages..."
                if command -v apt-get >/dev/null 2>&1; then
                    apt-get update -qq
                    apt-get install -y -qq python3-setuptools python3-pkg-resources 2>&1 | grep -v "WARNING" || true
                fi
                
                if $SYSTEM_PYTHON_ABS -c "import pkg_resources" 2>/dev/null; then
                    print_success "pkg_resources installed successfully (Method 4 - system packages)"
                else
                    print_error "All methods failed to install pkg_resources."
                    print_error "This is required for compiling CUDA extensions with PyTorch."
                    echo ""
                    print_info "Diagnostic information:"
                    echo "  Python: $SYSTEM_PYTHON_ABS"
                    echo "  Python version: $($SYSTEM_PYTHON_ABS --version)"
                    echo "  Pip version: $($SYSTEM_PYTHON_ABS -m pip --version)"
                    echo ""
                    print_info "Checking what's installed:"
                    $SYSTEM_PYTHON_ABS -m pip list | grep -i setup || echo "  No setuptools found"
                    echo ""
                    print_info "Python path:"
                    $SYSTEM_PYTHON_ABS -c "import sys; print('\n'.join(sys.path))"
                    echo ""
                    print_error "Please try manually:"
                    echo "  1. $SYSTEM_PYTHON_ABS -m pip install --upgrade --force-reinstall setuptools"
                    echo "  2. $SYSTEM_PYTHON_ABS -c 'import pkg_resources; print(pkg_resources.__version__)'"
                    export PATH="$OLD_PATH_PIP"
                    exit 1
                fi
            fi
        fi
    fi
fi

# Final verification with detailed output
print_info "Final verification of pkg_resources..."
$SYSTEM_PYTHON_ABS -c "import pkg_resources; import setuptools; print('  setuptools:', setuptools.__version__); print('  pkg_resources: available')" 2>&1 | grep -v "DeprecationWarning"
print_success "pkg_resources is ready for CUDA extension compilation"

print_info "Installing additional packages into system Python..."
$SYSTEM_PYTHON_ABS -m pip install -q \
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

print_success "Additional Python packages installed"

# Restore PATH
export PATH="$OLD_PATH_PIP"

###############################################################################
# Step 7: Compile camera tracking extensions (using system Python)
###############################################################################

print_step "7/7" "Compiling camera tracking extensions (system Python)"

# Remove conda from PATH to ensure we use system Python
OLD_PATH_COMPILE="$PATH"
export PATH=$(echo "$PATH" | tr ':' '\n' | grep -v "$CONDA_INSTALL_DIR" | tr '\n' ':' | sed 's/:$//')

# Ensure SYSTEM_PYTHON_ABS is set (should be from previous step, but add fallback)
if [ -z "$SYSTEM_PYTHON_ABS" ] || [[ "$SYSTEM_PYTHON_ABS" == *"conda"* ]]; then
    SYSTEM_PYTHON_ABS=$(command -v "$PYTHON_CMD" 2>/dev/null || echo "$PYTHON_CMD")
    if [[ "$SYSTEM_PYTHON_ABS" != /* ]]; then
        if [ -f "/venv/main/bin/python3" ]; then
            SYSTEM_PYTHON_ABS="/venv/main/bin/python3"
        elif [ -f "/usr/bin/python3" ]; then
            SYSTEM_PYTHON_ABS="/usr/bin/python3"
        fi
    fi
fi

cd "$INSTALL_DIR/base"
print_info "Running setup.py install with $SYSTEM_PYTHON_ABS..."
$SYSTEM_PYTHON_ABS setup.py install

print_success "Camera tracking extensions compiled and installed"

# Restore PATH
export PATH="$OLD_PATH_COMPILE"

###############################################################################
# Step 8: Download required checkpoints
###############################################################################

print_step "8/8" "Downloading required checkpoints"

cd "$INSTALL_DIR"

# Depth-Anything checkpoint
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

# RAFT checkpoint
print_info "Preparing RAFT checkpoint directory"
mkdir -p "$INSTALL_DIR/cvd_opt"
cd "$INSTALL_DIR/cvd_opt"

if [ ! -f "raft-things.pth" ]; then
    print_info "Downloading RAFT checkpoint (~250 MB) via gdown..."
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
# Final summary and verification
###############################################################################

print_header "MegaSaM Installation Complete"

echo "Repository path : $INSTALL_DIR"
echo "Python command  : $PYTHON_CMD"
echo "Python path     : $($PYTHON_CMD -c 'import sys; print(sys.executable)')"
echo ""

# Version check
print_info "=== VERSION CHECK ==="
$PYTHON_CMD - << 'VERCHECK'
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
    print("PyTorch import error:", e)

try:
    import xformers
    print("xformers:", xformers.__version__)
except Exception as e:
    print("xformers import error:", e)
VERCHECK

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
print_info "Installation complete! All dependencies are installed in system Python."
print_info "No conda environment activation needed - just use python3/python directly."
echo ""
print_info "Next steps:"
echo "  1. Navigate to repository:"
echo "     cd $INSTALL_DIR"
echo ""
echo "  2. Edit paths in scripts as needed:"
echo "     - mono_depth_scripts/run_mono-depth_demo.sh"
echo "     - tools/evaluate_demo.sh"
echo "     - cvd_opt/cvd_opt_demo.sh"
echo ""
echo "  3. Run MegaSaM (using system Python):"
echo "     $PYTHON_CMD mono_depth_scripts/run_mono-depth_demo.sh"
echo "     $PYTHON_CMD tools/evaluate_demo.sh"
echo "     $PYTHON_CMD cvd_opt/cvd_opt_demo.sh"
echo ""
echo "  Or if scripts use shebang, just:"
echo "     ./mono_depth_scripts/run_mono-depth_demo.sh"
echo "     ./tools/evaluate_demo.sh"
echo "     ./cvd_opt/cvd_opt_demo.sh"
echo ""
