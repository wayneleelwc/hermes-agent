# Hermes Agent 深度拆解 —— 学习大纲与写作规划

> 系列定位：面向源码级的架构分析技术报告，以 Hermes Agent（Python，Nous Research）为主体做深度拆解，每篇设「三向对标」章节，与 Gemini CLI 和 Claude Code 做架构设计对比。

---

## 一、学习路线图

### 核心路线（理解 Agent 怎么运转）

> 01 → 02 → 04 → 05

先看懂整体架构，再深入核心循环，然后理解工具系统和自进化闭环。

### 完整路线（全面理解架构）

> 01 → 02 → 03 → 04 → 05 → 06 → 07 → 08 → 09 → 10

### 专题路线（按关注点跳读）

| 关注点 | 推荐路线 |
|--------|---------|
| Agent 内核 | 01 → 02 → 03 |
| 工具与平台 | 04 → 06 → 09 |
| 记忆与进化 | 05 → 07 |
| 工程与训练 | 08 → 10 |

---

## 二、源码全景速览

在进入各篇之前，先建立对代码库的全局认知。

### 关键文件（load-bearing entry points）

| 文件 | 行数 | 职责 |
|------|------|------|
| `run_agent.py` | ~13,700 | AIAgent 类 —— 核心对话循环 |
| `cli.py` | ~11,500 | HermesCLI 类 —— 交互式终端 |
| `model_tools.py` | ~1,000 | 工具发现、Schema 收集、分发 |
| `toolsets.py` | ~700 | 工具集定义与平台预设 |
| `hermes_state.py` | ~2,000 | SQLite 会话数据库（FTS5） |
| `hermes_constants.py` | ~300 | HERMES_HOME 路径管理 |
| `batch_runner.py` | ~1,200 | 并行批量轨迹生成 |

### 关键目录

| 目录 | 职责 |
|------|------|
| `agent/` | Agent 内核：prompt 组装、上下文压缩、记忆管理、模型路由 |
| `hermes_cli/` | CLI 子命令：配置、设置向导、皮肤引擎、命令注册表 |
| `tools/` | 工具实现：每个工具一个文件，自注册到 registry.py（61 个工具） |
| `gateway/` | 消息网关：19+ 平台适配器（Telegram/Discord/Slack/WhatsApp/...） |
| `plugins/` | 插件系统：记忆 provider、上下文引擎、图片生成等 |
| `skills/` | 内置 Skill 库（按类别分目录） |
| `optional-skills/` | 可选 Skill（默认不激活，需手动安装） |
| `environments/` | RL 训练环境（Atropos）+ 终端后端 |
| `ui-tui/` | Ink (React) 终端 UI |
| `cron/` | 定时任务调度器 |
| `scripts/` | 构建/测试/发布脚本 |
| `tests/` | ~700 文件、~15,000 测试用例 |

### 文件依赖链

```
tools/registry.py  （无依赖 —— 被所有工具文件导入）
       ↑
tools/*.py  （每个文件调用 registry.register() 自注册）
       ↑
model_tools.py  （导入 registry + 触发工具发现）
       ↑
run_agent.py, cli.py, batch_runner.py, environments/
```

---

## 三、系列文章目录

### 01 · 架构全景 —— 多入口与六层子系统

**聚焦问题**：Hermes Agent 的整体架构是怎样的？多个入口如何共享同一内核？

**源码范围**：
- `run_agent.py`（AIAgent 类结构）
- `cli.py`（HermesCLI 入口）
- `gateway/run.py`（Gateway 入口）
- `acp_adapter/`（IDE 集成入口）
- `batch_runner.py`（批量入口）
- `hermes_cli/main.py`（CLI 子命令入口）

**内容规划**：
1. 五入口架构：CLI / Gateway / ACP / Batch / API Server
2. AIAgent 类的六层子系统：Prompt Builder → Provider Resolution → Tool Dispatch → Context Compression → Memory Management → Session Persistence
3. 文件依赖链与模块边界
4. 配置系统：config.yaml + .env + DEFAULT_CONFIG + profile 多实例
5. 三向对标：Hermes vs Gemini CLI vs Claude Code 架构差异

