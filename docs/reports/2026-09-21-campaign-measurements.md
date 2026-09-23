# 冻结实验逐案例测量

代码：`f86969a784f939a2a75f1eb42aa8514a81ff2108`。

镜像：`sha256:6c9300e43e1fcee42535b65138fea6ff592f41b8ce1f388f662cfaafbf674c76`。

成功数和均值只覆盖完成评分且复位通过的有效观察。token 包含可捕获的 Agent 辅助调用；缓存 token 是输入 token 的子集。调查耗时为 `tool_catalog` 至 `agent_final` 的墙钟跨度，排除环境准备、MCP 初始化和评分。账单费用未知。

| 阶段 | 案例 | 配置 | 有效/计划 | 成功 | composite 均值 | 输入 token | 输出 token | 缓存 token | 调查秒 | 拒绝/次 | 重复调用/次 |
|---|---|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| dev | network_policy_block | baseline | 3/3 | 0 | 0.00 | 376155.00 | 2583.00 | 311082.67 | 57.25 | 2.67 | 0.67 |
| dev | network_policy_block | combined | 3/3 | 0 | 0.19 | 1163980.67 | 5507.33 | 1074090.67 | 150.81 | 3.67 | 1.67 |
| dev | network_policy_block | recovery | 3/3 | 0 | 0.22 | 832678.00 | 3359.67 | 749098.67 | 79.42 | 2.33 | 0.00 |
| dev | network_policy_block | review | 3/3 | 0 | 0.15 | 1253020.33 | 4918.67 | 1122133.33 | 132.41 | 2.67 | 0.33 |
| dev | wrong_service_selector_social_network | baseline | 3/3 | 3 | 1.00 | 581113.33 | 2341.67 | 492416.00 | 63.91 | 2.33 | 0.00 |
| dev | wrong_service_selector_social_network | combined | 3/3 | 3 | 1.00 | 763007.00 | 3557.00 | 662528.00 | 82.79 | 2.00 | 1.67 |
| dev | wrong_service_selector_social_network | recovery | 3/3 | 2 | 0.81 | 628458.00 | 2602.67 | 536960.00 | 67.64 | 2.00 | 0.00 |
| dev | wrong_service_selector_social_network | review | 3/3 | 3 | 1.00 | 825730.67 | 3516.00 | 722133.33 | 93.73 | 2.00 | 0.67 |
| validation | namespace_memory_limit | baseline | 3/3 | 1 | 0.56 | 166883.00 | 2545.00 | 149162.67 | 52.52 | 6.33 | 0.00 |
| validation | namespace_memory_limit | combined | 3/3 | 0 | 0.48 | 336585.33 | 4277.33 | 304213.33 | 86.08 | 4.33 | 0.67 |
| validation | readiness_probe_misconfiguration_social_network | baseline | 3/3 | 2 | 0.78 | 226759.33 | 2863.33 | 180522.67 | 54.03 | 5.00 | 1.00 |
| validation | readiness_probe_misconfiguration_social_network | combined | 3/3 | 2 | 0.89 | 655642.00 | 5390.67 | 599680.00 | 163.14 | 4.00 | 1.67 |

validation 汇总：baseline 3/6 成功、平均 composite 0.6683、Agent 输入加输出 token 1,197,152；combined 2/6 成功、平均 composite 0.6867、Agent 输入加输出 token 3,005,686。combined 的成功数更低，token 约为 baseline 的 2.51 倍，平均调查耗时约为 2.34 倍。

替代 attempt 使用 3/4。原始失败 attempt 均保留；12 条有效 validation 之外不把 setup、清理或代理故障计作 Agent 结果。524 个本地 evidence 文件通过已知凭据拒绝检查；39 个 attempt 的哈希、复核次数、工具错误语义、实际模型上下文以及 validation/草稿导出隔离审计为 0 项问题。

此表是小样本描述统计，不提供稳定提分或充分泛化结论。
