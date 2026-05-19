# Skill 持续训练框架 — 使用手册

本文档手把手教你如何使用 `skill-training-framework/` 对任何项目级 skill 进行持续训练。

**前提**: 已安装 Claude Code CLI (`claude`)、`uv`、`jq`。

**所有 `make` 命令都在项目根目录执行**，不需要进入子目录，不需要开 Claude 对话框。首次使用前确认终端里 `claude -p "hello"` 能跑通（完成 CLI 认证）。

---

## 一、完整流程概览

```
/skill-creator 创建 skill
       ↓
把 skill 放到 skills/ 目录
       ↓
make generate-evals SKILL=xxx      ← AI 自动生成能力评估测试集
make generate-triggers SKILL=xxx   ← Inversion 模式生成触发率测试集
       ↓
（可选）审阅并调整 evals
       ↓
make train SKILL=xxx               ← 跑一轮迭代（执行×3次取均值 → 评分 → 汇总 → 报告）
       ↓
make suggest SKILL=xxx             ← 生成改进建议 → skills/<name>/TRAINING-FEEDBACK.md
       ↓
Claude 对话："帮我改进 xxx skill"   ← Claude 读 TRAINING-FEEDBACK.md，协助改 SKILL.md
       ↓
make train SKILL=xxx               ← 验证改动效果
       ↓
make diff SKILL=xxx                ← 对比进步
       ↓
重复直到收敛
       ↓
make trigger-optimize SKILL=xxx    ← 最后优化触发率（可选）
       ↓
make deploy SKILL=xxx              ← 部署到全局 ~/.claude/skills/ 和 ~/.agent/skills/
```

---

## 二、项目结构速览

```
auto_train_skills/
├── skill-training-framework/       ← 框架本体（不用改）
│   ├── Makefile                    ← 所有命令入口（RUNS 变量控制每 eval 跑几次）
│   ├── scripts/                    ← 执行、评分、生成、汇总脚本
│   ├── templates/                  ← evals.json 模板
│   ├── workspaces/                 ← 训练产物 + baseline 缓存（自动生成，不 commit）
│   └── docs/                       ← 方法论文档
├── skills/                         ← 你的 skill 们
│   ├── strict-flow/                ← 示例：已有 evals
│   │   ├── SKILL.md
│   │   ├── TRAINING-FEEDBACK.md    ← make suggest 生成，Claude 改进的入口
│   │   └── evals/
│   │       ├── evals.json          ← 能力评估测试集
│   │       └── trigger-evals.json  ← 触发率测试集（可选）
│   └── <your-skill>/
│       ├── SKILL.md
│       ├── TRAINING-FEEDBACK.md
│       └── evals/evals.json
└── TRAIN_README.md                 ← 本文件
```

---

## 三、从零开始：训练一个新 Skill

### Step 0: 确认在项目根目录

```bash
cd /path/to/auto_train_skills
```

之后所有 `make` 命令都在这里执行，不需要进入子目录。

### Step 1: 检查环境

```bash
make check
```

预期输出：
```
==> 检查依赖
  ✓ claude CLI
  ✓ uv
  ✓ jq
  ✓ skill-creator（官方）
==> OK
```

### Step 2: 用 /skill-creator 创建 skill

在 **Claude Code 对话里**操作（不是终端）：

```
/skill-creator

我想创建一个 xxx skill，它的功能是...
```

创建完成后，把 skill 目录放到项目的 `skills/` 下。

**关键**：skill 目录下必须有 `SKILL.md`（带 YAML frontmatter）。

### Step 3: 生成 evals

```bash
make generate-evals SKILL=my-skill
```

AI 自动生成 4-6 个 eval，每个含 4 条 expectations。生成后建议审阅一下。

**如果你更想手写**：
```bash
make init SKILL=my-skill    # 生成空模板，然后手动编辑
```

手写指南见 `docs/writing-evals.md`。

### Step 4: 跑第一轮迭代

```bash
make train SKILL=my-skill
```

默认每个 eval 跑 **3 次**取均值（减少 LLM 输出随机性），`without_skill` baseline 自动缓存到 `workspaces/my-skill/baseline/`。

依次执行：执行 eval × 3 runs → LLM-as-judge 逐 run 评分 → 跨 run 聚合 benchmark → 生成报告（含 pass rate 波动范围）。

产物在 `workspaces/my-skill/iteration-1/`，耗时约 8-15 分钟。

如果想用旧行为（单次运行）：
```bash
make train SKILL=my-skill RUNS=1
```

### Step 5: 生成改进建议

```bash
make suggest SKILL=my-skill
```

分析失败模式，写入 `skills/my-skill/TRAINING-FEEDBACK.md`。

