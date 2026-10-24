# 评测套件

[English](README.md) | [简体中文](README.zh-CN.md)

## 确定性测试

```sh
uv run pytest
```

使用预设模型响应和模拟 GitHub 响应执行实际 Graph 与来源读取器，不需要网络或模型密钥。
这类测试验证程序规则，不衡量真实模型质量。

## 对照 GitHub 验证题集

```sh
uv run python -m evals.answers --validate
```

此命令读取 GitHub，不调用模型；验证数据结构、场景 ID 唯一性、参考 ID、不可变政策 commit 和准确原文摘录。
题集的 `corpus_commit` 表示远程政策版本，不是本地数据库。
固定题集包含 45 场景／51 轮／36 来源锚点，包括六个多轮场景，以及事实、跨文件、错误前提、
证据不足、越界、提示注入和中文问题。可选的只读 `POLICY_GITHUB_TOKEN` 用于提高公开 REST API 配额。

## 真实评测

```sh
uv run python -m evals.answers --live --limit 3 --output evals/reports/answers-smoke.json
uv run python -m evals.answers --live --workers 3 --output evals/reports/answers-local.json
```

需要配置支持工具调用的聊天模型，真实调用会产生服务商费用。
默认输出 `evals/reports/answers-local.json`，由 Git 忽略，不会覆盖已提交基线。
`--workers 1..4` 可并发执行隔离场景，默认 1，结果顺序固定；不同并发数不能用于受控延迟比较。

运行器固定题集政策版本，调用与 API 相同的 `ChatService`。
每个问题创建新读取器，由 LLM 自行选择并打开文件。
同场景后续轮次只接收此前已完成问答，最多 20 对；不同场景重置上下文。
前置问题失败时，停止依赖它的追问。参考原文仅供评测器验证，不提供给 Agent；
对于其他引用文件，也独立下载核对。

报告记录问题、回答、精确引用、轨迹、版本／模型／Prompt、用量、耗时和错误类型，不含凭据。
只有显式生成的合成场景评测报告会落盘；应用聊天和来源缓存保持临时。
生成报告默认忽略，明确选定后才纳入版本控制。

## 指标与语义审核

自动检查类型匹配、准确引用来源、本轮读取、引用存在性、来源版本和预期文件／锚点覆盖。
**这些不等于答案准确率，也不能证明语义支持。** 非政策回复无需读取即可通过部分引用检查；
正确的其他证据也可能导致预期来源覆盖较低。

逐轮审核 `human_review.correctness`、`grounding`、`citation_support` 和 `notes`，
检查是否准确回答问题、正确理解追问、保留例外，以及每条重要论述是否被引用行支持。
非政策回复的依据／引用支持可不适用，但仍要判断回复是否恰当。
未审核字段保持 null；区分开发编码 Agent 的观察和独立人工判断。没有实现额外的模型裁判 Prompt。

题集是公开开发数据。Prompt、模型或读取行为改变后，需要重新真实运行，才能宣称新的质量分数。
未改写的[已记录报告](reports/answers-online.json)及已知失败见
[ONLINE_RESULTS](../docs/ONLINE_RESULTS.md)；当前工程验证见 [VERIFICATION](../docs/VERIFICATION.md)。
