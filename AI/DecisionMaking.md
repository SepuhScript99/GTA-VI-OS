# Engineering Decision Making

Version: 1.0

---

# Before Every Change

Before modifying any file, evaluate:

- current architecture
- subsystem boundaries
- dependencies
- maintainability
- testing
- validation
- recovery
- documentation

---

# Decision Questions

Ask yourself:

Is this the simplest correct solution?

Will another contributor understand this?

Will this scale?

Can responsibilities be separated?

Can code be reused?

Can failures be recovered?

Can this be tested?

Can this be validated automatically?

Can documentation be improved?

---

# Technical Debt

Continuously search for:

- duplicated code
- unnecessary complexity
- poor naming
- oversized files
- hidden dependencies
- missing validation
- missing testing

Whenever practical,

reduce technical debt.

---

# Architectural Decisions

Major architectural changes should include:

Reason

Expected Benefits

Possible Risks

Compatibility Impact

Files Affected

---

# Engineering Judgment

Do not blindly follow previous implementations.

If a better solution exists,

explain it,

then implement it.

---

# Quality Over Quantity

Never measure progress by:

- number of commits
- number of files
- lines of code

Measure progress by:

- architecture quality
- maintainability
- documentation
- reliability
- testing

---

# Continuous Review

Treat every completed task as an opportunity to improve the repository.

Always leave the project in a better state than before.