# Vice OS AI Constitution

Version: 1.0

Last Updated: 2026-07-24

---

## Purpose

This document defines the highest-level governance for every AI contributing to Vice OS.

Every AI working on this repository must follow this Constitution before making architectural, implementation, documentation, or maintenance decisions.

This document has higher priority than temporary implementation goals.

---

# Vision

Vice OS is intended to become a professional Debian-based Linux distribution with a clean, modular, maintainable architecture.

The project should evolve gradually while remaining stable, understandable, and extensible.

The repository should always become healthier over time.

---

# Core Objectives

Every engineering decision should improve at least one of the following:

- Maintainability
- Reliability
- Scalability
- Readability
- Recoverability
- Testability
- Documentation
- Developer Experience

---

# Long-Term Philosophy

Assume the repository will eventually contain:

- hundreds of source files
- multiple contributors
- several years of development

Design for the future, not only for the current milestone.

---

# Authority

The AI is allowed to:

- create new files
- create new folders
- refactor code
- introduce reusable modules
- improve documentation
- improve architecture

when those changes are technically justified.

Never redesign the repository without strong engineering reasons.

---

# Compatibility

Always preserve compatibility whenever practical.

Avoid unnecessary breaking changes.

If a breaking change is required, document the reason.

---

# Continuous Improvement

Never assume the current implementation is optimal.

Every implementation may be improved if there is measurable engineering benefit.

---

# Repository First

The repository is the source of truth.

Never rely on assumptions.

Always inspect the current implementation before making decisions.

---

# Documentation

Documentation is part of the project.

Implementation without documentation is considered incomplete.

---

# End Goal

The goal is not merely to complete tasks.

The goal is to continuously improve Vice OS into a maintainable professional Linux distribution.