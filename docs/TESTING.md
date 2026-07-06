Testing Guide - GTA VI OS (Vice OS)
This document outlines the testing strategy for Vice OS, including how to run tests locally, what the CI pipeline checks, and guidelines for writing new tests.

🧪 Testing Strategy
Vice OS employs a multi-layered testing approach:

Unit Tests: Validate individual Python functions and classes (lib/python/).
Linting: Enforce code style and catch syntax errors in Bash and Python.
Integration Tests: Validate the structural integrity of the generated ISO.
Smoke Tests: Boot the ISO in a headless VM to verify it reaches a login prompt.
🏃 Running Tests Locally
Prerequisites
Python 3.12+
flake8 (Python linter)
shellcheck (Bash linter)
xorriso, qemu-system-x86_64 (For integration/smoke tests)
1. Python Unit Tests
Unit tests for core utilities are located in tests/test_vice_utils.py.

# Run all unit testspython3 -m unittest discover -s tests -p "test_*.py"
2. Linting
Linting ensures code quality and adherence to style guides (PEP 8 for Python, ShellCheck for Bash).
# Lint Python files
flake8 --ignore=E501,F401,F403 $(find . -name "*.py" -not -path "./.git/*")

# Lint Bash files
shellcheck $(find . -name "*.sh" -not -path "./.git/*")

Note: E501 (line too long) is ignored as it is often handled by formatters. F401/F403 are ignored in __init__.py for module exports.

3. ISO Validation
After building the ISO (sudo bash build_iso.sh), validate its structure:
bash tests/validate_iso.sh out/gta-vi-os-amd64.iso

4. QEMU Smoke Test
Boot the ISO headlessly to verify it reaches a login prompt:
bash tests/smoke_test_qemu.sh out/gta-vi-os-amd64.iso

⚙️ CI/CD Pipeline
GitHub Actions workflows automate the testing process on every push and pull request.

Workflows
.github/workflows/lint.yml: Runs ShellCheck, Flake8, and Python unit tests.
.github/workflows/ci.yml: Builds the ISO, runs ISO validation, and executes the QEMU smoke test.
📝 Writing New Tests
Python Unit Tests
Create a file named test_<module_name>.py in the tests/ directory.
Use the standard unittest framework.
Use unittest.mock to mock system calls (e.g., subprocess.Popen, file I/O) to ensure tests are deterministic and safe.
Ensure the file is discovered by the unittest discover command (must start with test_).
Bash Integration Tests
Place executable scripts in the tests/ directory.
Source lib/common.sh for access to logging and validation utilities.
Ensure the script exits with 0 on success and non-zero on failure.