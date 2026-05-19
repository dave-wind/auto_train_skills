# Skill 训练实战指南 — 以 content-rewriter 为例

> 本文档基于 content-rewriter skill 的真实训练过程（3 个阶段）总结，涵盖从零开始到跑通一轮完整改进的所有知识点。
>
> **注意：** 由于中途执行了 `make clean`（清理 workspace 和 baseline 缓存），workspace 的 iteration 编号会重置。下文用"阶段"区分逻辑步骤，与 workspace 的 iteration-N 编号不完全对应。

---

## 一、知识点扫盲

### 1.1 什么是 Skill？

Skill 是一个 Markdown 文件（`SKILL.md`），由 **YAML frontmatter** + **正文** 两部分组成。它本质是一段 prompt，告诉 Claude 在特定场景下如何行为。

```
skills/<name>/SKILL.md       ← skill 定义
skills/<name>/evals/          ← 测试集
```

**SKILL.md 结构：**

```yaml
---
name: content-rewriter                          # skill 名称
description: 改写和优化文本内容...当用户说"改写"...时使用  # 触发条件描述
type: prompt                                    # 类型（prompt 是最常见）
parameters:                                     # 参数定义（供 skill 系统使用）
  - name: original_text
    type: string
    required: true
---
# 正文（skill 的行为指令）
你是一位资深的文字编辑...
```

- **frontmatter 中的 `description`**：决定 skill **什么时候被触发**。用户输入匹配关键词时激活。
- **正文（body）**：决定 skill 触发后 **怎么做事**。这是训练的主要对象。

### 1.2 什么是训练？

训练 = 跑一组测试（evals），量化 skill 的表现，找出问题，改进 SKILL.md，再验证。

**核心逻辑：** 同一个 prompt，分别用 `with_skill`（带 skill）和 `without_skill`（不带 skill）跑，对比差异。skill 的价值 = with_skill 分数 - without_skill 分数（即 **delta**）。

### 1.2.1 Skill 是怎么注入的？

框架**不使用** Claude Code 的 skill 自动发现系统。它通过 `claude -p` 的 `--append-system-prompt` 参数显式注入 SKILL.md 内容：

```
with_skill:    claude -p "<eval prompt>" --append-system-prompt "<SKILL.md 全文>"
without_skill: claude -p "<eval prompt>"
```

`run_evals.py` 用 `utils.load_skill_md()` 读取 `skills/<name>/SKILL.md` 的完整文本（frontmatter + 正文），原样作为 system prompt 注入。

**这意味着：**
- `references/`、`agents/` 等子目录的文件**不会**被注入到训练中——只有 SKILL.md 本身
- 训练环境和部署环境行为可能不同：部署后 Claude Code 交互模式会加载整个 skill 目录（含 references/）
- A/B 对比完全可控：with_skill 一定有 SKILL.md，without_skill 一定没有

### 1.3 什么是 Eval？

Eval 是一条测试用例。每个 eval 包含：

- `prompt`：给 Claude 的输入（模拟用户请求）
- `expectations`：一组期望条件，用来评判输出是否正确
- `expected_output`：对期望输出的简要描述（给人看的，不参与评分）

**eval 不等于单元测试。** Eval 的 expectation 是自然语言描述，由 LLM（grader）来评判 pass/fail，不是代码断言。

### 1.4 什么是 Baseline？

Baseline 是 **不带 skill** 的运行结果（`without_skill` 配置）。它代表 Claude 在没有 skill 帮助时的原生能力。

**为什么需要 baseline？** 如果一个问题 Claude 本来就能做好，那 skill 没有加分价值。只有 skill 做到了 baseline 做不到的事，delta 才为正。

**Baseline 缓存：** `without_skill` 结果在第一次运行后会缓存到 `workspaces/<name>/baseline/`。后续迭代复用缓存，节省约 50% 的 API 调用。

```
Iteration 1: with_skill (新跑) + without_skill (新跑，然后缓存)
Iteration 2: with_skill (新跑) + without_skill (从缓存读取)
```

