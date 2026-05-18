"""Grader: LLM-as-judge.

对每个 eval 的每个 config 的每个 run 的 output,逐条评估 expectations 是否满足。
调用 claude -p 当评分员,返回 JSON。

支持新旧目录结构:
  新: eval-N/<config>/run-K/outputs/output.txt  → grading/eval-N-<config>-run-K.json
  旧: eval-N/<config>/outputs/output.txt        → grading/eval-N-<config>.json
"""
import argparse
import json
import re
import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from utils import latest_iteration_dir, load_json, save_json


GRADER_PROMPT_TEMPLATE = """You are an evaluation grader. Judge whether each expectation is met by the given output.

# Original Prompt to the Skill
```
{prompt}
```

# Skill's Output
```
{output}
```

# Expectations to Verify
{expectations_block}

# Your Task

For each expectation, decide whether it is met by the output. Return ONLY a JSON object (no markdown, no prose) in this exact format:

{{
  "expectations": [
    {{"text": "<expectation text>", "passed": true|false, "evidence": "<short quote or reason>"}}
  ]
}}

Be strict but fair. Quote evidence from the output when possible. If the output is empty, errored, or completely off-topic, mark all expectations failed."""


def repair_json(text):
    """Attempt to fix common LLM JSON mistakes."""
    # Remove trailing commas before ] or }
    text = re.sub(r",\s*([}\]])", r"\1", text)
    # Remove JS-style comments
    text = re.sub(r"//.*$", "", text, flags=re.MULTILINE)
    # Add missing commas between }{ and ][ (LLM sometimes omits them)
    text = re.sub(r"\}\s*\{", "}, {", text)
    text = re.sub(r"\]\s*\[", "], [", text)
    # Add missing commas between "value" and "key" (missing comma in object)
    text = re.sub(r'"\s*\n\s*"', '",\n"', text)
    return text


def try_parse_json(raw):
    """Try multiple strategies to extract and parse JSON from LLM output.

    Returns (parsed_dict, None) on success or (None, error_string) on failure.
    """
    # Strip markdown code fences
    cleaned = re.sub(r"^```(?:json)?\s*\n?", "", raw)
    cleaned = re.sub(r"\n?```\s*$", "", cleaned).strip()

    # Strategy 1: greedy regex + direct parse
    match = re.search(r"\{.*\}", cleaned, re.DOTALL)
    if match:
        candidate = match.group(0)
        try:
            return json.loads(candidate), None
        except json.JSONDecodeError:
            pass
        # Try repair on the greedy match
        try:
            return json.loads(repair_json(candidate)), None
        except json.JSONDecodeError:
            pass

    # Strategy 2: brace-counting to find first complete JSON object, then repair
    depth = 0
    for i, c in enumerate(cleaned):
        if c == "{":
            depth += 1
        elif c == "}":
            depth -= 1
            if depth == 0:
                candidate = cleaned[:i+1]
                try:
                    return json.loads(candidate), None
                except json.JSONDecodeError:
                    pass
                try:
                    return json.loads(repair_json(candidate)), None
                except json.JSONDecodeError as e:
                    return None, f"JSON decode error: {e}"
    return None, "no parseable JSON object found in grader output"


def call_grader(prompt, output, expectations, timeout=360):
    expectations_block = "\n".join(f"{i+1}. {e}" for i, e in enumerate(expectations))
    full_prompt = GRADER_PROMPT_TEMPLATE.format(
        prompt=prompt,
        output=output[:8000],
        expectations_block=expectations_block,
    )
    result = subprocess.run(
        ["claude", "-p", full_prompt],
        capture_output=True,
        text=True,
        timeout=timeout,
    )
    if result.returncode != 0:
        return None, f"grader rc={result.returncode}: {result.stderr}"
    raw = result.stdout.strip()
    parsed, err = try_parse_json(raw)
    if err:
        return None, f"JSON decode error: {err}"
    return parsed, None


