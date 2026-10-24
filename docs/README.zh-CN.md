# 中文文档目录

[项目首页](../README.zh-CN.md) | [English project README](../README.md)

## 当前设计与使用说明

| 文档 | 内容 | 英文版 |
| --- | --- | --- |
| [项目运行说明](../README.zh-CN.md) | 安装、配置、启动、API、测试和容器运行 | [English](../README.md) |
| [实施计划与当前范围](PLAN.zh-CN.md) | 已确定的架构、范围和交付要求 | [English](PLAN.md) |
| [架构与接口约定](ARCHITECTURE.zh-CN.md) | 在线读取时序图、来源生命周期、工具、引用和上下文 | [English](ARCHITECTURE.md) |
| [Agent 内部机制](AGENT_INTERNALS.md) | LangChain／LangGraph 分工、State、节点、Hook 和重试 | 原文件已是中文 |
| [Web 界面](UI.zh-CN.md) | 临时对话、交互行为、引用面板和真实截图 | [English](UI.md) |
| [验收核对](ACCEPTANCE.zh-CN.md) | 作业要求、实现状态与能力边界 | [English](ACCEPTANCE.md) |
| [验证记录](VERIFICATION.zh-CN.md) | 按时间保留的环境、测试、真实问答和交付记录 | [English](VERIFICATION.md) |
| [评测套件](../evals/README.zh-CN.md) | 自动测试、题集验证、真实评测和语义审核方法 | [English](../evals/README.md) |
| [在线评测结果](ONLINE_RESULTS.zh-CN.md) | 当前在线架构的真实结果、指标含义和已知失败 | [English](ONLINE_RESULTS.md) |

验证记录按时间保留旧状态，当前范围以实施计划和架构说明为准；
某次 CI 或测试通过，仅验证该次对应版本。回答类型匹配和来源检查不等于答案准确率。

## 历史记录

以下文档记录已移除的本地政策库／混合检索和历史持久化功能，不代表当前架构：

| 文档 | 内容 | 英文版 |
| --- | --- | --- |
| [历史评测结果](RESULTS.zh-CN.md) | 旧关键词／混合检索的配置、指标和限制 | [English](RESULTS.md) |
| [历史真实演示](DEMO.zh-CN.md) | 旧版中文两轮问答和截图 | [English](DEMO.md) |
| [历史语义检查](../evals/REVIEW.zh-CN.md) | 旧版回答的漏答、过度概括和后续质量工作 | [English](../evals/REVIEW.md) |

## 时序图源文件

- [端到端问答时序图](sequence.mmd)：图内文字已是中文，同图见[架构说明](ARCHITECTURE.zh-CN.md)。
- [Agent 内部时序图](agent-internals.mmd)：图内文字已是中文，同图见[Agent 内部机制](AGENT_INTERNALS.md)。
