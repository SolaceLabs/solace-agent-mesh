@echo off
REM Copyright Solace Corporation
REM SPDX-License-Identifier: Apache-2.0

REM Windows build script. See build.sh for the Mac/Linux equivalent.
REM Cross-compiles to SAM_TOOL_TARGET_OS / SAM_TOOL_TARGET_ARCH. The arch
REM is a property of the deployment, not this toolset, so it is never
REM defaulted: sam config apply discovers it from the target platform and
REM exports it. For a manual build, set both env vars first.
setlocal
if "%SAM_TOOL_BUILD_OUT%"=="" set SAM_TOOL_BUILD_OUT=dist
if "%SAM_TOOL_TARGET_OS%"=="" ( echo SAM_TOOL_TARGET_OS must be set by sam config apply, or exported for a manual build ^(e.g. linux^) 1>&2 & exit /b 1 )
if "%SAM_TOOL_TARGET_ARCH%"=="" ( echo SAM_TOOL_TARGET_ARCH must be set by sam config apply, or exported for a manual build ^(e.g. amd64^) 1>&2 & exit /b 1 )
REM Default tracks the STR runtime container's Python (3.11).
if "%SAM_TOOL_PYTHON_VERSION%"=="" set SAM_TOOL_PYTHON_VERSION=3.11

set HOST_OS=windows
set HOST_ARCH=amd64
if /I "%PROCESSOR_ARCHITECTURE%"=="ARM64" set HOST_ARCH=arm64
if /I "%PROCESSOR_ARCHITEW6432%"=="ARM64" set HOST_ARCH=arm64
for /f "tokens=2 delims= " %%v in ('python3 --version 2^>^&1') do set HOST_PYTHON_RAW=%%v
for /f "tokens=1,2 delims=." %%a in ("%HOST_PYTHON_RAW%") do set HOST_PYTHON_VERSION=%%a.%%b

set PLATFORM_ARGS=
set NEED_PLATFORM=0
if /I not "%SAM_TOOL_TARGET_OS%-%SAM_TOOL_TARGET_ARCH%"=="%HOST_OS%-%HOST_ARCH%" set NEED_PLATFORM=1
if not "%HOST_PYTHON_VERSION%"=="%SAM_TOOL_PYTHON_VERSION%" set NEED_PLATFORM=1
if "%NEED_PLATFORM%"=="1" (
  if "%SAM_TOOL_TARGET_OS%-%SAM_TOOL_TARGET_ARCH%"=="linux-arm64"   set PLATFORM=manylinux2014_aarch64
  if "%SAM_TOOL_TARGET_OS%-%SAM_TOOL_TARGET_ARCH%"=="linux-amd64"   set PLATFORM=manylinux2014_x86_64
  if "%SAM_TOOL_TARGET_OS%-%SAM_TOOL_TARGET_ARCH%"=="darwin-arm64"  set PLATFORM=macosx_11_0_arm64
  if "%SAM_TOOL_TARGET_OS%-%SAM_TOOL_TARGET_ARCH%"=="darwin-amd64"  set PLATFORM=macosx_10_9_x86_64

  if "%PLATFORM%"=="" (
    echo unsupported target %SAM_TOOL_TARGET_OS%-%SAM_TOOL_TARGET_ARCH% >&2
    exit /b 1
  )
  set PLATFORM_ARGS=--platform "%PLATFORM%" --python-version "%SAM_TOOL_PYTHON_VERSION%" --only-binary=:all:
)

if not exist "%SAM_TOOL_BUILD_OUT%\python" mkdir "%SAM_TOOL_BUILD_OUT%\python"
python3 -m pip install --target "%SAM_TOOL_BUILD_OUT%\python" ^
  %PLATFORM_ARGS% ^
  --upgrade ^
  .
if errorlevel 1 exit /b %errorlevel%

copy /Y manifest.yaml "%SAM_TOOL_BUILD_OUT%\manifest.yaml" >nul
echo built %SAM_TOOL_TARGET_OS%/%SAM_TOOL_TARGET_ARCH% tool: %SAM_TOOL_BUILD_OUT%\python\bin\sla-clock
