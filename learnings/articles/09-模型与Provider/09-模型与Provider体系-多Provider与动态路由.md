# Hermes Agent 深度拆解：模型与 Provider 体系 —— 30+ Provider 与动态路由

> 聚焦问题：Hermes 如何支持 30+ 模型 Provider？OAuth/API Key/外部进程三种鉴权如何统一？模型切换、fallback、辅助模型路由怎么设计？

![模型与 Provider — 封面](./diagrams/all-diagrams.html)

---

## 架构总览

Hermes 的 Provider 体系由四层组成：**认证层**（auth.py，~4,700 行）→ **身份层**（providers.py，~700 行）→ **模型目录层**（models.py，~3,500 行）→ **运行时解析层**（runtime_provider.py，~1,300 行）。四层合力实现了"用户只说模型名，系统自动找 key + url + 协议"的零配置体验。

![Provider 体系全景 — 四层架构与数据流](./diagrams/all-diagrams.html)

```
┌─────────────────────────────────────────────────────────────────┐
│                     Provider 体系四层架构                          │
│                                                                  │
│  ┌──────────────────────────────────────────────────────────┐   │
│  │  1. 认证层 (auth.py)                                      │   │
│  │  OAuth Device Code │ API Key Env Vars │ External Process  │   │
│  │  auth.json 持久化 + 跨进程文件锁 + Token 自动刷新           │   │
│  └───────────────────────┬──────────────────────────────────┘   │
│                          │                                       │
│  ┌───────────────────────┴──────────────────────────────────┐   │
│  │  2. 身份层 (providers.py)                                 │   │
│  │  models.dev catalog (109+ providers) + HermesOverlay       │   │
│  │  transport │ is_aggregator │ auth_type │ extra_env_vars    │   │
│  └───────────────────────┬──────────────────────────────────┘   │
│                          │                                       │
│  ┌───────────────────────┴──────────────────────────────────┐   │
│  │  3. 模型目录层 (models.py)                                 │   │
│  │  _PROVIDER_MODELS │ OpenRouter 动态拉取 │ Vercel AI GW     │   │
│  │  Codex 动态列表 │ xAI models.dev 缓存                       │   │
│  └───────────────────────┬──────────────────────────────────┘   │
│                          │                                       │
│  ┌───────────────────────┴──────────────────────────────────┐   │
│  │  4. 运行时解析层 (runtime_provider.py)                     │   │
│  │  resolve_runtime_provider() → {provider, api_key,          │   │
│  │    base_url, api_mode} → AIAgent                           │   │
│  └──────────────────────────────────────────────────────────┘   │
└─────────────────────────────────────────────────────────────────┘
```

---

## 一、认证层：三种鉴权模式的统一抽象

`auth.py` 中的 `PROVIDER_REGISTRY` 是所有认证 Provider 的中央注册表。每个 Provider 通过 `ProviderConfig` 声明其鉴权类型：

```python
# 三种鉴权模式在 PROVIDER_REGISTRY 中的代表性配置
"nous": ProviderConfig(
    id="nous", name="Nous Portal",
    auth_type="oauth_device_code",  # 模式1：OAuth 设备码流
    portal_base_url="https://portal.nousresearch.com",
)
"anthropic": ProviderConfig(
    id="anthropic", name="Anthropic",
    auth_type="api_key",            # 模式2：API Key 环境变量
    api_key_env_vars=("ANTHROPIC_API_KEY", "ANTHROPIC_TOKEN", "CLAUDE_CODE_OAUTH_TOKEN"),
)
"copilot-acp": ProviderConfig(
    id="copilot-acp", name="Copilot ACP",
    auth_type="external_process",   # 模式3：外部进程凭证获取
)
```

### 1.1 OAuth Device Code 流（Nous Portal、MiniMax、Codex、Qwen）

用户运行 `hermes login --provider nous` → 打开浏览器完成 OAuth 授权 → 回调服务器接收 token → 加密存入 `~/.hermes/auth.json`。

关键设计：
- **Token 自动刷新**：access token 到期前 2 分钟自动刷新（`ACCESS_TOKEN_REFRESH_SKEW_SECONDS = 120`）
- **Agent Key Minting**：Nous Portal 使用短效 agent key（默认 30 分钟 TTL），每次 `run_conversation()` 自动重新签发
- **跨进程文件锁**：`fcntl`（Linux）/ `msvcrt`（Windows）保证多进程并发访问 auth.json 安全

### 1.2 API Key 环境变量（Anthropic、OpenRouter、DeepSeek 等）

API Key 类型的 Provider 通过环境变量链查找密钥。以 Anthropic 为例：

```
ANTHROPIC_API_KEY → ANTHROPIC_TOKEN → CLAUDE_CODE_OAUTH_TOKEN
```

Hermes 按顺序检查多个环境变量，第一个非空值即被使用。这允许用户通过不同渠道获取的密钥都能自动生效。

### 1.3 外部进程凭证（Copilot ACP、Gemini CLI OAuth）

