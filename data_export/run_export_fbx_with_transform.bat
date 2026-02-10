@echo off
REM Transform poses CSV (Z-up, scale, reverse) and export to FBX for UE5.
REM Run from repo root (e.g. open cmd with admin if needed):
REM   cd /d D:\PyProjects\mega-sam-custom
REM   data_export\run_export_fbx_with_transform.bat input_poses.csv [output.fbx]
REM
REM Arguments:
REM   %1  Input poses CSV (required): frame_id, qw, qx, qy, qz, tx, ty, tz
REM   %2  Output FBX path (optional). Default: same dir as input, base name + _camera.fbx
REM
REM Optional env vars (set before running):
REM   TRANSFORM_SCALE   Path scale factor (default 0.01). E.g. set TRANSFORM_SCALE=0.1
REM   TRANSFORM_REVERSE 1 = reverse path (default), 0 = keep original direction
REM   EXPORT_FPS        Frame rate for FBX (default 30)

set REPO_ROOT=%~dp0..
cd /d "%REPO_ROOT%"

if "%~1"=="" (
  echo Usage: %~nx0 input_poses.csv [output.fbx]
  echo Example: %~nx0 plaza_10s_csv\poses.csv plaza_10s_camera.fbx
  echo Example: %~nx0 my_poses\poses.csv
  echo Optional: set TRANSFORM_SCALE=0.1  set TRANSFORM_REVERSE=0  set EXPORT_FPS=24
  exit /b 1
)

set "INPUT_CSV=%~1"
set "OUTPUT_FBX=%~2"
set "TRANSFORMED_CSV=%~dpn1_ue5.csv"

if "%OUTPUT_FBX%"=="" set "OUTPUT_FBX=%~dpn1_camera.fbx"

if not defined TRANSFORM_SCALE set TRANSFORM_SCALE=0.01
if not defined TRANSFORM_REVERSE set TRANSFORM_REVERSE=1
if not defined EXPORT_FPS set EXPORT_FPS=30

if not exist "%INPUT_CSV%" (
  echo Error: input CSV not found: %INPUT_CSV%
  exit /b 1
)

echo Step 1: Transform trajectory (swap-yz, scale=%TRANSFORM_SCALE%, reverse=%TRANSFORM_REVERSE%)...
if "%TRANSFORM_REVERSE%"=="1" (
  python -m data_export.trajectory_control "%INPUT_CSV%" "%TRANSFORMED_CSV%" --swap-yz --scale %TRANSFORM_SCALE% --reverse
) else (
  python -m data_export.trajectory_control "%INPUT_CSV%" "%TRANSFORMED_CSV%" --swap-yz --scale %TRANSFORM_SCALE%
)
if errorlevel 1 exit /b 1

echo Step 2: Export FBX...
python -m data_export.run_export_fbx "%TRANSFORMED_CSV%" "%OUTPUT_FBX%" --fps %EXPORT_FPS%
exit /b %ERRORLEVEL%