**配图建议**（预计 5-6 张）：

| # | 图型 | Skill Type | 内容 |
|---|------|-----------|------|
| 01 | 全景架构图 | `framework` | 五入口 → AIAgent 六层子系统全景 |
| 02 | 流水线图 | `flowchart` | CLI 启动流程：main.py → load_config → AIAgent.__init__ → run_conversation |
| 03 | 流水线图 | `flowchart` | Gateway 启动流程：gateway/run.py → platform.start → AIAgent.spawn |
| 04 | 对比图 | `comparison` | 五入口对比：CLI vs Gateway vs ACP vs Batch vs API Server |
| 05 | 分类图 | `infographic` | 配置系统层级：DEFAULT_CONFIG → user config.yaml → .env → runtime override |
| 06 | 对比图 | `comparison` | 三向架构对比：Hermes 六层 vs Gemini CLI 七包 vs Claude Code 单体 |

---

### 02 · Agent 执行内核 —— 同步循环、中断与预算

**聚焦问题**：AIAgent 的核心循环怎么运转？中断、预算、容错机制如何设计？

**源码范围**：
- `run_agent.py`（`_run_agent_loop` / `run_conversation`）
- `model_tools.py`（`handle_function_call` / `discover_builtin_tools`）
- `agent/prompt_builder.py`（System Prompt 组装）
- `agent/auxiliary_client.py`（辅助 LLM 调用）

**内容规划**：
1. `run_conversation()` 完整循环：System Prompt → LLM Call → Tool Dispatch → Append → Loop
2. `_budget_grace_call` 机制：预算耗尽时的一次"体面告别"
3. 中断处理：`_interrupt_requested` + `/stop` + Ctrl+C
4. 迭代预算：`max_iterations` + `iteration_budget` 双层限制
5. `handle_function_call()` 工具分发核心
6. 容错与重试：JSON 解析失败、空响应、工具调用异常
7. 三向对标：同步循环 vs Gemini CLI 四阶段 vs Claude Code async generator

**配图建议**（预计 5 张）：

| # | 图型 | Skill Type | 内容 |
|---|------|-----------|------|
| 07 | 状态机图 | `flowchart` | Agent 主循环状态机：init → prompt_build → llm_call → tool_dispatch / text_response → end |
| 08 | 流水线图 | `flowchart` | `handle_function_call()` 分发流程：tool_call → registry.lookup → handler → JSON result → message append |
| 09 | 决策树图 | `flowchart` | 中断判断决策树：interrupt_requested? → budget_exhausted? → grace_call? → continue/break |
| 10 | 对比图 | `comparison` | 重试策略对比：JSON 解析失败 / 空响应 / tool_call 异常 |
| 11 | 对比图 | `comparison` | 三向核心循环对比 |

---

### 03 · 上下文压缩与缓存 —— 智能压缩管道

**聚焦问题**：对话历史过长时如何压缩？Prompt Cache 怎么管理？

**源码范围**：
- `agent/context_compressor.py`（默认压缩引擎）
- `agent/prompt_caching.py`（Anthropic Prompt Cache）
- `trajectory_compressor.py`（轨迹压缩器）
- `agent/model_metadata.py`（Token 估算 + 上下文长度）
- `hermes_state.py`（会话持久化）

**内容规划**：
1. 上下文压缩触发条件：Token 阈值检测
2. `context_compressor.py` 压缩策略：保留最新 N 轮 + LLM 摘要旧历史
3. 压缩降级：主模型失败 → fallback 模型 → 纯截断
4. Anthropic Prompt Caching：cache_control 断点管理 + cache_ttl
5. `trajectory_compressor.py`：面向训练的轨迹压缩
6. 三向对标：Hermes 单层压缩 vs Gemini CLI 六道防线 vs Claude Code AutoCompact + Collapse

**配图建议**（预计 5 张）：

