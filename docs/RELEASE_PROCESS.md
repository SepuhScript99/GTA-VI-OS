Release Process - GTA VI OS (Vice OS)
This document outlines the step-by-step process for cutting a new stable release of Vice OS.

🚀 Pre-Release Checklist
Update Version Numbers:
Update VERSION and VERSION_ID in config/os-release.
Update DISTRIB_RELEASE in config/lsb-release.
Update the version string in desktop/login.py (if hardcoded).
Ensure docs/CHANGELOG.md is updated with the new version and release date.
Run Local Tests:
Run all unit tests: python3 -m unittest discover -s tests -p "test_*.py"
Run linters: flake8 and shellcheck.
Clean Build:
Perform a clean build to ensure no stale artifacts affect the release:
sudo bash build_iso.sh --clean
Verify the ISO:
Validate ISO structure: bash tests/validate_iso.sh out/gta-vi-os-amd64.iso
Run QEMU smoke test: bash tests/smoke_test_qemu.sh out/gta-vi-os-amd64.iso
Manually test in VMware/VirtualBox (boot, login, test apps, run installer).
📦 Release Steps
Create Release Branch (Optional but recommended for major versions):
git checkout -b release/v1.0git push origin release/v1.0
Merge to Main:Ensure all release prep changes are merged into the main branch.
Tag the Release:
git tag -a v1.0.0 -m "Release v1.0.0 Stable"git push origin v1.0.0
Create GitHub Release:
Go to the GitHub repository -> Releases -> Draft a new release.
Select the tag created in the previous step.
Title the release (e.g., v1.0.0 Stable).
Copy the relevant changelog entries from docs/CHANGELOG.md into the release description.
Upload the following artifacts from the out/ directory:
gta-vi-os-amd64.iso
SHA256SUMS
build_info.txt
Publish the release.
Post-Release Announcement:
Announce the release on official channels (forums, social media, website).
Update the project website to link to the new ISO.
🛠️ CI/CD Pipeline Role
The .github/workflows/ci.yml workflow will automatically trigger on the tag push. It will:

Build the ISO from scratch.
Run the validation and smoke tests.
Upload the final ISO as a workflow artifact.
If the CI pipeline fails, the release tag should be considered broken. Delete the tag, fix the issues, and start the release steps again.