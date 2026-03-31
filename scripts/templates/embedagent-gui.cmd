@echo off
setlocal EnableDelayedExpansion

:: EmbedAgent GUI Launcher for Windows 7 Portable Bundle
:: This script launches the PyWebView-based GUI frontend

set "BUNDLE_ROOT=%~dp0"
set "PYTHONHOME=%BUNDLE_ROOT%runtime\python"
set "PYTHONPATH=%BUNDLE_ROOT%app;%BUNDLE_ROOT%runtime\site-packages"
set "PYTHONNOUSERSITE=1"

:: Add bundled tools to PATH
set "PATH=%BUNDLE_ROOT%bin\git\cmd;%BUNDLE_ROOT%bin\rg;%BUNDLE_ROOT%bin\ctags;%BUNDLE_ROOT%bin\llvm\bin;%PATH%"

:: Set EmbedAgent home directory
if not defined EMBEDAGENT_HOME (
    set "EMBEDAGENT_HOME=%USERPROFILE%\.embedagent"
)

:: Check if Python exists
if not exist "%PYTHONHOME%\python.exe" (
    echo Error: Python runtime not found in %PYTHONHOME%
    echo Please ensure the bundle is complete.
    exit /b 1
)

:: Check for bundled Fixed Version WebView2 Runtime
if not exist "%BUNDLE_ROOT%runtime\webview2-fixed-runtime\msedgewebview2.exe" (
    echo Error: Bundled Fixed Version WebView2 runtime not found.
    echo GUI no longer falls back to IE11. Please use TUI/CLI or repair the bundle.
    exit /b 1
)

:: Launch GUI
"%PYTHONHOME%\python.exe" "%BUNDLE_ROOT%app\embedagent\frontend\gui\launcher.py" %*
