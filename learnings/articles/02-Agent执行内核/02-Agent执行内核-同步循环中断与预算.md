# Hermes Agent 深度拆解：Agent 执行内核 —— 同步循环、中断与容错

> 聚焦问题：`run_conversation()` 怎么运转？中断、预算、容错如何设计？

![Agent 执行内核 — 封面](./diagrams/all-diagrams.html)

---

## 架构总览

Hermes 的 Agent 执行内核是一条**同步的、单线程的、支持中断的对话循环**。它不像 Gemini CLI 那样分阶段（Map→Route→Execute→Iterate），也不像 Claude Code 那样用 async generator，而是用一个简单但精心设计的 `while` 循环驱动整个 Agent 行为。

![Agent 执行内核全景 — 主循环状态流转](./diagrams/all-diagrams.html)

```
┌──────────────────────────────────────────────────────────────────┐
│                     run_conversation() 主循环                      │
│                                                                   │
│  while (api_call_count < max_iterations                           │
│         and budget.remaining > 0) or _budget_grace_call:         │
│                                                                   │
│  ┌────────────────┐   ┌──────────────┐   ┌──────────────┐        │
│  │ 1. 中断检查     │→→→│ 2. 预算消费   │→→→│ 3. 消息组装   │        │
│  │ _interrupt_     │   │ budget.      │   │ API messages  │        │
│  │ requested?      │   │ consume()    │   │ + caching     │        │
│  └────────┬───────┘   └──────┬───────┘   └──────┬───────┘        │
│           │                  │                   │                │
│    [是：break]          [预算耗尽 → break]        │                │
│                                                   │                │
│  ┌────────────────────────────────────────────────┴───────┐       │
│  │ 4. API 调用（带重试循环）                                 │       │
│  │    → 构建请求参数（_build_api_kwargs）                   │       │
│  │    → 流式 / 非流式调用（_interruptible_api_call）         │       │
│  │    → 失败 → 按错误类型重试（auth/rate-limit/context...）   │       │
│  └────────────────────────┬───────────────────────────────┘       │
│                           │                                        │
│                    ┌──────┴──────┐                                │
│                    ▼              ▼                                │
│              ┌──────────┐  ┌──────────────┐                       │
│              │ 有 tool_  │  │ 无 tool_calls│                       │
│              │ calls     │  │ → 最终响应   │                       │
│              └─────┬────┘  └──────┬───────┘                       │
│                    │              │                                │
│                    ▼              ▼                                │
│          ┌────────────────┐  [return result]                      │
│          │ 5. 工具执行      │                                     │
│          │ handle_function │                                     │
│          │ _call()         │                                     │
│          └────────┬───────┘                                       │
│                   │                                                │
│                   ▼                                                │
│              [下一轮循环]  ←── api_call_count++                     │
│                                                                   │
│  ── 循环外 ──                                                      │
│  6. 后处理：背景审查 fork / Skill Nudge / 会话持久化                │
└──────────────────────────────────────────────────────────────────┘
```

---

## 一、主循环的精确语义

### 1.1 循环条件

```python
# run_agent.py — 主循环条件
while (api_call_count < self.max_iterations
       and self.iteration_budget.remaining > 0) \
      or self._budget_grace_call:
```

这个条件有三层含义：

1. **`api_call_count < max_iterations`**（默认 90）：硬上限，防止无限循环。子 Agent 可单独设置更低的上限（默认 50）。
2. **`iteration_budget.remaining > 0`**：共享预算，父 Agent 和所有子 Agent 共用一个 `IterationBudget`。这是 Hermes 独有的双层预算设计。
3. **`_budget_grace_call`**：当预算用尽但模型可能正在生成有意义的最终响应时，允许再做**一次** API 调用完成对话。

循环内部的流程是**每次一整个 API 调用的原子周期**：发送请求 → 接收响应 → 有工具调用就执行 → 下一轮。不会出现"一次循环内多次 API 调用"或"跳过工具执行直接继续"的情况。

### 1.2 消息流：不修改原始消息

每次 API 调用前，循环会从 `messages`（完整历史）复制出 `api_messages`（仅用于发送）：

