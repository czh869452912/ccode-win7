import unittest
from pathlib import Path

import pytest

pytestmark = pytest.mark.release

ROOT = Path(__file__).resolve().parents[1]
LAUNCHER_SOURCE = ROOT / "scripts" / "launcher" / "embedagent_gui_launcher.cpp"
BUILD_SCRIPT = ROOT / "scripts" / "build-gui-launcher.ps1"
PREPARE_SCRIPT = ROOT / "scripts" / "prepare-offline.ps1"
VALIDATE_SCRIPT = ROOT / "scripts" / "validate-offline-bundle.ps1"
DEPENDENCY_CHECKER = ROOT / "scripts" / "check-bundle-dependencies.py"


def read(path: Path) -> str:
    with open(path, "r", encoding="utf-8") as handle:
        return handle.read()


class TestGuiLauncherExeContract(unittest.TestCase):
    def test_launcher_source_is_thin_win32_process_launcher(self):
        source = read(LAUNCHER_SOURCE)

        self.assertLess(source.index("#include <windows.h>"), source.index("#include <shellapi.h>"))
        self.assertIn("CreateProcessW", source)
        self.assertIn("SetEnvironmentVariableW", source)
        self.assertIn("CommandLineToArgvW", source)
        self.assertIn("runtime\\\\python\\\\python.exe", source)
        self.assertIn("app\\\\embedagent\\\\frontend\\\\gui\\\\launcher.py", source)
        self.assertIn("runtime\\\\webview2-fixed-runtime\\\\msedgewebview2.exe", source)
        self.assertIn("EMBEDAGENT_BUNDLE_ROOT", source)
        self.assertIn("PYTHONNOUSERSITE", source)
        self.assertNotIn("ShellExecute", source)
        self.assertNotIn("PyInstaller", source)
        self.assertNotIn("Nuitka", source)

    def test_build_script_targets_gui_subsystem_launcher(self):
        script = read(BUILD_SCRIPT)

        self.assertIn("embedagent_gui_launcher.cpp", script)
        self.assertIn("embedagent-gui.exe", script)
        self.assertIn("/SUBSYSTEM:WINDOWS,6.01", script)
        self.assertIn("cl.exe", script)
        self.assertIn("clang-cl.exe", script)
        self.assertIn("EMBEDAGENT_LAUNCHER_CC", script)
        self.assertIn("vswhere.exe", script)
        self.assertIn("VsDevCmd.bat", script)
        self.assertIn("Microsoft.VisualStudio.Component.VC.Tools.x86.x64", script)
        self.assertIn("LauncherCompilerExitCode", script)

    def test_prepare_offline_stages_native_gui_launchers(self):
        script = read(PREPARE_SCRIPT)

        self.assertIn("GuiLauncherExePath", script)
        self.assertIn("gui_launcher_exe", script)
        self.assertIn("EmbedAgent.exe", script)
        self.assertIn("embedagent-gui.exe", script)
        self.assertIn("Generated embedagent.cmd, embedagent-tui.cmd, embedagent-gui.cmd", script)

    def test_validate_offline_bundle_requires_native_gui_launchers(self):
        script = read(VALIDATE_SCRIPT)

        self.assertIn("bundle.launcher.gui_exe_user", script)
        self.assertIn("bundle.launcher.gui_exe_cli", script)
        self.assertIn("dynamic.gui_launcher_exe_user", script)
        self.assertIn("dynamic.gui_launcher_exe_cli", script)
        self.assertIn("EmbedAgent.exe --help", script)
        self.assertIn("embedagent-gui.exe --help", script)
        self.assertIn("embedagent-gui.cmd --help", script)

    def test_dependency_checker_requires_native_gui_launchers(self):
        script = read(DEPENDENCY_CHECKER)

        self.assertIn('"EmbedAgent.exe"', script)
        self.assertIn('"embedagent-gui.exe"', script)
        self.assertIn('"embedagent-gui.cmd"', script)


if __name__ == "__main__":
    unittest.main()
