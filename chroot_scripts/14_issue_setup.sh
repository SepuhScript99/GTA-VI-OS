#!/bin/bash
set -Eeuo pipefail

# ============================================================================
# GTA VI OS (Vice OS) Chroot Script: Login Banner (issue) Setup
# Installs the custom /etc/issue and /etc/issue.net files for TTY branding.
# ============================================================================

# Source the shared library from the payload directory
if [ ! -f /vice_payload/lib/common.sh ]; then
    echo "Error: /vice_payload/lib/common.sh not found." >&2
    exit 1
fi
source /vice_payload/lib/common.sh

main() {
    log_info "Configuring TTY login banner (issue)..."

    local issue_src="/vice_payload/config/issue"

    if [ ! -f "$issue_src" ]; then
        log_error "issue file not found in payload! Aborting."
        exit 1
    fi

    # Install to /etc/issue (local TTY logins)
    cp "$issue_src" /etc/issue
    chown root:root /etc/issue
    chmod 644 /etc/issue

    # Install to /etc/issue.net (remote network logins via SSH)
    cp "$issue_src" /etc/issue.net
    chown root:root /etc/issue.net
    chmod 644 /etc/issue.net

    log_success "Login banner setup completed."
}

main "$@"