外部进程模式通过执行外部命令获取临时凭证。例如 Copilot ACP 通过 `HERMES_COPILOT_ACP_COMMAND` 环境变量指定的外部命令获取 GitHub Copilot 的临时 token。

---

## 二、身份层：109+ Provider 的元数据融合

Hermes 的 Provider 元数据来自两个数据源的运行时合并：

### 2.1 models.dev 动态目录

`models.py` 从 `https://models.dev/api.json` 动态拉取 109+ Provider 的完整元数据：base URL、环境变量名、显示名称、模型上下文长度、成本、能力标记。结果缓存到 `$HERMES_HOME/models_dev_cache.json`，离线时使用缓存。

### 2.2 HermesOverlay 本地补丁

`providers.py` 中的 `HERMES_OVERLAYS` 补充 models.dev 不提供的信息：传输协议类型（`openai_chat` / `anthropic_messages` / `codex_responses`）、是否为聚合器、鉴权类型、额外环境变量：

```python
HERMES_OVERLAYS = {
    "openrouter": HermesOverlay(
        transport="openai_chat", is_aggregator=True,
        base_url_env_var="OPENROUTER_BASE_URL",
    ),
    "anthropic": HermesOverlay(
        transport="anthropic_messages",
        extra_env_vars=("ANTHROPIC_TOKEN", "CLAUDE_CODE_OAUTH_TOKEN"),
    ),
    "openai-codex": HermesOverlay(
        transport="codex_responses", auth_type="oauth_external",
        base_url_override="https://chatgpt.com/backend-api/codex",
    ),
    # ... 30+ more overlays
}
```

三种传输协议：
| 协议 | 使用场景 | 代表 Provider |
|------|---------|-------------|
| `openai_chat` | OpenAI-compatible API | OpenRouter、Nous、DeepSeek、Qwen |
| `anthropic_messages` | 原生 Anthropic Messages API | Anthropic、MiniMax、GLM |
| `codex_responses` | OpenAI Codex Responses API | openai-codex、copilot-acp、xAI |

### 2.3 用户自定义 Provider

用户在 `config.yaml` 的 `providers:` 节可以注册自定义 Provider，覆盖 models.dev + HermesOverlay 的任何字段。这允许连接任何兼容 OpenAI API 的本地或私有端点。

---

## 三、模型目录层：按 Provider 组织的模型清单

### 3.1 静态清单 `_PROVIDER_MODELS`

`models.py` 中的 `_PROVIDER_MODELS` 字典为每个 Provider 维护模型列表：

```python
_PROVIDER_MODELS = {
    "nous": ["moonshotai/kimi-k2.6", "anthropic/claude-opus-4.7", ...],
    "anthropic": ["claude-opus-4-7", "claude-sonnet-4-6", ...],
    "openai-codex": _codex_curated_models(),  # 动态推导
    "xai": _xai_curated_models(),            # 从 models.dev 缓存推导
    # ... 25+ providers
}
```

### 3.2 动态目录

- **OpenRouter**：从 `OPENROUTER_MODELS` 静态回退 + 在线拉取 OpenRouter `/models` 端点
- **Vercel AI Gateway**：从 `VERCEL_AI_GATEWAY_MODELS` 静态回退 + 在线拉取
- **Codex**：从 `codex_models.py` 的 `DEFAULT_CODEX_MODELS` + 前向兼容推导
- **xAI**：从 `$HERMES_HOME/models_dev_cache.json` 读取最新模型列表，自动反映 xAI 重命名

### 3.3 用户模型选择

用户通过 `/model` 命令或启动时的 `--model` 参数选择模型。Hermes 在 provider 上下文中验证模型可用性——如果用户选 "gpt-5.4" 而当前 provider 是 Anthropic，Hermes 会提示切换 provider。

---

## 四、运行时解析：`resolve_runtime_provider()` 的决策树

`runtime_provider.py` 中的 `resolve_runtime_provider()` 是每次 Agent 启动时的关键入口。解析链如下：

![模型解析链路](./diagrams/all-diagrams.html)

```
resolve_runtime_provider(requested="auto", target_model=None)
  │
  ├─ 1. resolve_requested_provider("auto")
  │     → 检查 auth.json 活跃 Provider
  │     → 遍历 PROVIDER_REGISTRY 找 API Key
  │     → 返回 detected provider id
  │
  ├─ 2. Azure 特殊路径（Anthropic / Foundry）
  │     → 直接构建 runtime dict
  │
  ├─ 3. _resolve_named_custom_runtime()
  │     → 检查 config.yaml providers: 自定义端点
  │
  ├─ 4. resolve_provider() → auth.py
  │     → OAuth token 刷新 / API Key 读取
  │
  ├─ 5. _resolve_explicit_runtime()
  │     → explicit_api_key / explicit_base_url 优先
  │
  ├─ 6. CredentialPool（多 key 轮换）
  │     → 从池中获取可用凭证
  │
  └─ 7. 返回 {provider, api_key, base_url, api_mode, source}
```