### 1.5 什么是 Grader？

Grader 是另一个 LLM 调用（`claude -p`），充当"评委"。它读取 eval 的 prompt、期望输出 和模型实际输出，逐条 expectation 判断 pass/fail 并给出证据。

评分结果保存在 `grading/` 目录：

```
grading/
├── eval-1-with_skill-run-1.json      ← eval 1, with_skill 配置, 第 1 次运行的评分
├── eval-1-without_skill-run-1.json   ← eval 1, without_skill 配置
└── ...
```

### 1.6 什么是 Iteration？

Iteration 是一次完整的训练轮次。每次 `make train` 创建一个新的 iteration 目录：

```
workspaces/content-rewriter/
├── baseline/                  ← without_skill 缓存
├── iteration-1/               ← 第一轮
│   ├── eval-1/ ... eval-6/
│   ├── grading/
│   ├── benchmark.json
│   └── report.md
└── iteration-2/               ← 第二轮（SKILL.md 改进后）
```

`make diff` 可以对比两个 iteration 的数据。

### 1.7 什么是 Delta？

```
delta = with_skill_pass_rate - without_skill_pass_rate
```

- **delta > 0**：skill 有正向价值（好）
- **delta = 0**：skill 没带来额外价值（evals 可能太简单）
- **delta < 0**：skill 反而有副作用（SKILL.md 有害指令）

### 1.8 Multi-run Averaging

单次 `claude -p` 输出方差很大。默认每个 eval 跑 **3 次**（`RUNS=3`），取均值 + min-max range：

```
pass_rate: 0.85 (0.75-1.00, n=3)   ← 均值 0.85, 最低 0.75, 最高 1.00, 跑了 3 次
```

`RUNS=1` 跑单次（快但不可靠），`RUNS=3` 是推荐默认值。

---

## 二、文件结构详解

### 2.1 evals.json 字段解释

```json
{
  "skill_name": "content-rewriter",         // 对应 skills/<name>/ 目录名
  "evals": [
    {
      "id": 1,                              // eval 编号，唯一标识
      "name": "concise-remove-redundancy",  // 人类可读的名称（出现在报告中）
      "prompt": "精简这段话：...",            // 发给 claude -p 的输入内容
      "expected_output": "A single concise rewrite...",  // 期望输出的简要描述（给人看，grader 参考）
      "files": [],                          // 附加文件（通常为空）
      "expectations": [                     // 评判标准列表
        "The response is entirely in Chinese",
        "The rewrite removes redundant paired expressions",
        "..."
      ]
    }
  ]
}
```

**字段说明：**

| 字段 | 必填 | 说明 |
|------|------|------|
| `id` | 是 | 唯一编号，用于目录命名（eval-1, eval-2...） |
| `name` | 是 | 出现在报告的名称，用 kebab-case |
| `prompt` | 是 | 模拟用户输入，发给 `claude -p` |
| `expected_output` | 是 | 给 grader 的参考，描述期望输出 |
| `files` | 否 | 附加文件路径（用于需要读取文件的 eval） |
| `expectations` | 是 | 字符串数组，每条是一个可判断的 pass/fail 条件 |

### 2.2 SKILL.md 字段解释

```yaml
---
name: content-rewriter           # skill 名称，必须与目录名一致
description: 改写和优化文本...     # 触发描述，决定什么时候激活
type: prompt                     # skill 类型
parameters:                      # 参数定义
  - name: original_text
    type: string
    description: 要改写的原始文本
    required: true
  - name: rewrite_mode
    type: string
    description: "改写模式：concise/expand/formal/..."
    required: false
---
```

| 区域 | 作用 |
|------|------|
| `description` | **触发条件** — 用户输入匹配时激活 skill。优化用 `make trigger-eval` |
| `parameters` | 参数定义，影响 skill 系统如何传参 |
| **正文** | **行为指令** — 告诉 skill 触发后怎么做。训练优化的主要对象 |

### 2.3 Workspace 输出文件

