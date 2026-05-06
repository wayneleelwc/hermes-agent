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

> 拆分原则：以 Hermes 自身架构基因为主轴，每个子系统聚焦其"独有设计"。不与 Claude Code 或 Gemini CLI 系列强行对齐。

### 01 · 架构全景 —— 五入口与六层子系统

**聚焦问题**：Hermes 的整体架构是怎样的？CLI、Gateway、ACP、Batch、API Server 五个入口如何共享同一内核？

**源码范围**：`run_agent.py` / `cli.py` / `gateway/run.py` / `acp_adapter/` / `batch_runner.py` / `hermes_cli/main.py`

**内核六层**：Prompt Builder → Provider Resolution → Tool Dispatch → Context Compression → Memory Management → Session Persistence

**配图**（5 张）：全景架构图 / CLI 启动流程 / Gateway 启动流程 / 五入口对比 / 配置层级

---

### 02 · Agent 执行内核 —— 同步循环、中断与容错

**聚焦问题**：`run_conversation()` 怎么运转？中断、预算、容错如何设计？

**源码范围**：`run_agent.py`（核心循环） / `model_tools.py`（工具分发） / `agent/prompt_builder.py`

**关键机制**：`_budget_grace_call` 体面告别 / `_interrupt_requested` 中断 / `max_iterations` + `iteration_budget` 双层预算

**配图**（4 张）：主循环状态机 / 工具分发流程 / 中断决策树 / 三向循环对比

---

### 03 · 记忆与知识系统 —— 双层架构与自进化闭环 【Demo 篇】

**聚焦问题**：Hermes 如何记住用户？如何从对话中提炼知识？知识如何自我维护？

**源码范围**：`agent/memory_provider.py`（ABC） / `agent/memory_manager.py`（编排器） / `plugins/memory/`（8 个 provider） / `skills/` / `agent/curator.py`（自主审查）

**核心命题**：
- **双层记忆**：Built-in（MEMORY.md/USER.md，声明性） + External Provider（Honcho/Mem0 等，可插拔）
- **知识转化**：Memory（声明性） → Skill（过程性） → Curator（自主维护）
- **Review Fork**：每轮对话后 fork 子进程审视"该不该记住什么"
- **Curator**：7 天周期后台审查，评分/合并/清理 skill 库

**配图**（7 张）：知识系统全景 / MemoryProvider 生命周期 / Provider 对比矩阵 / 知识转化流水线 / Skill 生命周期状态机 / Curator 审查流程 / 三向记忆系统对比

---

### 04 · 上下文压缩与缓存 —— 智能压缩管道

**聚焦问题**：对话过长时如何优雅压缩？Prompt Cache 怎么管理？

**源码范围**：`agent/context_compressor.py` / `agent/prompt_caching.py` / `trajectory_compressor.py`

**降级策略**：主模型摘要 → fallback 模型 → 纯截断

**配图**（4 张）：压缩全流程 / 降级状态机 / Cache 断点布局 / 三向压缩对比

---

### 05 · 工具系统 —— 自注册、Schema 与七种终端后端

**聚焦问题**：61 个工具如何自注册？七种终端后端（local/docker/ssh/daytona/singularity/modal/vercel）有什么区别？

**源码范围**：`tools/registry.py` / `tools/*.py` / `toolsets.py` / `tools/terminal_tool.py` / `tools/approval.py`

**配图**（5 张）：工具系统全景 / 自注册流程 / 工具分类 / 终端后端对比 / 审批三级

---

### 06 · 多平台 Gateway —— 19+ 消息平台与可插拔架构

**聚焦问题**：一个 Gateway 进程如何同时服务 19+ 消息平台？可插拔平台架构怎么设计？

**源码范围**：`gateway/run.py` / `gateway/platforms/` / `gateway/session.py`

**配图**（4 张）：Gateway 全景 / 平台分类 / 消息处理流程 / 平台能力矩阵

---

### 07 · CLI 与 TUI 双界面 —— 皮肤引擎与命令系统

**聚焦问题**：Hermes 同时提供 CLI 和 TUI，它们如何共存？皮肤引擎怎么工作？

**源码范围**：`cli.py` / `ui-tui/src/` / `tui_gateway/` / `hermes_cli/commands.py` / `hermes_cli/skin_engine.py`

**配图**（4 张）：双界面全景 / TUI JSON-RPC 通信 / 命令注册表派生 / 皮肤系统

---

### 08 · 多 Agent 委派与并行 —— delegate_task 与 Batch Runner

**聚焦问题**：Hermes 如何委派任务给子 Agent？隔离和并行如何保证？

**源码范围**：`tools/delegate_tool.py` / `batch_runner.py` / `run_agent.py`（子 agent 逻辑）

**配图**（3 张）：多 Agent 全景 / delegate_task 时序 / 并行模式对比

---

### 09 · 模型与 Provider 体系 —— 30+ Provider 与动态路由

**聚焦问题**：Hermes 如何支持 30+ 模型 Provider？模型切换、fallback、辅助模型路由怎么设计？

**源码范围**：`hermes_cli/auth.py` / `hermes_cli/runtime_provider.py` / `hermes_cli/models.py` / `agent/auxiliary_client.py`

**配图**（3 张）：Provider 体系全景 / 模型解析链路 / 辅助模型路由

---

### 10 · RL 训练与工程体系 —— Atropos、批量轨迹与测试

**聚焦问题**：Hermes 的 RL 训练基础设施如何设计？~15,000 测试怎么跑？

**源码范围**：`environments/agent_loop.py` / `environments/hermes_base_env.py` / `batch_runner.py` / `scripts/run_tests.sh`

**配图**（3 张）：RL 训练全景 / 两阶段训练 / Batch Runner 流水线

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
