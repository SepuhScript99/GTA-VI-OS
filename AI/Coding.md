# Coding Standards

Version: 1.0

---

# General

Write code for humans first.

Correctness is more important than cleverness.

Readability is preferred over brevity.

---

# Naming

Use descriptive names.

Avoid unnecessary abbreviations.

Directory names should describe responsibility.

---

# Shell

Follow POSIX when practical.

Use ShellCheck-compatible syntax.

Quote variables appropriately.

Avoid duplicated logic.

Prefer reusable helper functions.

---

# Python

Follow PEP 8.

Use clear function names.

Prefer small functions.

Separate responsibilities.

Avoid global state unless justified.

---

# Qt

Use Qt Style Sheets (QSS).

Do not use unsupported CSS features.

Organize UI logically.

---

# Configuration

Configuration belongs in config/.

Do not hardcode values that should be configurable.

---

# Documentation

Complex logic should be documented.

Public scripts should explain their purpose.

---

# Error Handling

Always prefer explicit error handling.

Meaningful error messages are required.

Recover gracefully whenever practical.

---

# Logging

Important operations should be logged.

Logs should help diagnose failures.

---

# Testing

Every important subsystem should eventually become testable.

---

# Validation

Inputs should be validated.

Build artifacts should be verified.

---

# Recovery

Failures should leave enough information for recovery whenever practical.

---

# Final Review

Before considering implementation complete,

review

Readability

Maintainability

Compatibility

Documentation

Testing

Validation

Recovery