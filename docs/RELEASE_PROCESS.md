# Release Process - GTA VI OS (Vice OS)

This document outlines the step-by-step process for cutting and publishing a new release of Vice OS.

---

## 🚀 Pre-Release Checklist

1. **Verify Version Identifiers**:
   - `config/os-release`: `VERSION` and `VERSION_ID`
   - `config/lsb-release`: `DISTRIB_RELEASE`
   - `docs/CHANGELOG.md` and root `CHANGELOG.md`: ensure unreleased changes are grouped under the release header with date.
2. **Execute Full Test Suite**:
   ```bash
   python3 -m unittest discover -s tests -p "test_*.py"
   bash tests/test_validation.sh
   bash tests/test_common_sh.sh
   bash tests/test_system_utils.sh
   bash tests/test_system_utils_runtime.sh
   bash tests/test_apps.sh
   bash tests/test_recovery_suite.sh
   ```
3. **Run Validation Suite**:
   ```bash
   bash validation/run_all.sh
   ```

---

## 📦 Automated Release with `scripts/release.sh`

The project includes an automated release script that executes pre-flight checks, clean builds, Git tagging, and GitHub Releases:

```bash
# Dry run: verifies tests and environment without cutting a release
bash scripts/release.sh v1.0.0 --dry-run

# Full release: builds ISO, verifies checksums, tags repository
bash scripts/release.sh v1.0.0
```

---

## 🛠️ Manual Release Steps

If performing a manual release:

1. **Clean Build**:
   ```bash
   sudo bash build_iso.sh --clean
   ```

2. **Verify the ISO**:
   ```bash
   bash validation/validate_iso.sh out/gta-vi-os-amd64.iso
   bash tests/smoke_test_qemu.sh out/gta-vi-os-amd64.iso
   ```

3. **Tag the Release**:
   ```bash
   git tag -a v1.0.0 -m "Release v1.0.0 Stable"
   git push origin v1.0.0
   ```

4. **Publish GitHub Release**:
   - Create a new release referencing tag `v1.0.0`.
   - Title: `Vice OS v1.0.0 Stable`.
   - Upload build artifacts from `out/`:
     - `gta-vi-os-amd64.iso`
     - `SHA256SUMS`
     - `build_info.txt`

---

## ⚙️ CI/CD Release Automation

Pushing a version tag (`v*`) automatically triggers the `.github/workflows/ci.yml` release job:
1. Rebuilds the ISO in a clean Debian container.
2. Runs all unit, integration, and smoke tests.
3. Automatically attaches `gta-vi-os-amd64.iso`, `SHA256SUMS`, and release notes to the GitHub Release.
