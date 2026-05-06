# Hermes Agent 深度拆解：RL 训练与工程体系 —— Atropos、批量轨迹与测试

> 聚焦问题：Hermes 的 RL 训练基础设施如何设计？~15,000 测试怎么跑？批量轨迹生成如何 checkpoint？

![RL 训练 — 封面](./diagrams/all-diagrams.html)

---

## 架构总览

Hermes 的工程体系由三大支柱组成：**RL 训练基础设施**（environments/ 目录，基于 Atropos 框架 + HermesAgentLoop）→ **批量轨迹生成**（batch_runner.py，multiprocessing Pool + 智能 checkpoint）→ **测试体系**（tests/ 目录，~700 文件、~15,000 用例，pytest-xdist 并行）。三者构成从"训练模型"到"验证质量"的完整闭环。

![RL 训练全景 — 三大工程支柱](./diagrams/all-diagrams.html)

```
┌─────────────────────────────────────────────────────────────────┐
│                     Hermes 工程体系全景                            │
│                                                                  │
│  ┌──────────────────────────────────────────────────────────┐   │
│  │           RL 训练基础设施 (environments/)                  │   │
│  │  ┌──────────────┐  ┌──────────────┐  ┌───────────────┐  │   │
│  │  │ Atropos 集成  │  │HermesAgent-  │  │ Benchmark     │  │   │
│  │  │BaseEnv + Conf│  │Loop (async)  │  │ Envs (SWE等)  │  │   │
│  │  └──────────────┘  └──────────────┘  └───────────────┘  │   │
│  └───────────────────────┬──────────────────────────────────┘   │
│                          │                                       │
│  ┌───────────────────────┴──────────────────────────────────┐   │
│  │           批量轨迹生成 (batch_runner.py)                   │   │
│  │  ┌──────────────┐  ┌──────────────┐  ┌───────────────┐  │   │
│  │  │ Pool 多进程   │  │ Smart        │  │ Tool Stats    │  │   │
│  │  │ (num_workers)│  │ Checkpoint   │  │ Aggregation   │  │   │
│  │  └──────────────┘  └──────────────┘  └───────────────┘  │   │
│  └───────────────────────┬──────────────────────────────────┘   │
│                          │                                       │
│  ┌───────────────────────┴──────────────────────────────────┐   │
│  │            测试体系 (tests/)                               │   │
│  │  ┌──────────────┐  ┌──────────────┐  ┌───────────────┐  │   │
│  │  │ ~700 测试文件 │  │ ~15,000 用例 │  │ CI: pytest-xdist│  │   │
│  │  │ Unit+Integ+E2E│  │ Hermetic Env │  │ 4 workers     │  │   │
│  │  └──────────────┘  └──────────────┘  └───────────────┘  │   │
│  └──────────────────────────────────────────────────────────┘   │
└─────────────────────────────────────────────────────────────────┘
```

---

## 一、RL 训练基础设施

Hermes 的 RL 训练基于 **Atropos** 框架（`atroposlib`），通过 `environments/` 目录中的环境类将 Hermes Agent 包装为可训练的 RL 环境。

### 1.1 两阶段训练模式

`HermesAgentBaseEnv` 支持两种模式：

| 阶段 | 模式 | 说明 |
|------|------|------|
| **Phase 1** | OpenAI Server | 直接连接 OpenAI-compatible API（VLLM、SGLang、OpenRouter），模型通过标准 `tool_calls` 交互 |
| **Phase 2** | ManagedServer | 使用 Atropos 的 `ManagedServer` + 客户端 tool call parser，支持需要自定义解析的模型（如 GLM、DeepSeek、Kimi） |

这种双模设计让 Hermes 既可以用成熟的 API 服务快速迭代（Phase 1），也可以对需要特殊处理的开源模型进行深度训练（Phase 2）。

### 1.2 HermesAgentLoop — 训练用的 Agent 循环

`environments/agent_loop.py` 中的 `HermesAgentLoop` 是专门为 RL 训练优化的 Agent 循环。与 `run_agent.py` 中的 `AIAgent.run_conversation()` 不同：

