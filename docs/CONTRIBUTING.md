Contributing to GTA VI OS (Vice OS)
First off, thank you for considering contributing to Vice OS! It’s people like you that make the open-source community great.

This document outlines the guidelines and architectural rules for contributing to the project. Adhering to these rules ensures that Vice OS remains maintainable, modular, and stable as it scales.

🏗️ Architecture & Single Responsibility Principle (SRP)
Vice OS strictly follows the Single Responsibility Principle (SRP). No file should contain multiple unrelated responsibilities. If a script handles partitioning, it should not also handle package installation.

Build Pipeline: Orchestration is handled by build_iso.sh, which delegates to modular scripts in build/.
Chroot Configuration: Orchestration is handled by chroot_setup.sh, which delegates to numbered scripts in chroot_scripts/ (e.g., 00_base_config.sh, 01_install_packages.sh).
Shared Libraries: All reusable logic must be placed in lib/common.sh (Bash) or lib/python/vice_utils.py (Python). Do not duplicate logging or validation functions.
🛠️ Development Guidelines
Bash Scripts
Strict Mode: Every script MUST start with set -Eeuo pipefail.
Error Trapping: Every script MUST register a trap cleanup EXIT SIGINT SIGTERM function to safely unmount filesystems or remove temporary files.
Shared Library: Source the common library at the top of your script:
if [ ! -f "$WORKDIR/lib/common.sh" ]; then    echo "Error: lib/common.sh not found." >&2    exit 1fisource "$WORKDIR/lib/common.sh"
Validation: Use check_root, check_dependencies, and check_internet from the shared library.
Logging: Use log_info, log_success, log_warn, and log_error. Do not use raw echo for status updates.
Python Scripts
PEP 8: All Python code must be PEP 8 compliant.
Shared Library: Import shared utilities from vice_utils:
sys.path.insert(0, '/opt/vice-os/lib')
from python.vice_utils import log_info, log_error, launch_command

Type Hinting: Use type hints for function arguments and return values where possible.
Qt Style Sheets (QSS)
Qt Specification: Only use properties and selectors supported by Qt6 Style Sheets. Do not use unsupported CSS properties.
Linter Clean: The .qss files must produce ZERO syntax warnings in Visual Studio Code.
📦 Adding Software
To add a new package to the OS:

Open config/packages.list.
Add the package name on a new line under the appropriate category comment.
Do not add packages directly via apt-get install in the chroot scripts unless there is a specific ordering dependency (like live-boot needing to be installed before the kernel).
🧪 Testing & Validation
Before submitting a Pull Request, you must ensure your changes pass the validation and testing layers.

1.Build the ISO: sudo bash build_iso.sh --clean
2.Validate Structure: bash tests/validate_iso.sh out/gta-vi-os-amd64.iso
3.Smoke Test (QEMU): bash tests/smoke_test_qemu.sh out/gta-vi-os-amd64.iso

Note: This requires qemu-system-x86_64 installed on your host.
🔄 Pull Request Process
Ensure your code passes all local tests mentioned above.
Ensure your code does not introduce any new linting warnings (ShellCheck for Bash, VS Code linter for QSS/Python).
Update the README.md and docs/ with details of any changes to the architecture or new features.
Submit your Pull Request targeting the main branch. GitHub Actions CI will automatically build and test your PR. It must pass CI to be merged.
🚀 Maturity Model
When adding a new feature (e.g., a new recovery tool), ensure it fulfills all layers of the Maturity Model:

Implementation: The script itself.
Configuration: Any required config files in config/.
Validation/Testing: Add tests to tests/ if applicable.
Recovery: Consider if the feature needs a recovery utility in recovery/.
Documentation: Document the feature in docs/ or README.md.
Thank you for your contribution!