```python
# 构建 api_messages —— API 调用专用副本
api_messages = []  # 从 messages 逐条复制并做转换
for idx, msg in enumerate(messages):
    api_msg = msg.copy()  # 浅拷贝，原始消息不受影响
    # 注入 memory context（仅本轮 user message）
    # 复制 reasoning 到 reasoning_content
    # 清理内部字段（finish_reason, _thinking_prefill）
    # 规范化 tool_call JSON 格式（sort_keys, separators）
    api_messages.append(api_msg)

# 应用 Anthropic Prompt Cache breakpoints
if self._use_prompt_caching:
    api_messages = apply_anthropic_cache_control(api_messages, ...)
```

这个"原始消息 + API 转换"的二层模型保证了两件事：
- **Session 持久化存储的是未修改的原始消息**（包括 reasoning 等 UI 需要但 API 不需要的字段）
- **API 调用发送的是严格符合 provider 要求的格式化消息**

### 1.3 每次迭代的保护措施

在进入 API 调用前，有一系列前置检查：

```
中断检查 → 预算消耗 → 步进回调 → /steer 排空 → 消息组装
→ System Prompt 缓存 → Prompt Cache 断点 → 孤儿结果清理
→ Thinking-only 回合删除 → JSON 规范化 → Unicode 清理
→ 请求大小预估 → 确定流式/非流式 → start API call
```

其中值得关注的设计决策：
- **System Prompt 缓存**：首次构建后缓存到 `self._cached_system_prompt`，后续轮次复用，保证 Anthropic Prompt Cache 前缀命中
- **孤儿结果清理**：如果 session 加载时有多余的 tool 结果或缺少的工具结果，在 API 调用前补全/删除，防止 400 错误
- **JSON 规范化**：`sort_keys=True, separators=(",", ":")` 保证不同轮次中相同内容的消息具有 bit-perfect 的相同格式，提升缓存命中率

---

## 二、双层预算体系

### 2.1 核心设计

Hermes 的预算系统有两层：

| 预算层 | 变量 | 作用域 | 用途 |
|--------|------|--------|------|
| **本地上限** | `max_iterations` | 当前 Agent | 硬上限，防止无限循环 |
| **共享预算** | `IterationBudget` | 父 + 所有子 Agent | 父子共享的总预算池 |

```python
# run_agent.py — IterationBudget
self.max_iterations = max_iterations  # 本地默认 90
self.iteration_budget = iteration_budget or IterationBudget(max_iterations)
```

父 Agent 创建 `IterationBudget(max_iterations)`，子 Agent 在 delegation 时**继承同一个 `IterationBudget` 实例**。这意味着：

- 父 Agent 用了 30 次 API 调用，子 Agent 只能从剩余 60 次中消费
- 子 Agent 的 `max_iterations` 只是它的**单 Agent 上限**，不是独立预算
- 总消费 = 父 + 所有子 Agent 的 API 调用次数之和

### 2.2 预算耗尽后的策略

当 `iteration_budget.consume()` 返回 False（预算用尽）时，不是直接退出，而是有一套体面的告别流程：

```python
# 预算耗尽后的处理（简化）
if not self.iteration_budget.consume():
    # 1. 注入"预算耗尽"消息
    messages.append({
        "role": "user",
        "content": "⚠️ You have exceeded the iteration budget. "
                   "Please provide a summary of what you've accomplished."
    })
    # 2. 设置 grace call，允许最后一次 API 调用
    self._budget_grace_call = True
    # 3. 不再消费预算，回到循环顶部 → 再做一次 API 调用
    continue
```

如果模型在 grace call 中仍然返回 tool_call，循环条件 `_budget_grace_call` 为 False（已被消耗），循环自然退出。最终使用 `_force_final_response()` 合成一条消息。

### 2.3 设计哲学

Hermes 选择**只在预算真正耗尽时才通知模型**，不在中间施加压力（如 "还剩 20% 的预算"）。原因是：

> "Intermediate pressure warnings caused models to 'give up' prematurely on complex tasks (#7915)"

这与 Claude Code 的设计一致——让模型专注于完成任务，而不是在预算压力下做次优决策。

---

## 三、中断机制

### 3.1 多信号源、一人响应

Hermes 的中断机制是**多线程协作**的典型设计。不同于事件驱动架构，Hermes 用简单的**标志位 + 线程信号**实现跨线程通信：

