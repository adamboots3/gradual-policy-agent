# 验收核对——在线读取版，2026-10-24

[English](ACCEPTANCE.md) | [简体中文](ACCEPTANCE.zh-CN.md) | [中文文档目录](README.zh-CN.md)

当前设计遵循用户调整后的范围：仅 Web 端访问、临时对话，以及直接从 GitHub 选择并读取政策文件的 Agent。
本地政策库、Embedding、文档入库／索引和交互式 CLI 均已移除。

| 要求 | 当前实现 | 能力边界 |
| --- | --- | --- |
| 基于政策提供支持 | 获取目录，由 LLM 选择／读取文件，依据本轮原文回答 | 仍可能漏选文件或过度解释原文 |
| 多轮对话 | 使用前端最多 20 轮已完成问答；上下文超限时从最早的一轮开始裁剪 | 不做摘要，不恢复历史记录 |
| 来源引用 | 本轮实际读取的来源 ID、准确的原文行范围、不可变 commit 链接 | 来源真实不等于结论得到支持 |
| Agent 框架 | LangChain 工具／模型适配器，以及有预算限制的 LangGraph 执行流程 | 无任意网页浏览或生产环境身份认证 |
| Web 访问 | React 聊天、正文引用、来源面板和在线来源信息 | 政策回答需要访问模型和 GitHub |
| 运行环境 | 锁定 Python/npm 依赖，支持原生和 Compose 启动，无需政策初始化 | 最新已执行检查见 VERIFICATION；旧 CI 结果不代表新版本验证 |
| 评测 | 两次完整在线评测；最终完成 51/51 轮，类型匹配 50/51，来源检查 51/51 | 已记录文件选择／语义问题，独立人工审核未完成 |
| GitHub 交付 | 私有仓库 main 分支，包含在线读取代码、报告和时序图 | 评审需要仓库访问权限；已发布版本的检查状态以 Actions 为准 |

项目仓库：[adamboots3/gradual-policy-agent](https://github.com/adamboots3/gradual-policy-agent)。
较早的 Web-only 提交 `4bc4639` 通过了全部五项 GitHub Actions 检查。
在线读取改动单独记录，旧报告仅作历史参考。
没有创建公开部署或自动邀请评审。凭据保留在本地，不会包含在提交的报告中。

相关记录：[验证日志](VERIFICATION.zh-CN.md)、[在线评测结果](ONLINE_RESULTS.zh-CN.md)。
