# Testing Guide - GTA VI OS (Vice OS)

This document outlines the testing strategy, test suites, local execution steps, and CI/CD quality gates for Vice OS.

---

## 🧪 Testing Strategy

Vice OS employs a multi-layered testing methodology to ensure distribution reliability:

1. **Python Unit Tests**: Validate shared library logic, system metrics, panel configuration, watchdog behavior, and process execution (`tests/test_vice_utils.py`).
2. **Bash Shared Library Tests**: Validate common Bash utilities, timestamp generation, retry loops, cleanup handlers, and command availability (`tests/test_common_sh.sh`).
3. **Integration Tests**: Verify cross-subsystem dependencies, desktop files, helper modules, recovery scripts, chroot scripts, Wayland stack, ARM64/RPi boot files, and login greeter (`tests/test_validation.sh`).
4. **System Utilities Tests**: Verify syntax, strict mode, shared library preambles, and category distribution across all 48 system utilities (`tests/test_system_utils.sh`).
5. **System Utilities Runtime Tests**: Validate function-level parameter enforcement, exit codes, and execution paths across all 48 utilities (`tests/test_system_utils_runtime.sh`).
6. **Artifact Validation Suite**: Deep structural and payload inspection of built packages, chroot rootfs, kernel, initramfs, and final ISO (`validation/run_all.sh`).
7. **Smoke Tests**: Headless QEMU virtual machine boot verification to ensure the system boots to a functional login prompt (`tests/smoke_test_qemu.sh`).

---

## 🏃 Running Tests Locally

### Prerequisites
- Python 3.10+
- `flake8` (Python linter)
- `shellcheck` (Bash linter)
- `xorriso`, `isoinfo` (for ISO inspection)
- `qemu-system-x86_64` (for VM smoke testing)

### 0. Master Test Suite Orchestrator (148+ automated tests in 8 suites)
Runs all 8 unit, structural, application, recovery, build, chroot, and integration test suites in a single command:
```bash
bash tests/run_all_tests.sh
```

### 1. Python Unit Tests (43 tests)
Unit tests for core Python utilities, desktop components, panel configuration, and watchdog:
```bash
python3 -m unittest discover -s tests -p "test_*.py"
```

### 2. Bash Shared Library Tests (11 tests)
Validates `lib/common.sh`:
```bash
bash tests/test_common_sh.sh
```

### 3. Cross-Subsystem Integration Tests (20 tests)
Validates configuration integrity, desktop modules, recovery tools, and sessions:
```bash
bash tests/test_validation.sh
```

### 4. System Utilities Structure Tests (9 tests)
Validates syntax and strict mode compliance across all 47 `system_utils/` scripts:
```bash
bash tests/test_system_utils.sh
```

### 5. System Utilities Runtime Tests (40+ tests)
Validates command parsing and runtime behavior:
```bash
bash tests/test_system_utils_runtime.sh
```

### 6. Apps & Installer Tests (21 tests)
Validates live installer partition safety, LUKS2/boot, chpasswd stdin security, and post-install hooks:
```bash
bash tests/test_apps.sh
```

### 7. Recovery Tool Suite Tests (19 tests)
Validates TUI recovery, GRUB rebuild, network reset, and flock concurrency protection:
```bash
bash tests/test_recovery_suite.sh
```

### 8. Build Pipeline Tests (13 tests)
Validates debootstrap clean-retry, ARM64 cross-architecture support, virtual filesystem mounts, and reproducibility:
```bash
bash tests/test_build_pipeline.sh
```

### 9. Chroot Scripts & Configuration Tests (12 tests)
Validates all 49 chroot scripts, shebangs, audio package compatibility, XML validity, autostart references, and ARM64 configs:
```bash
bash tests/test_chroot_scripts.sh
```

### 10. Artifact Validation Suite (6 validators)
Executes package list, rootfs, kernel, initramfs, and ISO validators:
```bash
# Run full suite (skips chroot/ISO tests if not yet built)
bash validation/run_all.sh

# Run standalone validators directly
bash validation/validate_packages.sh
bash validation/validate_rootfs.sh /path/to/chroot
bash validation/validate_kernel.sh /path/to/chroot
bash validation/validate_initramfs.sh /path/to/chroot
bash validation/validate_iso.sh out/gta-vi-os-amd64.iso
```

### 11. Linting & Static Analysis
```bash
# Lint Python files
flake8 --ignore=E501,F401,F403 $(find . -name "*.py" -not -path "./.git/*")

# Lint Bash files
shellcheck $(find . -name "*.sh" -not -path "./.git/*")
```

### 12. QEMU Smoke Test
Boot the ISO headlessly to verify it reaches a login prompt:
```bash
bash tests/smoke_test_qemu.sh out/gta-vi-os-amd64.iso
```

---

## ⚙️ CI/CD Pipeline

The project uses GitHub Actions workflows to enforce quality gates on every push and pull request:

- **`.github/workflows/lint.yml`**: Runs ShellCheck, Flake8, and static analysis (YAML, JSON, trailing whitespace, file permissions).
- **`.github/workflows/ci.yml`**: Full pipeline:
  1. Runs unit tests and integration tests.
  2. Runs system utilities runtime tests.
  3. Builds the ISO using `build_iso.sh`.
  4. Runs ISO validation (`validation/validate_iso.sh` and `tests/validate_iso.sh`).
  5. Executes the headless QEMU smoke test.
  6. Publishes build artifacts (`.iso`, `.sha256`, `build_info.txt`).

---

## 📝 Writing New Tests

### Python Unit Tests
- Create or update test cases in `tests/test_vice_utils.py` or new `tests/test_*.py` files.
- Use Python's standard `unittest` framework.
- Mock external subprocesses and file I/O with `unittest.mock` to maintain deterministic behavior.

### Bash Integration & Runtime Tests
- Integration tests belong in `tests/test_validation.sh`.
- Runtime parameter tests belong in `tests/test_system_utils_runtime.sh`.
- Source `lib/common.sh` for unified logging and strict error handling (`set -Eeuo pipefail`).
- Clean up any temporary files created during testing using `install_cleanup` or custom traps.
