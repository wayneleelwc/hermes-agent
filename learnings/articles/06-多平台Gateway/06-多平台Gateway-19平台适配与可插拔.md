# Hermes Agent 深度拆解：多平台 Gateway —— 20 平台适配与可插拔架构

> 聚焦问题：一个 Gateway 进程如何同时服务 20 个消息平台？可插拔平台架构怎么设计？

![Gateway — 封面](./diagrams/all-diagrams.html)

---

## 架构总览

Hermes Gateway 是一个**asyncio 长驻进程**，启动后同时连接 20 个消息平台（Telegram、Discord、Slack、WhatsApp、Signal、Matrix、Mattermost、Email、SMS、钉钉、飞书、企业微信、微信、QQ、HomeAssistant 等）。每个平台适配器实现相同的 `on_message() + send_message()` 接口。

![Gateway 全景 — 20 平台适配器共享消息分发引擎](./diagrams/all-diagrams.html)

```
┌─────────────────────────────────────────────────────────────────┐
│                     Gateway 架构全景                              │
│                                                                  │
│  ┌──────────────────────────────────────────────────────────┐   │
│  │                  Platform Adapters (20)                    │   │
│  │  ┌─────────┐ ┌─────────┐ ┌──────────┐ ┌──────────────┐  │   │
│  │  │Telegram │ │ Discord │ │ WhatsApp │ │    微信/飞书   │  │   │
│  │  │ Bot API │ │Gateway │ │  Baileys  │ │  Webhook/API  │  │   │
│  │  └────┬────┘ └────┬────┘ └────┬─────┘ └──────┬───────┘  │   │
│  │       └───────────┴───────────┴──────────────┘           │   │
│  └───────────────────────┬──────────────────────────────────┘   │
│                          │                                       │
│  ┌───────────────────────┴──────────────────────────────────┐   │
│  │              GatewayRunner (gateway/run.py)               │   │
│  │  ┌─────────────┐  ┌─────────────┐  ┌─────────────────┐  │   │
│  │  │ Message     │  │ Session     │  │ Hook System     │  │   │
│  │  │ Dispatch    │  │ Store       │  │ (lifecycle)     │  │   │
│  │  └──────┬──────┘  └──────┬──────┘  └────────┬────────┘  │   │
│  └─────────┼────────────────┼──────────────────┼───────────┘   │
│            │                │                  │                │
│            ▼                ▼                  ▼                │
│  ┌─────────────────────────────────────────────────────────┐   │
│  │              AIAgent (run_agent.py)                      │   │
│  │  每收到消息创建一个 AIAgent 实例，注入会话历史               │   │
│  └─────────────────────────────────────────────────────────┘   │
└─────────────────────────────────────────────────────────────────┘
```

---

## 一、Platform Adapter 模式

每个平台适配器是一个 Python 类，实现标准接口：

```python
# 所有平台适配器的接口契约
class PlatformAdapter:
    async def start(self) -> None:
        """建立连接（WebSocket/长轮询/Webhook）"""

    async def on_message(self, event: MessageEvent) -> None:
        """收到消息回调"""

    async def send_message(self, chat_id: str, content: str) -> None:
        """发送回复"""
```

启动流程：`start_gateway()` → 遍历配置的平台列表 → 对每个平台 `adapter.start()` → 进入 asyncio 事件循环。

---

## 二、消息分发流程

```
平台事件到达
  → Adapter.on_message() → MessageEvent
    → GatewayRunner._handle_message()
      → 用户鉴权（白名单 / DM 授权）
      → 解析 Session Key（如 agent:main:telegram:dm:123）
      → 从 SessionStore 加载对话历史
      → 创建 AIAgent(session_id=..., history=...)
      → AIAgent.run_conversation()
      → 通过 Adapter.send_message() 发送回复
```

### 2.1 Session Key

Session Key 是 `agent:<profile>:<platform>:<chat_type>:<chat_id>` 格式，确保：
- 不同 profile 的会话隔离
- 不同平台的会话隔离
- 群聊和私聊的会话隔离

### 2.2 并发处理

多个平台的消息会**并行**触发 `_handle_message()`。每个消息处理在自己的 asyncio task 中运行，但由于 `AIAgent` 是同步的，实际执行通过 `asyncio.to_thread()` 转移到线程池。

---

## 三、Cron 集成与 Curator 调度

Gateway 内置 `cron/` 调度器：

- **定时任务**：用户通过 skill 创建的 cron job → `jobs.json` → scheduler 定期检查并执行
- **Curator**：7 天周期的知识审查 → Gateway cron ticker 触发 → fork 新 AIAgent 执行审查流程

---

## 四、Hook 系统

Gateway 支持插件钩子（通过 `builtin_hooks/` 和插件系统）：

| 钩子 | 触发时机 | 用途 |
|------|---------|------|
| `on_session_start` | 新会话创建 | 初始化会话状态 |
| `pre_llm_call` | API 调用前 | 注入上下文 |
| `pre_api_request` | 请求发送前 | 请求拦截/修改 |
| `agent:step` | 每个工具步进 | 监听 Agent 行为 |

---

## 五、对标分析

| 维度 | Hermes | Gemini CLI | Claude Code |
|------|--------|-----------|-------------|
| **消息平台** | 20 平台 Gateway | 无 | 无 |
| **进程模型** | asyncio 长驻 | CLI 单进程 | CLI 单进程 |
| **会话存储** | SessionStore（SQLite） | 文件系统 | 文件系统 |
| **Cron 任务** | 内置调度器 | 无 | 无 |
| **Webhook 支持** | ✓ | ✗ | ✗ |

**关键差异**：Gateway 是 Hermes 独有的架构基因——它让 Hermes 不只是开发者的 CLI 工具，而是一个可以部署在服务器上的自主 Agent 后台服务。

---

*下一篇：[07 · CLI 与 TUI 双界面](../09-CLI与TUI交互/07-CLI与TUI交互-双界面皮肤引擎与命令系统.md)*

*系列归属：Hermes Agent 深度拆解 · 第 06 篇*