| 维度 | AIAgent.run_conversation() | HermesAgentLoop |
|------|--------------------------|-----------------|
| **用途** | 交互式对话 | RL rollout 生成 |
| **运行方式** | 同步 while 循环 | async for 循环 |
| **工具执行** | 直接调用 handle_function_call | 通过 ThreadPoolExecutor 异步执行 |
| **预算管理** | IterationBudget + max_iterations | max_turns（默认 30） |
| **持久化** | SessionStore 完整持久化 | AgentResult（messages + stats） |
| **工具池** | 无（直接调用） | ThreadPoolExecutor（默认 128 workers） |

关键设计：工具执行使用 `_tool_executor`（全局 ThreadPoolExecutor），因为 Modal/Docker/Daytona 等终端后端内部使用 `asyncio.run()`——在 Atropos 的 async 事件循环中直接调用会导致死锁。线程池隔离解决了这个问题。

### 1.3 HermesAgentBaseEnv — 环境基类

`hermes_base_env.py` 定义了所有 Hermes 训练环境的抽象基类。子类只需实现六个方法：

```python
class HermesAgentBaseEnv(BaseEnv):
    def setup(self):           # 加载数据集，初始化状态
    def get_next_item(self):   # 返回下一个训练项
    def format_prompt(self):   # 将数据集项转换为用户消息
    def compute_reward(self):  # 评分（有完整 ToolContext 访问权限）
    def evaluate(self):        # 定期评估
```

关键配置项（`HermesAgentEnvConfig`）：
- `max_agent_turns`（默认 30）：每次 rollout 最大 LLM 调用次数
- `distribution`：工具集分布（如 "development"、"terminal_tasks"）
- `terminal_backend`：终端后端（local/docker/daytona）
- `tool_pool_size`：工具线程池大小（默认 128）

### 1.4 Benchmark 环境

Hermes 包含多个专门用于评估的 benchmark 环境：

| Benchmark | 文件 | 评估维度 |
|-----------|------|---------|
| **TerminalBench 2** | `terminalbench_2/` | 终端命令能力 |
| **SWE-bench** | `hermes_swe_env/` | 软件工程能力 |
| **YC Benchmark** | `yc_bench/` | 创业/产品决策 |
| **Web Research** | `web_research_env.py` | 网络研究能力 |
| **Agentic OPD** | `agentic_opd_env.py` | 自主问题解决 |

### 1.5 Tool Call Parser 体系

`tool_call_parsers/` 目录包含 11 个模型专用的 parser，处理不同模型输出 tool call 时的格式差异：

| Parser | 目标模型 | 处理的问题 |
|--------|---------|-----------|
| `hermes_parser.py` | Hermes 系列 | 标准格式 |
| `deepseek_v3_parser.py` | DeepSeek V3 | 特殊 JSON 结构 |
| `glm47_parser.py` | GLM-4.7 | 中文 function call 格式 |
| `kimi_k2_parser.py` | Kimi K2 | Moonshot 自定义格式 |
| `qwen3_coder_parser.py` | Qwen3-Coder | Qwen tool call 变体 |

---

## 二、批量轨迹生成：Batch Runner

`batch_runner.py`（~1,300 行）是 Hermes 的大规模轨迹生成引擎。

### 2.1 架构

```
python batch_runner.py --dataset_file=data.jsonl --batch_size=10 --run_name=my_run
  → BatchRunner.__init__()
    → 加载 dataset (JSONL)
    → 切分为 batches (batch_size=10)
    → 初始化 checkpoint 目录
  → BatchRunner.run()
    → multiprocessing.Pool(num_workers=4)
      → 每个 worker: process_item(item)
        → AIAgent(skip_context_files=True)  # 不加载用户上下文
        → agent.run_conversation(prompt)
        → 保存 trajectory (from/value pairs)
        → 更新 checkpoint
    → 汇总 tool_stats  + reasoning_stats
```

### 2.2 Checkpoint 机制

Batch Runner 的 checkpoint 设计精巧：