```
iteration-N/
├── eval-1/
│   ├── eval_metadata.json           ← eval 的 prompt、expectations 等元信息
│   ├── with_skill/
│   │   ├── run-1/
│   │   │   ├── outputs/output.txt   ← 模型实际输出（最关键的一手数据）
│   │   │   ├── transcript.md        ← 完整对话记录
│   │   │   └── timing.json          ← 耗时统计
│   │   ├── run-2/ ...
│   │   └── run-3/ ...
│   └── without_skill/               ← 从 baseline 缓存恢复
│       └── run-1/ ...
├── grading/
│   ├── eval-1-with_skill-run-1.json   ← grader 对每条 expectation 的评分
│   └── ...
├── benchmark.json    ← 聚合数据：均值、方差、per-run 详情
└── report.md         ← 人类可读报告
```

**最常查看的文件：**

| 文件 | 用途 |
|------|------|
| `output.txt` | 看模型到底输出了什么（一手数据） |
| `grading/*.json` | 看 grader 为什么判 pass/fail（证据） |
| `report.md` | 快速看整体通过率和失败项 |
| `benchmark.json` | 完整的数值数据，含 per-run 明细 |

### 2.4 grading JSON 结构

```json
{
  "eval_id": 1,
  "eval_name": "concise-remove-redundancy",
  "configuration": "with_skill",
  "run_number": 1,
  "result": {
    "pass_rate": 0.75,     // 4 条 expectation 通过了 3 条
    "passed": 3,
    "failed": 1,
    "total": 4
  },
  "expectations": [
    {
      "text": "The response contains exactly one rewritten version...",
      "passed": false,
      "evidence": "Includes parenthetical meta-commentary: (原文 130 字 → 47 字...)"
    }
  ]
}
```

---

## 三、命令速查

所有命令在**项目根目录**执行。前置依赖：`claude` CLI、`uv`、`jq`。

```bash
# 基础
make check                        # 检查依赖是否就绪
make list                         # 列出所有可训练的 skill

# 完整训练（一个命令搞定）
make train SKILL=<name>           # 默认 RUNS=3，跑 eval × 3 次 → 评分 → 汇总 → 报告
make train SKILL=<name> RUNS=1    # 单次运行（快，但不可靠）

# 分步执行
make run SKILL=<name>             # 只跑 eval（不评分）
make grade SKILL=<name>           # 只评分（依赖已有的 run 结果）
make grade SKILL=<name> FORCE=1   # 强制重跑所有评分（修复坏数据）
make benchmark SKILL=<name>       # 聚合评分 → benchmark.json
make report SKILL=<name>          # 生成 report.md

# 对比与诊断
make diff SKILL=<name>            # 对比最近两个 iteration
make suggest SKILL=<name>         # 生成 TRAINING-FEEDBACK.md（改进建议）

# 数据集管理
make generate-evals SKILL=<name>    # AI 生成能力 evals
make generate-triggers SKILL=<name> # AI 生成触发 evals（hard negatives）
make init SKILL=<name>              # 创建空的 evals 模板

# 触发率优化（委托给官方 skill-creator）
make trigger-eval SKILL=<name>
make trigger-optimize SKILL=<name>

# 部署与清理
make deploy SKILL=<name>          # 部署到 ~/.claude/skills/ 和 ~/.agent/skills/
make clean SKILL=<name>           # 清理 workspace + baseline 缓存
```

---

## 四、完整实战流程

以下是我们改进 content-rewriter 的真实过程，从首轮训练到最终验证。全程使用 `RUNS=1`（快速迭代），正式训练建议用默认 `RUNS=3` 获取更可靠的数据。

### 第 0 步：准备

```bash
# 确认 skill 结构完整
ls skills/content-rewriter/SKILL.md        # 必须存在
ls skills/content-rewriter/evals/evals.json  # 必须存在
```

### 第 1 步：首轮训练

```bash
make train SKILL=content-rewriter   # RUNS=1，快速验证
```

