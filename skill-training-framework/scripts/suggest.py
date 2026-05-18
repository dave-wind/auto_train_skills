"""Generate a training feedback document for a skill based on the latest training results.

Reads the latest benchmark + transcripts, calls claude -p to analyze failure patterns,
and writes TRAINING-FEEDBACK.md directly into skills/<name>/ so Claude can find it
next to SKILL.md in a conversation.

Output: skills/<name>/TRAINING-FEEDBACK.md
"""
import argparse
import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from utils import latest_iteration_dir, load_json, load_skill_md, previous_iteration_dir


ANALYSIS_PROMPT = """You are an expert at improving Claude Code skills (SKILL.md prompt files).

A skill is a SKILL.md file injected as a system prompt to guide Claude's behavior. Your job is to analyze training results and identify the ROOT CAUSES of failures — not to fix individual evals, but to find generalizable improvements.

# Current SKILL.md

```
{skill_md}
```

# Training Results — {skill_name} / {iteration}

## Summary
- with_skill pass_rate: {with_pr:.3f}{delta_str}
- without_skill pass_rate (baseline): {without_pr:.3f}
- delta (skill value): {delta}

## Per-Eval Results
{eval_table}

## Failed Expectations (with_skill)
{failed_with}

## Sample Transcripts (with_skill failures)
{transcripts}

---

# Your Task

Analyze the failures and produce a structured improvement suggestion document in this exact format:

## Failure Pattern Analysis

Group the failures into 2-4 root cause patterns. For each pattern:
- Name the pattern (e.g., "Gate interaction not enforced")
- Count how many evals / expectations it affects
- Quote 1-2 specific evidence snippets
- Explain WHY the current SKILL.md causes this (what instruction is missing, ambiguous, or misleading)

## Suggested Directions for SKILL.md

For each pattern, suggest a direction (NOT a specific rewrite — that's for the user to decide with Claude):
- What principle needs to be added/clarified/removed
- Why it would help (connect back to the failure evidence)
- What to avoid (overfitting risks)

## What NOT to change

List 2-3 things in the current SKILL.md that are working well and should be preserved.

## Overfitting Warnings

Flag any direction that risks overfitting to the current eval set rather than solving a general problem.

---

Rules for your analysis:
- Write principles, not rules. "The skill should explain WHY gates require user confirmation" not "Add: MUST wait for user before Gate 2"
- Think from the USER's perspective, not the skill author's
- If a failure looks like an eval quality issue (not a skill issue), say so explicitly
- Be concise — this document will be read by Claude in a fresh conversation to help improve SKILL.md"""


def collect_transcripts(iter_dir, max_evals=3, max_chars=800):
    """Collect with_skill transcripts for failed evals, truncated."""
    bench = load_json(iter_dir / "benchmark.json")
    # Use eval_summary to find failed evals
    eval_summary = bench.get("eval_summary", {})
    with_evals = {e["eval_id"]: e for e in eval_summary.get("with_skill", [])}

    failed_eval_ids = [
        eid for eid, e in with_evals.items() if e["pass_rate"] < 1.0
    ]
    # Fallback for old format
    if not with_evals:
        for r in bench["runs"]:
            if r["configuration"] == "with_skill" and r["result"]["pass_rate"] < 1.0:
                failed_eval_ids.append(r["eval_id"])

    snippets = []
    for eid in failed_eval_ids[:max_evals]:
        # Try new layout (run-1/transcript.md) then old layout
        t_file = iter_dir / f"eval-{eid}" / "with_skill" / "run-1" / "transcript.md"
        if not t_file.exists():
            t_file = iter_dir / f"eval-{eid}" / "with_skill" / "transcript.md"
        if not t_file.exists():
            continue
        text = t_file.read_text(encoding="utf-8")[:max_chars]
        snippets.append(f"### eval-{eid} (truncated)\n{text}\n[...]")

    return "\n\n".join(snippets) if snippets else "(no transcripts found)"


