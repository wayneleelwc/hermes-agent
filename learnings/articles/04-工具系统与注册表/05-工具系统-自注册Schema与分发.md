# Hermes Agent 深度拆解：工具系统 —— 自注册、Schema 与七种终端后端

> 聚焦问题：61 个工具如何自注册？七种终端后端（local/docker/ssh/daytona/singularity/modal/vercel）有什么区别？

![工具系统 — 封面](./diagrams/all-diagrams.html)

---

## 架构总览

Hermes 的工具系统由三个核心组件构成：**registry.py**（中央注册表）、**tools/*.py**（61 个工具实现，每个文件一个工具）、**model_tools.py**（工具发现与分发调度）。它的独特之处在于自注册模式——工具文件在被导入时自动注册，零手动配置。

![工具系统全景 — 自注册 → Schema → 分发 → 执行](./diagrams/all-diagrams.html)

```
┌─────────────────────────────────────────────────────────────────┐
│                      Hermes 工具系统                              │
│                                                                  │
│  ┌─────────────┐    ┌─────────────────┐    ┌──────────────────┐ │
│  │ tools/      │    │ registry.py     │    │ model_tools.py   │ │
│  │ registry.py │    │ 工具发现    工具分发│    │ 工具集管理       │ │
│  │ 中央注册表   │    │ 安全审批    结果回传│    │ Schema 生成      │ │
│  └──────┬──────┘    └────────┬────────┘    └────────┬─────────┘ │
│         │                    │                      │           │
│  ┌──────┴────────────────────┴──────────────────────┴─────────┐ │
│  │ 61 个工具实现 (tools/*.py)                                   │ │
│  │ ┌───────────┐ ┌──────────┐ ┌──────────┐ ┌──────────────┐  │ │
│  │ │ File Tools│ │Terminal  │ │ Web      │ │ Multi-Agent  │  │ │
│  │ │ read/write│ │local/docker│ │search    │ │ delegate    │  │ │
│  │ │ patch     │ │/ssh/daytona │ │extract   │ │ _task        │  │ │
│  │ │ search    │ │/singularity │ │browser   │ │              │  │ │
│  │ └───────────┘ └──────────┘ └──────────┘ └──────────────┘  │ │
│  │ ┌───────────┐ ┌──────────┐ ┌──────────┐ ┌──────────────┐  │ │
│  │ │ Memory    │ │Skill     │ │MCP       │ │Vision/Code   │  │ │
│  │ │ search/write│ │manage    │ │discover  │ │ read_image   │  │ │
│  │ │ profile   │ │install   │ │call      │ │ execute_code │  │ │
│  │ └───────────┘ └──────────┘ └──────────┘ └──────────────┘  │ │
│  └────────────────────────────────────────────────────────────┘ │
└─────────────────────────────────────────────────────────────────┘
```

---

## 一、自注册模式：导入即注册

Hermes 不维护手动配置的工具列表。每个工具文件在底部调用 `registry.register()` 自注册：

```python
# tools/file_tools.py — 自注册模式（简化）
from tools.registry import register

@register(
    name="read_file",
    description="Read the contents of a file",
    parameters={"path": {"type": "string", "description": "..."}},
    toolset="files",
)
def read_file(path: str) -> str:
    ...
```

`model_tools.py` 中的 `discover_builtin_tools()` 负责导入所有工具文件，导入过程触发自注册。最终 `registry.get_all_tools()` 返回完整清单。

### 设计优势

- **零配置**：新增工具只需创建一个 `.py` 文件并调用 `register()`，无需修改任何配置文件
- **去中心化**：工具注册和工具实现在同一个文件中，单一职责
- **按需导入**：`discover_builtin_tools()` 只在构造 `AIAgent` 时执行一次

---

## 二、Schema 生成：OpenAI Function Calling 格式

每个注册的工具自动生成 OpenAI Function Calling 格式的 JSON Schema：

```json
{
  "type": "function",
  "function": {
    "name": "read_file",
    "description": "Read the contents of a file",
    "parameters": {
      "type": "object",
      "properties": {
        "path": {"type": "string", "description": "File path"}
      },
      "required": ["path"]
    }
  }
}
```

生成的 Schema 通过 `model_tools.py` 收集，注入到每次 API 调用的 `tools` 参数中。对于 61 个工具，Schemas 自身可能贡献 20-30K tokens。

---

## 三、工具分发与安全审批

`model_tools.handle_function_call()` 是分发中心：

```
API Response → tool_calls[]
  → 解析 tool_call["function"]["name"] + arguments
    → 安全审批：approval.py 检查危险命令
      → CLI：交互式弹窗（allow/deny/always）
      → Gateway：回调到平台
      → ACP：编辑器内弹窗
    → 执行工具函数
    → 结果回传（追加 tool role 消息到 history）
```

### 审批三级

| 级别 | 含义 | 适用场景 |
|------|------|---------|
| `allow once` | 本次允许 | 一次性的安全操作 |
| `allow always` | 记住许可 | 频繁的安全操作 |
| `deny` | 拒绝 | 危险操作 |

---

## 四、七种终端后端

`terminal_tool.py` 支持七种执行后端，统一通过 `TerminalBackend` 接口：

| 后端 | 隔离方式 | 适用场景 |
|------|---------|---------|
| **local** | 本地进程 | 日常开发 |
| **docker** | Docker 容器 | 环境隔离 |
| **ssh** | SSH 远程 | 远程服务器 |
| **daytona** | Daytona 工作区 | 云端开发环境 |
| **singularity** | Singularity 容器 | HPC/科研环境 |
| **modal** | Modal 云函数 | 无服务器计算 |
| **vercel** | Vercel 沙箱 | 边缘计算 |

所有后端实现相同的 `execute(command, cwd, env)` 接口，工具调用方不感知后端差异。

---

## 五、工具集（Toolset）管理

Hermes 使用**工具集**概念来分组管理工具。52 个工具集包括：

- `hermes-core`：基础工具集（文件 + 终端 + web）
- `hermes-acp`：编辑器模式精选工具集
- `memory`：记忆管理工具
- `skills`：Skill 管理工具
- `mcp`：MCP 工具
- 以及 47 个按功能分类的子工具集

CLI/Gateway/ACP/Batch Runner 可以通过 `enabled_toolsets` / `disabled_toolsets` 参数控制工具范围：

```python
# CLI：全量工具集
AIAgent(enabled_toolsets=None)

# ACP：编辑器精选
AIAgent(enabled_toolsets=["hermes-acp"])

# Batch Runner：按分布抽样
AIAgent(disabled_toolsets=["messaging"])
```

---

## 六、对标分析

| 维度 | Hermes | Gemini CLI | Claude Code |
|------|--------|-----------|-------------|
| **注册模式** | 自注册（`@register()`） | `ToolRegistry` 集中式 | `tools.ts` 分散式 |
| **工具定义** | OpenAI Function Calling | Gemini `functionDeclarations` | Anthropic `tool_use` |
| **终端后端** | 7 种（local/docker/ssh/daytona/singularity/modal/vercel） | 本地 Shell | 本地 Shell + 沙箱 |
| **MCP 集成** | MCP client（~3,100 行） | 无 | 无 |
| **安全审批** | 三级（allow once/always/deny） | 单级 | 三级（y/n/always） |

---

## 七、设计哲学提炼

**命题一：自注册消除了配置与实现的分离。** 工具文件自己负责注册，没有独立的注册文件需要维护。新增工具不会忘记注册——因为注册就在工具文件里。

**命题二：终端不应只有一种。** Hermes 的 7 种终端后端证明，Agent 的终端能力应该是可插拔的。本地开发和远程部署只需要切换一个参数。

---

*下一篇：[06 · 多平台 Gateway —— 19+ 消息平台与可插拔架构](../06-多平台Gateway/06-多平台Gateway-19平台适配与可插拔.md)*

*系列归属：Hermes Agent 深度拆解 · 第 05 篇*
