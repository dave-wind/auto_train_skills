"""根据 SKILL.md 自动生成 evals.json。

读取 SKILL.md,用 claude -p 让 LLM 分析 skill 的核心能力,
然后生成 4-6 个覆盖不同场景的 eval(含 prompt + expectations)。

用法:
  python generate_evals.py --skill-name xxx --skills-dir ../skills
  或:
  make generate-evals SKILL=xxx
"""
import argparse
import json
import re
import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from utils import load_skill_md, save_json


GENERATE_PROMPT = """You are an expert at creating evaluation test suites for AI skills.

Given the following SKILL.md, generate a set of evals that test whether the skill works correctly in practice.

# SKILL.md Content

```
{skill_content}
```

# Your Task

Generate 4-6 evals following these principles:

1. **Prompts must be realistic** — like what a real user would actually type. Include specific details, file paths, code snippets, informal language. NOT abstract requests like "test the skill".

2. **Cover different scenarios**:
   - 1-2 typical happy path cases (most common usage)
   - 1 edge case (unusual input, boundary condition)
   - 1 special instruction case (e.g., "just do it", "skip", "详细解释" if the skill supports such modes)
   - 1 multi-step or complex task
   - If the skill mentions multiple languages, include at least 1 non-English prompt

3. **Expectations must be**:
   - Objectively verifiable (a third party could judge pass/fail without knowing the skill)
   - Single assertion per expectation (don't combine multiple checks in one)
   - Written from the USER's perspective (what the user should see), NOT from the skill author's perspective (what the model should do internally)
   - 4-6 per eval

4. **Bad expectations** (avoid these):
   - "The output is high quality" (subjective)
   - "Gate 1 is executed" (internal skill jargon — say what the user sees instead)
   - "The skill was triggered" (that's trigger testing, not capability testing)

5. **Good expectations** (aim for these):
   - "The response proposes at least one approach and explicitly asks the user to choose"
   - "A complete, runnable code snippet is provided"
   - "The response is in the same language as the user's input"

Return ONLY a JSON object in this exact format (no markdown, no prose):

{{
  "skill_name": "{skill_name}",
  "evals": [
    {{
      "id": 1,
      "name": "descriptive-kebab-case-name",
      "prompt": "Realistic user prompt here...",
      "expected_output": "Human-readable success criteria",
      "files": [],
      "expectations": [
        "Objectively verifiable assertion 1",
        "Objectively verifiable assertion 2",
        "Objectively verifiable assertion 3",
        "Objectively verifiable assertion 4"
      ]
    }}
  ]
}}"""


def call_claude(prompt, timeout=360):
    import os
    cmd = ["claude", "-p", prompt]
    env = dict(os.environ)
    env.pop("CLAUDECODE", None)
    try:
        result = subprocess.run(
            cmd, capture_output=True, text=True, timeout=timeout, env=env
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
    ap.add_argument("--overwrite", action="store_true", help="覆盖已存在的 evals.json")
    args = ap.parse_args()

    skill_md = load_skill_md(args.skills_dir, args.skill_name)
    evals_path = Path(args.skills_dir) / args.skill_name / "evals" / "evals.json"

    if evals_path.exists() and not args.overwrite:
        print(f"已存在: {evals_path}")
        print("如要覆盖,加 --overwrite 参数")
        return

    print(f"==> 分析 SKILL.md 并生成 evals...")
    full_prompt = GENERATE_PROMPT.format(
        skill_content=skill_md,
        skill_name=args.skill_name,
    )

    raw, err = call_claude(full_prompt, timeout=360)
    if err or raw is None:
        print(f"错误: {err}")
        sys.exit(1)

    # 去掉 markdown 代码块包裹
    cleaned = re.sub(r"^```(?:json)?\s*\n?", "", raw)
    cleaned = re.sub(r"\n?```\s*$", "", cleaned)

    match = re.search(r"\{.*\}", cleaned, re.DOTALL)
    if not match:
        print("错误: 未在输出中找到 JSON")
        print(f"原始输出(前 500 字): {raw[:500]}")
        sys.exit(1)

    try:
        evals_data = json.loads(match.group(0))
    except json.JSONDecodeError as e:
        print(f"错误: JSON 解析失败: {e}")
        print(f"原始输出(前 500 字): {raw[:500]}")
        sys.exit(1)

    # 基本校验
    if "evals" not in evals_data or not isinstance(evals_data["evals"], list):
        print("错误: 生成的 JSON 缺少 evals 数组")
        sys.exit(1)

    for ev in evals_data["evals"]:
        if "prompt" not in ev or "expectations" not in ev:
            print(f"错误: eval {ev.get('id', '?')} 缺少 prompt 或 expectations")
            sys.exit(1)
        if not ev.get("name"):
            ev["name"] = f"eval-{ev.get('id', 0)}"

    evals_data["skill_name"] = args.skill_name
    save_json(evals_path, evals_data)

    n = len(evals_data["evals"])
    total_exp = sum(len(ev.get("expectations", [])) for ev in evals_data["evals"])
    print(f"==> 已生成: {evals_path}")
    print(f"    {n} 个 eval,共 {total_exp} 条 expectations")
    print()
    print("请审阅并调整,然后运行:")
    print(f"  make train SKILL={args.skill_name}")


if __name__ == "__main__":
    main()