| # | 图型 | Skill Type | 内容 |
|---|------|-----------|------|
| 12 | 流水线图 | `flowchart` | 压缩触发与执行全流程：Token检测 → 阈值判断 → LLM摘要 → 历史替换 |
| 13 | 状态机图 | `flowchart` | 压缩降级状态机：main_model → fallback_model → truncation_only |
| 14 | 架构图 | `blueprint` | Prompt Cache 断点布局：SI_prefix → tools → messages → cache_control |
| 15 | 对比图 | `comparison` | 三向压缩策略对比：六道 vs 单层 vs Collapse |
| 16 | 流水线图 | `flowchart` | Trajectory Compressor：原始轨迹 → 去重 → 摘要 → 训练数据 |

---

### 04 · 工具系统与注册表 —— 自注册、Schema 收集与分发

**聚焦问题**：61 个工具如何注册？Schema 怎么生成？调用如何分发？

**源码范围**：
- `tools/registry.py`（中央注册表）
- `tools/*.py`（每个工具一个文件，自注册）
- `toolsets.py`（工具集定义与平台预设）
- `model_tools.py`（`get_tool_definitions` / `discover_builtin_tools`）
- `tools/terminal_tool.py`（终端工具 + 六种后端）
- `tools/approval.py`（危险命令检测）

**内容规划**：
1. 工具自注册机制：`registry.register()` → 自动发现
2. Schema 生成：OpenAI Function Calling 格式
3. 工具集系统：_HERMES_CORE_TOOLS + 平台预设（CLI / Telegram / Discord）
4. 终端后端：local / Docker / SSH / Daytona / Singularity / Modal / Vercel
5. 审批系统：危险命令检测 + 硬编码阻止列表
6. 三向对标：自注册 vs Gemini CLI DeclarativeTool vs Claude Code 分散式

**配图建议**（预计 6 张）：

| # | 图型 | Skill Type | 内容 |
|---|------|-----------|------|
| 17 | 全景架构图 | `framework` | 工具系统全景：registry → discovery → schema → dispatch → result |
| 18 | 流水线图 | `flowchart` | 工具注册与发现流程：import → register() → _registry dict → discover_builtin_tools() |
| 19 | 分类图 | `infographic` | 61 个工具按类别分组：文件操作 / 终端 / Web / 浏览器 / 图片 / TTS / 审批 |
| 20 | 分类图 | `infographic` | 六种终端后端对比：隔离级别 / 启动延迟 / 持久性 / 适用场景 |
| 21 | 对比图 | `comparison` | 审批系统：dangerous / hardline / allowed 三级 |
| 22 | 对比图 | `comparison` | 三向工具系统对比 |

---

### 05 · 自进化闭环 —— Curator、Review Fork 与 Skill 生命周期

**聚焦问题**：Hermes 如何实现自我改进？Curator 和 Background Review Fork 如何协作？

**源码范围**：
- `hermes_cli/curator.py`（Curator 命令实现，如存在）
- `agent/` 中与 background review 相关的代码
- `skills/` 目录结构
- `agent/memory_manager.py`（记忆管理器）
- `agent/skill_commands.py`（Skill 命令处理）

**内容规划**：
1. **Curator 系统**：7 天周期后台审查，skill 评分/合并/清理
2. **Background Review Fork**：每轮后 fork 子进程审查"是否更新记忆/技能"
3. **rubric-based 决策**：从自由形式到结构化的评分标准
4. **Skill 生命周期**：创建 → 使用 → 评分 → 改进 → 合并/归档
5. **agentskills.io 标准**：Skill 的开放标准格式
6. 三向对标：Hermes 闭环 vs Gemini CLI memoryService vs Claude Code（无此能力）

**配图建议**（预计 6 张）：

| # | 图型 | Skill Type | 内容 |
|---|------|-----------|------|
| 23 | 全景架构图 | `framework` | 自进化闭环全景：Curator周期 + Review Fork实时 + Skill生命周期 |
| 24 | 流水线图 | `flowchart` | Curator 执行流程：扫描 → 评分 → 合并候选 → 清理 → 报告 |
| 25 | 状态机图 | `flowchart` | Skill 生命周期状态机：created → used → graded → improved → consolidated/archived |
| 26 | 流水线图 | `flowchart` | Review Fork 执行流程：turn完成 → fork → rubric打分 → 决定更新/创建 |
| 27 | 对比图 | `comparison` | Curator vs Review Fork：周期 vs 实时、广度 vs 深度、群体 vs 个体 |
| 28 | 对比图 | `comparison` | 自进化能力三向对比 |