### 4.1 api_mode 自动检测

`_detect_api_mode_for_url()` 根据 base URL 自动判断使用哪种 API 协议：

- `api.openai.com` → `codex_responses`（GPT-5.x 工具调用需要 Responses API）
- `api.minimax.io/anthropic` → `anthropic_messages`
- `api.x.ai` → `codex_responses`
- 其他 → 默认 `chat_completions`

这确保 Hermes 在切换到不同 provider 时自动使用正确的 API 协议，用户无需手动配置。

---

## 五、辅助模型路由：`auxiliary_client.py` 的 fallback 链

`auxiliary_client.py` 为"非对话"任务提供独立的模型路由。这些任务包括：

| 任务 | 用途 | 典型模型 |
|------|------|---------|
| 上下文压缩 | 对话摘要生成 | summary_model（可配置） |
| 会话搜索 | 历史对话检索 | 轻量模型 |
| 网页内容提取 | HTML → 文本 | 通用模型 |
| 视觉分析 | 图片理解 | 多模态模型 |
| 浏览器视觉 | 截图分析 | 多模态模型 |

### 5.1 文本任务 fallback 链（auto 模式）

```
1. 用户主 provider + 主模型（无论 provider 类型）
2. OpenRouter（OPENROUTER_API_KEY）
3. Nous Portal（~/.hermes/auth.json）
4. 自定义端点（config.yaml model.base_url + OPENAI_API_KEY）
5. 原生 Anthropic
6. 直接 API-key provider（z.ai/GLM、Kimi/Moonshot、MiniMax 等）
7. None（无可用 provider）
```

### 5.2 信用耗尽 fallback

当解析到的 provider 返回 HTTP 402 或 credit 相关错误时，`call_llm()` **自动切换到下一个可用 provider**。这意味着用户的 OpenRouter 余额耗尽时，Hermes 自动 fallback 到 Codex OAuth 或 Anthropic API Key——用户甚至可能感知不到切换。

### 5.3 Codex OAuth 的有意排除

Codex OAuth 被**有意排除**在 fallback 链之外。原因是 OpenAI 对 Codex 端点实施了未公开的、持续变化的模型白名单——"just try Codex with a hardcoded model" 策略会随时间腐化。Codex 仅在用户显式选择为 main provider 时使用。

---

## 六、Provider 优先级自动检测

`resolve_provider()` 在 `requested="auto"` 时的检测链：

1. **检查 auth.json 活跃 Provider**：如果用户登录了 Nous Portal 且 token 有效 → 返回 "nous"
2. **遍历 API Key Provider**：按 `PROVIDER_REGISTRY` 顺序检查环境变量 → 第一个有有效 key 的 provider
3. **特殊排除**：GitHub token 虽常见但不自动用于 Copilot（避免劫持推理），LM Studio 虽本地但不自动选择
4. **无可用 Provider**：提示用户运行 `hermes login` 或设置环境变量

---

## 七、对标分析

| 维度 | Hermes | Gemini CLI | Claude Code |
|------|--------|-----------|-------------|
| **Provider 数量** | 109+（models.dev） | Gemini API only | Anthropic API + API Proxy |
| **鉴权模式** | 3 种（OAuth/API Key/外部进程） | OAuth2 | OAuth / API Key |
| **Token 自动刷新** | ✓（到期前 2 分钟刷新 + 短效 agent key） | ✓（Gemini OAuth） | ✓（OAuth 自动刷新） |
| **模型目录** | models.dev 动态 + 静态回退 | 内置 | 内置 |
| **多 Key 轮换** | ✓（CredentialPool） | ✗ | ✗ |
| **辅助任务路由** | auxiliary_client 7 级 fallback | 单一模型 | 单一模型 |
| **信用耗尽 fallback** | ✓（402 自动切换 provider） | ✗ | ✗ |
| **用户自定义端点** | ✓（config.yaml providers:） | ✗ | ✗ |
| **API 协议自适应** | ✓（base URL → api_mode 自动检测） | ✗ | ✗ |
| **聚合器支持** | OpenRouter / Vercel AI GW / OpenCode | ✗ | ✗ |
| **文件锁保护** | fcntl / msvcrt 跨平台 | ✗ | ✗ |
| **语言** | Python | TypeScript | TypeScript |

**关键差异**：Hermes 的 Provider 体系设计哲学是"用户只说模型名，系统自动找 key + url + 协议"。109+ Provider 通过 models.dev 动态目录 + HermesOverlay 本地补丁 + 用户自定义覆盖三层数据融合实现。辅助模型的 7 级 fallback 链和信用耗尽自动切换是 Hermes 独有的容错设计——让 Agent 在各种环境下都能保持可用。

---

*下一篇：[10 · RL 训练与工程体系](../10-工程体系与RL训练/10-工程体系与RL训练-Atropos批量轨迹与评估.md)*

*系列归属：Hermes Agent 深度拆解 · 第 09 篇*