- **内容级恢复**：不是通过行号，而是通过 **prompt 文本内容匹配** 判断哪些已完成（`_scan_completed_prompts_by_content()`）
- **原子写入**：每个 batch 完成后的 checkpoint 使用原子文件替换
- **Resume 支持**：`--resume` 标志自动跳过已完成的 prompts

### 2.3 轨迹格式

每条轨迹保存为 JSON 对象，关键字段：

```json
{
  "prompt": "用户任务文本",
  "messages": [{"from": "user", "value": "..."}, {"from": "assistant", "value": "..."}],
  "tool_stats": {"terminal": {"count": 3, "success": 2, "failure": 1}},
  "reasoning_stats": {"turns_with_reasoning": 5, "turns_without_reasoning": 3},
  "turns_used": 8,
  "finished_naturally": true
}
```

### 2.4 工具统计聚合

所有 worker 完成后，`_extract_tool_stats()` 遍历消息历史，对 61 个工具逐一统计：调用次数、成功/失败率。统计结果同时输出为 JSON 文件和 Rich 终端表格。

---

## 三、测试体系

Hermes 的测试体系规模宏大且高度自动化。

### 3.1 测试规模

| 维度 | 数值 |
|------|------|
| 测试文件数 | ~700 |
| 测试用例数 | ~15,000 |
| 测试框架 | pytest |
| 并行执行 | pytest-xdist（4 workers） |
| CI 超时 | 15 分钟 |

### 3.2 测试分类

```
tests/
├── agent/          # Agent 内核测试（上下文压缩、prompt 构建、辅助路由）
├── hermes_cli/     # CLI 命令测试（auth、config、models、providers）
├── tools/          # 工具单元测试（61 个工具逐一覆盖）
├── environments/   # 训练环境测试
├── gateway/        # Gateway 平台适配器测试
├── skills/         # Skill 系统测试
├── plugins/        # 插件系统测试
├── integration/    # 集成测试（CI 中跳过）→ --ignore=tests/integration
└── e2e/            # 端到端测试（CI 中跳过）→ --ignore=tests/e2e
```

### 3.3 密封环境（Hermetic Environment）

`scripts/run_tests.sh` 确保测试的可重复性：

- `TZ=UTC`、`LANG=C.UTF-8`、`PYTHONHASHSEED=0`（确定性）
- **清空所有凭据环境变量**：任何 `*_API_KEY`、`*_TOKEN`、`*_SECRET` 等命名的变量全部 unset
- `pytest-xdist -n 4` 并行执行（CI 环境为 4 核）
- `pytest-split` 支持分片执行（多 CI job 并行）

---

## 四、对标分析

| 维度 | Hermes | Gemini CLI | Claude Code |
|------|--------|-----------|-------------|
| **RL 训练框架** | Atropos + 自建环境 | 无 | 无 |
| **训练模式** | 两阶段（API Server + ManagedServer） | 不适用 | 不适用 |
| **Batch 轨迹生成** | ✓（multiprocessing Pool + checkpoint） | ✗ | ✗ |
| **Benchmark 环境** | 5 种（SWE/Terminal/YC/Web/OPD） | 无 | 无 |
| **Tool Parser 体系** | 11 个模型专用 parser | 无 | 无 |
| **测试文件数** | ~700 | ~100 | ~200（估计） |
| **测试用例数** | ~15,000 | ~2,000 | ~3,000（估计） |
| **并行测试** | pytest-xdist 4 workers | Jest parallel | Jest parallel |
| **密封测试环境** | ✓（凭据清空 + 确定性环境变量） | ✗ | ✗ |
| **语言** | Python（pytest + multiprocessing） | TypeScript（Jest） | TypeScript（Jest） |

**关键差异**：RL 训练基础设施是 Hermes 独有的工程基因。没有任何其他开源 Agent 项目（包括 Gemini CLI 和 Claude Code）提供了从"训练环境定义 → 批量轨迹生成 → Benchmark 评估"的完整 RL 训练闭环。这是 Hermes 定位为"可训练的 Agent 框架"而非"编程助手工具"的核心差异。

---

*系列归属：Hermes Agent 深度拆解 · 第 10 篇*

*全系列完 · 感谢阅读*
