# TRAINING-FEEDBACK — content-rewriter / iteration-1

> 本文件由 `make suggest` 自动生成，供 Claude 在对话中直接读取并协助改进 skill。
> 改完后运行 `make train SKILL=content-rewriter` 验证，`make diff SKILL=content-rewriter` 对比。

## Skill 文件位置

`/Users/dave.wind/dave/AI/auto_train_skills/skills/content-rewriter/`

改动前请先读该目录下的相关文件（SKILL.md 及 references/、agents/ 等）。

---

## 改进前必读：一手数据

**不要只依赖本文件的摘要和分析来改 SKILL.md。** 上面的失败模式分析是 LLM 基于摘要生成的，可能遗漏或误判。改动前必须阅读原始数据来验证你的判断：

1. **实际模型输出** — 看模型到底输出了什么，而不是 grader 的一句话摘要：
   `/Users/dave.wind/dave/AI/auto_train_skills/skill-training-framework/workspaces/content-rewriter/iteration-1/eval-*/with_skill/run-*/outputs/output.txt`

2. **逐条评分详情** — 看 grader 对每条 expectation 的判断依据和引用的证据：
   `/Users/dave.wind/dave/AI/auto_train_skills/skill-training-framework/workspaces/content-rewriter/iteration-1/grading/eval-*-with_skill-run-*.json`

3. **对比 iteration-1 的同类输出** — 确认退步/进步是真实的还是 grader 随机性：
   `/Users/dave.wind/dave/AI/auto_train_skills/skill-training-framework/workspaces/content-rewriter/iteration-（上一轮编号）/eval-*/with_skill/run-*/outputs/output.txt`

4. **benchmark.json 完整数据** — 含每个 run 的明细，不只看均值：
   `/Users/dave.wind/dave/AI/auto_train_skills/skill-training-framework/workspaces/content-rewriter/iteration-1/benchmark.json`

**工作方式**：先读 TRAINING-FEEDBACK.md 了解全局，再读上面的一手数据验证/修正你的判断，最后再改 SKILL.md。如果摘要说"模型没列方案"，去看实际输出确认是真的没列还是列了但格式不同。

---

## 当前训练状态

| 指标 | 值 |
|------|----|
| iteration | iteration-1 |
| with_skill pass_rate | 0.833 |
| without_skill pass_rate (baseline) | 0.958 |
| delta | -0.125 |

| Eval | Name | with_skill | without_skill | Δ |
|------|------|------------|---------------|---|
| 1 | concise-remove-redundancy | 0.75 | 1.00 | -0.25 |
| 2 | expand-with-sensory-details | 1.00 | 1.00 | +0.00 |
| 3 | formal-multi-claim-text | 0.50 | 1.00 | -0.50 |
| 4 | casual-without-exaggerating | 1.00 | 0.75 | +0.25 |
| 5 | professional-plain-text | 1.00 | 1.00 | +0.00 |
| 6 | creative-punchy-single-output | 0.75 | 1.00 | -0.25 |

---

## Failure Pattern Analysis

### Pattern 1: Output contains meta-commentary and process explanations
Affects: Eval 1 (1 expectation), Eval 3 (1 expectation)

The skill adds explanations of *what it did* alongside the actual rewrite — character counts, compression ratios, change summaries, before/after comparison tables.

- Eval 1: `（原文 130 字 → 47 字，精简至约 36%，去除了…等冗余修饰，合并了…表达。）`
- Eval 3: Includes a full `主要改写处理` table mapping original phrases to academic ones

**Why:** "第 3 步：输出" is completely empty — no guidance on output format at all. Meanwhile, the "故障排查" section explicitly instructs `改写前先复述原文核心含义，改写后对比确认`, which encourages the model to show its work. The model interprets "confirm by comparison" as "add a comparison section."

### Pattern 2: Multiple versions instead of a single definitive output
Affects: Eval 3 (1 expectation), Eval 6 (1 expectation)

The skill outputs 2-3 labeled alternatives (方案 A/B/C) instead of one best rewrite.

- Eval 3: Provides a formal rewrite plus a comparison table (effectively a second "version" of the content)
- Eval 6: `方案 A — 意境向`, `方案 B — 对比向`, `方案 C — 短句向`

**Why:** Nothing in the skill says to output a single result. The creative mode's `打破常规表达` combined with the absence of any output constraint leads the model to "be helpful" by offering choices. The examples in the skill each show exactly one output, but examples alone don't override the absence of an explicit instruction.

### Pattern 3: Markdown formatting when plain text is expected
Affects: Eval 3 (1 expectation)

The skill wraps output in markdown structures (bold headers, blockquotes, tables) when the eval expects a plain text paragraph.

- Eval 3: Uses `**正式学术版本（论文摘要风格）：**`, `> blockquote`, and a markdown table

**Why:** No output format constraint exists. Combined with Pattern 1, the model treats the response as a "document" rather than a direct text replacement. The skill's own SKILL.md uses heavy markdown, which the model mirrors in its output.

---

## Suggested Directions for SKILL.md

### 1. Add a clear output format principle
The skill should define what "done" looks like: a single block of rewritten text, nothing else. No headers wrapping it, no footnotes explaining it, no alternative versions. The output should be *ready to paste in place of the original*.

This directly addresses all three patterns. The current skill has an empty "第 3 步：输出" — filling it with an output discipline principle is the single highest-impact change.

### 2. Remove or reframe the troubleshooting section
The `故障排查` entry `改写前先复述原文核心含义，改写后对比确认` is actively harmful — it instructs the model to add comparison/verification content to the output. Either remove it entirely, or reframe it as an *internal* quality check (think, don't write).

### 3. Reinforce single-output discipline in mode descriptions
Each mode currently describes *how to rewrite* but not *what to output*. A single principle (not per-mode rules) that the skill should produce one best version is sufficient. Don't add per-mode output rules — that's overfitting.

---

## What NOT to Change

- **Mode definitions (concise/expand/formal/casual/professional/creative)** — these are working. The rewriting quality itself is good (evals 2, 4, 5 all pass). The problem is packaging, not content.
- **Examples** — the two examples in the skill each show exactly one clean output. They're correct signal; the issue is the instructions don't reinforce what the examples model.
- **The frontmatter and description** — trigger rate isn't the problem here; capability is.

---

## Overfitting Warnings

- **Don't add rules like "never use markdown" or "never use tables."** The issue is outputting meta-content alongside the rewrite, not markdown per se. A creative-mode rewrite for a blog post might legitimately use markdown. The principle should be about *outputting only the rewritten text*, not about banning specific formats.
- **Don't add per-eval fixes.** All three failures stem from the same root cause (no output format discipline). One principle change should fix all three.
- **The without_skill baseline is 0.958** — Claude *without* this skill produces cleaner output. The skill is adding harmful behavior, not failing to add helpful behavior. Any changes should *remove* instructions (the troubleshooting section) or *constrain* behavior (output format), not add more instructions.

---

## One-sentence diagnosis

The skill writes *about* the rewrite instead of just *being* the rewrite — it needs an output discipline principle and the removal of instructions that encourage meta-commentary.

---

## 验证命令

```bash
cd skill-training-framework
make train SKILL=content-rewriter   # 跑新一轮
make diff  SKILL=content-rewriter   # 对比前后 pass_rate
```
