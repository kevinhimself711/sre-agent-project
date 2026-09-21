# Baseline 实施报告（2026-09-19）

结论：计划中的真实链路已跑通。Holmes 原生两例通过；外部三次诊断中，Social Network 一次成功（100/100），NetworkPolicy 两次失败（0/100）。Stratus 对照一次失败（0/100）。四次外部运行均完成官方评分和清理，三条 Holmes 轨迹通过数据验收，成功轨迹导出 9 条 SFT 格式样本。没有测出 harness 提分，也没有训练模型。

## 固定设置与结果

原计划原样保留在 `docs/plans/2026-09-19-baseline-bootstrap.md`，它是本轮首个写入文件。运行节点 pci-2，Python 3.12.3；Holmes / SREGym 分别使用 Poetry / uv 上游锁文件与独立虚拟环境。

- Holmes：`3bd44edf04f9587c778ee8e9b244965190c40fdf`，分支 `sre-baseline`。
- SREGym：`46c853db3a79332ea1c0ada076d888cec7a02f7e`，分支 `holmes-baseline`。
- applications submodule：`887d093e4cb7ff90e5a37dd2f11320d70d2e47a7`。
- Agent / classifier / judge：百炼内地 `qwen3.8-max`，非思考模式；未切换模型。
- 外部评测：full profile、diagnosis only、filtered internet、单集群串行；Holmes 30 steps、输出上限 8192。两个故障族均属于 dev，不能作为未来独立测试集。

| 验证 | 官方结果 | Agent 输入 / 输出 token | 调查 / 判分 / 复位秒数 |
|---|---|---:|---:|
| Holmes 原生 `01_how_many_pods` | 通过，correctness 1 | 21,465 / 74 | 原生 holmes_duration 2.43 |
| Holmes 原生 `80_pvc_storage_class_mismatch` | 通过，correctness 1 | 59,974 / 1,023 | 原生 holmes_duration 15.24 |
| Stratus `network_policy_block` ×1 | diagnosis false，0 | 274,284 / 3,275，含结束摘要 | 63.26 / 8.85 / 241.88 |
| Holmes `network_policy_block` 第一次 | diagnosis false，0 | 146,090 / 1,183 | 29.69 / 10.22 / 89.40 |
| Holmes `network_policy_block` 第二次 | diagnosis false，0 | 254,857 / 2,584 | 62.63 / 8.46 / 89.39 |
| Holmes `wrong_service_selector_social_network` | diagnosis true，1.0（100/100） | 397,981 / 1,986 | 43.98 / 9.06 / 92.75 |

Token 来自模型响应或上游 usage 日志，不是字符估算。Stratus 的 ATIF 只覆盖其转换到的调查步骤，因此总开销采用 `stratus_usage.jsonl` 的 22 次请求，包含提交前后及 summary，不能直接把 ATIF 的 227,490 token 当成全部成本。原生 JUnit 中的 `cost=0.0` 是未知模型定价下的输出，**不代表免费**。未取得百炼账单；实际人民币费用未知，judge / classifier / 部分预检 token 未完整计量，不能宣称已得到本轮全部计费 token。

上表已记录的 Agent token 合计 1,164,776；另有基础 provider 预检 390 token。它们仍不是包括 judge/classifier 的完整账单总量。

结果规模仅用于接入与开发诊断，不能推断 Holmes 与 Stratus 孰优。冷启动 Stratus 部署耗时 1295.74 秒，包含首次镜像下载；Holmes 两轮 NetworkPolicy 部署约 124.87 / 124.70 秒；Social Network 首次部署 690.35 秒，包含镜像与 init-container 接入排错。完整周期主要时间花在部署与复位，模型调查也有独立的时间记录。

## 本次实现与验收

Holmes driver 使用原生 prompt 构造与 loop，通过 `/get_app` 获取公开任务、四组官方 MCP 调查，宿主 runner 负责注入、评分、归档和复位。driver 不读取故障 ID 或答案，不增加 planner 或答案改写。提交仅 POST 一次，响应丢失后查询状态并标记 unknown，不以 HTTP 200 代替诊断正确。

新增默认关闭的有效模型请求记录 hook，以及工具事件；本轮启用后记录实际传入 LiteLLM 的 messages / tools、响应、usage、调用 ID、耗时及停止原因。它不是 provider 报文抓包，也不声称捕获不可见的模型内部推理。摘要和压缩调用纳入同一边界；streaming 无完整捕获时明确不合格。

