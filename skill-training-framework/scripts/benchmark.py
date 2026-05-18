"""Aggregate grading results into benchmark.json.

汇总每个 eval 在 with_skill / without_skill 下的 pass_rate 和 timing。
支持多 run 聚合:同一 eval/config 的多个 run 取均值。

输出 workspaces/<skill>/iteration-N/benchmark.json。
"""
import argparse
import statistics
import sys
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from utils import latest_iteration_dir, load_json, save_json


def find_grading_runs(iter_dir, eval_dir, config):
    """Find grading results for all runs of an eval/config.

    Returns list of (run_number, grading_data, timing_data).
    Supports both new (eval-N-config-run-K.json) and old (eval-N-config.json) naming.
    """
    results = []

    # New layout: eval-N-config-run-K.json + run-K/timing.json
    grading_dir = iter_dir / "grading"
    run_files = sorted(grading_dir.glob(f"{eval_dir.name}-{config}-run-*.json"))
    for gf in run_files:
        grading = load_json(gf)
        # Extract run number from filename
        try:
            run_num = int(gf.stem.split("-run-")[1])
        except (ValueError, IndexError):
            run_num = 0
        timing_file = eval_dir / config / f"run-{run_num}" / "timing.json"
        timing = load_json(timing_file) if timing_file.exists() else {"duration_ms": 0}
        results.append((run_num, grading, timing))

    if results:
        return results

    # Old layout: eval-N-config.json + timing.json (single run)
    old_grading = grading_dir / f"{eval_dir.name}-{config}.json"
    if old_grading.exists():
        grading = load_json(old_grading)
        timing_file = eval_dir / config / "timing.json"
        timing = load_json(timing_file) if timing_file.exists() else {"duration_ms": 0}
        results.append((1, grading, timing))

    return results


def collect_runs(iter_dir, eval_dir, config):
    """Collect all runs for an eval/config, return a list of run records."""
    meta = load_json(eval_dir / "eval_metadata.json")
    grading_runs = find_grading_runs(iter_dir, eval_dir, config)

    if not grading_runs:
        return [{
            "eval_id": meta["eval_id"],
            "eval_name": meta.get("eval_name", f"eval-{meta['eval_id']}"),
            "configuration": config,
            "run_number": 1,
            "result": {
                "pass_rate": 0.0,
                "passed": 0,
                "failed": 0,
                "total": 0,
                "time_seconds": 0,
            },
            "expectations": [],
        }]

    records = []
    skipped = 0
    for run_num, grading, timing in grading_runs:
        summary = grading.get("summary", {"passed": 0, "failed": 0, "total": 0, "pass_rate": 0.0})
        if summary["total"] == 0:
            skipped += 1
            continue
        records.append({
            "eval_id": meta["eval_id"],
            "eval_name": meta.get("eval_name", f"eval-{meta['eval_id']}"),
            "configuration": config,
            "run_number": run_num,
            "result": {
                "pass_rate": summary["pass_rate"],
                "passed": summary["passed"],
                "failed": summary["failed"],
                "total": summary["total"],
                "time_seconds": round(timing.get("duration_ms", 0) / 1000, 2),
            },
            "expectations": grading.get("expectations", []),
        })
    if skipped:
        print(f"  ⚠ {eval_dir.name}/{config}: 跳过 {skipped} 个异常 grading (total=0)")
    return records


def summary_stats(values):
    if not values:
        return {"mean": 0, "stddev": 0, "min": 0, "max": 0}
    return {
        "mean": round(statistics.mean(values), 3),
        "stddev": round(statistics.stdev(values), 3) if len(values) > 1 else 0,
        "min": round(min(values), 3),
        "max": round(max(values), 3),
    }


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--skill-name", required=True)
    ap.add_argument("--workspace-root", required=True)
    args = ap.parse_args()

    iter_dir = latest_iteration_dir(args.workspace_root, args.skill_name)
    if not iter_dir:
        sys.exit("错误: 未找到 iteration")

    print(f"==> 汇总: {iter_dir}")

    eval_dirs = sorted(
        [p for p in iter_dir.glob("eval-*") if p.is_dir()],
        key=lambda p: int(p.name.split("-")[1]),
    )

    # Collect all runs (multiple runs per eval/config)
    all_runs = []
    runs_per_config = 1
    for eval_dir in eval_dirs:
        for config in ("with_skill", "without_skill"):
            run_records = collect_runs(iter_dir, eval_dir, config)
            all_runs.extend(run_records)
            if len(run_records) > runs_per_config:
                runs_per_config = len(run_records)

    # Aggregate by eval (average across runs)
    with_agg = []
    without_agg = []
    with_times = []
    without_times = []
    for eval_dir in eval_dirs:
        for config, agg_list, time_list in [
            ("with_skill", with_agg, with_times),
            ("without_skill", without_agg, without_times),
        ]:
            config_runs = [
                r for r in all_runs
                if r["eval_id"] == eval_dir_to_id(eval_dir) and r["configuration"] == config
            ]
            if not config_runs:
                continue
            pass_rates = [r["result"]["pass_rate"] for r in config_runs]
            avg_pass_rate = round(statistics.mean(pass_rates), 3)
            agg_list.append({
                "eval_id": config_runs[0]["eval_id"],
                "eval_name": config_runs[0]["eval_name"],
                "num_runs": len(config_runs),
                "pass_rate": avg_pass_rate,
                "pass_rate_range": summary_stats(pass_rates),
            })
            time_list.extend(r["result"]["time_seconds"] for r in config_runs)

    def aggregate_evals(eval_records):
        if not eval_records:
            return {
                "pass_rate": {"mean": 0, "stddev": 0, "min": 0, "max": 0},
                "time_seconds": {"mean": 0, "stddev": 0, "min": 0, "max": 0},
            }
        return {"pass_rate": summary_stats([e["pass_rate"] for e in eval_records])}

    with_summary = aggregate_evals(with_agg)
    without_summary = aggregate_evals(without_agg)
    with_summary["time_seconds"] = summary_stats(with_times)
    without_summary["time_seconds"] = summary_stats(without_times)

    benchmark = {
        "metadata": {
            "skill_name": args.skill_name,
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "evals_run": list(dict.fromkeys(r["eval_id"] for r in all_runs if r["configuration"] == "with_skill")),
            "runs_per_configuration": runs_per_config,
        },
        "runs": all_runs,
        "eval_summary": {
            "with_skill": with_agg,
            "without_skill": without_agg,
        },
        "run_summary": {
            "with_skill": with_summary,
            "without_skill": without_summary,
            "delta": {
                "pass_rate": f"{with_summary['pass_rate']['mean'] - without_summary['pass_rate']['mean']:+.3f}",
                "time_seconds": f"{with_summary['time_seconds']['mean'] - without_summary['time_seconds']['mean']:+.2f}",
            },
        },
    }

    save_json(iter_dir / "benchmark.json", benchmark)
    print(f"==> 已生成: {iter_dir}/benchmark.json")
    print(f"   with_skill   pass_rate: {with_summary['pass_rate']['mean']:.3f} ({runs_per_config} runs)")
    print(f"   without_skill pass_rate: {without_summary['pass_rate']['mean']:.3f}")
    print(f"   delta:                  {benchmark['run_summary']['delta']['pass_rate']}")


def eval_dir_to_id(eval_dir):
    """Extract eval id from directory name like 'eval-1'."""
    try:
        return int(eval_dir.name.split("-")[1])
    except (ValueError, IndexError):
        return 0


if __name__ == "__main__":
    main()