def grade_output(meta, output, expectations, timeout=360, max_retries=2):
    """Grade a single output against expectations. Returns grading result dict.

    Retries up to max_retries if the grader returns a mismatched number of
    expectations (e.g. empty array), which is a known LLM-as-judge reliability issue.
    Also retries on parse errors since they are often transient.
    """
    last_err = None
    last_items = []
    for attempt in range(max_retries + 1):
        parsed, err = call_grader(meta["prompt"], output, expectations, timeout=timeout)
        if err:
            last_err = err
            if attempt < max_retries:
                print(f"    ⚠ grader error: {err[:80]}, retrying ({attempt+1}/{max_retries})")
                continue
            break  # all retries exhausted, fall through to error
        items = parsed.get("expectations", [])
        last_items = items
        last_err = None
        if len(items) == len(expectations):
            passed = sum(1 for it in items if it.get("passed"))
            total = len(items)
            return {
                "expectations": items,
                "summary": {
                    "passed": passed,
                    "failed": total - passed,
                    "total": total,
                    "pass_rate": round(passed / total, 3) if total else 0.0,
                },
            }
        # Mismatch — grader returned wrong count, retry
        if attempt < max_retries:
            print(f"    ⚠ grader returned {len(items)}/{len(expectations)} expectations, retrying ({attempt+1}/{max_retries})")

    # All retries exhausted or parse error
    err_msg = last_err or f"expectations count mismatch ({len(last_items)}/{len(expectations)}) after {max_retries+1} attempts"
    return {
        "expectations": [
            {"text": e, "passed": False, "evidence": f"GRADER ERROR: {err_msg}"}
            for e in expectations
        ],
        "summary": {
            "passed": 0,
            "failed": len(expectations),
            "total": len(expectations),
            "pass_rate": 0.0,
        },
    }


def find_runs(eval_dir, config):
    """Find all run directories for an eval/config. Returns list of (run_num, output_path).

    Supports both new (run-K/outputs/output.txt) and old (outputs/output.txt) layouts.
    """
    config_dir = eval_dir / config

    # New layout: run-1, run-2, ...
    run_dirs = sorted(config_dir.glob("run-*"))
    if run_dirs:
        results = []
        for rd in run_dirs:
            output_file = rd / "outputs" / "output.txt"
            if output_file.exists():
                try:
                    run_num = int(rd.name.split("-")[1])
                except (ValueError, IndexError):
                    run_num = 0
                results.append((run_num, output_file))
        if results:
            return results

    # Old layout: flat outputs/output.txt
    old_path = config_dir / "outputs" / "output.txt"
    if old_path.exists():
        return [(1, old_path)]

    return []


def grade_one_multi(eval_dir, config, grading_dir, timeout=360, force=False):
    """Grade all runs for an eval/config."""
    meta = load_json(eval_dir / "eval_metadata.json")
    expectations = meta.get("expectations", [])
    if not expectations:
        print(f"  ○ 跳过 {eval_dir.name}/{config}: 无 expectations")
        return

    runs = find_runs(eval_dir, config)
    if not runs:
        print(f"  ✗ 跳过 {eval_dir.name}/{config}: 无 output")
        return

    for run_num, output_file in runs:
        grading_name = f"{eval_dir.name}-{config}-run-{run_num}"
        grading_file = grading_dir / f"{grading_name}.json"

        if grading_file.exists() and not force:
            print(f"  ○ 已评分 {grading_name}")
            continue

        output = output_file.read_text(encoding="utf-8")
        print(f"  → 评分 {grading_name}")
        result = grade_output(meta, output, expectations, timeout=timeout)
        save_json(grading_file, result)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--skill-name", required=True)
    ap.add_argument("--skills-dir", required=True)
    ap.add_argument("--workspace-root", required=True)
    ap.add_argument("--timeout", type=int, default=360, help="Per-grading timeout in seconds (default: 360)")
    ap.add_argument("--force", action="store_true", help="Re-grade even if grading file exists")
    args = ap.parse_args()

    iter_dir = latest_iteration_dir(args.workspace_root, args.skill_name)
    if not iter_dir:
        sys.exit(f"错误: 未找到 iteration, 请先 make run SKILL={args.skill_name}")

    print(f"==> 评分: {iter_dir}")
    grading_dir = iter_dir / "grading"
    grading_dir.mkdir(parents=True, exist_ok=True)

    eval_dirs = sorted(
        [p for p in iter_dir.glob("eval-*") if p.is_dir()],
        key=lambda p: int(p.name.split("-")[1]),
    )

    for eval_dir in eval_dirs:
        for config in ("with_skill", "without_skill"):
            grade_one_multi(eval_dir, config, grading_dir, timeout=args.timeout, force=args.force)

    print(f"==> 评分完成: {grading_dir}")


if __name__ == "__main__":
    main()
