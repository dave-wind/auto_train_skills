"""Generate human-readable markdown report from benchmark.json.

Supports both multi-run (averaged) and single-run data.
"""
import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from utils import latest_iteration_dir, load_json, previous_iteration_dir


def format_eval_table(benchmark):
    """Build per-eval breakdown table using eval_summary (averaged across runs)."""
    eval_summary = benchmark.get("eval_summary", {})
    with_evals = {e["eval_id"]: e for e in eval_summary.get("with_skill", [])}
    without_evals = {e["eval_id"]: e for e in eval_summary.get("without_skill", [])}

    # Fallback for old format (no eval_summary)
    if not with_evals and not without_evals:
        runs = benchmark.get("runs", [])
        by_eval = {}
        for r in runs:
            by_eval.setdefault(r["eval_id"], {})[r["configuration"]] = r
        lines = [
            "| Eval | Name | with_skill | without_skill | Δ pass |",
            "|------|------|------------|---------------|--------|",
        ]
        for eid in sorted(by_eval.keys()):
            ws = by_eval[eid].get("with_skill")
            wo = by_eval[eid].get("without_skill")
            ws_pr = ws["result"]["pass_rate"] if ws else 0
            wo_pr = wo["result"]["pass_rate"] if wo else 0
            name = (ws or wo).get("eval_name", "") if (ws or wo) else ""
            lines.append(f"| {eid} | {name} | {ws_pr:.2f} | {wo_pr:.2f} | {ws_pr - wo_pr:+.2f} |")
        return "\n".join(lines)

    all_ids = sorted(set(list(with_evals.keys()) + list(without_evals.keys())))

    lines = [
        "| Eval | Name | with_skill | without_skill | Δ pass |",
        "|------|------|------------|---------------|--------|",
    ]
    for eid in all_ids:
        ws = with_evals.get(eid)
        wo = without_evals.get(eid)
        ws_pr = ws["pass_rate"] if ws else 0
        wo_pr = wo["pass_rate"] if wo else 0
        name = (ws or wo).get("eval_name", "") if (ws or wo) else ""

        # Show range if multiple runs
        if ws and ws.get("num_runs", 1) > 1:
            rng = ws.get("pass_rate_range", {})
            ws_str = f"{ws_pr:.2f} ({rng.get('min', ws_pr):.2f}-{rng.get('max', ws_pr):.2f}, n={ws['num_runs']})"
        else:
            ws_str = f"{ws_pr:.2f}"

        if wo and wo.get("num_runs", 1) > 1:
            rng = wo.get("pass_rate_range", {})
            wo_str = f"{wo_pr:.2f} ({rng.get('min', wo_pr):.2f}-{rng.get('max', wo_pr):.2f}, n={wo['num_runs']})"
        else:
            wo_str = f"{wo_pr:.2f}"

        lines.append(f"| {eid} | {name} | {ws_str} | {wo_str} | {ws_pr - wo_pr:+.2f} |")

    return "\n".join(lines)


def format_failed_expectations(runs, config):
    """Format failed expectations from individual runs (show run number if multi-run)."""
    # Group by eval_id
    by_eval = {}
    for r in runs:
        if r["configuration"] != config:
            continue
        eid = r["eval_id"]
        by_eval.setdefault(eid, []).append(r)

    lines = []
    for eid in sorted(by_eval.keys()):
        eval_runs = by_eval[eid]
        name = eval_runs[0].get("eval_name", "")

        # Collect failed expectations across runs, noting which run failed
        multi_run = len(eval_runs) > 1
        failed_by_text = {}
        for r in eval_runs:
            run_num = r.get("run_number", 1)
            for e in r.get("expectations", []):
                if not e.get("passed"):
                    text = e["text"]
                    if text not in failed_by_text:
                        failed_by_text[text] = []
                    failed_by_text[text].append((run_num, e.get("evidence", "")))

        if not failed_by_text:
            continue

        lines.append(f"### Eval {eid} ({name})")
        for text, failures in failed_by_text.items():
            if multi_run:
                run_nums = sorted(set(fn[0] for fn in failures))
                runs_str = f" (run {', '.join(str(n) for n in run_nums)})"
            else:
                runs_str = ""
            evidence = failures[0][1].replace("\n", " ")[:200]
            lines.append(f"- ✗ {text}{runs_str}")
            lines.append(f"  - _evidence_: {evidence}")

    return "\n".join(lines) if lines else "(全部通过)"


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--skill-name", required=True)
    ap.add_argument("--workspace-root", required=True)
    args = ap.parse_args()

    iter_dir = latest_iteration_dir(args.workspace_root, args.skill_name)
    if not iter_dir:
        sys.exit("错误: 未找到 iteration")
    bench_file = iter_dir / "benchmark.json"
    if not bench_file.exists():
        sys.exit("错误: 未找到 benchmark.json, 先 make benchmark")

    benchmark = load_json(bench_file)
    meta = benchmark["metadata"]
    summary = benchmark["run_summary"]
    runs_per = meta.get("runs_per_configuration", 1)

    prev_dir = previous_iteration_dir(args.workspace_root, args.skill_name)
    prev_pr = None
    if prev_dir:
        prev_bench = prev_dir / "benchmark.json"
        if prev_bench.exists():
            prev_summary = load_json(prev_bench)["run_summary"]
            prev_pr = prev_summary["with_skill"]["pass_rate"]["mean"]

    delta_prev = ""
    if prev_pr is not None and prev_dir is not None:
        d = summary["with_skill"]["pass_rate"]["mean"] - prev_pr
        delta_prev = f" (vs {prev_dir.name}: {d:+.3f})"

    runs_note = f" ({runs_per} runs averaged)" if runs_per > 1 else ""

    md = f"""# Training Report — {meta['skill_name']}

**Iteration:** {iter_dir.name}
**Timestamp:** {meta['timestamp']}
**Evals run:** {len(meta['evals_run'])}{runs_note}

## Summary

| Configuration | Pass Rate |
|---------------|-----------|
| with_skill    | {summary['with_skill']['pass_rate']['mean']:.3f}{delta_prev} |
| without_skill | {summary['without_skill']['pass_rate']['mean']:.3f} |
| **delta**     | **{summary['delta']['pass_rate']}** |

## Per-Eval Breakdown

{format_eval_table(benchmark)}

## Failed expectations (with_skill)

{format_failed_expectations(benchmark['runs'], 'with_skill')}

## Failed expectations (without_skill — sanity check)

{format_failed_expectations(benchmark['runs'], 'without_skill')}

---

## How to read this

- **Pass rate (with_skill)** is your main metric. Higher = skill works.
- **Range** (e.g., `0.60-0.80, n=3`) shows min-max across runs — wide range = high variance.
- **Delta** = how much value the skill adds over no-skill baseline.
- **Failed expectations (with_skill)** = where to focus your next iteration.
- **Failed expectations (without_skill)** sanity-check that your evals are non-trivial.
"""

    out = iter_dir / "report.md"
    out.write_text(md, encoding="utf-8")
    print(f"==> 报告: {out}")
    print()
    print(md)


if __name__ == "__main__":
    main()
