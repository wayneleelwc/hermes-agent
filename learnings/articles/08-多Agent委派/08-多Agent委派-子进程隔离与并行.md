# Hermes Agent 深度拆解：多 Agent 委派与并行 —— 子进程隔离与 Batch Runner

> 聚焦问题：Hermes 如何委派任务给子 Agent？隔离和并行如何保证？

![多 Agent 委派 — 封面](./diagrams/all-diagrams.html)

---

## 架构总览

Hermes 通过 `delegate_tool.py` 实现子 Agent 委派——父 Agent 可以在对话中创建子 Agent 实例来处理子任务。关键约束是**子 Agent 运行在独立的线程中**，共享父 Agent 的 `IterationBudget`。

![多 Agent 全景 — delegate_task 的隔离架构](./diagrams/all-diagrams.html)

---

## 一、delegate_task 工具

```python
# tools/delegate_tool.py — 子 Agent 创建
# 父 Agent 调用 delegate_task(prompt, context, ...)
# → 创建新的 AIAgent 实例
# → 继承父 Agent 的 IterationBudget
# → 在独立线程中运行
# → 返回结果给父 Agent
```

### 隔离机制

| 隔离维度 | 实现方式 |
|---------|---------|
| **进程隔离** | 子 Agent 在独立线程运行，非子进程 |
| **预算隔离** | 共享 IterationBudget 实例（不能绕过总预算） |
| **中断传播** | 父 Agent 中断 → 递归传播到所有子 Agent |
| **工具限制** | 子 Agent 默认 max_iterations=50（父=90） |
| **审批安全** | 子 Agent 默认 auto-deny 危险命令 |

---

## 二、Batch Runner

`batch_runner.py` 是另一种并行模式——用于大规模轨迹生成：

```
python batch_runner.py --dataset_file=data.jsonl --batch_size=10 --run_name=my_run
  → multiprocessing.Pool
    → 每个 worker 进程创建一个独立的 AIAgent
    → skip_context_files=True（避免污染轨迹）
    → 执行 prompt → 保存 trajectory
    → checkpoint 支持 resume
```

与 delegate_task 的区别：

| 维度 | delegate_task | Batch Runner |
|------|-------------|-------------|
| **并行方式** | 线程（共享进程） | 多进程（Pool） |
| **关系** | 父子协作 | 独立 worker |
| **预算** | 共享 | 各自独立 |
| **用途** | 任务委派 | 数据生成 |

---

## 三、对标分析

| 维度 | Hermes | Gemini CLI | Claude Code |
|------|--------|-----------|-------------|
| **子 Agent** | delegate_task（线程隔离） | LocalAgent + BrowserAgent | Fork + Task |
| **预算共享** | ✓（IterationBudget 继承） | ✗（独立） | ✗（独立） |
| **Batch 模式** | multiprocessing Pool + checkpoint | 无 | 无 |
| **中断传播** | 递归传播到子 Agent | 独立中断 | 独立中断 |

**关键差异**：Hermes 的子 Agent 共享父 Agent 的预算池——这是最独特的设计。大多数系统（包括 Gemini CLI 和 Claude Code）给子 Agent 独立预算，但 Hermes 认为子 Agent 的工作也是总工作的一部分，应该从同一个池子中消耗。

---

*下一篇：[09 · 模型与 Provider 体系](../09-模型与Provider/09-模型与Provider体系-多Provider与动态路由.md)*

*系列归属：Hermes Agent 深度拆解 · 第 08 篇*
