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

- 覆盖：network_policy 失败的主因是没有查询故障对象类（11/12 从未查询 NetworkPolicy）。先用离线预言探针 E3/E3b 检验"看到证据就能归因"；通过后，以开局命名空间对象清单（T4b）在 floor 类上做 live 检验（≥3/6，单侧 Fisher p≈0.015–0.025）。
- 归因：已看到证据仍失败的 8 条集中在"选错对象"（NML 失败 D1=0，readiness 失败 D2≤0.33）。用最终答案契约（F1）和新上下文结论撰写（A2）的最后一步重放来检验。
- 噪声：NML 的官方判定由 judge 噪声主导（离线 5 次重评中 3/6 条目不稳定，多数判定 3/6，而官方为 1/6）；NML 结论必须经过多次重评，不能依据单次判定。
- 成本：日志标签合并可以无损减少 get_logs 字符 57.6%（累计输入字符 30.4%），只作为成本项，不作为诊断提升。
- 离线实验 E2b–E10 因模型 API 账户欠费中断，判定标准已预先登记；恢复后从闸门 G1 继续。本轮没有启动 live。
- evidence 包用于代码审阅和结果核查，不是 Agent 输入、skills、训练 prompt 或 judge 的额外输入。

## 审阅入口

- 代码改动：`patches/holmesgpt.patch`、`patches/sregym.patch`。
- 评测摘要：`docs/reports/2026-09-21-campaign-measurements.md`。
- 逐 attempt 脱敏证据：`evidence/diagnosis-20260921/`（生成后提交）。
- evidence 生成器：`scripts/export_campaign_evidence.py`。
- Harness 改进候选、排序与否决闸门：`docs/plans/2026-09-23-harness-improvement-candidates.md`。
- 离线复算与实验原始输出（本地，被忽略）：`artifacts/offline-20260923/`。
