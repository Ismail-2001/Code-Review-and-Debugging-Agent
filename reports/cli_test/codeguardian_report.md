# CodeGuardian Review Report

**Repository**: .
**Date**: 2026-06-08 19:10:25
**Quality Score**: 🟢██████████████████░░ **91.0/100**

---

## Executive Summary

| Metric | Value |
|--------|-------|
| Total Issues | **3** |
| 🔴 Critical | 0 |
| 🟠 High | 0 |
| 🟡 Medium | 3 |
| 🟢 Low | 0 |
| ℹ️ Info | 0 |

---

## Detailed Findings

### 🟡 1. Long Function

| Field | Value |
|-------|-------|
| **Severity** | `MEDIUM` |
| **File** | `src/main.py` |
| **Line** | `73` |

**Description**: Function 'review' is 61 lines long (>50). Long functions are harder to understand and test.

**Recommendation**: Extract helper functions from 'review'. Aim for functions under 20 lines.

---

### 🟡 2. Too Many Parameters

| Field | Value |
|-------|-------|
| **Severity** | `MEDIUM` |
| **File** | `src/main.py` |
| **Line** | `73` |

**Description**: Function 'review' has 9 parameters (>5). Hard to use correctly without documentation.

**Recommendation**: Consider using a parameter object or kwargs pattern for 'review'.

---

### 🟡 3. No Test Coverage

| Field | Value |
|-------|-------|
| **Severity** | `MEDIUM` |
| **File** | `src/main.py` |
| **Line** | `1` |

**Description**: File 'src\main.py' has no test coverage detected. No tests exercise this code.

**Recommendation**: Add unit tests for 'src\main.py'. Aim for >80% coverage.

---

## Quality Score Breakdown

| Category | Issues |
|----------|--------|
| pattern | 2 |
| testing | 1 |

---

*Report generated automatically by CodeGuardian*