---

### 06 · 多平台 Gateway —— 19+ 平台适配与可插拔架构

**聚焦问题**：一个 Gateway 进程如何同时服务 19+ 消息平台？

**源码范围**：
- `gateway/run.py`（Gateway 主循环）
- `gateway/session.py`（会话管理）
- `gateway/platforms/`（各平台适配器）
- `gateway/builtin_hooks/`（Gateway Hook 扩展点）
- `hermes_cli/gateway.py`（CLI 侧 gateway 管理命令）

**内容规划**：
1. Gateway 架构：单进程 → 多平台 → 共享 AIAgent 池
2. 平台适配器模式：Base Platform → Telegram/Discord/Slack/WhatsApp/Signal/...
3. 消息队列：`_pending_messages` + 两道 guard 机制
4. 可插拔平台架构：v0.12 新增 plugin-shipped platform
5. 会话连续性：gateway 重启后自动恢复对话
6. 平台特定能力：Telegram 按钮菜单、Slack slash command、Signal 原生格式化
7. 三向对标：Gateway 模式 vs Gemini CLI（无此能力）vs Claude Code（无此能力）

**配图建议**（预计 5 张）：

| # | 图型 | Skill Type | 内容 |
|---|------|-----------|------|
| 29 | 全景架构图 | `framework` | Gateway 全景：platforms → message queue → AIAgent pool → response routing |
| 30 | 分类图 | `infographic` | 19 个平台按类型分组：IM / 协作 / 邮件 / SMS / 国内平台 |
| 31 | 流水线图 | `flowchart` | 消息处理流程：receive → guard1 → guard2 → dispatch → agent.run → send |
| 32 | 时序图 | `flowchart` | 中断处理时序：用户 /stop → guard bypass → agent.interrupt → respond |
| 33 | 对比图 | `comparison` | 各平台能力矩阵：多图片 / 音频 / 按钮 / 格式化 / 命令自动完成 |

---

### 07 · 记忆与 Skill 系统 —— 多 Provider 插件与知识沉淀

**聚焦问题**：Hermes 的记忆系统如何支持多种后端？Skill 和 Memory 有什么区别？

**源码范围**：
- `agent/memory_manager.py`（记忆管理器编排）
- `agent/memory_provider.py`（MemoryProvider ABC）
- `plugins/memory/`（honcho, mem0, supermemory, byterover, hindsight, ...）
- `skills/`（内置 Skill 库）
- `optional-skills/`（可选 Skill）
- `agent/skill_commands.py`（Skill 加载/卸载/搜索）

**内容规划**：
1. MemoryProvider 插件架构：ABC → 多个实现 → manager 编排
2. 记忆生命周期：`sync_turn` → `prefetch` → `shutdown`
3. 各 provider 对比：honcho（辩证用户建模）、mem0、supermemory、...
4. Skill 系统：SKILL.md 格式、frontmatter、tags/category/config
5. Skill 与 Memory 的关系：Skill = 过程性知识（怎么做），Memory = 声明性知识（是什么）
6. 三向对标：Hermes 多 provider vs Gemini CLI GEMINI.md 层级 vs Claude Code CLAUDE.md 层级

**配图建议**（预计 5 张）：

| # | 图型 | Skill Type | 内容 |
|---|------|-----------|------|
| 34 | 全景架构图 | `framework` | 记忆系统全景：manager → providers → sync/prefetch/shutdown |
| 35 | 分类图 | `infographic` | Memory Provider 对比：honcho / mem0 / supermemory / byterover / hindsight |
| 36 | 流水线图 | `flowchart` | Memory 生命周期：session_start → sync_turn(每轮) → prefetch(启动时) → shutdown |
| 37 | 对比图 | `comparison` | Skill vs Memory：格式 / 生命周期 / 使用方式 / 存储位置 |
| 38 | 对比图 | `comparison` | 三向记忆系统对比 |

