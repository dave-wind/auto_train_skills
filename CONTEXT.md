# 项目上下文 — 给下次 Claude 对话用的接续信息

> 本文件记录了截至 2026-05-18 的项目状态,供新对话的 Claude 快速理解。

## 项目是什么

`auto_train_skills/` 里的 `skill-training-framework/` 是一个**通用的 skill 持续训练框架**。
背景:用户用 `/skill-creator` 创建 skill 后,只有一个黑箱——没人知道怎么系统性地迭代改进。这个框架把黑箱拆开,变成可命令行执行的工程化流程。

## 当前训练状态

### strict-flow skill

已完成多轮迭代,核心改动:

| 版本 | Gate 1 行为 | 结果 |
|------|------------|------|
| 原始 | "只有零个替代方案才跳过" → 几乎永远阻塞 | Eval 5 卡死在 Gate 1 |
| iteration-2 | "一个方案明显最优就跳过呈现" → 过度自动 | Eval 1 不列方案直接前进 |
| 当前 | **"始终呈现方案 + 推荐 + 前进"** | 跳过等待,不跳过呈现 |

**evals 已重写**:去掉了跟单轮 `claude -p` 执行环境矛盾的 expectation（"询问用户选择"、"等待确认后才继续"）。改为"呈现并推荐"、"展示计划"、"包含三个 gate 结构"。

### content-rewriter skill

evals + trigger-evals 已准备好,尚未跑过 `make train`。

## 框架改进（本轮完成）

### grader 可靠性修复 (`grade.py`)

- **重试机制**: grader 返回空 expectations 或 JSON 解析失败时自动重试（最多 3 次）
- **JSON 修复**: `repair_json()` 处理 LLM 常见格式错误（trailing comma、缺逗号、JS 注释）
- **多策略解析**: greedy regex → brace-counting → repair,三层递进
- **`--force` 参数**: `make grade SKILL=xxx FORCE=1` 可重跑已有 grading 文件

### benchmark 防御 (`benchmark.py`)

- 跳过 `total=0` 的异常 grading,不影响均值计算
- `config_runs` 为空时 `continue`,避免 `statistics.mean([])` 崩溃

### 其他脚本修复

- `suggest.py`, `generate_evals.py`, `generate_triggers.py`: 加了 `TimeoutExpired` 捕获
- `diff_iterations.py`: 检查 benchmark.json 存在性
- `report.py`: `pass_rate_range` 访问加 `.get()` 防御
- `generate_evals.py`: `__import__("os")` 改成正常 `import os`

### 文档更新

- `CLAUDE.md`: 加了"改进前必读一手数据"指引 + `FORCE=1` 命令
- `TRAIN_README.md`: 命令速查表加了 `FORCE=1`
- `docs/writing-evals.md`: 示例 eval 同步更新 + 加了"单轮执行环境注意事项"
- `suggest.py` 生成的 TRAINING-FEEDBACK.md: 加了一手数据必读区块

## 未完成 / 下一步

### 立即可做
- [ ] strict-flow: 用新 evals 跑一轮 `make train SKILL=strict-flow RUNS=1` 看效果
- [ ] content-rewriter: 跑 `make train SKILL=content-rewriter` 验证 evals 质量

### 中期改进
- [ ] `run_evals.py` 支持并行（目前串行跑 eval,慢）
- [ ] 框架支持多轮 eval（测 Gate 阻塞等交互行为）
- [ ] 集成 skill-creator 的 `eval-viewer/generate_review.py` 做可视化

### 架构考虑
- [ ] 是否要把框架独立出来成通用项目
- [ ] CI:每次改 SKILL.md 自动跑 `make train`,pass_rate 不能比上次低
- [ ] 模型升级回归检测（Claude 版本更新后重跑所有 skill 的 baseline）
