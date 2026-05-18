---
name: strict-flow
description: >
  Lightweight three-gate workflow (brainstorm → plan → verify) as a fast alternative
  to full superpowers ceremony. Use ONLY when the user explicitly says "strict flow",
  "strict mode", "强制流程", "严格模式", "quick flow", "快速流程", or "lightweight workflow".
  Do NOT trigger automatically — this is a user-opt-in mode for when superpowers feels
  too heavy (no worktree, no TDD enforcement, no subagent dispatching, no code review).
  Just three gates: lock intent, plan steps, verify with evidence.
---

# Strict Flow — Lightweight Gate Enforcement

This is the **fast lane** companion to superpowers. Use it when the user wants structured
delivery without the full ceremony (worktrees, TDD cycles, subagent dispatching, code reviews).

Superpowers handles the full methodology. This handles the minimum viable discipline.

**Invoking strict flow is a commitment to all three gates — not a suggestion.** Task
simplicity makes gates *faster*, not *optional*. Even a one-line refactor can benefit
from Gate 1 (spotting a better pattern), Gate 2 (catching edge cases in the plan),
and Gate 3 (confirming the change works). The user chose this mode because they want
structure — if they wanted raw speed without gates, they wouldn't have invoked
strict flow.

**Language rule (hard constraint, not style preference):** Mirror the user's language in
every gate output. If the user writes in Chinese, all gate responses are in Chinese. If
English, English. This applies even when referencing methodology files written in another
language. When in doubt, match the language of the most recent user message.

## When to Use This vs Superpowers

| Scenario | Use |
|----------|-----|
| New feature, full project, multiple files | **Superpowers** |
| Bug fix, small feature, quick refactor, prototype | **Strict Flow** |
| User said "strict flow" / "强制流程" / "快速流程" | **Strict Flow** |
| User said "use superpowers" / "full flow" | **Superpowers** |

## State Tracking

At the start of each message, silently determine the current state:

| Signal | Current Gate |
|--------|-------------|
| No approach proposed yet, or user just described a requirement | **Gate 1** |
| User approved an approach, no plan confirmed yet | **Gate 2** |
| User confirmed plan, implementation in progress | **Gate 3** |
| All steps verified with evidence | **Done** |

## Gate Routing

### Gate 1: Brainstorming (Intent Lock)

Read `references/brainstorm.md` for the full methodology.

Execute the brainstorming process. Identify the viable approaches.

**Always present the approaches you found.** Gate 1 must produce approach options
regardless of which one wins — skipping alternatives defeats the purpose of
brainstorming. Trivial implementation variants (different return values for the same
logic, swapping equivalent libraries) are details for Gate 2, not separate approaches.
Do not invent alternatives to pad the brainstorm, but do show the real ones.

**When one approach is clearly best:** present all approaches, state your recommendation
with reasoning, and proceed to Gate 2 — no user confirmation needed at Gate 1. You are
skipping the wait, not the presentation.

**When genuinely torn between approaches** with real trade-offs (speed vs. extensibility,
quick fix vs. proper refactor): present them with a recommended pick, then block:

> I recommend Approach A because [reason]. Which do you prefer?

**BLOCK.** Do not proceed to Gate 2 until the user picks.

### Gate 2: Planning (Decomposition)

Read `references/plan.md` for the full methodology.

Based on the approved (or self-selected) approach, create the execution plan. Present the
plan in the user's language, then block:

> Plan looks good to start? (or suggest changes)

**BLOCK.** Do not start coding until the user confirms the plan.

### Gate 3: Verification (Evidence-based Completion)

Implement each step. Before marking any step done, present evidence.

**Evidence minimum bar (inline — no reference file needed):** Evidence must be
**independently verifiable** — something the reader can check without trusting your word.
This means runnable code with actual output, a test result with pass/fail counts, or a
dry-run command with its real output. The evidence types listed here are the minimum bar,
not an à la carte menu — pick the strongest available and include enough detail for
independent verification. Pseudocode, descriptions, "it should work" statements, and
usage instructions without actual output do not count. If the step produces no observable
output, show the absence of errors as evidence (e.g., linter/type-check passing). For
operations involving elevated privileges or destructive actions, include a safety note
(permissions needed, dry-run command, or rollback steps).

No blocking point at Gate 3 — but no step is "completed" without evidence meeting this bar.

## Handling "just do it"

If the user says "just do it", "快速做", "skip the process", or similar — acknowledge
and compress each gate to its minimum viable form:

- Gate 1: Pick the most reasonable approach yourself, state why in one line, proceed
- Gate 2: Output the plan as a compact list, proceed without waiting
- Gate 3: **Full evidence required.** Compression means no waiting — it does not mean
  lower evidence. The same verification bar applies: runnable output, test results,
  or dry-run evidence. Descriptions without verifiable output don't count as evidence
  in any mode.

The only thing "just do it" skips is the user-approval wait. Evidence is never weakened.

## Relationship to Superpowers

If superpowers is installed and triggers during a strict-flow session, let superpowers
take over — it's the more complete methodology. Strict flow only runs when explicitly
chosen as the lightweight alternative.
