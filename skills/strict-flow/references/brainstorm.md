# Brainstorming — Gate 1 Execution Methodology

The goal of this gate is to prevent the most expensive mistake in software development:
building the wrong thing. Most AI-assisted development failures come from jumping to code
with an incomplete understanding of the problem.

## Step 1: Context Exploration

Before thinking about solutions, understand the landscape:

1. **Read the change area** — Find and read the files most likely to be affected.
   Use grep/find to locate relevant modules. Don't read everything — focus on the
   boundary where the new code will connect to existing code.

2. **Understand the data flow** — Trace how data moves through the change area.
   Where does input come from? Where does output go? What shape is it?

3. **Check for existing patterns** — Look for similar features already implemented.
   The codebase usually has a preferred way of doing things. Find it and follow it.

4. **Summarize in 2-3 sentences** — What exists now, what needs to change, where the
   new code plugs in. This summary forces you to be concrete about your understanding.

## Step 2: Clarifying Questions

Only ask questions that would actually change your approach. Don't ask questions
for the sake of appearing thorough.

**Good questions** (they change the implementation):
- "Should this support pagination or is the dataset always small?"
- "Is this an internal API or will external clients call it?"
- "Should we handle the case where [X] fails, or is that out of scope?"

**Bad questions** (they waste time):
- "Do you want me to use good variable names?" (obviously yes)
- "Should the code be tested?" (obviously yes)
- Questions that can be answered by reading the codebase yourself

If nothing is genuinely ambiguous, skip to approaches and note "No blocking questions —
requirement is clear enough to propose approaches."

## Step 3: Approach Proposals

Present 2-3 approaches. Each must have real trade-offs, not fake ones.

### Structure

```
### Approach A: [concise name]
- What: [one sentence on the core idea]
- Pros: [specific, concrete advantages]
- Cons: [specific, concrete costs/risks]
- Effort: [S/M/L relative to other approaches]
```

### What makes a good proposal

**Real trade-offs** mean you'd genuinely be uncertain which to pick without knowing
the user's priorities. If one approach is strictly better, you haven't found the real options.

Common legitimate trade-offs:
- Speed of implementation vs. extensibility
- Simplicity vs. performance at scale
- Consistency with existing patterns vs. better architecture
- Quick fix now vs. proper refactor that enables future work

### What to avoid

- Don't propose a "straw man" bad option just to fill the 2-3 slots
- Don't make all approaches essentially the same with minor naming differences
- Don't hide your preferred choice — state it with reasoning, but let the user decide
