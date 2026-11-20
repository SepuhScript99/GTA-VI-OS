# AI Bootstrap

Version: 1.0

---

# Purpose

This document is the entry point for every AI session.

Its purpose is to ensure every AI contributor starts from the same understanding of the project before making any architectural or implementation decisions.

Do not skip this document.

---

# Repository Is The Source Of Truth

Do not rely on assumptions.

Do not rely on previous conversations.

Do not rely on memory.

Always use the repository as the authoritative source of information.

If documentation and implementation disagree, identify the discrepancy and resolve it.

---

# Reading Order

Complete the following steps before writing code.

## Step 1 — Understand The Project

Read:

- README.md
- PROJECT_STATUS.md
- ROADMAP.md
- TODO.md
- ARCHITECTURE.md
- CHANGELOG.md

Understand:

- project goals
- current development phase
- roadmap
- current priorities
- repository architecture
- recent changes

---

## Step 2 — Understand Engineering Standards

Read every document inside:

AI/

Recommended order:

1. Constitution.md
2. Principles.md
3. DecisionMaking.md
4. Architecture.md
5. Workflow.md
6. Coding.md
7. Context.md
8. Mission.md
9. Quality.md
10. Decision_Log.md
11. Technical_Debt.md
12. Repository_Health.md
13. Session_Handoff.md
14. Milestones.md

These documents define engineering expectations and repository standards.

---

## Step 3 — Inspect The Repository

Inspect the current implementation.

Understand:

- directory structure
- subsystem boundaries
- dependencies
- existing architecture
- implementation style

Never assume undocumented behavior.

---

## Step 4 — Determine Current Work

Determine:

- current mission
- current subsystem
- highest-priority task
- architectural risks
- technical debt

Use documentation together with the current implementation.

---

# Development Rules

During development:

- Respect existing architecture.
- Preserve compatibility whenever practical.
- Improve maintainability.
- Reduce technical debt.
- Prefer reusable solutions.
- Document important decisions.
- Avoid unnecessary complexity.
- Keep the repository consistent.

Never modify architecture without engineering justification.

---

# Development Loop

Repeat the following cycle.

1. Inspect
2. Plan
3. Implement
4. Review
5. Improve
6. Document
7. Continue

Do not stop after one completed file if meaningful work remains.

---

# Before Ending A Session

Always perform a final review.

Update documentation whenever necessary.

At minimum review and update:

- PROJECT_STATUS.md
- TODO.md
- CHANGELOG.md
- AI/Decision_Log.md
- AI/Session_Handoff.md

If architecture changed significantly, also update:

- ARCHITECTURE.md
- AI/Repository_Health.md
- AI/Technical_Debt.md
- AI/Milestones.md

Documentation is considered part of the implementation.

---

# Engineering Priorities

When multiple tasks are available, prioritize them in this order:

1. Broken builds
2. Security issues
3. Data loss or recovery
4. Validation
5. Testing
6. Reliability
7. Maintainability
8. Documentation
9. Performance
10. New features

Avoid adding features while critical engineering issues remain unresolved.

---

# Definition Of Done

A task is complete only when:

- implementation is correct
- architecture remains consistent
- documentation is updated
- compatibility is preserved
- validation is complete (when applicable)
- testing is updated (when applicable)
- technical debt has not increased without justification

---

# Mission

Your objective is not to maximize lines of code.

Your objective is to continuously improve Vice OS into a professional, maintainable, scalable, and well-documented Debian-based Linux distribution.

Leave the repository in a better state than you found it.