---

### 08 · 多 Agent 委派 —— delegate_task、子进程隔离与并行

**聚焦问题**：Hermes 如何委派任务给子 Agent？隔离和通信如何保证？

**源码范围**：
- `tools/delegate_tool.py`（delegate_task 工具实现）
- `run_agent.py` 中子 agent 相关逻辑
- `batch_runner.py`（并行批处理）
- `tools/todo_tool.py`（Agent 级工具模式）

**内容规划**：
1. `delegate_task` 工具：spawn 子 agent → 传递上下文 → 执行 → 回收结果
2. 子进程隔离：独立的 AIAgent 实例 + 独立的 toolset
3. `_last_resolved_tool_names` 全局状态的保存/恢复
4. 并行执行：batch_runner 的并行批处理模式
5. checkpoint 与文件状态协调：跨 agent 文件一致性
6. 三向对标：delegate_task vs Gemini CLI LocalAgent/BrowserAgent vs Claude Code Fork/Task

**配图建议**（预计 4 张）：

| # | 图型 | Skill Type | 内容 |
|---|------|-----------|------|
| 39 | 全景架构图 | `framework` | 多 Agent 全景：parent → delegate → spawn → execute → result |
| 40 | 时序图 | `flowchart` | delegate_task 时序：spawn → context_copy → run_loop → tool_calls → return |
| 41 | 对比图 | `comparison` | 并行模式对比：batch_runner vs delegate_task vs sequential |
| 42 | 对比图 | `comparison` | 三向多 Agent 对比 |

---

### 09 · CLI 与 TUI 交互 —— 双界面、皮肤引擎与命令系统

**聚焦问题**：Hermes 同时提供 CLI 和 TUI，它们如何共存？皮肤引擎怎么工作？

**源码范围**：
- `cli.py`（HermesCLI 类 —— prompt_toolkit）
- `ui-tui/src/`（Ink React TUI）
- `tui_gateway/`（Python JSON-RPC 后端）
- `hermes_cli/commands.py`（COMMAND_REGISTRY）
- `hermes_cli/skin_engine.py`（皮肤引擎）
- `hermes_cli/callbacks.py`（交互式回调）
- `agent/display.py`（KawaiiSpinner）

**内容规划**：
1. CLI vs TUI 双界面设计：prompt_toolkit vs Ink React
2. TUI 进程模型：Node (Ink) ←→ stdio JSON-RPC ←→ Python (tui_gateway)
3. 命令系统：COMMAND_REGISTRY → resolve → dispatch（CLI + Gateway + Telegram 菜单 + Slack 自动衍生）
4. 皮肤引擎：SkinConfig dataclass → 内置皮肤 → 用户 YAML → 运行时切换
5. KawaiiSpinner：动画表情 + 工具活动反馈
6. 仪表盘嵌入：xterm.js + PTY bridge
7. 三向对标：双界面 vs Gemini CLI 纯 CLI vs Claude Code 纯 CLI

**配图建议**（预计 5 张）：

| # | 图型 | Skill Type | 内容 |
|---|------|-----------|------|
| 43 | 全景架构图 | `framework` | CLI+TUI 双界面全景：输入 → 命令解析 → AIAgent → 输出渲染 |
| 44 | 数据流图 | `flowchart` | TUI JSON-RPC 通信：Ink request → stdio → Python process → response |
| 45 | 分类图 | `infographic` | 命令注册表派生关系：COMMAND_REGISTRY → CLI / Gateway / Telegram / Slack / Autocomplete |
| 46 | 分类图 | `infographic` | 皮肤可定制元素：banner / spinner / tool_prefix / branding |
| 47 | 对比图 | `comparison` | 三向 CLI 交互对比 |

---

### 10 · 工程体系与 RL 训练 —— Atropos、批量轨迹与评估

**聚焦问题**：Hermes 的 RL 训练基础设施如何设计？批量轨迹生成怎么工作？

