# 常见问题排查

## make run 报错

### "claude CLI not found"

框架依赖 `claude` 命令行工具。确认安装:
```bash
which claude
claude --version
```

如果没有,安装 Claude Code CLI。

### "evals.json not found"

每个 skill 必须有 `evals/evals.json`。运行:
```bash
make init SKILL=<name>
```
然后编辑生成的模板。

### "ERROR rc=1" 或 "TIMEOUT"

claude -p 调用失败或超时。可能原因:
- API key 过期或额度不足
- prompt 太长(检查 eval prompt 长度)
- 网络问题
- 超时时间太短(默认 300s,可在 run_evals.py 里调整 `timeout` 参数)

## make grade 报错

### "no JSON found in grader output"

LLM-as-judge 没返回合法 JSON。grader 会自动重试最多 3 次,并尝试修复常见的 LLM JSON 格式错误(trailing comma、缺逗号等)。如果仍然失败:
- 模型输出格式不稳定,尝试在 grader prompt 里更强调 "ONLY return JSON"
- 输出太长被截断,检查 `output[:8000]` 的截断是否切掉了关键内容

### grading 文件里出现 "GRADER ERROR"

grader 多次重试后仍无法获取有效结果。可以用 `make grade FORCE=1` 重跑:
```bash
make grade SKILL=<name> FORCE=1
```

### 所有 expectations 都 failed

检查 `transcript.md`:
1. 输出是否为空或错误 → executor 问题
2. 输出正常但 grader 判断不对 → grader prompt 需要调整
3. 输出确实没有满足 expectation → SKILL.md 需要改进

## benchmark 数据异常

### with_skill 和 without_skill 结果一样

两种可能:
- **eval 太简单**:不用 skill 也能过。加强 expectations 或换个更复杂的场景。
- **skill 没起作用**:检查 `transcript.md`,确认模型确实读了 SKILL.md 内容。

### pass_rate 忽高忽低

LLM 输出有随机性。如果同一条 expectation 这次过下次不过:
- 增加 runs_per_configuration(默认 3 取平均,可用 `RUNS=1` 回退单次)
- 看看是不是边界 case,grader 自己也不确定
- 如果确实 flaky,考虑拆成更明确的 expectation 或直接删掉

## 迭代没有进步

### 改了 SKILL.md 但 pass_rate 没变

1. 确认你改的跟失败的 expectation 有关联
2. 读 transcript:模型有没有读到你的改动?
3. 试试更大幅度的改写,微调往往不够

### 改了 A 让 B 退步

典型的 skill 复杂度问题:
- 如果 A 和 B 是同类型的 expectation → 找更通用的表述
- 如果 A 和 B 冲突 → 你可能需要分开成两个 skill,或者加条件判断
- 接受 trade-off:明确哪个更重要,优先保那个

## 和 skill-creator 配合

### 什么时候用 skill-creator,什么时候用本框架?

| 场景 | 工具 |
|---|---|
| 从零创建一个 skill | `/skill-creator` |
| 持续迭代已有 skill | 本框架 (`make train`) |
| 优化 skill 的触发率(description) | skill-creator 的 `run_loop.py` |
| 对比两个版本(blind test) | skill-creator 的 comparator agent |
| 日常回归测试 | 本框架 (`make run && make grade`) |

两者互补,不冲突。本框架专注于**可重复、可量化、可版本化的迭代循环**。

### 本框架和 skill-creator 的工件格式兼容吗?

benchmark.json 兼容 skill-creator 的 schema。
你可以用 skill-creator 的 `eval-viewer/generate_review.py` 来可视化本框架的输出:
```bash
python ~/.claude/skills/skill-creator/eval-viewer/generate_review.py \
  workspaces/<skill>/iteration-N \
  --skill-name <skill> \
  --benchmark workspaces/<skill>/iteration-N/benchmark.json
```