首次运行会：
1. 跑所有 eval × 2 配置（with_skill / without_skill）
2. 缓存 without_skill 结果到 baseline/
3. 对每个 run 评分
4. 生成 benchmark.json + report.md

**看报告：**

```
with_skill:    0.958
without_skill: 0.917
delta:         +0.041    ← 极小，几乎没区分度
```

**问题：** 6 个 eval 中 5 个 with_skill = without_skill，只有 eval 6 有区分度。Evals 太简单，baseline Claude 本身就能做好。

### 第 2 步：设计更好的 Evals（提升区分度）

**原则：好的 eval 应该测试 skill 独特的价值，而不是 Claude 的通用能力。**

**content-rewriter iteration-1 的问题：**
- 文本太短太简单 → baseline 轻松通过
- 没有测试"单版本输出"约束 → baseline 倾向于提供多个版本，但没被抓住

**改进策略：**

1. **用更复杂的文本** — 冗余长句、重度口语、技术术语，让 baseline 容易"多做"
2. **每个 eval 都包含约束性 expectation** — "exactly one rewrite"、"no markdown formatting"、"no meta-commentary"
3. **去掉不实际的精确目标** — 不要要求 60-75% 长度（LLM 做不到），改为定性约束

**实操：重写 evals.json**

```json
{
  "expectations": [
    "Technical terms are simplified to everyday language...",
    "The rewrite does not add claims not present in the original...",
    "The response is exactly one casual rewrite without multiple labeled versions...",
    "The tone uses conversational patterns..."
  ]
}
```

关键：第 3 条 expectation 测试的是 **skill 的独特约束**（单版本输出），baseline 没有这个指令，容易失败。

### 第 3 步：二轮训练 — 发现 skill 有害

```bash
make train SKILL=content-rewriter   # RUNS=1
```

```
with_skill:    0.833   ← 反而比 baseline 低！
without_skill: 0.958
delta:         -0.125  ← skill 有害
```

**Evals 现在有区分度了（好），但暴露了 SKILL.md 的问题（坏）。**

失败的 with_skill 输出：
- Eval 1：加了元评论 `(原文 130 字 → 47 字，精简至约 36%...)`
- Eval 3：输出了 bold 标题 + 对比表格 + 多个版本
- Eval 6：输出了 3 个方案 A/B/C

**根因：** SKILL.md 的"第3步：输出"是空的，而"故障排查"写着"改写后对比确认"，鼓励模型展示工作过程。

### 第 4 步：生成改进建议

```bash
make suggest SKILL=content-rewriter
# → 生成 skills/content-rewriter/TRAINING-FEEDBACK.md
```

**TRAINING-FEEDBACK.md 包含：**
- 失败模式分析（归纳为 2-3 个根因）
- 修改方向（原则级别）
- 不要改的部分
- 过拟合警告

**重要：不要只看摘要就改 SKILL.md。** 先读一手数据验证：

```bash
# 看模型实际输出了什么（替换为当前最新的 iteration 编号）
cat workspaces/content-rewriter/iteration-N/eval-1/with_skill/run-1/outputs/output.txt
cat workspaces/content-rewriter/iteration-N/eval-3/with_skill/run-1/outputs/output.txt

# 看 grader 的评分依据
cat workspaces/content-rewriter/iteration-N/grading/eval-1-with_skill-run-1.json
```

### 第 5 步：改进 SKILL.md

基于 TRAINING-FEEDBACK.md + 一手数据验证，改了三处：

**改动 1：第1步 — 明确"内部思考，不输出分析"**

```diff
- ### 第 1 步：分析原文
- - 理解原文的核心含义
- - 识别文体、语气、受众
- - 判断需要改进的地方
+ ### 第 1 步：分析原文
+ 在内部理解原文的核心含义、文体、语气、受众和需要改进的地方。不要在输出中呈现分析过程。
```

**改动 2：第3步 — 从空白改为明确的输出纪律**

```diff
- ### 第 3 步：输出
+ ### 第 3 步：输出
+
+ 只输出改写后的文本本身。不添加分析说明、对比表格、压缩比例、多个版本或追问。
+ 输出应该可以直接替换原文使用。
```