**源码范围**：
- `environments/agent_loop.py`（HermesAgentLoop —— 可复用训练引擎）
- `environments/hermes_base_env.py`（训练环境基类）
- `environments/`（具体训练环境）
- `batch_runner.py`（并行批量处理）
- `trajectory_compressor.py`（轨迹压缩）
- `scripts/run_tests.sh`（CI 一致性测试包装器）
- `pyproject.toml`（依赖与构建配置）

**内容规划**：
1. RL 训练架构：Atropos → HermesAgentBaseEnv → HermesAgentLoop → 具体环境
2. HermesAgentLoop：与主循环相同的 tool-calling 模式，作为训练引擎
3. 两阶段训练：Phase 1（OpenAI server SFT）→ Phase 2（VLLM ManagedServer RL + logprobs）
4. ToolContext：per-rollout 工具访问句柄，支持 reward 函数直接调用工具
5. batch_runner：并行轨迹生成
6. 测试体系：~15,000 测试 + hermetic 环境 + 4 xdist workers
7. 三向对标：Hermes 训练设施 vs Gemini CLI（无）vs Claude Code（无）

**配图建议**（预计 4 张）：

| # | 图型 | Skill Type | 内容 |
|---|------|-----------|------|
| 48 | 全景架构图 | `framework` | RL 训练全景：Atropos → Env → AgentLoop → Reward → Trajectory |
| 49 | 流水线图 | `flowchart` | 两阶段训练流程：Phase1 SFT → Phase2 RL + logprobs |
| 50 | 流水线图 | `flowchart` | Batch Runner：任务队列 → 并行 AIAgent → 结果收集 |
| 51 | 对比图 | `comparison` | 测试策略对比：hermetic + xdist vs standard pytest |

---

## 四、配图总量与密度参考

| 编号 | 文章 | 预计图数 | 图号范围 | 密度 |
|:----:|------|:-------:|---------|:----:|
| 01 | 架构全景 | 6 | 01-06 | 6张/篇 |
| 02 | Agent 执行内核 | 5 | 07-11 | 5张/篇 |
| 03 | 上下文压缩与缓存 | 5 | 12-16 | 5张/篇 |
| 04 | 工具系统与注册表 | 6 | 17-22 | 6张/篇 |
| 05 | 自进化闭环 | 6 | 23-28 | 6张/篇 |
| 06 | 多平台 Gateway | 5 | 29-33 | 5张/篇 |
| 07 | 记忆与 Skill 系统 | 5 | 34-38 | 5张/篇 |
| 08 | 多 Agent 委派 | 4 | 39-42 | 4张/篇 |
| 09 | CLI 与 TUI 交互 | 5 | 43-47 | 5张/篇 |
| 10 | 工程体系与 RL 训练 | 4 | 48-51 | 4张/篇 |
| **合计** | | **51** | | **~5张/篇** |

命名规范沿用已建立的规范：`{中文主题描述}_{序号}.png`，中文描述用 `·` 分隔主副标题。

---

## 五、作图方法论参考

基于之前 Gemini CLI 系列的实战沉淀，Hermes 系列沿用相同的作图体系：

### Style 选择

技术深度拆解文章仅两种风格：
- **`vector-illustration`**（首选）：对比图、分类图、决策树
- **`blueprint`**（次选）：架构图、数据流图、时序图

### 图插入位置

- 文章开头（前情提要后、第一章前）：全景架构图
- 章节开篇（标题后、小节前）：分类图、链路图
- 小节中间（解释完概念、展示差异时）：细节对比图、决策树
- 流程类章节：流水线图、时序图（先给全景再拆每步）

核心原则：**图永远在它要解释的文字之前，是预览不是总结。**

### 图复用规则

- 同一命题出现在多篇时共享同一张图文件，alt text 可差异化
- 子篇章只挑直接相关的图，不把完整版图全搬

---

## 六、三向对标术语对照表

