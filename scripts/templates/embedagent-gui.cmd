@echo off
setlocal EnableDelayedExpansion

:: EmbedAgent GUI Launcher for Windows 7 Portable Bundle
:: This script launches the PyWebView-based GUI frontend

set "BUNDLE_ROOT=%~dp0"
set "PYTHONHOME=%BUNDLE_ROOT%runtime\python"
set "PYTHONPATH=%BUNDLE_ROOT%app;%BUNDLE_ROOT%runtime\site-packages"

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

:: Check for WebView2 Runtime on Windows
if exist "%ProgramFiles(x86)%\Microsoft\EdgeWebView\Application\*" (
    echo Info: WebView2 Runtime detected
) else if exist "%LOCALAPPDATA%\Microsoft\EdgeWebView\Application\*" (
    echo Info: WebView2 Runtime detected (user install)
) else (
    echo Warning: WebView2 Runtime not detected
    echo GUI will use IE11 fallback mode on Windows 7
    echo For better experience, install WebView2 Runtime:
    echo https://developer.microsoft.com/microsoft-edge/webview2/
)

:: Launch GUI
"%PYTHONHOME%\python.exe" -m embedagent.frontend.gui.launcher %*