**改动 3：故障排查 — 去掉有害指令**

```diff
- 解决：改写前先复述原文核心含义，改写后对比确认
+ 解决：在内心确认改写保留了原文核心含义，不要在输出中展示对比过程
```

**没改的部分：** 6 个模式定义、两个示例、frontmatter（TRAINING-FEEDBACK 说这些没问题）。

### 第 6 步：清理 + 验证

```bash
make clean SKILL=content-rewriter     # 清理旧 baseline 缓存（会重置 workspace iteration 编号）
make train SKILL=content-rewriter     # 重新训练
```

```
with_skill:    1.000   ← 完美！
without_skill: 0.958
delta:         +0.042  ← 正向
```

三个失败全部修复。Skill 不再有害。

### 第 7 步：对比 + 部署

```bash
make diff SKILL=content-rewriter      # 对比 iteration-1 vs iteration-2
make deploy SKILL=content-rewriter    # 部署到全局
```

---

## 五、Evals 设计最佳实践

### 5.1 好的 eval 长什么样

**特征：**
- 测试 skill 独特约束，而非模型通用能力
- 至少 1 条 expectation 测试"只有 skill 才知道的规则"
- without_skill 应该在至少 1 条 expectation 上失败（否则 eval 太简单）
- expectation 是可判断的自然语言陈述，不是代码断言

**content-rewriter 的区分性 expectations：**

| Expectation | 测什么 | 为什么 baseline 容易失败 |
|------------|--------|----------------------|
| "exactly one rewrite, no alternatives" | 输出纪律 | baseline 倾向于提供多个版本 |
| "no meta-commentary" | 输出纯粹性 | baseline 倾向于解释做了什么 |
| "no markdown formatting" | 格式约束 | baseline 倾向于用 headers/bullets |
| "no fabricated metrics" | 忠实度 | baseline 倾向于编造数据 |
| "conversational tone, not marketing" | 语气准确性 | baseline 倾向于保留原始语气 |

### 5.2 坏的 eval 长什么样

**特征：**
- with_skill 和 without_skill 都得 1.0 → 没区分度
- expectation 太模糊（"输出质量高"）→ grader 随机判
- 测试 LLM 通用能力而非 skill 特定行为
- 要求 LLM 做不到的事（如精确的字符数比例）

**content-rewriter 的失败教训：**

| 问题 eval | 为什么失败 |
|-----------|----------|
| "rewrite is 60-75% of original length" | LLM 无法精确控制输出长度比例，with_skill 和 without_skill 都失败 |
| "preserve Russian text" | 任何 LLM 都倾向统一语言，不是 skill 的问题 |
| 5 字扩写到 150-200%（7-10 字） | 太短，没有有意义的扩写空间 |

### 5.3 Expectation 编写原则

1. **每条 expectation 只测一件事** — 不要写"输出简洁且准确且无幻觉"，拆成三条
2. **可观察、可判断** — grader 需要从输出中找到证据。"语气友好"比"写得好"好
3. **明确 what not how** — 说期望结果，不说实现方式
4. **4 条左右为宜** — 太少区分度不够，太多稀释重点

### 5.4 如何判断 evals 需要改进

看 report.md 中的 **without_skill 失败项（sanity check）**：

- **without_skill 0 失败** → evals 太简单，baseline 全能过，没有区分度
- **without_skill 失败在核心 expectation 上** → 好的 eval，正好测出 skill 的价值
- **without_skill 失败在无关 expectation 上** → expectation 设计有问题

---

## 六、SKILL.md 改进最佳实践

### 6.1 核心原则

1. **写原则不写规则** — 解释 why，而非堆 MUST/NEVER
2. **不针对单个 eval 写死规则** — 会过拟合
3. **删掉没起作用的指令** — 保持 prompt 精简
4. **不要动 "What NOT to Change" 列出的部分** — 避免破坏已有效果
5. **skill 不应该让事情变糟** — delta < 0 说明 SKILL.md 有害指令，需要删除或修改

