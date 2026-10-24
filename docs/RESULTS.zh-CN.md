# 历史评测结果——2026-10-22

[English](RESULTS.md) | [简体中文](RESULTS.zh-CN.md) | [中文文档目录](README.zh-CN.md)

这些真实评测早于 2026-10-24 的页面内存／仅 Web 改版，不是当前在线文件读取架构的新质量分数。
下述本地政策库、Embedding 和混合检索已于 2026-10-24 移除。
当前检查见[验证日志](VERIFICATION.zh-CN.md)和[在线评测结果](ONLINE_RESULTS.zh-CN.md)。

## 配置

政策版本：`b9578b546d2506febda1da2cd7431644d58e512c`，57 份 Markdown 文档、721 个片段。
最终 Prompt：`policy-agent-v2`。聊天：DeepSeek `deepseek-flash`，非思考模式工具调用。
Embedding：北京地域阿里百炼 `qwen3.7-text-embedding-flash`，1,024 维浮点向量，每批 20 条。
混合检索采用 SQLite FTS5 + 余弦相似度，以倒数排名融合（RRF）合并；Agent 检索还会补充有数量限制的相邻原文。

## 真实回答

各次均使用相同的 45 个场景／51 轮问题，其中 6 个多轮场景。
它们是公开开发案例，不是独立保留的基准。三份报告均包含真实回答、引用摘录和工具轨迹，没有请求错误。

| 版本 | 预期回答类型匹配 | 引用来源检查 | 政策回答有引用 |
| --- | --- | --- | --- |
| 初始关键词／v1 | 48/51（94.1%） | 51/51 | 51/51 检查通过 |
| 关键词／v2 + 相邻上下文 | 50/51（98.0%） | 51/51 | 51/51 检查通过 |
| 最终混合检索／v2 + 相邻上下文 | 49/51（96.1%） | 51/51 | 51/51 检查通过 |

非政策回答无需引用，因此引用存在性检查可自动通过。各次来源版本均与政策库版本一致。
最终在有参考要求的 45 轮中，预期文档和参考锚点的平均覆盖均为 97.8%。
最终延迟中位数为 6.02 秒，最大 12.84 秒；这只是单台机器的一次顺序执行，不是负载或延迟基准。

**这些是结构／覆盖指标，不是答案准确率或语义依据分数。**
最终混合检索未比关键词 v2 提高类型匹配；模型采样和检索变化同时存在，不能归因于单一因素。

初始中文申诉问题漏掉相邻的六个月条款，错误暗示政策中没有该规定。
v2 Prompt 和有数量限制的相邻上下文在后续关键词／混合检索中找回该条款。
这是针对已知失败的开发迭代，不是独立验证。

开发编码 Agent 检查了全部最终回答与场景要求，并针对发现的问题核对原文；
[审核记录](../evals/REVIEW.zh-CN.md)保留漏答和过度概括。人工字段仍为 null，
没有宣称独立人工准确率或经校准的模型裁判分数。

## 检索对比

固定扩展题集包含 24 个问题：12 个原始英文问题、6 个英文改写和 6 个中文问题。
两种模式都取前 6 个片段，不使用 Agent 的相邻上下文扩展。
指标只判断预期文档是否出现，不衡量章节覆盖或回答质量。

| 问题 | 关键词 | 混合检索 |
| --- | --- | --- |
| 英文（18） | 16/18 | 16/18 |
| 中文（6） | 0/6 | 6/6 |
| 合计 | 16/24（66.7%） | 22/24（91.7%） |

两种模式均未召回 `paraphrase-research` 和 `paraphrase-copyright` 的预期专门文档。
检索到的相关政策可能有用，但按预期文档指标仍算未命中。
较简单的原始 12 题英文基线达到 12/12，不能替代上述对比。

以下为旧架构在同步／索引政策并配置 Embedding 后的复现命令；当前架构已移除检索运行器，不能直接运行旧命令：

```sh
uv run python -m evals.retrieval --dataset evals/datasets/retrieval-extended.jsonl --mode keyword --output evals/reports/retrieval-keyword-extended.json
uv run python -m evals.retrieval --dataset evals/datasets/retrieval-extended.jsonl --mode hybrid --output evals/reports/retrieval-hybrid.json
uv run python -m evals.answers --live --output evals/reports/answers-live.json
```

旧混合检索评测调用 Embedding API，不调用聊天 API；真实回答评测调用聊天 API，混合模式还会调用查询 Embedding API。
费用和免费额度取决于评审的服务商账号；实际金额未独立核算。服务商提供的 token 用量会保留。

## 环境与界面

- 在独立 Python 环境安装最终 wheel，**55 项后端测试通过**。
- 前端从锁文件干净安装，**6 项测试**、格式检查和 TypeScript／生产构建通过；其后未修改前端。
- 在 614px 宽视口验证真实中文两轮对话、切换来源和刷新后恢复历史；[演示](DEMO.zh-CN.md)包含真实回答。
- 源码版本 `b8af71c` 已上传私有仓库 [adamboots3/gradual-policy-agent](https://github.com/adamboots3/gradual-policy-agent)。
- [GitHub Actions](https://github.com/adamboots3/gradual-policy-agent/actions/runs/39810856851) 的五项检查全部通过：Windows/Linux 后端、Windows/Linux 前端，以及 Docker 构建／启动／健康检查。容器检查未执行政策同步／索引或付费模型调用；本机没有 Docker。

当时已知限制包括：模型过度概括、偶发错误拒答、无身份认证、有限上下文窗口、
使用固定政策快照而非实时版本，以及引用的语义支持仍需审核。
