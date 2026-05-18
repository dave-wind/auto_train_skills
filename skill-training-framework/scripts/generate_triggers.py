"""用 Inversion 反转模式自动生成 trigger-evals.json。

核心思路:
1. 从 SKILL.md 的 description 和 body 提取 should_trigger: true 的 query
2. 对每个 true query 做 Inversion: 保留领域/关键词,扭转意图 → should_trigger: false
3. 生成后进入交互确认:逐条展示,用户可以翻转、删除、修改

这就是 ML 里 hard negative mining 的 prompt 版本。

用法:
  python generate_triggers.py --skill-name xxx --skills-dir ../skills
  python generate_triggers.py --skill-name xxx --skills-dir ../skills --no-confirm  # 跳过确认
  或:
  make generate-triggers SKILL=xxx
"""
import argparse
import json
import os
import re
import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from utils import load_skill_md, save_json


GENERATE_PROMPT = """You are an expert at creating trigger evaluation test suites for AI skills.

Your task is to generate queries that test whether a skill's **description** causes Claude to correctly trigger (or not trigger) the skill.

# SKILL.md Content

```
{skill_content}
```

# The Inversion Method

You will generate two types of queries:

## Type 1: should_trigger: true (8-10 queries)
Realistic user prompts that SHOULD cause this skill to be triggered. Base these on:
- The skill's description field (what it does, when to use it)
- The skill's body (what capabilities it provides)
- The trigger phrases mentioned in the description

Make these realistic — include specific details, informal language, typos, mixed languages if the skill supports them. NOT abstract test prompts.

## Type 2: should_trigger: false (8-10 queries) — using INVERSION

For each true query, create an **inverted** version that:
- Stays in the SAME domain (same keywords, same topic area)
- TWISTS the intent so this skill is NOT the right one
- Would fool a naive keyword matcher but NOT a semantic understanding

**Inversion patterns to use:**

1. **Scale inversion**: If the skill is for small/quick tasks, invert to a massive/full-scope task
   - true: "quick flow帮我修个小bug" → false: "用完整流程帮我从零搭建一个包含认证、数据库、CI/CD的微服务架构"

2. **Direction inversion**: If the skill does X→Y, ask for Y→X (reverse direction)
   - true: "帮我把这段话改得更专业" → false: "帮我把这段专业文本翻译成通俗易懂的解释,要面向小学生"

3. **Tool substitution**: Same problem, but a different tool/approach is more appropriate
   - true: "strict flow帮我重构这个函数" → false: "帮我做一次完整的code review,检查安全问题和最佳实践"

4. **Adjacent domain**: Same keywords, different skill should handle it
   - true: "改写这段营销文案" → false: "帮我分析这段营销文案的SEO关键词密度和优化建议"

5. **Meta-request**: Asking ABOUT the skill rather than USING it
   - true: "快速流程修复这个类型错误" → false: "strict flow和superpowers有什么区别?各自的适用场景是什么?"

6. **Overkill detection**: Task is too simple to need any skill at all
   - true: "强制流程帮我写一个复杂的数据清洗脚本" → false: "帮我读一下这个文件的内容"

**Key rule for false queries**: They must be GENUINELY TRICKY. "Write a fibonacci function" as a false test for a writing skill is useless — it's too easy. The best false queries are ones where a keyword matcher WOULD trigger but a semantic understanding WOULD NOT.

Return ONLY a JSON array (no markdown, no prose):

[
  {{"query": "realistic user prompt...", "should_trigger": true}},
  {{"query": "inverted near-miss prompt...", "should_trigger": false}},
  ...
]

Aim for roughly equal numbers of true and false, interleaved."""


def call_claude(prompt, timeout=360):
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


