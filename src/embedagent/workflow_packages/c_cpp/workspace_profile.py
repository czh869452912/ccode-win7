from __future__ import annotations

import os
from typing import Dict, Tuple

_C_CPP_CODE_EXTENSIONS = {
    ".c",
    ".cc",
    ".cpp",
    ".cxx",
    ".h",
    ".hh",
    ".hpp",
    ".hxx",
}
_C_CPP_BUILD_FILE_NAMES = {"CMakeLists.txt", "Makefile", "makefile", "meson.build"}
_C_CPP_TEST_FILE_HINTS = ("test_", "_test", "_spec", "spec_")


class CCppWorkspaceProfileDetector(object):
    def detect_file(
        self,
        name: str,
        absolute_path: str,
        relative_root: str,
        root_name: str,
    ) -> Dict[str, bool]:
        del absolute_path, relative_root, root_name
        ext = os.path.splitext(name)[1].lower()
        lower_name = name.lower()
        is_code = name in _C_CPP_BUILD_FILE_NAMES or ext in _C_CPP_CODE_EXTENSIONS
        is_test = ext in _C_CPP_CODE_EXTENSIONS and any(
            hint in lower_name for hint in _C_CPP_TEST_FILE_HINTS
        )
        return {"code": is_code, "tests": is_test}


def c_cpp_workspace_profile_detectors() -> Tuple[CCppWorkspaceProfileDetector, ...]:
    return (CCppWorkspaceProfileDetector(),)