新增 Holmes ATIF adapter，复用上游 SQLite 和 CSV 导出。独立数据验收检查模型 / 工具配对、episode 结束、附件存在与哈希；原始记录为事实来源。官方结果只作为宿主标签，不拼入模型输入。每次 SFT 样本保留该次真实上下文，只监督当前 assistant，避免将未来工具结果提前写进输入。

三条 Holmes 轨迹数据验收通过，模型 / 工具调用分别 5/13、11/29、9/25；会话 UUID 不同，并在 MCP 服务日志中确认各自被使用。前两条失败轨迹不导出正样本；第三条成功轨迹导出 9 条格式样本，均保留真实上下文、tool-call 配对与监督 mask。重复导出字节一致；重复 SQLite ingest 不增行。真实轨迹没有触发 compaction，压缩后输入的保真目前由离线测试覆盖，不能声称已完成真实压缩效果实验。

最终 SQLite 有 4 条轨迹，标准 CSV 导出为 runs 4 行 / steps 57 行 / tools 90 行（包含 driver 的提交步骤，因此不等于调查工具次数）。三条 Holmes 的模型可见 messages 中未出现两个 benchmark case ID。独立复位快照确认业务 namespace、observe 和 NetworkPolicy 均无残留；四个 KIND 节点正常，原有 k3s active、`fw-coexistence` 容器仍运行。临时代理已结束。

最新针对轨迹转换、提交丢失、工具错误、缺失附件、上下文时序、CSV 评分格式、索引与导出的回归：83 项通过；Holmes hook 测试 5 项断言通过，但该次命令触发上游全仓 46% 覆盖率门槛（实际 14.80%），不能记为整条命令通过。此前包括配置隔离在内的扩展回归 93 项通过。两个原生 live eval 各一次通过；这些测试集有重叠，不相加作为唯一测试数。2026-09-21 工程化阶段将使用 `--no-cov -n 0` 对 hook 子集单独重跑，不降低上游覆盖率要求。

## 环境接入调整与失败记录

1. pci-2 的 Docker 为 cgroupfs / cgroup v1，上游 KIND 的 systemd kubelet 配置不能启动。保留两次失败证据，仅重建专用 `sre-agent-dev`，把该集群 kubelet/containerd 配置调整为 cgroupfs；没有修改宿主 cgroup 或重启已有 Docker/k3s。四节点与 Calico 结构保留。
2. 节点 Docker Hub 访问超时，使用临时 SSH 代理、skopeo 与 KIND import 预加载；GHCR 原生拉取。修正预加载器的 tag+digest 与多架构 archive 兼容性，并避免慢镜像阻塞已下载镜像的导入。失败日志保留。
3. 百炼非思考模式的工具调用往返、Holmes classifier、Stratus backend、SREGym detailed judge 已真实预检。classifier 需移除 SDK 模型名的 `openai/` 前缀，并传入 `enable_thinking=false`，否则 forced tool choice 不兼容。
4. 上游宿主 Kubernetes proxy 原先忽略外部 KUBECONFIG，可能读取默认 k3s 配置。新增显式 `SREGYM_ADMIN_KUBECONFIG`，与 agent 的过滤配置分开；新增专用缓存目录。配置隔离有回归测试。
5. `enable_all_toolsets_possible=False` 并不足以关闭默认内置工具；工具状态缓存还可能恢复旧目录。实际工具预检暴露后，adapter 显式禁用整个内置目录、关闭 prerequisite cache、启动时验证精确白名单。最终真实请求只包含官方工具，未开放本地 bash / internet / skills。
6. 官方结果 CSV 实际采用 `Diagnosis.*` 扁平列，导出器已按真实格式读取，保留旧格式兼容。提交接收与评分正确分别记录。
7. Social Network 两个 init container 在线克隆 DeathStarBench 时长时间停留在初始化。故障注入前，仅给它们配置 KIND bridge 上的临时代理，并固定实际使用的 revision `6ecb09706140f8730b5385c08f1386c654c3c526`；初始化结束后关闭监听。记录在 `social-init-proxy.json`。该环境接入调整不扩大 agent 权限。

NetworkPolicy 独立探测已完成“可连通 → 阻断 → 恢复”；早期探测失败日志保留。inotify 运行时调整为 1024 instances / 1048576 watches。SREGym 自身 bounded retry / cleanup guard 保留，未叠加无限重试。预检失败、KIND 创建失败、镜像下载失败均为环境/兼容性记录，不计为额外有效诊断样本。

