# Skill Training Framework

一个**通用的、与具体 skill 解耦的**项目级 skill 持续训练框架。

把任何符合约定的 skill 丢进来,它都能被反复测试、量化评估、版本化迭代——把 `/skill-creator` 这个黑箱拆开,落地成一套可工程化的方法论。

## 核心理念

> **项目级 skill = 可被反复测试的 prompt 资产。**
>
> 不需要重新训练模型。你优化的是 SKILL.md 这段文本,让固定的 Claude 模型在 in-context 下表现更好。这是 prompt engineering 的工程化形态。

## 两大训练维度

本框架覆盖两个独立的优化维度,对应 skill 的两个部分:

| 维度 | 优化对象 | 测什么 | 用什么工具 |
|---|---|---|---|
| **能力评估** | SKILL.md body(正文) | 触发后做得好不好 | 本框架(`make train`) |
| **触发率优化** | SKILL.md description(frontmatter) | 能否被正确触发 | 官方 `skill-creator/run_loop.py` |

官方 skill-creator 只做了触发率优化。**能力评估是黑箱的来源**——本框架补的就是这一块。

## 训练循环(单轮迭代)

```
  ┌──────────────────┐
  │ 1. 写/改 SKILL.md │
  └────────┬─────────┘
           ↓
  ┌──────────────────────────┐
  │ 2. 准备 evals/evals.json │ ← 测试集(prompt + expectations)
  └────────┬─────────────────┘
           ↓
  ┌──────────────────────────────────┐
  │ 3. make run SKILL=xxx            │ ← executor: claude -p × N runs
  │    with_skill × N + without_skill │   (without_skill 从 baseline 缓存恢复)
  └────────┬─────────────────────────┘
           ↓
  ┌──────────────────────────────────┐
  │ 4. make grade SKILL=xxx          │ ← grader: LLM-as-judge
  │    逐 run 给每条 expectation 打分 │
  └────────┬─────────────────────────┘
           ↓
  ┌──────────────────────────────┐
  │ 5. make benchmark SKILL=xxx │ ← 跨 run 聚合取均值 + 波动范围
  └────────┬───────────────────┘
           ↓
  ┌──────────────────────────────┐
  │ 6. 人工 review + 写 feedback│
  └────────┬───────────────────┘
           ↓
  ┌──────────────────┐
  │ 7. 改进 SKILL.md │ → 回到第 1 步,新 iteration
  └──────────────────┘
```

## 与 ML 训练的对照

| ML 概念 | 框架里的对应物 |
|---|---|
| Training data | `evals/evals.json` 中的 prompt 集合 |
| Labels / ground truth | `expectations` 字段 |
| Model weights | **SKILL.md 文本本身**(不变的是底层模型) |
| Forward pass | `claude -p` 执行 eval（× N runs 取均值） |
| Epoch | 一次 `make train`（所有 eval × N runs） |
| Loss / metric | expectation pass_rate |
| Validation set | held-out evals(可选) |
| Baseline | `without_skill` 配置 |
| Checkpoint | `workspaces/<skill>/iteration-N/` |
| Early stopping | feedback 全空 / pass_rate 收敛 |
| Overfitting | SKILL.md 写死了测试集细节 → 泛化差 |
| Regularization | "keep the prompt lean",删冗余指令 |

## 快速上手

### 1. 检查依赖

```bash
cd skill-training-framework
make check
```

确认 `claude` CLI 可用、Python 3 可用、`jq` 可用。

### 2. 为你的 skill 准备 evals

```bash
make init SKILL=<skill-name>
```

会在 `skills/<skill-name>/evals/evals.json` 创建模板。编辑它,填入 3-5 个测试用例。

如果还想测触发率,额外创建 `skills/<skill-name>/evals/trigger-evals.json`:
```json
[
  {"query": "用户的真实提问...", , "should_trigger": true},
  {"query": "不应该触发的提问...", "should_trigger": false}
]
```

### 3. 跑一次完整能力评估

```bash
make train SKILL=<skill-name>            # 默认每个 eval 跑 3 次取均值
make train SKILL=<skill-name> RUNS=1     # 单次运行（旧行为）
```

