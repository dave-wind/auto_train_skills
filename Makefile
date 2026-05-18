# Skill Training Framework
#
# 所有命令在项目根目录执行。
#
# 用法:
#   make check                       检查依赖
#   make list                        列出所有可训练的 skill
#   make train SKILL=<name>          一键跑完整轮能力评估迭代
#   make suggest SKILL=<name>        生成改进建议 → skills/<name>/TRAINING-FEEDBACK.md
#   make deploy SKILL=<name>         部署到 ~/.claude/skills/ 和 ~/.agent/skills/
#   make trigger-eval SKILL=<name>   测试触发率
#   make trigger-optimize SKILL=<name> 自动优化 description

SHELL := /bin/bash
ROOT := $(shell pwd)
FRAMEWORK := $(ROOT)/skill-training-framework
SKILLS_DIR := $(ROOT)/skills
WORKSPACES := $(FRAMEWORK)/workspaces
SCRIPTS := $(FRAMEWORK)/scripts
SKILL_CREATOR := $(HOME)/.claude/skills/skill-creator
PY := uv run

# 每个 eval 跑几次取均值(默认 3)。用 RUNS=1 回退旧行为。
RUNS ?= 3

.PHONY: help check init generate-evals generate-triggers run grade benchmark report train diff suggest deploy clean list trigger-eval trigger-optimize

help:
	@echo "Skill Training Framework"
	@echo ""
	@echo "=== 能力评估 ==="
	@echo "  make train SKILL=<name>          一键跑完整轮迭代(run×N+grade+benchmark+report)"
	@echo "  make train SKILL=<name> RUNS=1   单次运行(旧行为,无均值)"
	@echo "  make run SKILL=<name>            执行所有 eval(with_skill × N + baseline缓存)"
	@echo "  make grade SKILL=<name>          LLM-as-judge 评分"
	@echo "  make grade SKILL=<name> FORCE=1  重跑所有评分(包括已有的)"
	@echo "  make benchmark SKILL=<name>      汇总指标"
	@echo "  make report SKILL=<name>         生成 markdown 报告"
	@echo "  make diff SKILL=<name>           对比最近两轮 iteration"
	@echo "  make suggest SKILL=<name>        生成改进建议 → skills/<name>/TRAINING-FEEDBACK.md"
	@echo "  make deploy SKILL=<name>         部署到 ~/.claude/skills/ 和 ~/.agent/skills/"
	@echo ""
	@echo "=== 触发率优化 ==="
	@echo "  make trigger-eval SKILL=<name>   测试 description 触发率"
	@echo "  make trigger-optimize SKILL=<name> 自动优化 description(迭代5轮)"
	@echo ""
	@echo "=== 通用 ==="
	@echo "  make check                       检查依赖"
	@echo "  make list                        列出所有可训练的 skill"
	@echo "  make init SKILL=<name>           为 skill 创建 evals 空模板(需手写)"
	@echo "  make generate-evals SKILL=<name> 用 AI 根据 SKILL.md 自动生成 evals"
	@echo "  make generate-triggers SKILL=<name> 用 Inversion 反转模式自动生成 trigger-evals"
	@echo "  make clean SKILL=<name>          清空该 skill 的 workspace"

check:
	@echo "==> 检查依赖"
	@command -v claude >/dev/null 2>&1 && echo "  ✓ claude CLI" || (echo "  ✗ 缺少 claude CLI" && exit 1)
	@command -v uv >/dev/null 2>&1 && echo "  ✓ uv" || (echo "  ✗ 缺少 uv (curl -LsSf https://astral.sh/uv/install.sh | sh)" && exit 1)
	@command -v jq >/dev/null 2>&1 && echo "  ✓ jq" || (echo "  ✗ 缺少 jq(brew install jq)" && exit 1)
	@if [ -d "$(SKILL_CREATOR)" ]; then echo "  ✓ skill-creator (官方)"; else echo "  ○ skill-creator 未安装(触发率优化不可用)"; fi
	@echo "==> OK"