def format_eval_table(benchmark):
    """Format eval table, preferring eval_summary (averaged) over raw runs."""
    eval_summary = benchmark.get("eval_summary", {})
    with_evals = {e["eval_id"]: e for e in eval_summary.get("with_skill", [])}
    without_evals = {e["eval_id"]: e for e in eval_summary.get("without_skill", [])}

    if with_evals:
        lines = ["| Eval | Name | with_skill | without_skill | Δ |",
                 "|------|------|------------|---------------|---|"]
        for eid in sorted(set(list(with_evals.keys()) + list(without_evals.keys()))):
            ws = with_evals.get(eid)
            wo = without_evals.get(eid)
            ws_pr = ws["pass_rate"] if ws else 0
            wo_pr = wo["pass_rate"] if wo else 0
            name = (ws or wo).get("eval_name", "") if (ws or wo) else ""
            lines.append(f"| {eid} | {name} | {ws_pr:.2f} | {wo_pr:.2f} | {ws_pr - wo_pr:+.2f} |")
        return "\n".join(lines)

    # Fallback: old single-run format
    by_eval = {}
    for r in benchmark["runs"]:
        by_eval.setdefault(r["eval_id"], {})[r["configuration"]] = r

    lines = ["| Eval | Name | with_skill | without_skill | Δ |",
             "|------|------|------------|---------------|---|"]
    for eid in sorted(by_eval.keys()):
        ws = by_eval[eid].get("with_skill")
        wo = by_eval[eid].get("without_skill")
        ws_pr = ws["result"]["pass_rate"] if ws else 0
        wo_pr = wo["result"]["pass_rate"] if wo else 0
        name = (ws or wo)["eval_name"] if (ws or wo) else ""
        lines.append(f"| {eid} | {name} | {ws_pr:.2f} | {wo_pr:.2f} | {ws_pr - wo_pr:+.2f} |")
    return "\n".join(lines)


def format_failed(runs, config):
    """Format failed expectations, noting which runs failed for each."""
    by_eval = {}
    for r in runs:
        if r["configuration"] != config:
            continue
        eid = r["eval_id"]
        by_eval.setdefault(eid, {"name": r.get("eval_name", ""), "failed": {}})
        for e in r.get("expectations", []):
            if not e.get("passed"):
                text = e["text"]
                if text not in by_eval[eid]["failed"]:
                    by_eval[eid]["failed"][text] = []
                by_eval[eid]["failed"][text].append(
                    (r.get("run_number", 1), e.get("evidence", "").replace("\n", " ")[:200])
                )

    config_runs = [r for r in runs if r["configuration"] == config]
    multi_run = len(config_runs) > 0 and max(r.get("run_number", 1) for r in config_runs) > 1

    lines = []
    for eid in sorted(by_eval.keys()):
        info = by_eval[eid]
        if not info["failed"]:
            continue
        lines.append(f"**Eval {eid} ({info['name']})**")
        for text, failures in info["failed"].items():
            if multi_run:
                run_nums = sorted(set(fn[0] for fn in failures))
                total_runs = len([r for r in config_runs if r["eval_id"] == eid])
                runs_str = f" (run {', '.join(str(n) for n in run_nums)}, {len(run_nums)}/{total_runs} runs)"
            else:
                runs_str = ""
            evidence = failures[0][1]
            lines.append(f"- ✗ {text}{runs_str}")
            lines.append(f"  - evidence: {evidence}")
    return "\n".join(lines) if lines else "(none)"