### 6.2 改进前必做的验证

```
1. 读 TRAINING-FEEDBACK.md → 了解全局
2. 读一手数据 → 验证诊断
   - output.txt（模型实际输出）
   - grading/*.json（grader 评分证据）
3. 改 SKILL.md
4. make clean + make train → 验证
```

### 6.3 常见的 SKILL.md 问题模式

| 问题 | 症状 | 解法 |
|------|------|------|
| 空的输出步骤 | 模型自由发挥，加分析/多版本 | 填充明确的输出格式指令 |
| 有害的故障排查 | 鼓励模型展示过程 | 改为内部检查，不输出 |
| 过度结构化的指令 | 模型在输出中复刻结构 | 简化，强调"只输出结果" |
| 没有输出约束 | 模型提供多个版本/追问 | 加"只输出一个最终结果" |

---

## 七、完整训练循环（速查版）

```
┌─────────────────────────────────────┐
│  make train SKILL=<name>            │  ← 收集数据
│  (eval × N runs → grade → report)   │
└──────────────┬──────────────────────┘
               ↓
┌─────────────────────────────────────┐
│  看 report.md                       │  ← 诊断
│  - with_skill pass_rate 够高吗？     │
│  - delta 是正的吗？                  │
│  - 哪些 expectation 失败了？         │
└──────────────┬──────────────────────┘
               ↓
     ┌─────────┴──────────┐
     ↓                    ↓
  evals 太简单          skill 有问题
  (delta ≈ 0)          (delta < 0)
     ↓                    ↓
  改 evals.json        make suggest →
  (加约束性             读 TRAINING-FEEDBACK.md
   expectations)        读一手数据验证
     ↓                    ↓
  make train            改 SKILL.md
                        make clean
                        make train
     └─────────┬──────────┘
               ↓
┌─────────────────────────────────────┐
│  make diff SKILL=<name>             │  ← 对比验证
└──────────────┬──────────────────────┘
               ↓
┌─────────────────────────────────────┐
│  make deploy SKILL=<name>           │  ← 满意后部署
└─────────────────────────────────────┘
```

---

## 八、content-rewriter 训练数据总结

> 由于中途执行了 `make clean`，workspace 的 iteration 编号重置了。下表用"阶段"对应文档中的步骤，"workspace iteration" 是实际目录名。

| 阶段 | workspace iteration | with_skill | without_skill | delta | 主要改动 |
|------|-------------------|-----------|--------------|-------|---------|
| 1（原始 evals） | iteration-1（已 clean） | 0.958 | 0.917 | +0.041 | 初始状态，evals 太简单 |
| 2（新 evals） | iteration-1 | 0.833 | 0.958 | **-0.125** | evals 有区分度了，但暴露 skill 有害 |
| 3（改进 SKILL.md） | iteration-2 | **1.000** | 0.958 | **+0.042** | 修复输出纪律，skill 不再有害 |

**关键洞察：**
- Delta 从 +0.041 → -0.125 → +0.042，不是线性进步
- 中间的"退步"（-0.125）反而是最有价值的一步——它暴露了 SKILL.md 的真正问题
- 好的 evals 不是让分数变高，而是**让问题暴露出来**

---

## 九、部署后实测验证

部署命令：`make deploy SKILL=content-rewriter`

以下使用 `claude -p` 直接测试部署后的 skill，验证 6 种改写模式的实际效果。

### 9.1 精简模式（concise）

**输入：**
> 精简这段话：在这个充满着不确定性因素和复杂多变的市场环境之中，我们的团队通过深入细致的研究分析和全面系统的市场调研，最终得出了一个非常重要的结论，那就是我们需要在产品的核心功能层面进行一次彻底而全面的升级和改造，这样才能够真正有效地提升用户的使用体验，让用户在我们的平台上获得更加优质的服务体验和更加满意的使用感受。

