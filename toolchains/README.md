# Bundled LLVM/Clang Toolchain

This directory hosts the project-local bundled LLVM/Clang toolchain used to keep the build environment self-contained.

Current active root:

- `toolchains/llvm/current`

Current composition:

- `clang.exe`, `clang++.exe`, `clang-cl.exe`: from `vovkos/llvm-package-windows` `clang-20.1.8-windows-amd64-msvc17-libcmt.7z`
- `clang-tidy.exe`: from `cpp-linter/clang-tools-static-binaries` `clang-tidy-20_windows-amd64.exe`
- `llvm-cov.exe`, `llvm-profdata.exe`, `lld-link.exe` and the broader LLVM bin set: from `c3lang/win-llvm` `llvm-21.1.8-windows-amd64-msvc17-libcmt.7z`
- `clang-analyzer.bat`: local wrapper that maps to `clang.exe --analyze`

Validated locally:

- `clang --version`
- `clang-tidy --version`
- `llvm-profdata --version`
- bare-command PATH injection through `ToolRuntime`
- compile object file with `clang`
- static analysis with `clang --analyze`
- `clang-tidy` run on a minimal C file
- end-to-end coverage flow: `clang -fprofile-instr-generate -fcoverage-mapping` -> `llvm-profdata merge` -> `llvm-cov report`

Important caveat:

- The current bundled root is a tested composite toolchain, not a single-vendor monolithic package.
- `clang`/`clang-tidy` are version 20.x, while `llvm-cov`/`llvm-profdata`/`clang_rt.profile.lib` come from 21.1.8.
- The local coverage smoke test passed, but this mixed-version setup should still be treated as provisional until it is validated on the real target C project and on Windows 7.