## 可讲清楚的后端边界

| 问题 | 本轮实际设计与归属 |
|---|---|
| 系统边界 | 上游 Holmes 决策与工具循环；上游 SREGym 环境、隔离、评分、复位；本次提供接入、权限配置隔离、原始记录与严格导出验收 |
| 并发 | 同一故障集群串行 attempt；Holmes 原生工具线程并发与 MCP 锁保留；镜像预加载并发 3。没有引入调度服务或队列 |
| 数据 | 每 attempt 原始 append JSONL + 文件；ATIF 与 SQLite 可重建；request ID、tool-call ID、session UUID 关联；评分与 agent 可见内容分开 |
| 失败与一致性 | 提交响应丢失不重放；host 官方结果最终裁定；数据失败不改任务得分；复位失败停止复用；SQLite 使用上游去重和事务 |
| 观测 | 关联 raw trace、driver、官方 phase 记录、模型 usage、provenance、独立 data-acceptance；区分环境、agent、judge、数据层结果 |
| 瓶颈 | 冷启动镜像和每轮遥测重建/复位比调查更慢；模型调用在调查耗时中占主要部分。工具耗时可并发，不能简单相加当作墙钟时间 |

开源 issue / merged PR 不属于本轮结果；没有重写后端或新增 REST/队列/独立数据库。

## 下一轮候选，按当前证据排序

1. **调查与停止策略**：NetworkPolicy 上 Stratus 与 Holmes 两轮均锚定已恢复的启动错误；Holmes 分别指向 rate、geo，而未验证持续网络故障。Social Network 的选择器故障能成功定位，说明工具与评分链路可用，但不证明策略普遍有效。可以比较证据新鲜度、当前业务症状确认、结束前反证检查；不能把已知 NetworkPolicy 答案写进通用 prompt。
2. **工具错误语义和恢复**：真实 MCP 返回 `Command Rejected`（管道禁用、资源 RBAC 拒绝），Holmes 外层仍记 `status=success`。可研究保留原始结果的错误归类、受限命令重写与恢复率，避免仅按外层 status 统计成功。
3. **上下文成本**：第二轮最后一次输入 47,404 token，11 次调用累计输入 254,857；可研究证据筛选、日志时间范围与结构化工作状态。当前没有压缩触发证据，不优先声称需要长期记忆或复杂摘要。
4. **环境生命周期**：两次热部署与复位合计各约 214 秒。可先分析遥测重建和就绪等待，讨论保留基础设施是否仍满足隔离与 benchmark 约束，再设计对照；不能直接跳过复位换取表面吞吐。
5. **用量完整性**：补齐 judge / classifier / 所有预检 usage，并引入有版本的价格表或账单核对。当前费用缺测是明确缺口，不采用零值兜底。

后续算法训练需要重新选择 tokenizer / chat template、建立独立故障族划分；这些 dev 轨迹不进入独立测试集。本轮未启动 SFT / RL。

## 文件与复现边界

入口说明：`README.md`；配置：`configs/`；可重建补丁：`patches/`，已在固定 base 的临时 Git index 上验证可应用。两个上游历史和开发分支保留，本轮没有创建远程仓库、推送或发布。

本地实际证据位于忽略的 `artifacts/pci-2/`，本轮下载 110 个证据文件：`native-evals.xml`、各运行日志、`results/` 下官方 CSV / raw / ATIF / SQLite、`trace-export/`、`results-audit.json`、`runtime-after-reset.json`、`provenance-*.json`。凭据扫描后下载，不纳入 Git。Linux 原始证据保留在 `~/sre-agent-project/artifacts/` 与 `repos/sregym/results/`。

成功样本文件：`artifacts/pci-2/results/0919_2021/holmes/wrong_service_selector_social_network/run_1/sft-format-samples.jsonl`。失败运行位于 `0919_1943/stratus/` 与 `0919_2011/holmes/`；全部保留，没有追加故障实验筛选好结果。

上游部分基础设施使用可变镜像 tag 或在线 Helm chart；实际 chart 版本和 37 个 image digest 另存 `configs/runtime-observed.json` 与 runtime snapshot。本轮能在保留缓存的节点复跑，但尚未把所有第三方 chart/blob 打包成完全离线、不可变的环境发行物。补丁基于固定代码版本，不能把它与完整环境供应链锁定混为一谈。
