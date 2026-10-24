# GitHub 政策支持助手

[English](README.md) | [简体中文](README.zh-CN.md)

使用 LangChain、LangGraph、FastAPI 和 React/TypeScript 构建的 Web 助手。
它在线浏览 [github/site-policy](https://github.com/github/site-policy)：先列出政策文件，
由 LLM 选择文件，再读取带行号的原文，最后生成带有来源摘录的回答。
无需本地政策数据库、关键词或向量索引、Embedding 服务、文档入库或预先切分的片段。

项目仓库：[adamboots3/gradual-policy-agent](https://github.com/adamboots3/gradual-policy-agent)
（私有仓库，评审需要访问权限）。相关文档：[架构与时序图](docs/ARCHITECTURE.md)、
[Agent 内部机制](docs/AGENT_INTERNALS.md)、[验证记录](docs/VERIFICATION.md)、
[当前评测结果](docs/ONLINE_RESULTS.md)、[评测说明](evals/README.zh-CN.md)。

## 本地运行

环境要求：Python 3.12、[uv](https://docs.astral.sh/uv/getting-started/installation/)、
Node.js 24，以及访问 GitHub 和所选模型 API 的网络连接。

```sh
git clone https://github.com/adamboots3/gradual-policy-agent.git
cd gradual-policy-agent
uv sync --locked --all-extras
```

将 `.env.example` 复制为 `.env`，选择支持工具调用的模型。
如果使用兼容接口，可通过 LangChain 的 `openai` 适配器配置自己的模型和 API 地址：

```dotenv
POLICY_CHAT_PROVIDER=openai
POLICY_CHAT_MODEL=YOUR_TOOL_CAPABLE_MODEL
POLICY_CHAT_BASE_URL=YOUR_COMPATIBLE_API_BASE_URL
POLICY_CHAT_API_KEY=YOUR_CHAT_KEY
POLICY_CHAT_CONTEXT_WINDOW_TOKENS=YOUR_MODEL_CONTEXT_CAPACITY
```

将上述占位值替换为实际配置；上下文容量应填写模型支持的 token 数。
`openai` 表示选择适配器，不限定模型服务商。依赖锁也包含 `anthropic` 适配器；
其他服务商需要安装对应的集成包。可选配置 `POLICY_CHAT_EXTRA_BODY` 接收服务商专用的 JSON 参数。
凭据仅由后端读取，无需配置 Embedding API 密钥，也无需执行政策初始化命令。
模型生成可能产生服务商费用。

`POLICY_GITHUB_REF=HEAD` 跟随政策仓库的默认分支。每次提问只解析一次版本，
后续读取和引用都绑定到本轮确定的不可变 commit。可填写完整 commit SHA 来指定版本。
访问这个公开政策仓库不需要 token；也可配置 `POLICY_GITHUB_TOKEN`，提高 REST API 限额。
请使用仅有读取权限的 token。模型密钥与 GitHub token 独立配置。
GitHub 限流或网络失败时，系统会明确返回错误，不会依据模型记忆拼凑政策回答。

启动后端：

```sh
uv run uvicorn policy_agent.api:app --host 127.0.0.1 --port 8000
```

在另一个终端启动前端：

```sh
cd frontend
npm ci --no-audit --no-fund
npm run dev
```

打开 [Web 页面](http://localhost:5173)；[API 交互文档](http://localhost:8000/docs)。
Vite 将 `/api` 请求代理到 8000 端口。若需修改开发环境的后端地址，
请在启动 Vite 前设置 `POLICY_API_PROXY_TARGET`。更新源码后，需要重启已有进程。
Web 页面是唯一的对话入口。

## Agent 与来源引用

模型可使用三个工具：

| 工具 | 用途 |
| --- | --- |
| `list_policy_documents()` | 获取政策文件路径和大小，确定本轮 commit |
| `read_policy_document(path, start_line, line_count)` | 打开选定文件，返回带行号的原文 |
| `submit_answer(kind, answer, citations)` | 提交答案及准确的原文行范围 |

LLM 根据目录和文件名选择文件，也可以继续打开其他文件或阅读长文档的后续部分。
系统不使用算法相关性排序或自动片段选择。默认每次提问最多允许 6 次文件读取尝试、
2 次目录请求和 10 次成功的模型响应；每次模型响应最多处理 4 个工具请求。
每次读取最多返回 200 行、24,000 字符，以及继续读取所需的信息。
服务端校验 Git blob 内容标识；同一次提问内重复读取文件会复用内存内容。
政策正文和对话状态均不写入磁盘。

政策回答由模型提供 `[[1]]`、`[[2]]` 等标记和引用行范围。
每个引用列表项将来源 ID 绑定到具体行范围；同一次读取中的不同段落可以使用不同编号。
服务端检查每项引用是否选择了本轮实际读取范围内的 1–80 行，提取原文，
并生成指向不可变版本的 GitHub URL。此检查验证来源真实性，
**不保证每条结论都得到原文的语义支持**。选错文件、遗漏条件或作出无依据解释，仍是模型可能出现的问题。

## 临时上下文与 API

已完成问答只保存在当前页面的 React 内存中。刷新、离开页面、关闭窗口或新建对话会清空记录。
系统没有历史记录列表、浏览器存储、服务端会话数据库或持久化的 Graph Checkpointer。

请求体示例：

```json
{
  "content": "应该在哪里提交？",
  "history": [{"question": "账号被暂停后可以申诉吗？", "answer": "上一轮的回答"}]
}
```

`POST /api/chat` 最多接收 20 轮已完成问答，每轮问题和答案分别限制为 4,000 和 6,000 字符。
容量允许时，后端使用全部传入历史。每次调用模型前，包括在线读取政策之后，
都会计算系统提示、工具 Schema、历史问答、当前问题和本轮消息的容量预算。
系统预留输出空间，并从最早的**完整历史问答对**开始删除，直到估算输入能放入窗口。
当前问题和本轮工具调用／结果对保持完整。
若服务商返回可识别的上下文超限错误，会继续裁剪历史并进行有界重试。
系统不导入历史摘要或上一轮 Agent／工具执行过程。

`POLICY_CHAT_CONTEXT_WINDOW_TOKENS=0` 时，优先使用 LangChain 模型规格；
无法获取时，使用 32,768 tokens 作为兜底值。自定义接口应明确填写模型的实际容量。
输出上限由 `POLICY_CHAT_MAX_OUTPUT_TOKENS` 控制，默认 2,048；
另通过 `POLICY_CHAT_CONTEXT_MARGIN_TOKENS` 预留安全余量，默认 512。
Token 数使用本地保守估算，不是服务商 tokenizer 的精确计数。
如果仅当前问题和本轮必要内容就已超限，API 会明确返回 422。
裁剪只影响 LLM 输入，不会删除页面上显示的历史。
旧的 `POLICY_HISTORY_TURNS`、检索和 Embedding 配置不再生效。

| 接口 | 约定 |
| --- | --- |
| `GET /api/health` | 返回后端／模型配置状态，不发起外部调用 |
| `GET /api/policies` | 返回仓库／ref 配置，不消耗 GitHub API 配额 |
| `POST /api/chat` | 接收当前问题和临时历史，返回答案及来源摘录 |

响应包含 `source_commit`、`read_calls`、模型／Prompt 信息、耗时，以及历史接收／使用／裁剪轮数。
问候等未读取政策的回复，其来源 commit 可以为空。聊天响应使用 `Cache-Control: no-store`。
来源／配置失败返回 503，上下文／请求结构错误返回 422，其他模型服务商错误返回经过脱敏的 502。
旧的 `/api/knowledge` 和 `/api/conversations` 接口已移除。
项目不包含身份认证或公开应用部署。

## 验证与评测

```sh
uv run ruff check .
uv run ruff format --check .
uv run pytest
uv run python -m evals.answers --validate
```

自动测试使用预设模型响应和模拟 GitHub 响应，不需要模型密钥或网络。
题集验证会在线读取固定版本的参考文件，但不会调用模型。
在 `frontend/` 目录运行：`npm test`、`npm run format:check`、`npm run build`。
[评测套件](evals/README.zh-CN.md) 包含 45 个场景、51 轮问题和精确的来源锚点。
真实评测调用同一套在线 Agent，会产生模型费用。
[最终在线评测](docs/ONLINE_RESULTS.md) 完成 51/51 轮、无请求错误，
50/51 轮回答类型符合预期，51/51 轮来源检查通过。
这些指标不是语义准确率；文件选择和原文解释仍有已知问题。
旧版混合／关键词检索报告仅供历史参考，不代表当前架构的效果。

## 容器运行

```sh
docker compose up --build -d --wait
```

打开[容器版 Web 页面](http://localhost:8080)。存在 `.env` 时 Compose 会读取它；
缺少模型配置时，页面会给出提示。无需数据卷、政策仓库克隆、索引构建或 Embedding 步骤。
健康检查不需要模型密钥或 GitHub 连接。
Windows/Linux 前后端 CI，以及 Docker 构建、启动和健康检查，定义在 `.github/workflows/ci.yml`。