等价于:
```bash
make run       SKILL=<skill-name>   # 执行 × N runs，baseline 缓存复用
make grade     SKILL=<skill-name>   # 逐 run LLM-as-judge 评分
make benchmark SKILL=<skill-name>   # 跨 run 聚合取均值
make report    SKILL=<skill-name>   # 输出报告（含波动范围）
```

产物保存在 `workspaces/<skill-name>/iteration-N/`。

### 4. 查看结果

```bash
make report SKILL=<skill-name>
```

输出 markdown 报告,包含:
- with-skill vs without-skill 的 pass_rate 对比
- 每个 eval 的均值及波动范围（如 `0.65 (0.60-0.80, n=3)`）
- 与上一轮的 delta
- 失败的 expectations 及证据（标注来自哪个 run）

### 5. 改 SKILL.md,再跑一轮

```bash
vim skills/<skill-name>/SKILL.md
make train SKILL=<skill-name>
make diff SKILL=<skill-name>   # 对比最近两轮 iteration
```

### 6. 优化触发率(可选,用官方脚本)

```bash
make trigger-eval SKILL=<skill-name>      # 先测当前触发率
make trigger-optimize SKILL=<skill-name>  # 自动迭代优化 description
```

## 目录结构

```
skill-training-framework/
├── README.md              ← 本文件
├── Makefile               ← 通用入口(能力评估 + 触发率优化)
├── scripts/
│   ├── run_evals.py       ← executor: 用 claude -p 跑所有 eval
│   ├── grade.py           ← grader: LLM-as-judge
│   ├── benchmark.py       ← 汇总 grading 结果
│   ├── report.py          ← 生成 markdown 报告
│   ├── diff_iterations.py ← 对比两轮 iteration
│   └── utils.py           ← 共用工具
├── templates/
│   └── evals.template.json
├── workspaces/            ← 训练产物(不 commit)
└── docs/
    ├── methodology.md     ← 方法论详解
    ├── writing-evals.md   ← 怎么写好 expectations
    └── debugging.md       ← 遇到问题怎么办

skills/<skill-name>/       ← 任何项目级 skill
├── SKILL.md               ← 必需
└── evals/
    ├── evals.json         ← 必需(能力评估测试集)
    └── trigger-evals.json ← 可选(触发率测试集)

workspaces/<skill-name>/   ← 训练产物
├── baseline/              ← without_skill 缓存（首次训练后自动生成，后续复用）
│   ├── baseline_meta.json
│   └── eval-1/without_skill/run-1/..., run-3/...
├── iteration-1/
│   ├── eval-1/
│   │   ├── with_skill/
│   │   │   ├── run-1/outputs/, timing.json, transcript.md
│   │   │   ├── run-2/...
│   │   │   └── run-3/...
│   │   └── without_skill/  (从 baseline 缓存恢复)
│   │       ├── run-1/...
│   │       └── run-3/...
│   ├── grading/
│   │   ├── eval-1-with_skill-run-1.json
│   │   ├── eval-1-with_skill-run-2.json
│   │   └── ...
│   ├── benchmark.json     ← 聚合结果（含 eval_summary + per-run details）
│   └── report.md
└── iteration-2/
```

## 关键设计决策

- **Multi-run averaging (default 3)** — 单次 `claude -p` 输出有随机性，同一 prompt 跑 3 次可能得到完全不同的结果。取均值 + min-max range 消除噪声。
- **Baseline caching** — `without_skill` 结果不会因 SKILL.md 改动而变化（底层模型和 prompt 相同），首次跑后缓存到 `workspaces/<name>/baseline/`，后续迭代自动复用，节省 ~50% API 调用。
- **Backward compatible** — `RUNS=1 make train` 退化为旧行为；旧格式 iteration 可被所有脚本读取。

## 约定(Contract)

任何 skill 想被这个框架训练,只需满足:

1. **位置**: 放在 `skills/<skill-name>/`
2. **必有**: `SKILL.md`(带 YAML frontmatter)
3. **必有**: `evals/evals.json`(可用 `make init` 生成模板)

满足这三条 → `make train SKILL=xxx` 就能跑。

触发率优化额外需要 `evals/trigger-evals.json`,格式见上方。

## 文档

- [docs/methodology.md](docs/methodology.md) — 方法论和原理
- [docs/writing-evals.md](docs/writing-evals.md) — 怎么写好 evals 和 expectations
- [docs/debugging.md](docs/debugging.md) — 常见问题排查