### Step 6: 用 Claude 改进 SKILL.md

在项目根目录开 Claude 对话：

```
帮我改进 my-skill
```

Claude 会自动读取 `skills/my-skill/TRAINING-FEEDBACK.md`，分析失败模式并协助修改 SKILL.md。也可以直接调用 `/skill-creator`，效果相同。

**改 SKILL.md 的原则**：
- 写原则不写规则——解释 why，而非堆 MUST/NEVER
- 不要针对单个 eval 写死规则（过拟合）
- 删掉没起作用的指令，保持 prompt 精简

### Step 7: 验证改动

```bash
make train SKILL=my-skill    # 跑新一轮
make diff  SKILL=my-skill    # 对比前后 pass_rate
```

### Step 8: 重复直到满意

**停止信号**（任一）：
- 通过率连续两轮 delta < 3%（收敛）
- 改了 SKILL.md 但通过率不再提升（到达模型/任务边界）
- 你对实际使用效果已经满意

### Step 9: 部署

```bash
make deploy SKILL=my-skill
```

同步到 `~/.claude/skills/`（Claude Code 全局）和 `~/.agent/skills/`（通用 agent 全局，如存在）。

`evals/` 目录和 `TRAINING-FEEDBACK.md` 不会被部署——这两个是开发产物，不是运行时需要的。

---

## 四、分步执行

`make train` 是一键版。你也可以分步控制：

```bash
make run       SKILL=my-skill    # 只执行（with_skill × N runs，without_skill 从缓存恢复）
make grade     SKILL=my-skill    # 只评分（每个 run 独立评分）
make benchmark SKILL=my-skill    # 只汇总（跨 run 聚合取均值）
make report    SKILL=my-skill    # 只生成报告
```

适用场景：
- `make run` 跑完后先人工看输出质量，再决定要不要评分
- 改了 grader 逻辑后，只重新评分不重跑执行
- 只想重新生成报告

---

## 五、触发率优化（独立循环）

上面的流程测的是 **skill 被触发后做的好不好**。另一个维度是 **skill 能不能被正确触发**。

### 生成 trigger-evals

```bash
make generate-triggers SKILL=my-skill
```

用 **Inversion 反转模式** 自动生成 16-20 条 query（8-10 条 should_trigger:true + 8-10 条 false），并进入交互确认：

```
[1/18] ✓ TRIGGER
    帮我把这段话改写一下，换种表达方式
    Enter=保留  f=翻转  d=删除  q=退出
    →
```

**6 种 Inversion 模式**（从 true query 出发，保留关键词，扭转意图）：

| 模式 | 示例 |
|---|---|
| Scale inversion | "修个小bug" → "从零搭微服务架构" |
| Direction inversion | "改写得更专业" → "把专业文本翻译成通俗解释" |
| Tool substitution | "重构函数" → "做完整 code review" |
| Adjacent domain | "优化文案" → "分析 SEO 关键词密度" |
| Meta-request | "修复类型错误" → "strict flow 和 superpowers 区别?" |
| Overkill detection | "写复杂清洗脚本" → "帮我读一下这个文件" |

### 测试和优化触发率

```bash
make trigger-eval     SKILL=my-skill    # 测试当前触发率
make trigger-optimize SKILL=my-skill    # 自动迭代优化 description（最多5轮）
```

---

## 六、和 /skill-creator 的关系

| 能力 | /skill-creator | 本框架 |
|---|---|---|
| 创建 skill | ✅ 对话式 | 不做（用 /skill-creator） |
| 生成测试集 | 手动 | `make generate-evals` / `make generate-triggers` |
| 跑 eval + 评分 | 对话里临时做 | `make train` 持久化到文件 |
| 改进 SKILL.md | ✅ 对话式 | `make suggest` 生成 TRAINING-FEEDBACK.md，再交给 Claude 对话 |
| 跨版本对比 | 不支持 | `make diff` |
| 触发率优化 | ✅ `run_loop.py` | 复用官方脚本 |
| 部署到全局 | 手动 | `make deploy` |
| 结果持久化 | 不支持 | evals.json + benchmark.json 跟 git 走 |

> **用 /skill-creator 生孩子，用本框架养孩子。**

---

## 七、防漂移：持续训练的核心价值

skill 会"漂移"——底层模型在升级、用户需求在变。本框架通过保留测试集 + 历史基线来检测和应对。

### 定期检测建议

```bash
# 模型升级后立刻跑
make train SKILL=xxx
make diff  SKILL=xxx

# 季度巡检
make train        SKILL=xxx    # 能力是否退化？
make trigger-eval SKILL=xxx    # 触发率是否漂移？
```