**改进前（旧 SKILL.md）：**
> 复杂多变的市场环境中，团队经深入研究和系统调研得出结论：需全面升级产品核心功能，以切实提升用户体验和服务质量。
>
> （原文 130 字 → 47 字，精简至约 36%，去除了"不确定性因素"、"深入细致"、"全面系统"、"非常重要的结论，那就是"、"彻底而全面的升级和改造"等冗余修饰，合并了末尾重复的"体验/感受"表达。）

**改进后（新 SKILL.md）：**
> 面对复杂多变的市场环境，我们经过深入研究和系统调研，得出结论：必须全面升级产品核心功能，才能真正提升用户体验和服务质量。

**对比：** 改写质量相当，但旧版追加了整段元评论（字数压缩比、去除内容说明），新版直接输出结果。

---

### 9.2 创意广告模式（creative）

**输入：**
> 用创意广告风格重写：这款运动鞋很轻便，跑步的时候特别舒服。

**改进前（旧 SKILL.md）：**
> ## 创意广告风格改写
>
> **原文：** 这款运动鞋很轻便，跑步的时候特别舒服。
>
> ---
>
> ### 方案 A — 意境向
> > 脚下无鞋，心中有风。每一步落地都像踩进一朵云里，轻盈到让地心引力怀疑人生。穿上它，你跑的不是路——是飞。
>
> ### 方案 B — 对比向
> > 一根羽毛的重量，一双跑鞋的灵魂。当你起跑的那一刻，脚底只剩风的私语，膝盖只剩享受的叹息。轻，是它的底色；爽，是它的本能。
>
> ### 方案 C — 短句向（适合海报/社媒）
> > 轻·若无物，跑·如御风。脚感这件事，穿上就懂了。
>
> ---
>
> 三种调性供你选择，需要进一步调整方向可以告诉我。

**改进后（新 SKILL.md）：**
> 双脚踩上云端的秘密——轻到让你忘记它的存在，每一步都在和风赛跑。这不是跑步，是起飞。

**对比：** 旧版输出 3 个方案 + 追问，正文还带了 markdown 标题和引用块。新版直接给一个最佳版本，简洁有力。

---

### 9.3 专业模式（professional）

**输入：**
> 改成商务报告风格：我们去年花了不少力气做市场推广，效果还不错，用户增长了很多，收入也跟着涨了不少。

**改进前（旧 SKILL.md）：**
> 本年度公司加大市场推广战略投入，取得显著成效。用户规模实现大幅增长，营收同步提升，市场拓展目标达成情况良好。

**改进后（新 SKILL.md）：**
> 过去一年，公司在市场推广方面持续加大投入，取得了显著成效。用户规模实现大幅增长，带动营业收入同步提升，整体业务呈现出良好的增长态势。

**对比：** 两者都干净。旧版在这个 case 上恰好没有出问题，新版语义更完整（"带动"体现了因果关系）。

---

### 9.4 口语化模式（casual）

**输入：**
> 用日常口语改写这段：本产品采用先进的纳米级分子渗透技术，通过深层滋养修复受损毛鳞片，实现从内到外的全面修复与长效保湿。

**改进前（旧 SKILL.md）：**
> 这个产品用了纳米级的小分子技术，能直接钻进头发里头，把受损的毛鳞片一点点养回来，从里到外给你修好，而且保湿效果能管很久。

**改进后（新 SKILL.md）：**
> 这款产品用了纳米级的渗透技术，能深层滋养、修护你受损的发丝，从里到外帮你把头发养回来，还能持久保湿。

**对比：** 两者都是口语化单版本输出。新版措辞更自然（"帮你把头发养回来" vs "给你修好"）。

---

### 9.5 正式学术模式（formal）

**输入：**
> 改成正式书面语，用于学术论文摘要：这个实验说实话一开始我们也没抱太大希望，结果一跑出来好家伙直接炸了，准确率比之前那几个方法高出一大截，而且跑起来贼快，基本上可以说是性价比拉满了，不过有个小问题就是内存占用有点夸张。