def interactive_confirm(triggers):
    """逐条展示 trigger query,让用户确认/翻转/删除/修改。"""
    print("\n" + "=" * 60)
    print("交互确认:逐条审阅 trigger-evals")
    print("  Enter = 保留  f = 翻转(trigger↔not-trigger)  d = 删除  q = 全部保留并退出")
    print("=" * 60 + "\n")

    result = []
    for i, item in enumerate(triggers):
        label = "✓ TRIGGER" if item["should_trigger"] else "✗ NO-TRIGGER"
        print(f"[{i+1}/{len(triggers)}] {label}")
        print(f"    {item['query']}")
        print(f"    操作: Enter=保留  f=翻转  d=删除  q=全部保留退出")

        choice = input("    → ").strip().lower()

        if choice == "q":
            result.append(item)
            result.extend(triggers[i + 1:])
            break
        elif choice == "d":
            print("    已删除")
            continue
        elif choice == "f":
            item["should_trigger"] = not item["should_trigger"]
            new_label = "✓ TRIGGER" if item["should_trigger"] else "✗ NO-TRIGGER"
            print(f"    已翻转 → {new_label}")
            result.append(item)
        else:
            result.append(item)

    return result


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--skill-name", required=True)
    ap.add_argument("--skills-dir", required=True)
    ap.add_argument("--overwrite", action="store_true", help="覆盖已存在的 trigger-evals.json")
    ap.add_argument("--no-confirm", action="store_true", help="跳过交互确认,直接保存")
    args = ap.parse_args()

    skill_md = load_skill_md(args.skills_dir, args.skill_name)
    triggers_path = Path(args.skills_dir) / args.skill_name / "evals" / "trigger-evals.json"

    if triggers_path.exists() and not args.overwrite:
        print(f"已存在: {triggers_path}")
        print("如要覆盖,加 --overwrite 参数")
        return

    print(f"==> 用 Inversion 模式生成 trigger-evals...")

    full_prompt = GENERATE_PROMPT.format(skill_content=skill_md)
    raw, err = call_claude(full_prompt, timeout=360)
    if err or raw is None:
        print(f"错误: {err}")
        sys.exit(1)

    cleaned = re.sub(r"^```(?:json)?\s*\n?", "", raw)
    cleaned = re.sub(r"\n?```\s*$", "", cleaned)

    match = re.search(r"\[.*\]", cleaned, re.DOTALL)
    if not match:
        print("错误: 未在输出中找到 JSON 数组")
        print(f"原始输出(前 500 字): {raw[:500]}")
        sys.exit(1)

    try:
        triggers = json.loads(match.group(0))
    except json.JSONDecodeError:
        # Greedy regex may have captured too much — find the first complete JSON array
        depth = 0
        for i, c in enumerate(cleaned):
            if c == "[":
                depth += 1
            elif c == "]":
                depth -= 1
                if depth == 0:
                    try:
                        triggers = json.loads(cleaned[:i+1])
                        break
                    except json.JSONDecodeError as e:
                        print(f"错误: JSON 解析失败: {e}")
                        print(f"原始输出(前 500 字): {raw[:500]}")
                        sys.exit(1)
        else:
            print("错误: 未找到完整的 JSON 数组")
            print(f"原始输出(前 500 字): {raw[:500]}")
            sys.exit(1)
    except json.JSONDecodeError as e:
        print(f"错误: JSON 解析失败: {e}")
        print(f"原始输出(前 500 字): {raw[:500]}")
        sys.exit(1)

    if not isinstance(triggers, list):
        print("错误: 输出不是 JSON 数组")
        sys.exit(1)

    # 校验
    for item in triggers:
        if "query" not in item or "should_trigger" not in item:
            print(f"错误: 缺少 query 或 should_trigger: {item}")
            sys.exit(1)

    # 交互确认
    if not args.no_confirm:
        triggers = interactive_confirm(triggers)

    n_true = sum(1 for t in triggers if t["should_trigger"])
    n_false = sum(1 for t in triggers if not t["should_trigger"])

    save_json(triggers_path, triggers)
    print(f"\n==> 已保存: {triggers_path}")
    print(f"    {len(triggers)} 条 query: {n_true} should-trigger + {n_false} should-not-trigger")
    print()
    print("下一步:")
    print(f"  make trigger-eval SKILL={args.skill_name}")


if __name__ == "__main__":
    main()
