@echo off
REM Export poses CSV to FBX for Unreal Engine 5.
REM Run from repo root (e.g. open cmd with admin if needed, then):
REM   cd /d D:\PyProjects\mega-sam-custom
REM   data_export\run_export_fbx.bat plaza_csv\poses.csv plaza_camera.fbx

set REPO_ROOT=%~dp0..
cd /d "%REPO_ROOT%"

if "%~1"=="" (
  echo Usage: %~nx0 poses_csv output_fbx [--fps 30]
  echo Example: %~nx0 plaza_csv\poses.csv plaza_camera.fbx --fps 30
  exit /b 1
)

python -m data_export.run_export_fbx %*
exit /b %ERRORLEVEL%
