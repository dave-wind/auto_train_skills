"""Compare the latest two iterations side by side.

Uses eval_summary (averaged across runs) when available, falls back to single-run data.
"""
import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from utils import latest_iteration_dir, load_json, previous_iteration_dir


def get_eval_scores(benchmark):
    """Extract per-eval pass_rate from benchmark, preferring eval_summary."""
    eval_summary = benchmark.get("eval_summary", {})
    with_evals = {e["eval_id"]: e for e in eval_summary.get("with_skill", [])}

    if with_evals:
        return {eid: e["pass_rate"] for eid, e in with_evals.items()}, \
               {eid: e.get("eval_name", "") for eid, e in with_evals.items()}

    # Fallback: single-run (old format)
    by_eval = {}
    names = {}
    for r in benchmark["runs"]:
        if r["configuration"] == "with_skill":
            by_eval[r["eval_id"]] = r["result"]["pass_rate"]
            names[r["eval_id"]] = r.get("eval_name", "")
    return by_eval, names


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--skill-name", required=True)
    ap.add_argument("--workspace-root", required=True)
    args = ap.parse_args()

    cur = latest_iteration_dir(args.workspace_root, args.skill_name)
    prev = previous_iteration_dir(args.workspace_root, args.skill_name)
    if not cur or not prev:
        sys.exit("错误: 至少需要两轮 iteration 才能对比")

    cur_bench = cur / "benchmark.json"
    prev_bench = prev / "benchmark.json"
    if not cur_bench.exists():
        sys.exit(f"错误: {cur_bench} 不存在, 请先 make benchmark SKILL={args.skill_name}")
    if not prev_bench.exists():
        sys.exit(f"错误: {prev_bench} 不存在, 请先 make benchmark SKILL={args.skill_name}")

    cur_b = load_json(cur_bench)
    prev_b = load_json(prev_bench)

    cur_scores, cur_names = get_eval_scores(cur_b)
    prev_scores, prev_names = get_eval_scores(prev_b)

    cur_runs = cur_b["metadata"].get("runs_per_configuration", 1)
    runs_note = f" ({cur_runs} runs avg)" if cur_runs > 1 else ""

    print(f"==> 对比 {prev.name} → {cur.name}{runs_note}")
    print()
    print(f"{'Eval':<6} {'Name':<30} {'Prev':>8} {'Curr':>8} {'Delta':>8}")
    print("-" * 64)
    for eid in sorted(set(cur_scores) | set(prev_scores)):
        p = prev_scores.get(eid, 0)
        c = cur_scores.get(eid, 0)
        name = (cur_names.get(eid) or prev_names.get(eid, ""))[:30]
        delta = c - p
        marker = "↑" if delta > 0 else ("↓" if delta < 0 else "=")
        print(f"{eid:<6} {name:<30} {p:>8.3f} {c:>8.3f} {delta:>+7.3f} {marker}")

    p_mean = prev_b["run_summary"]["with_skill"]["pass_rate"]["mean"]
    c_mean = cur_b["run_summary"]["with_skill"]["pass_rate"]["mean"]
    print("-" * 64)
    print(f"{'TOTAL':<6} {'with_skill mean':<30} {p_mean:>8.3f} {c_mean:>8.3f} {c_mean - p_mean:>+7.3f}")


if __name__ == "__main__":
    main()
