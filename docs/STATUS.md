# 当前状态

最后更新：2026-09-25

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

- 模型与服务：自 2026-09-25 起，全部改用 newapi 网关上的 glm-5.3-flash（agent 与 judge）。live 管线仍按百炼和 `enable_thinking` 编写，G3 之前必须完成 R8 适配；历史 qwen 结果与之后的结果不能直接比较。
- 覆盖：离线预言探针已通过。在 glm 下，给 network_policy 注入真实对象后多数成功 9/11，安慰剂 1/11；只给名字清单时，7/11 会主动取回。待验证：开局命名空间对象清单（T4b，按预先登记规则加上 F1）能否在 live floor 类上达到 ≥3/6（对照为 glm 同期的 0/9，p=0.044）。
- 归因：新上下文结论撰写（A2）离线通过，归因错误组多数成功 7 对 5，原成功不下降；F1 契约单独使用、提交抽取、skill 与 thinking 均已淘汰。待验证：A2 在 live 中的效果。由于 glm judge 无法区分 NML 的定位错误，A2 的 live 设计需要在 G4 之前修订。
- 噪声与 judge：qwen judge 下，NML 判定由噪声主导；glm judge 则把 5/5 条官方 NML 失败都判为成功。NML 结论必须注明 judge 模型，并经过多次重评。
- 成本：标签合并可无损减少 get_logs 字符 57.6%；在 glm 最后一步重放中，prompt token 减少 37.2%（加折叠为 54.3%），判定非劣。只作为成本项。
- 本轮没有启动 live。
- evidence 包用于代码审阅和结果核查，不是 Agent 输入、skills、训练 prompt 或 judge 的额外输入。

## 审阅入口

- 代码改动：`patches/holmesgpt.patch`、`patches/sregym.patch`。
- 评测摘要：`docs/reports/2026-09-21-campaign-measurements.md`。
- 逐 attempt 脱敏证据：`evidence/diagnosis-20260921/`（生成后提交）。
- evidence 生成器：`scripts/export_campaign_evidence.py`。
- Harness 改进候选、排序与否决闸门：`docs/plans/2026-09-23-harness-improvement-candidates.md`。
- 离线复算与实验原始输出（本地，被忽略）：`artifacts/offline-20260923/`（qwen E1/E2），`artifacts/offline-20260925/`（glm G1）。
- 离线否决实验 G1 结果：`docs/reports/2026-09-25-offline-g1-glm.md`。