---

## 八、命令速查

| 命令 | 作用 | 产物 |
|---|---|---|
| `make check` | 检查依赖 | 终端输出 |
| `make list` | 列出可训练 skill | 终端输出 |
| `make init SKILL=xxx` | 创建 evals 空模板 | `skills/xxx/evals/evals.json` |
| `make generate-evals SKILL=xxx` | AI 自动生成 evals | `skills/xxx/evals/evals.json` |
| `make generate-triggers SKILL=xxx` | Inversion 模式生成 trigger-evals | `skills/xxx/evals/trigger-evals.json` |
| `make run SKILL=xxx` | 执行所有 eval × N runs，baseline 缓存 | `workspaces/xxx/iteration-N/eval-*/` |
| `make grade SKILL=xxx` | LLM 逐 run 评分 | `workspaces/xxx/iteration-N/grading/` |
| `make grade SKILL=xxx FORCE=1` | 重跑所有评分（修复坏数据） | `workspaces/xxx/iteration-N/grading/` |
| `make benchmark SKILL=xxx` | 跨 run 聚合取均值 | `workspaces/xxx/iteration-N/benchmark.json` |
| `make report SKILL=xxx` | 生成报告（含波动范围） | `workspaces/xxx/iteration-N/report.md` |
| `make train SKILL=xxx` | 一键跑完整轮（默认 3 runs） | 以上全部 |
| `make train SKILL=xxx RUNS=1` | 单次运行（旧行为） | 以上全部 |
| `make suggest SKILL=xxx` | 生成改进建议 | `skills/xxx/TRAINING-FEEDBACK.md` |
| `make diff SKILL=xxx` | 对比最近两轮 | 终端输出 |
| `make trigger-eval SKILL=xxx` | 测触发率 | 终端输出 |
| `make trigger-optimize SKILL=xxx` | 自动优化 description | 终端输出 |
| `make deploy SKILL=xxx` | 部署到全局 | `~/.claude/skills/` + `~/.agent/skills/` |
| `make clean SKILL=xxx` | 清空训练产物和 baseline 缓存 | 删除 `workspaces/xxx/` |

---

## 九、深入阅读

### 框架方法论文档

- `skill-training-framework/docs/methodology.md` — 和 ML 训练的对照、迭代心态
- `skill-training-framework/docs/writing-evals.md` — 怎么写好 expectations（附反模式）
- `skill-training-framework/docs/debugging.md` — 常见问题排查

### 实战案例文档

- **`docs/content-rewriter-training-guide.md`** — 完整训练实战指南，以 content-rewriter 为例。包含：
  - 知识点扫盲（Skill / Eval / Baseline / Grader / Delta / Iteration）
  - 文件结构详解（evals.json、SKILL.md、grading JSON 每个字段解释）
  - 完整实战流程（3 个阶段的真实数据：evals 太简单 → 发现 skill 有害 → 修复）
  - Evals 设计最佳实践（好 eval vs 坏 eval、expectation 编写原则）
  - SKILL.md 改进最佳实践（常见问题模式、改进前必读一手数据）
  - 部署后 6 种模式的 before/after 对比测试
  - 训练机制：`claude -p` 通过 `--append-system-prompt` 注入 SKILL.md

### Skill 内部文档

- `skills/content-rewriter/TRAINING-FEEDBACK.md` — 最新一轮训练的失败模式分析和改进建议
- `skills/strict-flow/TRAINING-FEEDBACK.md` — strict-flow skill 的训练反馈

---

## 十、训练机制说明

### `claude -p` 与 Skill 注入

训练框架通过 `claude -p`（非交互管道模式）运行 eval，**不走** Claude Code 的 skill 自动发现系统。

```
with_skill:    claude -p "<eval prompt>" --append-system-prompt "<SKILL.md 全文>"
without_skill: claude -p "<eval prompt>"
```

- `run_evals.py` 用 `--append-system-prompt` 将 `skills/<name>/SKILL.md` 的完整文本注入
- `references/`、`agents/` 等子目录文件**不会**被注入训练——只有 SKILL.md 本身
- A/B 对比完全可控：with_skill 一定有 SKILL.md，without_skill 一定没有

### 训练 vs 部署的区别

| 场景 | Skill 加载方式 | references/ 是否生效 |
|------|--------------|-------------------|
| `make train`（训练） | `--append-system-prompt` 显式注入 SKILL.md | 不生效 |
| Claude Code 交互模式（部署后） | Claude Code 内部 skill 发现+触发系统 | 生效 |
| `claude -p`（手动测试） | 依赖全局 `~/.claude/skills/` 中的 skill | 取决于 Claude Code 自动加载 |
