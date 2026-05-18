# strict-flow

轻量级三阶段门禁开发流程 skill，适用于 AI 编码代理。

**Brainstorm → Plan → Verify** — 有纪律，不搞仪式。

[English](#english) | [中文](#中文)

---

## 中文

### 它是什么

在任何开发任务上强制执行三个阶段：

| 阶段 | 目的 | 规则 |
|------|------|------|
| **1. 头脑风暴** | 编码前锁定意图 | 提出 2-3 个方案并附权衡分析，等用户选择 |
| **2. 计划拆解** | 拆分为可执行步骤 | 带依赖关系的编号计划，等用户确认 |
| **3. 证据验证** | 基于证据的完成 | 展示命令输出、测试结果 — "我觉得完成了"不算 |

### 适用场景

- Bug 修复、小功能、快速重构、原型验证
- 觉得 [superpowers](https://github.com/obra/superpowers) 太重的时候（无 worktree、无 TDD 强制、无子 agent 分发）
- 想要纪律，不想要仪式

### 安装

#### npx 一键安装（推荐）

```bash
npx strict-flow
```

自动检测已安装的 agent 并安装到对应目录。支持指定目标：

```bash
npx strict-flow --agent codex     # 只装到 Codex（CLI + App）
npx strict-flow --agent claude    # 只装到 Claude Code
npx strict-flow --agent all       # 装到所有支持的 agent
npx strict-flow --uninstall       # 卸载
```

#### Codex App 安装

Codex App（桌面应用）使用统一的 skill 目录 `~/.agents/skills/`。有两种方式：

**方式一：npx 安装（推荐）**

```bash
npx strict-flow --agent codex
```

自动安装到 `~/.agents/skills/strict-flow/`，Codex App 会自动发现。

**方式二：手动安装**

```bash
mkdir -p ~/.agents/skills
git clone https://github.com/dave-wind/strict-flow.git ~/.agents/skills/strict-flow
```

安装后重启 Codex App，在侧边栏的 Skills 区域可以看到 "Strict Flow"。

> strict-flow 配置了 `allow_implicit_invocation: false`，不会被自动触发。
> 使用时需要手动输入 `$strict-flow` 或在提示词中说 "strict flow"。

#### git clone 手动安装

```bash
# Codex CLI（旧路径）
mkdir -p ~/.codex/skills && git clone https://github.com/dave-wind/strict-flow.git ~/.codex/skills/strict-flow

# Claude Code
mkdir -p ~/.claude/skills && git clone https://github.com/dave-wind/strict-flow.git ~/.claude/skills/strict-flow
```

#### 项目级安装（团队共享）

```bash
# 在项目根目录
mkdir -p .agents/skills
git clone https://github.com/dave-wind/strict-flow.git .agents/skills/strict-flow
```

提交到 git，团队成员 clone 后自动获得。

### 使用

启动新会话后说以下任意一个：

- `strict flow` / `strict mode`
- `强制流程` / `严格模式`
- `quick flow` / `快速流程`

然后描述你的任务，agent 会自动走三个阶段。

**快速模式：** 说 "just do it" 或 "快速做"，agent 会压缩阶段 1 和 2（自行选方案、跳过计划确认），但 **阶段 3（证据验证）永远不跳过**。

### 与 Superpowers 的关系

[Superpowers](https://github.com/obra/superpowers) 是完整方法论（brainstorm → worktree → plan → subagent → TDD → code review → finish branch）。strict-flow 是轻量替代：

|  | Superpowers | Strict Flow |
|--|--|--|
| 触发方式 | 自动 | 手动（用户说"强制流程"） |
| 适用场景 | 完整功能、多文件变更 | Bug 修复、小功能、原型 |
| Worktree | 有 | 无 |
| TDD 强制 | 有 | 无 |
| 子 agent 分发 | 有 | 无 |
| 代码审查 | 有 | 无 |
| 三阶段门禁 | 有（更多） | 有（只有这三个） |

两者同时安装时，如果 superpowers 触发了，strict-flow 自动让位。

### 兼容的 Agent

| Agent | 安装路径 |
|-------|---------|
| **Codex App / CLI / IDE** | `~/.agents/skills/strict-flow/` |
| **Codex CLI（旧版）** | `~/.codex/skills/strict-flow/` |
| **Claude Code** | `~/.claude/skills/strict-flow/` |
| **OpenCode** | `~/.opencode/skills/strict-flow/` |

任何支持 SKILL.md 格式的 agent 都可以使用。

### 文件结构

```
strict-flow/
├── SKILL.md                    # 阶段编排（轻量路由）
├── agents/
│   └── openai.yaml             # Codex App UI 元数据和调用策略
└── references/
    ├── brainstorm.md           # 阶段 1：上下文探索、方案对比
    ├── plan.md                 # 阶段 2：步骤粒度、依赖分析
    └── verify.md               # 阶段 3：证据等级、完成规则
```

---

<a id="english"></a>

## English

### What It Does

Enforces three gates on any development task:

| Gate | Purpose | Rule |
|------|---------|------|
| **1. Brainstorm** | Lock intent before coding | Propose 2-3 approaches with trade-offs, wait for user approval |
| **2. Plan** | Decompose into executable steps | Numbered plan with dependencies, wait for user confirmation |
| **3. Verify** | Evidence-based completion | Show command output, test results — no "I think it's done" |

### When to Use

- Bug fixes, small features, quick refactors, prototypes
- When [superpowers](https://github.com/obra/superpowers) feels too heavy (no worktree, no TDD enforcement, no subagent dispatching)
- When you want discipline without ceremony

### Install

#### npx (recommended)

```bash
npx strict-flow
```

Auto-detects installed agents and installs to the correct directories. Options:

```bash
npx strict-flow --agent codex     # Codex (CLI + App)
npx strict-flow --agent claude    # Claude Code only
npx strict-flow --agent all       # All supported agents
npx strict-flow --uninstall       # Remove
```

#### Codex App Installation

The Codex desktop app uses the unified skill directory `~/.agents/skills/`. Two options:

**Option A: npx (recommended)**

```bash
npx strict-flow --agent codex
```

Installs to `~/.agents/skills/strict-flow/`. Codex App auto-discovers it.

**Option B: Manual install**

```bash
mkdir -p ~/.agents/skills
git clone https://github.com/dave-wind/strict-flow.git ~/.agents/skills/strict-flow
```

Restart Codex App after installing. You'll see "Strict Flow" in the sidebar Skills section.

> strict-flow sets `allow_implicit_invocation: false` — it won't trigger on its own.
> Use `$strict-flow` in your prompt or type "strict flow" to activate it.

#### git clone

```bash
# Codex CLI (legacy path)
mkdir -p ~/.codex/skills && git clone https://github.com/dave-wind/strict-flow.git ~/.codex/skills/strict-flow

# Claude Code
mkdir -p ~/.claude/skills && git clone https://github.com/dave-wind/strict-flow.git ~/.claude/skills/strict-flow
```

#### Project-level (team sharing)

```bash
mkdir -p .agents/skills
git clone https://github.com/dave-wind/strict-flow.git .agents/skills/strict-flow
```

### Usage

Start a new session and say one of: `strict flow`, `strict mode`, `强制流程`, `quick flow`.

**Fast mode:** Say "just do it" or "快速做" to compress gates 1 and 2. **Gate 3 (evidence) never skips.**

### Relationship to Superpowers

[Superpowers](https://github.com/obra/superpowers) is the full methodology. Strict-flow is the lightweight alternative — same three gates, no ceremony. If both are installed and superpowers triggers, strict-flow steps aside.

|  | Superpowers | Strict Flow |
|--|--|--|
| Trigger | Automatic | Manual |
| Best for | Full features, multi-file | Bug fixes, small features |
| Worktree / TDD / Subagent | Yes | No |
| Three gates | Yes (and more) | Yes |

### Compatible Agents

| Agent | Install Path |
|-------|-------------|
| **Codex App / CLI / IDE** | `~/.agents/skills/strict-flow/` |
| **Codex CLI (legacy)** | `~/.codex/skills/strict-flow/` |
| **Claude Code** | `~/.claude/skills/strict-flow/` |
| **OpenCode** | `~/.opencode/skills/strict-flow/` |

Any agent that supports the SKILL.md format can use strict-flow.

### File Structure

```
strict-flow/
├── SKILL.md                    # Gate orchestration (thin router)
├── agents/
│   └── openai.yaml             # Codex App UI metadata and invocation policy
└── references/
    ├── brainstorm.md           # Gate 1: context exploration, approach comparison
    ├── plan.md                 # Gate 2: step sizing, dependency analysis
    └── verify.md               # Gate 3: evidence levels, completion rules
```

---

## License

MIT
