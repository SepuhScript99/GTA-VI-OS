Security Policy for GTA VI OS (Vice OS)
🛡️ Supported Versions
Vice OS is a rolling release based on Debian Bookworm. Security updates are applied automatically via the vp-autoupdate.timer systemd service. We support the latest stable release (v1.0+).

Version	Supported
1.0.x	:white_check_mark:
< 1.0	:x:
🔒 Built-in Security Features
Vice OS is designed with a secure-by-default posture for a desktop environment.

1. Network Security (UFW)
Default Policy: Deny all incoming, allow all outgoing.
Loopback: Explicitly allowed for desktop IPC.
Invalid Packets: Dropped persistently via /etc/ufw/before.rules for both IPv4 and IPv6.
Services: SSH (port 22) is rate-limited to prevent brute-force attacks. mDNS and Samba are allowed for local network discovery.
2. Kernel Hardening (sysctl.conf)
Memory: ZRAM is used for swap (vm.swappiness=100).
Networking: TCP SYN cookies, BBR congestion control, and source routing disabled. IP forwarding is enabled to support Docker.
Ptrace: kernel.yama.ptrace_scope=1 restricts process tracing to direct parents.
Symlinks: fs.protected_symlinks=1 and fs.protected_hardlinks=1 prevent standard privilege escalation vectors.
SysRq: Magic SysRq keys are restricted to safe sync/reboot operations only (kernel.sysrq=176).
3. User Privileges & Polkit
Live ISO: The vice user has passwordless sudo privileges for convenience.
Physical Install: The vp-installer.sh script enforces a password prompt for sudo and locks the root account by default.
Polkit: Users in the sudo group are granted administrative polkit privileges. Network management is delegated to the netdev group without requiring root passwords.
4. Service Isolation
Systemd services like vp-autoupdate.service are strictly sandboxed using ProtectSystem=strict, ProtectHome=true, and restricted CapabilityBoundingSet to minimize the attack surface if a compromised package attempts to escape.
🐛 Reporting a Vulnerability
We take the security of Vice OS seriously. If you believe you have found a security vulnerability, please report it to us.

DO NOT open a public GitHub issue.

Email your findings to security@vice-os-project.org (placeholder).
Provide a clear description of the issue, including steps to reproduce.
If possible, provide a Proof of Concept (PoC).
You should receive a response within 48 hours. If the vulnerability is accepted, we will work with you to patch it and coordinate a disclosure timeline.