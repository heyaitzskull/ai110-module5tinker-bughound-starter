# BugHound Mini Model Card (Reflection)

---

## 1) What is this system?

**Name:** BugHound

**Purpose:** Analyze a Python snippet, propose a fix, and run reliability checks that decide whether the fix is safe to auto-apply or should go to a human.

**Intended users:** Students learning how agentic workflows and AI reliability guardrails fit together.

---

## 2) How does it work?

BugHound runs a five-step loop in `BugHoundAgent.run()`:

- **Plan:** logs that it will scan the code and propose a fix. The plan is fixed, not chosen per input.
- **Analyze:** finds issues. Uses simple heuristics offline, or Gemini when an API key is set.
- **Act:** proposes a rewrite. Again heuristic offline, or Gemini.
- **Test:** `assess_risk` scores the change from 0 to 100 and assigns a risk level.
- **Reflect:** if risk is low it marks the fix as auto-applyable, otherwise it recommends human review.

Heuristics do string and regex checks (print statements, bare except, TODO). Gemini reads the prompt files in `prompts/` and returns issues as JSON and a full rewritten file. If Gemini errors or returns something unparseable, the agent falls back to heuristics.

---

## 3) Inputs and outputs

**Inputs:** short Python functions from `sample_code/` — `cleanish.py`, `print_spam.py`, `flaky_try_except.py`, and `mixed_issues.py`. Shapes were small functions, some with try/except blocks and comments.

**Outputs:**

- **Issues:** Code Quality (print), Reliability (bare except), Maintainability (TODO), each with a severity.
- **Fixes:** swapping print for logging, expanding bare except, or returning the code unchanged.
- **Risk report:** a score, a level (low/medium/high), the reasons for each deduction, and an auto-fix yes/no.

Example: `cleanish.py` produced zero issues and no change. `mixed_issues.py` produced three issues and a high-risk report. `print_spam.py` produced one low issue but a multi-line rewrite.

---

## 4) Reliability and safety rules

**Rule: "much shorter" fix (`len(fixed) < len(original) * 0.5`)**
Checks whether the fix deleted a large chunk of code. This matters because a fix that quietly drops half the file usually removed real logic. False positive: a legitimate simplification that removes dead code gets flagged. False negative: it ignores a fix that *grows* the file, so over-editing slips through (this is the gap I fixed in Part 3).

**Rule: return statements removed (`"return" in original and "return" not in fixed`)**
Checks whether the fix stripped out all returns, which changes what the function gives back. False positive: it fires even if a return was legitimately replaced by a raise. False negative: it only catches total removal, so changing a return *value* or dropping one of several returns passes unnoticed.

---

## 5) Observed failure modes

1. **Over-editing with false confidence.** On `print_spam.py`, the heuristic fixer added an import and rewrote every print, growing 4 lines to 6, but the scorer rated it low risk and marked it auto-applyable. A structural rewrite was treated as safe.

2. **Substring false positives.** The analyzer flags issues by raw text search, so `print(` inside a comment or string would be reported as a print-statement issue even though nothing runs.

---

## 6) Heuristic vs Gemini comparison

We ran mostly in heuristic mode to protect the 20-request quota.

- Heuristics were consistent and predictable but shallow — they only catch the three patterns they are coded for and cannot judge intent.
- Gemini is expected to catch issues heuristics miss (logic bugs, unclear naming, missing edge cases) but its output is less reliable: it can return extra prose, skip the JSON structure, or rewrite more than asked. That is exactly why the agent wraps it in parse checks and a heuristic fallback.
- The risk scorer mostly matched intuition, except it was too relaxed about over-editing until we added the growth check.

---

## 7) Human-in-the-loop decision

BugHound should refuse to auto-fix when a change touches control flow, return values, or error handling — the parts most likely to silently change behavior.

- **Trigger:** any fix that adds/removes returns, alters except blocks, or grows the file past a threshold.
- **Where:** in `risk_assessor.py`, so the decision lives with the other risk signals.
- **Message:** "This fix changes control flow or error handling. Please review before applying."

---

## 8) Improvement idea

Add a "changed line count" signal to `assess_risk`: compare original and fixed line by line and lower the score when too many lines changed at once. It is a small addition but it directly measures how invasive a fix is, which the current rules only approximate.
