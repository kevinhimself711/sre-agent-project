# 当前状态

最后更新：2026-09-23

## 代码与实验入口

- 当前工程分支：`codex/campaign-evidence`。
- 冻结 campaign 使用代码提交：`f86969a784f939a2a75f1eb42aa8514a81ff2108`。
- 最新 campaign：`diagnosis-20260921`。
- 完整原始运行材料仍在被忽略的 `artifacts/pci-2/`；根仓库只提交压缩后的审阅证据包。

## 已拍板结论

- HolmesGPT 原生 Agent Loop + SREGym 官方 MCP/runner/judge/复位链路保持不变。
- 诊断复核（review）没有带来冻结开发集的成功数提升，且增加 token 和调查时长，不进入推荐 baseline。
- MCP 错误语义与恢复提示（recovery）保留为可选配置；当前证据不足以声称它带来诊断提分。
- 不把完整上游源码 vendoring 到根仓库；通过固定上游 commit + 可校验 patch 重建，patch 是审阅本地改动的精确清单。

## 当前待验证假设

- 上下文/证据保留、工具选择、停止策略和可靠执行仍需基于新的失败样本逐项对照；尚未预先承诺哪一项有效。
- evidence 包用于代码审阅和结果核查，不是 Agent 输入、skills、训练 prompt 或 judge 的额外输入。

## 审阅入口

- 代码改动：`patches/holmesgpt.patch`、`patches/sregym.patch`。
- 评测摘要：`docs/reports/2026-09-21-campaign-measurements.md`。
- 逐 attempt 脱敏证据：`evidence/diagnosis-20260921/`（生成后提交）。
- evidence 生成器：`scripts/export_campaign_evidence.py`。