```python
# 中断信号源（多个线程可能同时写入）
self._interrupt_requested = False     # 主线程检查的标志位
self._interrupt_message = None        # 触发中断的消息
self._execution_thread_id = None      # 执行线程 ID（用于作用域隔离）

# interrupt() 方法（从另一个线程调用）
def interrupt(self, message: str = None) -> None:
    self._interrupt_requested = True
    self._interrupt_message = message
    # 作用域隔离：只向本 Agent 的执行线程发送中断信号
    if self._execution_thread_id is not None:
        _set_interrupt(True, self._execution_thread_id)
```

关键设计：
1. **有人设旗、有人看旗**：`interrupt()` 设 `_interrupt_requested` 和线程级信号，主循环在每轮开始时检查标志位
2. **作用域隔离**：`_set_interrupt(True, self._execution_thread_id)` 使用线程 ID 做密钥，确保 Gateway 多会话并发时互不干扰
3. **子 Agent 传播**：中断还会通过 `_active_children` 列表递归传播到所有正在运行的子 Agent
4. **工具线程传播**：通过 `_tool_worker_threads` 集合向并发工具执行的 worker 线程发送中断信号

### 3.2 中断的时机策略

中断不打断正在进行的 API 调用——它只打断**循环的下一次迭代**。这是因为：

- API 调用中的模型正在思考，打断它会导致资源浪费
- 工具执行中的操作（如 shell 命令）可以通过线程级中断信号优雅终止

```
中断请求到达
  → 如果 Agent 在执行工具 → _set_interrupt(True, tid) 中断工具
  → 如果 Agent 在 API 调用中 → 等待 API 返回
  → API 返回后 → 循环回到顶部 → 检查 _interrupt_requested → break
```

### 3.3 `/steer`：不中断的注入

除了 `interrupt()`，Hermes 还提供了一个更温和的注入机制——`steer()`：

- **interrupt**：打断当前循环，让 Agent 立即处理新消息
- **steer**：不中断，在当前工具结果中悄悄附加一段文本，模型在下一轮看到

`steer()` 的实现方式是找到 `messages` 中最后一个 `role="tool"` 的消息，把引导文本追加到 `content` 的末尾。这样可以保持消息角色的交替（user→assistant→tool→assistant...），不引入额外的 user 消息。

---

## 四、容错与重试

### 4.1 API 重试循环

每个 API 调用都包裹在一个内部 `while retry_count < max_retries` 循环中：

```python
while retry_count < max_retries:
    try:
        response = self._interruptible_streaming_api_call(api_kwargs, ...)
        # 成功：退出重试循环
        break
    except Exception as e:
        retry_count += 1
        # 按错误类型分类处理...
```

重试策略按错误类型分类，每种有独立的处理逻辑：

| 错误类型 | 检测方式 | 处理策略 |
|---------|---------|---------|
| **Auth 失败** | `401` HTTP | 重新解析 runtime credentials（copilot/nous/anthropic 各有独立重试） |
| **Rate Limit** | `429` HTTP | 等待 retry-after → 重试 |
| **Context 超限** | `context_length_exceeded` 错误 | 触发上下文压缩 → 重试 |
| **JSON 损坏** | JSON parse error | 修复 tool_call 参数 → 重试 |
| **空响应** | 模型返回空内容 | 注入重试提示 → 重试 |
| **Provider 故障** | 连接超时 | 尝试 fallback provider |

### 4.2 Fallback Provider 切换

当主 Provider 持续失败时，Hermes 可以切换到备用的 fallback provider：

```python
if self._try_activate_fallback():
    # 切换成功：重置重试计数器
    retry_count = 0
    compression_attempts = 0
    primary_recovery_attempted = False
    continue
```

Fallback 激活后，Agent 的 `provider`、`base_url`、`api_key`、`api_mode` 全部切换到备选值。下一次 API 调用会自动使用新的 provider。一旦 fallback 激活，后续所有轮次都使用 fallback，直到下一次 `run_conversation()` 调用时 `_restore_primary_runtime()` 恢复主 provider。

### 4.3 上下文压缩的容错兜底

上下文压缩本身也可能失败（主模型不可用），Hermes 设计了三级降级：

```
1. 主模型摘要（首选）
   ↓ 失败
2. Fallback 模型重试（如果可用）
   ↓ 也失败
3. 纯截断：保留最近 N 轮（保护首次和末尾消息）
```

---

