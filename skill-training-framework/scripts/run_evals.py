"""Executor: 用 claude -p 跑所有 eval,支持多次运行取均值和 baseline 缓存。

with_skill 配置:把 SKILL.md 的内容作为系统提示注入。
without_skill 配置:同样的 prompt,但不注入 skill。

产物:workspaces/<skill>/iteration-N/eval-<id>/<config>/
  ├── run-1/
  │   ├── outputs/output.txt    模型回复全文
  │   ├── transcript.md         可读形式
  │   └── timing.json           耗时
  ├── run-2/...
  └── run-3/...

Baseline 缓存:workspaces/<skill>/baseline/eval-<id>/without_skill/run-*/...
"""
import argparse
import json
import shutil
import subprocess
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from utils import (
    load_evals,
    load_skill_md,
    next_iteration_dir,
    save_json,
)


def run_claude(prompt, system_prompt=None, timeout=300):
    """Call claude CLI with -p, return (stdout, duration_ms)."""
    cmd = ["claude", "-p", prompt]
    if system_prompt:
        cmd.extend(["--append-system-prompt", system_prompt])
    start = time.time()
    try:
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=timeout,
        )
        duration_ms = int((time.time() - start) * 1000)
        if result.returncode != 0:
            return f"[ERROR rc={result.returncode}] {result.stderr}", duration_ms
        return result.stdout, duration_ms
    except subprocess.TimeoutExpired:
        duration_ms = int((time.time() - start) * 1000)
        return f"[TIMEOUT after {timeout}s]", duration_ms


def save_run_output(run_dir, eval_id, config, prompt, output, duration_ms):
    """Save a single run's output to the run directory."""
    outputs_dir = run_dir / "outputs"
    outputs_dir.mkdir(parents=True, exist_ok=True)

    (outputs_dir / "output.txt").write_text(output, encoding="utf-8")

    transcript = (
        f"# Eval {eval_id} — {config}\n\n"
        f"## Prompt\n\n```\n{prompt}\n```\n\n"
        f"## Output\n\n{output}\n"
    )
    (run_dir / "transcript.md").write_text(transcript, encoding="utf-8")

    save_json(
        run_dir / "timing.json",
        {
            "duration_ms": duration_ms,
            "duration_seconds": round(duration_ms / 1000, 2),
        },
    )


def run_one_multi(ev, skill_md, eval_dir, config, num_runs):
    """Run a single eval under a config multiple times."""
    config_dir = eval_dir / config
    prompt = ev["prompt"]
    system_prompt = skill_md if config == "with_skill" else None

    for run_num in range(1, num_runs + 1):
        run_dir = config_dir / f"run-{run_num}"
        if (run_dir / "outputs" / "output.txt").exists():
            continue

        print(f"  → [{config}] eval-{ev['id']} run-{run_num}: {ev.get('name', '')}")
        output, duration_ms = run_claude(prompt, system_prompt)
        save_run_output(run_dir, ev["id"], config, prompt, output, duration_ms)


def cache_baseline(eval_dir, baseline_dir, eval_id, num_runs):
    """Copy without_skill runs from eval_dir to baseline cache."""
    src_config = eval_dir / "without_skill"
    dst_config = baseline_dir / f"eval-{eval_id}" / "without_skill"
    if src_config.exists():
        shutil.copytree(src_config, dst_config, dirs_exist_ok=True)


def restore_baseline(eval_dir, baseline_dir, eval_id, num_runs):
    """Copy cached baseline runs into eval_dir. Returns True if cache existed."""
    src_config = baseline_dir / f"eval-{eval_id}" / "without_skill"
    dst_config = eval_dir / "without_skill"
    if not src_config.exists():
        return False
    shutil.copytree(src_config, dst_config, dirs_exist_ok=True)
    return True


def baseline_cache_exists(baseline_dir, eval_id, num_runs):
    """Check if baseline cache has all expected runs."""
    config_dir = baseline_dir / f"eval-{eval_id}" / "without_skill"
    if not config_dir.exists():
        return False
    for run_num in range(1, num_runs + 1):
        run_dir = config_dir / f"run-{run_num}"
        if not (run_dir / "outputs" / "output.txt").exists():
            return False
    return True


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--skill-name", required=True)
    ap.add_argument("--skills-dir", required=True)
    ap.add_argument("--workspace-root", required=True)
    ap.add_argument("--num-runs", type=int, default=3, help="Number of runs per eval per config")
    ap.add_argument("--skip-baseline", action="store_true", help="Reuse cached without_skill baseline")
    args = ap.parse_args()

    evals_data = load_evals(args.skills_dir, args.skill_name)
    skill_md = load_skill_md(args.skills_dir, args.skill_name)

    iter_dir, n = next_iteration_dir(args.workspace_root, args.skill_name)
    baseline_dir = Path(args.workspace_root) / args.skill_name / "baseline"

    print(f"==> iteration-{n}: {iter_dir}")
    print(f"==> {len(evals_data['evals'])} evals × {args.num_runs} runs × 2 configs")

    if args.skip_baseline and baseline_dir.exists():
        print(f"==> baseline 缓存: {baseline_dir}")

    for ev in evals_data["evals"]:
        eval_dir = iter_dir / f"eval-{ev['id']}"
        eval_dir.mkdir(parents=True, exist_ok=True)

        save_json(
            eval_dir / "eval_metadata.json",
            {
                "eval_id": ev["id"],
                "eval_name": ev.get("name", f"eval-{ev['id']}"),
                "prompt": ev["prompt"],
                "expected_output": ev.get("expected_output", ""),
                "expectations": ev.get("expectations", []),
            },
        )

        # with_skill: always run
        run_one_multi(ev, skill_md, eval_dir, "with_skill", args.num_runs)

        # without_skill: run or restore from cache
        baseline_ok = (
            args.skip_baseline
            and baseline_cache_exists(baseline_dir, ev["id"], args.num_runs)
        )
        if baseline_ok:
            print(f"  → [without_skill] eval-{ev['id']}: 从缓存恢复")
            restore_baseline(eval_dir, baseline_dir, ev["id"], args.num_runs)
        else:
            run_one_multi(ev, skill_md, eval_dir, "without_skill", args.num_runs)
            cache_baseline(eval_dir, baseline_dir, ev["id"], args.num_runs)

    # Save baseline metadata
    baseline_dir.mkdir(parents=True, exist_ok=True)
    save_json(
        baseline_dir / "baseline_meta.json",
        {
            "skill_name": args.skill_name,
            "num_runs": args.num_runs,
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "num_evals": len(evals_data["evals"]),
        },
    )

    print(f"==> 执行完成: {iter_dir}")


if __name__ == "__main__":
    main()
