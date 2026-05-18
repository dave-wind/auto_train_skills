# Planning — Gate 2 Execution Methodology

The goal of this gate is to turn an approved approach into a concrete, executable sequence
where each step produces a verifiable deliverable.

## Step Sizing

The right step size matters. Too big = hard to verify. Too small = overhead without value.

**Good step**: Creates one coherent unit of work that can be independently verified.
- "Add the `/api/users` endpoint with input validation" (one endpoint, one deliverable)
- "Write migration for new `user_settings` table" (one file, one schema change)

**Bad step**: Either too vague or too granular.
- "Handle the backend" (too big, no specific deliverable)
- "Import the `uuid` library" (too small, not a meaningful unit)

Rule of thumb: if you can't write a single verification command for a step, it's too big.
If the step doesn't produce a file or a testable behavior, it's too vague.

## Dependency Analysis

Not everything has to be sequential. Identify what can run in parallel.

### Dependency patterns

```
Sequential (must wait):
  Step 1: Create DB schema
  Step 2: Write model functions using that schema  ← depends on Step 1

Parallel (can run simultaneously):
  Step 2a: Write API endpoint    ← depends on Step 1, but not on 2b
  Step 2b: Write frontend form   ← depends on Step 1, but not on 2a
  Step 3:  Integration test      ← depends on both 2a and 2b
```

### Output format

```
## Execution Plan

- [ ] Step 1: [deliverable] — depends on: none
- [ ] Step 2a: [deliverable] — depends on: Step 1
- [ ] Step 2b: [deliverable] — depends on: Step 1
- [ ] Step 3: [deliverable] — depends on: Step 2a, Step 2b
```

Use `TaskCreate` to create these as tasks with proper dependencies (`addBlockedBy`).

## Handling Uncertainty

If a step has unknown complexity, flag it:

```
- [ ] Step 3: Integrate with payment provider API — depends on: Step 2
  ⚠ Uncertainty: API docs haven't been checked yet. May split into sub-steps after reading docs.
```

Don't pretend you know everything upfront. Honest uncertainty is better than
a plan that falls apart at step 3.

## What the Plan Is Not

- It's not a design doc — that was Gate 1's job
- It's not a commitment to exact line counts or hours — it's a sequence of deliverables
- It can change — if step 2 reveals that step 3 needs rethinking, say so and propose a revision