**改进前（旧 SKILL.md）：**
> 以下是改写结果：
>
> **正式学术版本（论文摘要风格）：**
>
> > 实验初期对该方法的预期性能持审慎态度，然而实验结果表明，所提方法在准确率上较现有基线方法取得了显著提升，同时推理速度表现出明显优势，综合性能表现优异。值得注意的是，该方法存在内存开销较大的局限性，有待进一步优化。
>
> **主要改写处理：**
>
> | 原文表达 | 学术表达 |
> |---|---|
> | 没抱太大希望 | 持审慎态度 |
> | 直接炸了 / 高出一大截 | 取得了显著提升 |
> | 贼快 | 推理速度表现出明显优势 |
> | 性价比拉满 | 综合性能表现优异 |
> | 内存占用有点夸张 | 内存开销较大的局限性，有待进一步优化 |

**改进后（新 SKILL.md）：**
> 初步实验结果表明，该方法在准确率方面显著优于已有方法，同时具备较高的计算效率，综合性能表现突出。然而，该方法的内存占用较高，有待进一步优化。

**对比：** 这是最明显的一组。旧版用 markdown 标题包装 + blockquote 引用 + 完整的对比表格。新版直接输出论文摘要，可以直接复制粘贴使用。

---

### 9.6 扩写模式（expand）

**输入：**
> 扩写这段话：这家咖啡馆氛围不错，适合周末放松。

**改进前（旧 SKILL.md）：**
> 这家咖啡馆的整体氛围确实让人印象深刻。推门进去的那一刻，暖黄色的灯光、原木色的桌椅和墙上随意挂着的几幅小画，营造出一种温暖又放松的感觉。空气里飘着现磨咖啡的香气，背景音乐音量恰到好处——不会吵到聊天，也不会安静到尴尬。角落里有几个带插座的座位，偶尔有人带着笔记本电脑安静地敲字，但大多数人只是坐着喝杯咖啡、聊聊天。周末来这里点一杯拿铁，窝在沙发里翻翻书或者发发呆，是一个相当不错的选择。

**改进后（新 SKILL.md）：**
> 这家咖啡馆藏在街角一处不太起眼的位置，推门进去却别有洞天。暖黄色的灯光洒在原木桌面上，空气中弥漫着现磨咖啡的醇厚香气，混着一点点肉桂和焦糖的甜味。背景音乐是轻柔的爵士乐，音量恰到好处——既不会打扰你发呆，也不会让沉默显得尴尬。靠窗的位置阳光很好，随手带本书或者干脆什么都不做，点一杯手冲慢慢喝，看着窗外偶尔走过的行人，一个下午就这么安静地溜走了。周末想找个地方从日常节奏里抽离一下，这里真的很合适。

**对比：** 两者都提供了丰富的感官细节（灯光、香气、音乐），且都是单版本纯净输出，无元评论。新版更长（~170 字），描述更细腻（加了肉桂焦糖气味、行人画面）。扩写模式在改进前后都没有格式问题。

---

### 9.7 实测总结

| 模式 | 改进前问题 | 改进后效果 | 改善幅度 |
|------|----------|----------|---------|
| 精简 concise | 追加元评论（字数压缩比、去除说明） | 纯净输出，可直接替换 | 明显 |
| 创意 creative | 3 个方案 + 追问 + markdown 标题 | 1 个最佳版本，2 句话 | **显著** |
| 专业 professional | （此 case 无明显问题） | 语义更完整，保持纯净 | 持平 |
| 口语化 casual | 口语化程度稍弱 | 更自然口语表达 | 小幅 |
| 正式 formal | markdown 标题 + blockquote + 对比表格 | 纯文本论文摘要 | **显著** |
| 扩写 expand | （改进前后都正常） | 单版本纯净输出 | 持平 |

**结论：** 改进前的三个核心问题（元评论、多版本方案、markdown 格式包装）在所有模式中消失。输出符合"可以直接替换原文使用"的设计目标。创意和正式模式改善最显著——从需要手动提取内容变为直接可用。