## 五、后处理：循环之外的工作

循环结束后，`run_conversation()` 还有一系列后处理：

```python
# 循环结束后
# 1. 持久化会话（写入 SessionDB）
self._persist_session(messages, conversation_history)

# 2. 后台审查 fork（Review Fork）
#    如果启用了记忆系统，fork 一个子进程审查本轮对话
#    "有没有值得记住的？有没有可以变成 Skill 的？"
if self._memory_enabled:
    self._fork_background_review(messages_snapshot)

# 3. Skill Nudge（周期性提示）
#    如果 tool 调用足够多但没用到 skill_manage，提示模型
if self._skill_nudge_interval > 0:
    self._iters_since_skill += api_call_count

# 4. 返回结果
return {
    "final_response": final_response,
    "messages": messages,
    "api_calls": api_call_count,
    "completed": not interrupted,
}
```

---

## 六、对标分析

### 6.1 与 Gemini CLI 对比

| 维度 | Hermes | Gemini CLI |
|------|--------|-----------|
| **循环模型** | `while` 同步循环 | `LocalAgentExecutor` 四阶段（Map→Route→Execute→Iterate） |
| **预算管理** | 双层：max_iterations + IterationBudget | 单层：maxIterations |
| **中断机制** | 标志位 + 线程信号（主循环轮次边界） | 事件驱动（AbortController） |
| **容错策略** | 按错误类型分类 + Fallback Provider | 统一 retry 策略 |
| **父子共享预算** | 是（IterationBudget 实例继承） | 否（子 Agent 独立预算） |
| **体面告别** | Budget Grace Call（最后一次 API 调用） | 无 |

**关键差异**：Hermes 的双层预算体系是其最大特色——父 Agent 和所有子 Agent 共享同一个 `IterationBudget` 实例，确保 delegation 不会绕过总预算限制。Gemini CLI 的四阶段模型更结构化，但父子 Agent 的预算是独立的。

### 6.2 与 Claude Code 对比

| 维度 | Hermes | Claude Code |
|------|--------|-------------|
| **循环模型** | `while` 同步循环 | `async generator`（`query.ts`） |
| **预算管理** | 双层：max_iterations + IterationBudget | 单层：`maxTurns` |
| **中断机制** | 线程级信号（支持多 Agent 隔离） | AbortSignal / CancellationToken |
| **容错策略** | 按错误类型分类 + Fallback Provider | 统一重试 + tool-level 容错 |
| **Steer/注入** | `/steer`（不中断，附加到工具结果） | 无对等机制 |
| **体面告别** | Budget Grace Call | `maxTurns` 到达后直接结束 |

**关键差异**：Hermes 的同步循环模型来自 Python 生态的务实选择——`while` 循环比 async generator 更容易理解和调试，多线程中断也比 asyncio 事件更容易跨平台兼容。Claude Code 的 async generator 模型更适合 TypeScript 生态，但需要更复杂的中断管理（AbortSignal/CancellationToken）。

---

## 七、设计哲学提炼

**命题一：同步循环不妨碍异步能力。** Hermes 证明了一个同步的 `while` 循环可以驱动复杂的 Agent 行为——流式输出通过 yield/callback 实现，中断通过线程信号和标志位实现，子 Agent delegation 通过新的 `AIAgent` 实例实现。关键在于在循环的固定边界点上插入非同步操作，而不是把整个循环变成异步的。

**命题二：预算应该是一个对象，不只是一个数字。** `IterationBudget` 的设计说明，当多个 Agent 共享预算时，把它建模为一个可被多个实例引用的对象远好于传递一个裸数字。对象封装了消费逻辑、剩余查询、跨 Agent 的完整性——这是 Agent delegation 架构中容易被忽略但至关重要的一层。

**命题三：中断应该是"下次停止"，不是"立即停止"。** Hermes 的中断在循环轮次边界生效，不是随时插入。这个简单的设计决策减少了大量的竞争条件和状态管理问题——每次中断只有"被检查到"和"没被检查到"两种状态，没有"中断进行到一半"的中间态。

---

*下一篇：[04 · 上下文压缩与缓存 —— 智能压缩管道](../03-上下文压缩与缓存/04-上下文压缩与缓存-智能压缩管道.md)*

*系列归属：Hermes Agent 深度拆解 · 第 02 篇*