def call_claude(prompt, timeout=360):
    try:
        result = subprocess.run(
            ["claude", "-p", prompt],
            capture_output=True, text=True, timeout=timeout,
        )
    except subprocess.TimeoutExpired:
        return None, f"claude -p timed out after {timeout}s"
    if result.returncode != 0:
        return None, f"claude -p failed (rc={result.returncode}): {result.stderr}"
    return result.stdout.strip(), None


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--skill-name", required=True)
    ap.add_argument("--skills-dir", required=True)
    ap.add_argument("--workspace-root", required=True)
    ap.add_argument("--timeout", type=int, default=360, help="Per-call timeout in seconds (default: 360)")
    args = ap.parse_args()

    iter_dir = latest_iteration_dir(args.workspace_root, args.skill_name)
    if not iter_dir:
        sys.exit(f"错误: 未找到 iteration，先运行 make train SKILL={args.skill_name}")

    bench_file = iter_dir / "benchmark.json"
    if not bench_file.exists():
        sys.exit("错误: 未找到 benchmark.json，先运行 make benchmark")

    benchmark = load_json(bench_file)
    skill_md = load_skill_md(args.skills_dir, args.skill_name)
    summary = benchmark["run_summary"]
    with_pr = summary["with_skill"]["pass_rate"]["mean"]
    without_pr = summary["without_skill"]["pass_rate"]["mean"]
    delta = summary["delta"]["pass_rate"]

    prev_dir = previous_iteration_dir(args.workspace_root, args.skill_name)
    delta_str = ""
    if prev_dir:
        prev_bench = prev_dir / "benchmark.json"
        if prev_bench.exists():
            prev_pr = load_json(prev_bench)["run_summary"]["with_skill"]["pass_rate"]["mean"]
            d = with_pr - prev_pr
            delta_str = f" (vs {prev_dir.name}: {d:+.3f})"

    print(f"==> 分析 {iter_dir.name} 的失败模式...")

    prompt = ANALYSIS_PROMPT.format(
        skill_md=skill_md,
        skill_name=args.skill_name,
        iteration=iter_dir.name,
        with_pr=with_pr,
        delta_str=delta_str,
        without_pr=without_pr,
        delta=delta,
        eval_table=format_eval_table(benchmark),
        failed_with=format_failed(benchmark["runs"], "with_skill"),
        transcripts=collect_transcripts(iter_dir),
    )

    analysis, err = call_claude(prompt, timeout=args.timeout)
    if err or analysis is None:
        sys.exit(f"错误: {err}")

    skill_dir = Path(args.skills_dir) / args.skill_name
    doc = f"""# TRAINING-FEEDBACK — {args.skill_name} / {iter_dir.name}

> 本文件由 `make suggest` 自动生成，供 Claude 在对话中直接读取并协助改进 skill。
> 改完后运行 `make train SKILL={args.skill_name}` 验证，`make diff SKILL={args.skill_name}` 对比。

## Skill 文件位置

`{skill_dir}/`

改动前请先读该目录下的相关文件（SKILL.md 及 references/、agents/ 等）。

---

## 改进前必读：一手数据

**不要只依赖本文件的摘要和分析来改 SKILL.md。** 上面的失败模式分析是 LLM 基于摘要生成的，可能遗漏或误判。改动前必须阅读原始数据来验证你的判断：

1. **实际模型输出** — 看模型到底输出了什么，而不是 grader 的一句话摘要：
   `{iter_dir}/eval-*/with_skill/run-*/outputs/output.txt`

2. **逐条评分详情** — 看 grader 对每条 expectation 的判断依据和引用的证据：
   `{iter_dir}/grading/eval-*-with_skill-run-*.json`

3. **对比 iteration-1 的同类输出** — 确认退步/进步是真实的还是 grader 随机性：
   `{iter_dir.parent}/iteration-（上一轮编号）/eval-*/with_skill/run-*/outputs/output.txt`

4. **benchmark.json 完整数据** — 含每个 run 的明细，不只看均值：
   `{iter_dir}/benchmark.json`

**工作方式**：先读 TRAINING-FEEDBACK.md 了解全局，再读上面的一手数据验证/修正你的判断，最后再改 SKILL.md。如果摘要说"模型没列方案"，去看实际输出确认是真的没列还是列了但格式不同。

---

## 当前训练状态

| 指标 | 值 |
|------|----|
| iteration | {iter_dir.name} |
| with_skill pass_rate | {with_pr:.3f}{delta_str} |
| without_skill pass_rate (baseline) | {without_pr:.3f} |
| delta | {delta} |

{format_eval_table(benchmark)}

---

{analysis}

---

## 验证命令

```bash
cd skill-training-framework
make train SKILL={args.skill_name}   # 跑新一轮
make diff  SKILL={args.skill_name}   # 对比前后 pass_rate
```
"""

    out = Path(args.skills_dir) / args.skill_name / "TRAINING-FEEDBACK.md"
    out.write_text(doc, encoding="utf-8")
    print(f"==> 已生成: {out}")
    print()
    print(f"下一步:")
    print(f"  在项目根目录开 Claude 对话，说:")
    print(f"  \"帮我改进 {args.skill_name} skill\"")
    print(f"  Claude 会读取 TRAINING-FEEDBACK.md 并协助修改 SKILL.md")
    print()
    print(f"  改完后验证:")
    print(f"  cd skill-training-framework")
    print(f"  make train SKILL={args.skill_name}")
    print(f"  make diff  SKILL={args.skill_name}")


if __name__ == "__main__":
    main()
