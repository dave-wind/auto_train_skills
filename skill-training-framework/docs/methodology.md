# 方法论:把 Skill 当 Prompt 资产去训练

## 核心命题

> 你不能训练 Claude 的权重,但你能训练 **Claude 读到的那段 prompt**。
> SKILL.md 就是那段 prompt 的工程化形态。

## 三个层次理解

### 1. 这不是 "魔法",是 in-context learning

Claude 看到 SKILL.md 的内容后,把它当作上下文示范来响应用户。
**底层模型权重不变。** 改 SKILL.md 一行 → 模型的行为就变了 → 这就是你的"梯度更新"。

### 2. 没有 backprop,但有 evaluation loop

传统 ML:
```
forward → loss → backprop → update weights → repeat
```

Skill 训练:
```
run evals → grade → identify failures → rewrite SKILL.md → repeat
```

本框架自动化了 **run evals + grade + identify failures** 三步,人来负责 **rewrite SKILL.md**(这是创造性的部分)。

### 3. 你的训练数据 = evals.json

`evals/evals.json` 不是 "测试用例",而是**训练集 + 验证集**:

- `prompt`: 输入 x
- `expectations`: 标签 y(我希望输出长这样)
- pass_rate: 损失函数(越高越好)

## 关键工程实践

### 实践 1: 永远保留 baseline

每轮都跑 `with_skill` + `without_skill`。理由:

- 没有 baseline,你不知道 skill 到底有没有用
- 如果 without_skill 也能 100% 通过,**你的 eval 太简单了**(eval 信噪比低)
- delta(with_skill - without_skill)才是 skill 的真实价值

### 实践 2: 别为了过 eval 而改 skill(过拟合)

看到失败的 expectation 时,问自己:

> 这个失败是因为 SKILL.md 缺了**通用指导**,还是缺了**针对这个 eval 的细节**?

如果答案是后者,**不要改 skill**。改了它,这条 eval 过了,但真实用户用别的 prompt 时会失败。

替代方案:
- 增加更多类似的 eval,逼自己抽象出通用模式
- 在 SKILL.md 里写**原则**而不是**规则**("why" 比 "what" 重要)

### 实践 3: 读 transcript,不只看 pass/fail

benchmark.json 只告诉你 **过/不过**。
要理解 **为什么不过**,必须读 `eval-N/with_skill/transcript.md`。

看模型在哪一步走偏:
- 它根本没读 skill?→ description 太弱,触发率问题
- 它读了但理解错了?→ 指令含糊,要重写
- 它做了不必要的动作?→ skill 里有冗余/误导指令,删掉

### 实践 4: 把 prompt 写薄,把原理讲透

反例:
```markdown
ALWAYS use bullet points. NEVER use paragraphs. MUST include a summary.
```

正例:
```markdown
Readers skim, so bullet points work better than paragraphs for status updates.
If the output is going to a human who needs to act on it, lead with the conclusion.
```

后者让模型有判断力,前者让模型变成查表机。

### 实践 5: 触发率和能力分开优化

两件事容易混淆:

| 问题 | 优化对象 |
|---|---|
| 用户输入相关问题,skill 没被激活 | **description**(frontmatter 里) |
| skill 激活了,但做得不好 | **body**(SKILL.md 正文) |

本框架默认通过 `--append-system-prompt` 强制注入 skill,所以测的是 **能力**,不是触发率。
触发率优化需要用 skill-creator 的 `run_loop.py`(那是另一个独立循环)。

## 何时停止迭代

停止信号(任一即可):

1. **with_skill pass_rate 收敛**:连续两轮 delta < 3%
2. **失败用例难以归纳**:每轮失败的 expectation 都不一样,说明已经到模型/任务边界
3. **改 skill 改不动了**:再加规则就开始过拟合,删规则就退步——平衡点已找到
4. **delta 足够大**:with_skill 比 without_skill 高 30%+,且实际使用感受良好

## 一个真实的迭代心态

第 1 轮:大概率惨烈,各种 expectation 不过。冷静,这是 baseline。
第 2 轮:针对最大痛点改 SKILL.md,通常能看到明显提升。
第 3 轮:开始遇到 trade-off——改了 A 让 B 退步。这时学会用原则代替规则。
第 4-5 轮:收敛。这就是你 skill 的能力上限,记下来。
第 N 轮(模型升级后):重跑 baseline,看是否需要为新模型调整。