list:
	@echo "可训练的 skill(在 $(SKILLS_DIR)):"
	@for d in $(SKILLS_DIR)/*/; do \
		name=$$(basename $$d); \
		if [ -f "$$d/SKILL.md" ]; then \
			if [ -f "$$d/evals/evals.json" ]; then \
				echo "  ✓ $$name (有 evals)"; \
			else \
				echo "  ○ $$name (缺 evals,运行 make init SKILL=$$name)"; \
			fi; \
		fi; \
	done

_check_skill:
	@if [ -z "$(SKILL)" ]; then echo "用法: make $@ SKILL=<skill-name>"; exit 1; fi
	@if [ ! -d "$(SKILLS_DIR)/$(SKILL)" ]; then echo "错误: skill '$(SKILL)' 不存在于 $(SKILLS_DIR)"; exit 1; fi
	@if [ ! -f "$(SKILLS_DIR)/$(SKILL)/SKILL.md" ]; then echo "错误: $(SKILLS_DIR)/$(SKILL)/SKILL.md 不存在"; exit 1; fi

init:
	@if [ -z "$(SKILL)" ]; then echo "用法: make init SKILL=<skill-name>"; exit 1; fi
	@mkdir -p $(SKILLS_DIR)/$(SKILL)/evals
	@if [ -f "$(SKILLS_DIR)/$(SKILL)/evals/evals.json" ]; then \
		echo "已存在: $(SKILLS_DIR)/$(SKILL)/evals/evals.json"; \
	else \
		sed 's/__SKILL_NAME__/$(SKILL)/g' $(FRAMEWORK)/templates/evals.template.json > $(SKILLS_DIR)/$(SKILL)/evals/evals.json; \
		echo "已创建: $(SKILLS_DIR)/$(SKILL)/evals/evals.json"; \
		echo "请编辑该文件,填入你的测试用例。"; \
	fi

generate-evals: _check_skill
	@$(PY) $(SCRIPTS)/generate_evals.py \
		--skill-name $(SKILL) \
		--skills-dir $(SKILLS_DIR)

generate-triggers: _check_skill
	@$(PY) $(SCRIPTS)/generate_triggers.py \
		--skill-name $(SKILL) \
		--skills-dir $(SKILLS_DIR)

# ========== 能力评估 ==========

run: _check_skill
	@$(PY) $(SCRIPTS)/run_evals.py \
		--skill-name $(SKILL) \
		--skills-dir $(SKILLS_DIR) \
		--workspace-root $(WORKSPACES) \
		--num-runs $(RUNS) \
		--skip-baseline

grade: _check_skill
	@$(PY) $(SCRIPTS)/grade.py \
		--skill-name $(SKILL) \
		--skills-dir $(SKILLS_DIR) \
		--workspace-root $(WORKSPACES) \
		$(if $(FORCE),--force)

benchmark: _check_skill
	@$(PY) $(SCRIPTS)/benchmark.py \
		--skill-name $(SKILL) \
		--workspace-root $(WORKSPACES)

report: _check_skill
	@$(PY) $(SCRIPTS)/report.py \
		--skill-name $(SKILL) \
		--workspace-root $(WORKSPACES)

train: _check_skill run grade benchmark report
	@echo ""
	@echo "==> 一轮能力评估完成,查看报告:"
	@latest=$$(ls -1d $(WORKSPACES)/$(SKILL)/iteration-* 2>/dev/null | tail -1); \
	echo "  $$latest/report.md"

diff: _check_skill
	@$(PY) $(SCRIPTS)/diff_iterations.py \
		--skill-name $(SKILL) \
		--workspace-root $(WORKSPACES)

suggest: _check_skill
	@$(PY) $(SCRIPTS)/suggest.py \
		--skill-name $(SKILL) \
		--skills-dir $(SKILLS_DIR) \
		--workspace-root $(WORKSPACES)

deploy: _check_skill
	@echo "==> 部署 $(SKILL) 到全局 skill 目录"
	@mkdir -p $(HOME)/.claude/skills/$(SKILL)
	@rsync -av --delete \
		--exclude='evals/' \
		--exclude='TRAINING-FEEDBACK.md' \
		$(SKILLS_DIR)/$(SKILL)/ \
		$(HOME)/.claude/skills/$(SKILL)/
	@if [ -d "$(HOME)/.agent/skills" ]; then \
		mkdir -p $(HOME)/.agent/skills/$(SKILL); \
		rsync -av --delete \
			--exclude='evals/' \
			--exclude='TRAINING-FEEDBACK.md' \
			$(SKILLS_DIR)/$(SKILL)/ \
			$(HOME)/.agent/skills/$(SKILL)/; \
	fi
	@echo "==> 完成"

# ========== 触发率优化 ==========

trigger-eval: _check_skill
	@if [ ! -d "$(SKILL_CREATOR)" ]; then echo "错误: skill-creator 未安装"; exit 1; fi
	@if [ ! -f "$(SKILLS_DIR)/$(SKILL)/evals/trigger-evals.json" ]; then \
		echo "错误: 需要 trigger-evals.json,先运行 make generate-triggers SKILL=$(SKILL)"; \
		exit 1; \
	fi
	cd $(SKILL_CREATOR) && $(PY) -m scripts.run_eval \
		--eval-set $(SKILLS_DIR)/$(SKILL)/evals/trigger-evals.json \
		--skill-path $(SKILLS_DIR)/$(SKILL) \
		--verbose

trigger-optimize: _check_skill
	@if [ ! -d "$(SKILL_CREATOR)" ]; then echo "错误: skill-creator 未安装"; exit 1; fi
	@if [ ! -f "$(SKILLS_DIR)/$(SKILL)/evals/trigger-evals.json" ]; then \
		echo "错误: 需要 trigger-evals.json,先运行 make generate-triggers SKILL=$(SKILL)"; \
		exit 1; \
	fi
	cd $(SKILL_CREATOR) && $(PY) -m scripts.run_loop \
		--eval-set $(SKILLS_DIR)/$(SKILL)/evals/trigger-evals.json \
		--skill-path $(SKILLS_DIR)/$(SKILL) \
		--max-iterations 5 \
		--verbose

# ========== 通用 ==========

clean: _check_skill
	@read -p "删除 $(WORKSPACES)/$(SKILL)/ 下所有迭代结果和 baseline 缓存? [y/N] " ans; \
	if [ "$$ans" = "y" ]; then rm -rf $(WORKSPACES)/$(SKILL); echo "已清空。"; fi
