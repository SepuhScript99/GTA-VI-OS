# Technical Debt

Version: 1.0

---

## Purpose

Track known engineering debt.
Do not hide technical debt — document it, prioritize it.

---

# High Priority

None remaining.

---

# Medium Priority

None remaining.

---

# Low Priority

None remaining.

---

# Deferred

None intentionally deferred.

---

# Resolved

- Critical chroot_scripts ordering bug (06_cleanup.sh → 99_cleanup.sh)
- Syntax errors in 4 system_utils scripts (unclosed quotes, missing parentheses)
  - dependency_checker.sh: array closed with `]` instead of `)` (Decision 022)
  - input_manager.sh: missing `}` in `${2:-0` (Decision 022)
  - shortcut_manager.sh: missing `}` in `${5:-Utility;` (Decision 022)
  - wallpaper_manager.sh: invalid redirection inside `for` word list (Decision 022)
- **Critical runtime bug: bootstrap_script circular dependency** — ~70 scripts called `eval "$(bootstrap_script ...)"` before sourcing `lib/common.sh` (where bootstrap_script is defined), breaking every affected script at runtime. Migrated to a working shared-library preamble (Decision 021).
- **test_common_sh.sh aborting** — `test_bootstrap_returns_workdir` triggered `init_script`'s `exit 1` inside `$(...)` under `set -e`, killing the suite before results printed (Decision 023).
- Missing packages (thunar, stalonetray) in packages.list
- Firefox MIME associations (firefox.desktop → firefox-esr.desktop)
- Missing zram-setup.conf installation
- **Boilerplate migration**: All 69 scripts across system_utils (47), system_scripts (6), apps (3), recovery (4), validation (4), build (4), scripts (1) migrated from manual WORKDIR/source/cleanup to shared bootstrap_script() function — eliminated ~700 lines of duplicated code
- **GRUB defaults**: Verified already installed by 00_base_config.sh during chroot build
- **Dead configs**: vscode.list and docker.list documented as intentionally user-managed
- **System_utils test coverage**: tests/test_system_utils.sh with 9 tests (syntax, structure, migration) added to CI pipeline
- **Validation suite resilience**: `validation/run_all.sh` crashed under `pipefail` when `$ISODIR` was not yet created, and miscounted skipped validators. Fixed directory check and counter.
- **Validation trap hygiene**: `validation/validate_iso.sh` used repeated `trap ... EXIT` calls that clobbered `lib/common.sh` cleanup handlers and leaked earlier temp files. Consolidated into unified cleanup trap with `TEMP_FILES` / `TEMP_DIRS` arrays.
- **Recovery flock trap isolation**: In `rebuild_grub.sh`, `reset_password.sh`, `vice-recovery.sh`, and `reset_network.sh`, a secondary process failing flock unmounted `/mnt` of the running instance. Added `LOCKED` and `MOUNTED` state guards.
- **Recovery stdout pollution**: `select_disk_partition()` in `vice-recovery.sh` printed prompts to stdout, contaminating `$root_part`. Redirected prompts to stderr.
- **Debootstrap dirty retry**: `build/create_rootfs.sh` retrying failed with "Target directory is not empty". Added clean wipe and re-creation before each retry.
- **BIOS GRUB rescue drop**: `create_bootloader.sh` missing `search_fs_file`, `part_gpt`, `fat` modules in `grub-mkstandalone`. Modules embedded.
- **Installer safety & LUKS2 boot**: Added `is_live_media()` to prevent overwriting active media, and allocated dedicated 1024MB `/boot` partition under LUKS2.
- **Documentation drift**: All 19 documents in `docs/` and root governance files reconciled against current codebase.

---

## Notes

Technical debt should decrease over time.
Never ignore repeated problems.
