# Hermes Agent 深度拆解：CLI 与 TUI 双界面 —— 皮肤引擎与命令系统

> 聚焦问题：Hermes 同时提供 CLI 和 TUI，它们如何共存？皮肤引擎怎么工作？

![CLI 与 TUI — 封面](./diagrams/all-diagrams.html)

---

## 架构总览

Hermes 提供两种界面：**CLI**（`cli.py`，基于 `prompt_toolkit`，~11,500 行）和 **TUI**（`ui-tui/`，基于 Ink React，TypeScript）。两者共享同一个 `AIAgent` 内核，通过不同的渲染层呈现。

![双界面全景 — CLI 和 TUI 共享 AIAgent，差异仅在 I/O 层](./diagrams/all-diagrams.html)

---

## 一、CLI 模式

CLI 使用 `prompt_toolkit` 实现交互式 REPL：

- **命令系统**：`/model`、`/skills`、`/memory`、`/tools`、`/reset`、`/new`、`/branch` 等斜杠命令
- **皮肤引擎**（`skin_engine.py`）：终端主题定制，颜色/样式/emoji 可配置
- **设置向导**（`setup.py` ~3,500 行）：首次启动的交互式配置流程

### 命令注册表

`commands.py` 中的 `COMMAND_REGISTRY` 是所有斜杠命令的中央注册表：

```
/model → 切换模型
/skills → 管理 Skill
/memory → 管理记忆
/tools → 管理工具
/reset → 清空会话
/new → 新建会话
/branch → 分支会话
/compact → 手动压缩
/steer → 注入引导
```

---

## 二、TUI 模式（`hermes --tui`）

TUI 由三部分组成：

| 组件 | 技术栈 | 职责 |
|------|--------|------|
| **ui-tui/src/** | Ink React (TypeScript) | 终端 UI 渲染 |
| **tui_gateway/** | Python JSON-RPC | 后端通信桥 |
| **AIAgent** | Python | Agent 内核 |

### JSON-RPC 通信

TUI 前端通过 `tui_gateway/` 的 JSON-RPC 接口与 Python 后端通信：

```
TUI (React) → JSON-RPC over stdio → tui_gateway (Python) → AIAgent
```

---

## 三、皮肤引擎

`skin_engine.py` 提供终端主题系统：

- **颜色方案**：预设主题 + 自定义颜色配置
- **Emoji 风格**：kawaii/neutral/minimal 三种风格
- **Spinner 动画**：`KawaiiSpinner` 类提供多种动画模式

---

## 四、对标分析

| 维度 | Hermes | Gemini CLI | Claude Code |
|------|--------|-----------|-------------|
| **CLI 技术** | prompt_toolkit (Python) | Ink React (TypeScript) | Ink React (TypeScript) |
| **TUI 技术** | Ink React + JSON-RPC | 无独立 TUI | 无独立 TUI |
| **皮肤系统** | ✓（skin_engine.py） | ✗ | ✗ |
| **设置向导** | ✓（setup.py ~3,500 行） | 首次引导 | 首次引导 |

---

*下一篇：[08 · 多 Agent 委派与并行](../08-多Agent委派/08-多Agent委派-子进程隔离与并行.md)*

*系列归属：Hermes Agent 深度拆解 · 第 07 篇*