| 概念 | Hermes Agent | Gemini CLI | Claude Code |
|------|-------------|-----------|-------------|
| 语言 | Python (~13.7k LOC 核心) | TypeScript (~220k LOC) | TypeScript (闭源) |
| 核心循环 | `run_conversation()` 同步循环 | `LocalAgentExecutor` 四阶段 | `query.ts` async generator |
| 工具注册 | `tools/registry.py` 自注册 | `ToolRegistry` 集中式 | `tools.ts` 分散式 |
| 工具定义 | OpenAI Function Calling | Gemini `functionDeclarations` | Anthropic `tool_use` |
| 上下文压缩 | `context_compressor.py` 单层 | 六道递进防线 | AutoCompact + Context Collapse |
| 记忆系统 | MemoryProvider 多插件 (honcho/mem0/...) | GEMINI.md 层级覆盖 | CLAUDE.md 层级覆盖 |
| Skill/扩展 | SKILL.md + agentskills.io 标准 | Extension + Hook 系统 | Skill 系统（Skill 文件） |
| 多 Agent | `delegate_task` + 子进程隔离 | LocalAgent + BrowserAgent | Fork + Task |
| 终端后端 | 6 种 (local/docker/ssh/daytona/singularity/modal) | 本地 Shell | 本地 Shell + 沙箱 |
| 自进化 | Curator + Review Fork 闭环 | memoryService Skill 提取 | 无 |
| CLI/TUI | prompt_toolkit + Ink React | Ink React | Ink React |
| 消息平台 | 19+ 平台 Gateway | 无 | 无 |
| RL 训练 | Atropos 环境 + HermesAgentLoop | 无 | 无 |
| 包管理 | uv + pyproject.toml | NPM Workspace Monorepo (7包) | 单体仓库 |
| API 格式 | OpenAI-compatible | Gemini API | Anthropic Messages API |
| 缓存策略 | Anthropic Prompt Cache | Gemini KV Cache（隐式） | Anthropic Prompt Cache（显式断点） |

---

## 七、目录结构

```
learnings/
├── README.md                    # 本文件 —— 学习大纲与写作规划
├── materials/                   # 收集的外部资料
│   ├── papers/                  # 相关论文/技术报告
│   ├── talks/                   # 演讲/分享链接
│   └── community/               # 社区讨论精华
├── notes/                       # 零散阅读笔记
│   └── architecture-notes.md    # 架构阅读笔记
└── articles/                    # 正式技术文章
    ├── images/                  # 共享配图（跨篇复用）
    ├── 01-架构全景/
    │   ├── images/
    │   └── 01-架构全景-多入口与六层子系统.md
    ├── 02-Agent执行内核/
    │   ├── images/
    │   └── 02-Agent执行内核-同步循环中断与预算.md
    ├── 03-上下文压缩与缓存/
    │   ├── images/
    │   └── 03-上下文压缩与缓存-智能压缩管道.md
    ├── 04-工具系统与注册表/
    │   ├── images/
    │   └── 04-工具系统与注册表-自注册Schema与分发.md
    ├── 05-自进化闭环/
    │   ├── images/
    │   └── 05-自进化闭环-Curator与ReviewFork.md
    ├── 06-多平台Gateway/
    │   ├── images/
    │   └── 06-多平台Gateway-19平台适配与可插拔.md
    ├── 07-记忆与Skill系统/
    │   ├── images/
    │   └── 07-记忆与Skill系统-多Provider插件与知识沉淀.md
    ├── 08-多Agent委派/
    │   ├── images/
    │   └── 08-多Agent委派-子进程隔离与并行.md
    ├── 09-CLI与TUI交互/
    │   ├── images/
    │   └── 09-CLI与TUI交互-双界面皮肤引擎与命令系统.md
    └── 10-工程体系与RL训练/
        ├── images/
        └── 10-工程体系与RL训练-Atropos批量轨迹与评估.md
```

---

## 八、写作规范（继承自已建立的标准）

1. **读者认知优先**：标题直指核心，概念关系前置澄清
2. **先问题后方案**：每章先明确"聚焦什么问题"，再展开拆解
3. **架构命题升华**：每篇结尾将实现细节升华为可迁移的架构命题
4. **术语规范**：新术语首次出现使用 `英文（中文）` 格式，如 `Curator（自主审查器）`
5. **代码引用**：引用文件使用 Markdown 链接格式 `[filename](file:///...)`
6. **三向对标**：每篇设置独立章节，与 Gemini CLI 和 Claude Code 做架构对比
