# Verification — Gate 3 Execution Methodology

The goal of this gate is simple: no step is "done" until there is evidence that it works.
This is the hardest gate to enforce because both AI and humans are biased toward
declaring completion prematurely.

## The Evidence Bar

Evidence must be **observable by the user**. If the user can't see it, it's not evidence.

### Levels of evidence (pick the strongest available)

| Level | Method | Example | When to use |
|-------|--------|---------|-------------|
| **L1: Automated test** | Run test suite | `pytest test_auth.py — 5/5 passed` | Always prefer this |
| **L2: Type/lint check** | Static analysis | `tsc — noEmit — 0 errors` | When no test covers it |
| **L3: Runtime check** | Run the code | `curl localhost:3000/api — 200 OK` | When tests don't exist yet |
| **L4: Manual inspection** | Show the output | `cat config.yaml` + explain what changed | Last resort |

For each step, use the highest level available. If L1 exists, don't fall back to L4.

## Evidence Format

For each completed step, present:

```
## Step X: [deliverable] — DONE

**Evidence:**
- Method: [test / type-check / runtime / manual]
- Ran: `[exact command]`
- Result: [pass/fail/0 errors/200 OK]
- Key output:
  ```
  [paste the relevant portion of output]
  ```
```

Keep the output trimmed to what matters. Don't paste 200 lines of test output —
show the summary line and any failures.

## What Counts as Evidence

### Acceptable
- Test suite output with pass/fail counts
- Compiler/type checker output with 0 errors
- HTTP response with status code and relevant body
- Screenshot of working UI (for frontend)
- `git diff` showing the changes + explanation of why they're correct
- Successful build output

### NOT Acceptable
- "I wrote the code and it should work"
- "The logic is correct" (without running it)
- "Tests should pass" (without running them)
- "I followed the pattern from [file]" (pattern-following is not verification)
- "No errors were introduced" (how do you know without checking?)

## Handling Failure

When verification fails:

1. **Report the failure immediately** — show the error output
2. **Fix the issue** — don't ask for permission to fix a bug you just found
3. **Re-verify** — run the same verification command again
4. **Only then mark done** — with the passing evidence

Do not hide failures. A step that passed on the third attempt with evidence of all
three runs is more trustworthy than a step that "passed first try" with no output.

## When Automated Verification Isn't Possible

Some changes can't be easily tested (config changes, documentation, infrastructure).

In these cases:
1. State why automated verification isn't available
2. Describe what manual check the user should perform
3. Ask: "Can you verify [specific thing] and confirm this step is done?"

The step remains in_progress until the user confirms.
