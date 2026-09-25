# Harness 改进候选全集、排序与否决闸门

日期：2026-09-23

状态：计划。本轮没有启动 live campaign。离线实验 E1、E2 已经完成。从 E2b 开始，百炼 API 返回 `400 Arrearage`（账户欠费），实验中断。E2b–E10 按第 5 节的闸门补做，判定标准已在本文预先登记，登记时尚未看到这些实验的结果。

修订（2026-09-25）：百炼账户欠费后，用户指定后续全部改用 newapi 网关（OpenAI 兼容接口）上的 `glm-5.3-flash`，agent 与离线 judge 使用同一模型。G1 按第 5 节的"修订 v2"执行，修订内容在任何 glm 实验结果之前写入并提交。基于 qwen3.8-max 的历史结论和历史对照，适用范围随之调整，见第 1.7 节与 G3、G4。

范围：只改 Holmes 层和 driver 层。不修改 benchmark 的 MCP 服务、权限、故障注入或评分。本文是计划，不是结果报告。候选条目里的数字只用来描述问题证据或离线上界，不代表诊断提升。

依据：

- 冻结 campaign `diagnosis-20260921` 的 36 条有效 attempt（dev 24、validation 12）。原始轨迹位于被忽略的 `artifacts/pci-2/campaigns/diagnosis-20260921/`；已提交的审阅证据包是 `evidence/diagnosis-20260921/`。
- 固定上游：`repos/holmesgpt`（`3bd44ed` 加 `patches/holmesgpt.patch`）、`repos/sregym`（`46c853d` 加 `patches/sregym.patch`），包括 `tests/llm/fixtures/test_ask_holmes/`。
- 既有计划与报告：`docs/plans/2026-09-21-engineering-and-harness.md`、`docs/reports/2026-09-21-engineering-and-harness.md`、`docs/reports/2026-09-21-campaign-measurements.md`。
- 复算脚本和离线实验原始输出放在被忽略的 `artifacts/offline-20260923/`，包括 `load.py`、`facts.py`、`rep.py`、`judge_offline.py`、`noise.jsonl`、`e2.jsonl` 和 `prereg.md`。脚本只从环境变量或被忽略的密钥文件读取 API key，不把它写入任何输出。结果文件 SHA256：`noise.jsonl` 为 `b9f59b717f430a00…`，`e2.jsonl` 为 `c26718e9fe3947be…`。
- 需求要求删除 `docs/plans/2026-09-23-harness-direction.md`。该文件在所有分支、远端引用、历史和工作区中都不存在，也没有任何引用处，所以没有删除提交。检索过程见第 7 节。

## 1. 现状与已核实事实

### 1.1 口径

- 统计单位是 attempt。成功以官方 `Diagnosis.success` 为准，即 DiagnosisJudge 的 composite ≥ 0.70。D1、D2、D3 权重为 0.33/0.33/0.34。judge 为 `qwen3.8-max`，温度 0，thinking 关闭；agent 也使用同一模型。
- 36 条有效 attempt 编号为 1–39，其中 27、30、31 是 validation 的替代 attempt，不计入有效结果。
- 轨迹取自 `holmes.events.jsonl`，按 `event` 字段区分记录类型。工具结果取 `tool_end.result.result` 中的 `status`、`error`、`data`；评分取 `*_results.csv` 中的 `Diagnosis.*`。
- 字符数不等于 token 数。token 数只取 API 返回的 `usage`。

### 1.2 故障对象类（机制指标的依据）

故障对象类来自静态 `inject_fault` 实现，不来自 root_cause 文本。机制指标只按对象类（kind 或字段）定义，不使用具体对象名。

| 案例 | 注入实现 | 故障对象类 | 覆盖判据 |
|---|---|---|---|
| network_policy_block | `sregym/conductor/problems/network_policy_block.py:44` | NetworkPolicy：选中目标 Pod，Ingress 和 Egress 规则都为空 | 查询过 NetworkPolicy，并且输出中出现该对象 |
| namespace_memory_limit | `sregym/conductor/problems/namespace_memory_limit.py:168` | ResourceQuota（memory）；同时删除目标 ReplicaSet，迫使其重建 | 查询过 ResourceQuota，并且看到 quota 与 admission 拒绝 |
| wrong_service_selector_social_network | `sregym/generators/fault/inject_virtual.py:801` | Service.spec.selector：多出一个键 | 输出中出现 selector 的多余键 |
| readiness_probe_misconfiguration_social_network | `sregym/generators/fault/inject_virtual.py:1524` | Deployment readinessProbe：httpGet 指向不存在的端点 | 输出中出现 probe 配置或 probe 失败事件 |

### 1.3 失败分解

| 类别 | 条数 | attempt | 维度特征（官方 dimensions） |
|---|---:|---|---|
| 从未看到故障对象证据 | 12 | network_policy #2 4 5 6 7 11 12 14 15 17 21；service_selector #9 | network_policy 12/12 的 D2=0。其中 #7、#17、#21 的 D1=1.0，定位到受影响服务，但没有说出机制。#9 的 D1=1.0、D2=0 |
| 看到证据但归因错误 | 8 | network_policy #23；NML #26 29 34 36 37；readiness #32 39 | NML 失败 5/5 的 D1=0：把受害的 search deployment 写成故障源，同时又引用了 quota。readiness 失败的 D2 为 0 和 0.33，都归因于 otel-collector DNS。#23 拿到了 NetworkPolicy YAML，得分仍为 0 |
| 成功 | 16 | 其余 attempt | 16/16 都取得了证据 |

按故障类统计 kubectl 查询覆盖：

- network_policy：12 次中只有 1 次查询 NetworkPolicy。
- NML：ResourceQuota 6/6，LimitRange 6/6。
- service_selector：endpoints 10/12。
- readiness：events 6/6。

### 1.4 已核实事实表

| 事实 | 复核值 | 口径或来源 |
|---|---|---|
| 有效 attempt / 成功 | 36 / 16 | 官方 `Diagnosis.success` |
| network_policy 成功 | 0/12，四种配置各为 0/3 | 同上 |
| 工具调用 | 共 1,186 次：kubectl 718、get_logs 245、get_metrics 107、get_alerts 39、get_services 24、get_traces 24、get_dependency_graph 15、get_labels 12、get_operations 2。rollback_command、get_previous_rollbackable_cmd、get_label_values 均为 0 | tool_end |
| 工具输出字符 | 5,851,367；get_logs 4,480,050（76.6%），kubectl 1,223,543（20.9%） | `data` + `error` |
| 日志行 | 7,476 条结构化行，格式为 `[ts] [labels] body`。单次 get_logs 中位 14 行，最多 99 行。245 次中有 158 次已使用 LogQL 行过滤 | get_logs 输出 |
| 标签合并（无损） | get_logs 字符 −57.6%（4,480,050 → 1,898,627）。连续同标签合并与按流分组的结果相同 | 离线复算 |
| 标签合并 + 去 ANSI + 连续同模板折叠 | −84.6%（→ 689,815）；ANSI 转义占 1.2% | 离线复算 |
| 累计请求输入字符 | 62,634,658；其中 get_logs 消息占 55.7%。标签合并可减少累计输入字符 30.4%，按 attempt 取中位为 33.1% | 对全部 model_request 的 messages 求和；是字符，不是 token |
| Jaeger 与告警 | get_traces 返回 `[]` 22/24；get_dependency_graph 为空 15/15；get_services 返回 None 21/24；get_alerts 为 "No firing alerts" 26/39 | tool_end |
| 命令拒绝 | 共 118 次，平均 3.28 次/attempt，36 个 attempt 每个至少 1 次 | kubectl 结果以 `Command Rejected` 开头 |
| 拒绝分类 | 管道/shell 87（其中 "Pipe commands are forbidden" 65、"Unsupported operator kind: list" 22）；`get all` 17（RBAC 拒绝 replicationcontrollers，17/17 失败）；代理 502 共 6（全部是 `get limitrange`，NoneType）；API NotFound 3；隐藏对象 403 共 2（负载生成器 Pod 返回 HTML 403）；未知资源类型 2（servicemonitor、podmonitor）；容器 exec 失败 1 | 按错误原文分类 |
| 管道命令形态 | 87 条中单个 grep/findstr 33，head/tail 22，其他 32。65 次 Pipe 拒绝之后，只有 18 次在随后 3 次 kubectl 内重发了去掉管道的基础命令 | 启发式分类 |
| 恢复规则的误分类 | 在 recovery/combined 中：隐藏对象 403 被归为 permission_denied，提示"改查单独资源类型"；NotFound 被归为 command_rejected，并提示"不要视为应用资源故障"。#37（NML）中目标 search Pod 的 NotFound 恰恰是与故障相关的观测 | driver `recovery_rules()` |
| 重复调用被拒 | 25 次 | safeguards |
| 系统 prompt | 17,206 字符，36 次的哈希完全一致。其中 TodoWrite 章节 1,614 字符，user 消息里的 TodoWrite 提醒出现 36/36 次，但工具目录中没有 TodoWrite。prompt 中还有要求询问用户的句子；"Disabled & failed Toolsets" 章节 5,267 字符，占 30.6%；并引用了不存在的 `kubectl_describe` 和 `fetch_finding_by_id` | 首个 model_request |
| 幻影引用的实际影响 | 调用目录外工具 0 次；assistant 文本提及 TodoWrite 0 次 | model_response |
| 时间 | 当前 UTC 时间写在首条 user 消息中（TIME_SKILLS 组件），不在系统 prompt 中 | 首个 model_request |
| 工具 schema | 12 个工具，共 5,851 字符。kubectl 工具描述来自 MCP 服务端，没有任何限制说明 | 同上 |
| spill | 阈值为 min(15% × 上下文, 25,000 token)。单次工具结果最大 75,591 字符（约 19k token），从未触发。落盘后的指针提示用 `cat` 读取，这需要 bash，而 bash 已禁用 | `tool_context_window_limiter.py:100` |
| 上下文压缩 | 阈值为 200k 的 95%。每个 episode 的最大 prompt 中位 75.5k、最大 154.4k，从未触发；成功者中位 84.2k，失败者中位 72.3k | usage.prompt_tokens |
| 缓存 | 输入 23,430,038 token，其中缓存 20,712,064（88.4%）；输出 130,387 | usage |
| 步数 | 模型调用中位 15、最大 27，上限 30，从未耗尽；工具调用中位 31 | model_request |
| 调查时长 | 首工具到末工具中位 67.3 s；tool_catalog 到 agent_final 中位 81.9 s | 时间戳 |
| 墙钟分布 | deploy 含重试约 56.2%，cleanup 约 21.5%，stage:diagnosis 18.9%，evaluate 1.8%；平均每 attempt 约 493 s | csv `phase.*` |
| 重复一致性 | 12 个（配置, 案例）单元中有 4 个结果不一致；36 对重复中 8 对不一致（22%）。pass@1 为 16/36；单元内至少一次成功 7/12 | 官方结果 |
| 最终答案 | 中位 2,300 字符。33/36 含诊断、根因或总结标题；10/36 以调查过程语句开头，其中 7 条失败 | `Diagnosis.submission` |
| 背景噪声关键词 | 结论最后 1,500 字符中提到 consul、otel、DNS、wrk2 或 jaeger：失败 20/20，成功 13/16，无法区分成败 | 关键词统计 |
| managedFields | 86 次 `-o yaml` 输出中 0 次包含 managedFields；23 次包含 last-applied-configuration | tool 输出 |
| 证据包哈希 | `manifest.json` 中的 SHA256 等于 Windows 工作区 CRLF 字节的哈希，而不是 git 中 LF blob 的哈希（`attempts.jsonl`、`prompt.txt` 两个文件都是如此） | 本地复算 |

### 1.5 与给定事实的差异

其余给定事实与复核值一致或在上表中已给出，只有三项存在差异：

| 事实 | 给定 | 复核 | 原因 |
|---|---|---|---|
| 从未看到证据的失败 | 12 | 若严格按"从未查询故障对象"统计，为 11，全部是 network_policy。若把 #9 计为未看到（它查询了 Service，但输出中从未出现 selector 的多余键），则为 12 | 定义不同。本文采用 12 = 11 + #9 |
| get_logs 占工具输出字符 | 76.8% | 76.6%（4,480,050 / 5,851,367） | 统计口径不同 |
| 标签合并节省 | 54.5% | 57.6% | 合并方法不同。本文报告 57.6%，方法是去掉每行重复的 `[labels]` 前缀，只在标签变化时写一次 |

### 1.6 已完成的离线实验

**E1：judge 噪声底。** 用 SREGym `judge.py` 的 DiagnosisJudge 原码（prompt、checklist、解析、计分都不变）对 36 份原提交各重评 5 次，共 180 次。只把 LangChain 后端替换为直连百炼 OpenAI 兼容接口，参数保持温度 0、max_tokens 4096、thinking 关闭。

- 与官方判定一致：170/180（94.4%）。composite 与官方完全相同：150/180（83.3%）。
- 5 次重评内部判定不稳定的条目有 2/36；如果把官方判定也算进去，是 3/36（#34、#35、#37），全部是 NML。其余 30 条非 NML 条目没有任何判定翻转。
- 条目内 composite 标准差平均为 0.017，最大极差为 0.34。问题级答案不稳定的比例是 17/324，集中在 D3-Q2（6）和 D1-Q2（3）。
- NML 按多数重评算是 3/6 成功，官方是 1/6。分组看：baseline 从官方 1/3 变为 2/3，combined 从 0/3 变为 1/3。
- 结论：NML 的判定由 judge 噪声主导，不能用单次判定对 NML 下结论。其余三类的判定稳定。
- 局限：离线后端路径与 live 并非逐字节相同。原判定与离线重评之间的差异混合了路径差异和采样噪声；离线内部的不稳定率（2/36）才是采样噪声的下界。

**E2：逐字最后一步重放。** 把原始最后一次请求逐字重发，包括全部消息、12 个工具 schema、温度 1e-8 和 thinking 关闭。每个 attempt 发 5 次，共 180 次，每个答案用离线 judge 评一次。

- API 错误 0 次。以 `stop` 收口的有 149/180（82.8%）。其余 31 次选择继续调用工具：network_policy 20、selector 5、readiness 5、NML 1。#2 和 #8 在 5 次中都没有收口。
- 149 份答案中，与原答案逐字相同的为 0 份。
- `stop` 样本的判定与官方一致：143/149（96.0%）。排除 2 个从未收口的 attempt 后，多数判定一致 34/34。发生翻转的只有 NML：#29 为 2/5 成功，#35 为 3/5，#37 为 2/4。
- 5 次中至少一次成功的 attempt 有 17 个，官方是 16 个。多出来的是 #29（NML）。
- 最后一步 prompt token 的中位数是 75,158。
- 结论：在给定上下文时，最后一步的判定对非 NML 类是稳定的。所以方差主要来自轨迹，而不是来自最后一步的措辞。据此，"只改最后一步"的候选（F1、F2、A2）可以用最后一步重放可靠否决；"改变证据获取"的候选必须依靠注入探针或 live。
- 局限：这次重放保留了工具，因此 17% 的样本没有收口。强制收口的对照组 E2b 因 API 欠费没有完成，已列入闸门 G1。

**工具可重放性（不需要 API）。** 在同一案例的不同 attempt 中，找出 (工具, 参数) 完全相同的调用：

- 这样的键有 164 个。原始输出完全相同的只有 59 个（36.0%）；把时间戳、ID 和数字归一化后，相同的是 89 个（54.3%）。
- 1,186 次调用中，有 680 次（57.3%）能在同案例的其他 attempt 中找到参数完全相同的调用。
- 结论：跨 attempt 的工具缓存至少有 42.7% 的调用级未命中，而且命中的结果也常常不是逐字相同。多步离线评测只能在单条轨迹内部录制回放，一旦偏离就算未命中。未命中率由 E9 正式测量。

### 1.7 统计功效

以下均为单侧 Fisher 精确检验，按 attempt 计：

| 设计 | 处理组需要的成功数 | p |
|---|---|---|
| network_policy：n=6 对历史 0/12 | ≥3/6 | 0.0245（2/6 为 0.098） |
| network_policy：n=6 对历史 0/12 加新 baseline 0/3（合并 0/15） | ≥3/6 | 0.015（2/6 为 0.071） |
| network_policy：n=6 对同期 0/6 | ≥4/6 | 0.030 |
| NML：对照 1/6 | n=6 时 ≥5/6；n=12 时 ≥9/12 | 0.040；0.032 |

- 功效：n=6、阈值 3/6 时，真实成功率为 30% / 50% / 70% 的检出概率分别是 0.26 / 0.66 / 0.93。n=12 对 0/12、阈值 4/12 时，真实率 50% 的功效是 0.93。
- 中等基线类的样本量：若要以 80% 功效检出 50% → 80%，每臂需要 36 次；检出 33% → 83%，每臂需要 15 次。当前预算做不到，所以结果类结论只在 floor 类（network_policy）上做，其他类只报告机制指标和描述统计。
- 噪声的影响：非 NML 类的 judge 噪声和最后一步噪声都接近 0，可以用单次判定。NML 必须每个答案重评 3–5 次取多数或均值，不做显著性宣称。
- 模型切换的影响（2026-09-25）：上表的历史对照（network_policy 0/12）来自 qwen3.8-max agent，不适用于 glm-5.3-flash agent。live 对照改为 glm 下的同期对照，见 G3、G4 修订。E1、E2 的噪声数字只描述 qwen judge 与 qwen agent；glm 的噪声底由 E1g、E2b 重新测量。

## 2. 已确定工程项

本节各项都是按构造成立的工程改动，一律标为"工程项"，不宣称带来诊断提升。验收只看构造正确性和机制指标。

### 工程项 1：修正 baseline（prompt 卫生、工具约束说明、时间、渲染检查、重跑 baseline）

- **证据**：
  - 36/36 次的 prompt 都渲染了 TodoWrite 指令和提醒，以及询问用户的句子，但目录中没有这些工具。
  - 系统 prompt 引用了不存在的 `kubectl_describe` 和 `fetch_finding_by_id`。
  - kubectl 工具描述中没有限制说明；管道/shell 与 `get all` 类拒绝合计 104 次，平均 2.89 次/attempt。
  - 时间目前在首条 user 消息中；系统 prompt 在 36 次中的哈希完全一致。
- **实现**：
  - `repos/sregym/clients/holmes/driver.py:192` 调用 `build_initial_ask_messages` 时传入 `prompt_component_overrides={TODOWRITE_INSTRUCTIONS: False, TODOWRITE_REMINDER: False, ASK_USER: False}`。组件定义见 `holmes/core/prompt.py:13`。
  - 在 `holmes/plugins/prompts/generic_ask.jinja2` 中，让引用 `kubectl_describe` 和 `fetch_finding_by_id` 的句子以对应工具存在为条件。这个模板已有同类条件写法，改动可提交上游。
  - kubectl 限制写进工具描述：MCP toolset 配置（`toolset_mcp.py:152`，与 `content_error_rules` 同一层）增加按工具名的描述后缀。`RemoteMCPTool.create`（`toolset_mcp.py:706`）目前直接用服务端描述，需要在这里拼接后缀。driver 只为 `sregym_kubectl` 设置，内容是：只执行一条 kubectl；拒绝 shell 运算符；`get all` 会被 RBAC 拒绝；可改用 `-l`、`--field-selector`、`-o jsonpath`、`-o name`、`--tail`、`--since`。
  - 时间：继续放在首条 user 消息中，不改写系统 prompt。另外在工具结果头（`holmes/core/models.py:104` 的 "Params used for the tool call" 一行）追加 `observed_at=<UTC>`。这只影响新追加的消息，历史仍然只追加，不影响前缀缓存。
- **渲染检查**：以 driver 相同的 overrides 和只含 12 个 SREGym 工具的替身 tool_executor 渲染 prompt，然后断言：
  - 渲染文本中出现的所有已知内置工具名（取自 `load_builtin_toolsets()` 的全部工具名，加上 TodoWrite、fetch_skill 等）都属于已启用的工具集合；
  - spill 指针等运行期提示文本也受同一检查约束（当前指针要求 `cat`，依赖未启用的 bash，只要触发就会失败）；
  - 同一配置两次渲染的系统 prompt 哈希相同。
  - 该检查放在 Holmes 补丁测试中；同时在 `scripts/audit_results.py` 里对每个 live attempt 的首个 model_request 复检。
- **验收**：离线测试全部通过，首个 model_request 不再含上述文本，工具 schema 中出现约束后缀。G3 重跑 fresh baseline（baseline-v2），报告每 attempt 被拒命令数、token 和缓存命中率，不报告诊断提升。

### 工程项 2：kubectl 错误分类，按真实原因区分

| 类别 | 真实原文（节选） | 当前处理 | 新处理 |
|---|---|---|---|
| NotFound | `Error from server (NotFound): pods "…" not found` | recovery 中归为 command_rejected，并提示"不要视为应用资源故障" | 作为观测返回（SUCCESS），写明对象不存在；对象不存在本身可能就是证据（#37） |
| 未知资源类型 | `error: the server doesn't have a resource type "servicemonitor"` | 通用拒绝 | 归为 `unknown_resource_type`，说明该 kind 不在此集群中，不要重试 |
| 代理 502 | `Error from server (InternalError) … Error code: 502 … Bad Gateway: 'NoneType' object is not iterable` | 通用拒绝 | 归为 `environment_proxy_error`，说明这是环境故障，不是应用证据 |
| 隐藏对象 403 | `Error from server (Forbidden): <!DOCTYPE HTML> … Error code: 403 … Access to this resource is not allowed` | 归为 permission_denied，提示改查单独资源类型（有误导性） | 归为 `hidden_resource`，说明该对象在调查范围之外 |

- **实现**：扩展 `driver.py:25` 的 `recovery_rules()`，并按需扩展 `toolset_mcp.py` 中 ContentErrorRule 的匹配能力（前缀或包含、大小写、是否作为 SUCCESS 返回）。规则顺序固定：NotFound 优先于 "forbidden" 的包含匹配。
- **验收**：用上表 4 类真实原文和 118 条历史拒绝写单元测试，要求分类结果与第 1.4 节完全一致。机制指标：同类错误后重复发出同一命令的比例。
- **边界**：只改 Holmes 层的结果语义，不自动重放命令，不改 benchmark 权限。

### 工程项 3：修复代理空列表崩溃（向 SREGym 上游提交）

- **证据**：6 次 `kubectl get limitrange`（表格输出）全部返回 502 NoneType；同一资源用 `-o yaml` 时 4 次都返回 `items: []`。
- **原因**：`sregym/service/k8s_proxy.py` 中 `_filter_namespace_list`（约第 173 行）和 `_filter_resource_list`（约第 189 行）对 `data["items"]` 与 `data["rows"]` 直接迭代，值为 null 时抛出异常。
- **实现**：改为 `data.get("items") or []`，`rows` 同样处理，并向上游提交 PR。合并之前，本地补丁对所有配置同时生效，并登记为环境变更，写入 `configs/runtime-observed.json` 和报告。本项不属于 harness 改动。
- **验收**：单元测试覆盖 items 为 null 和 Table rows 为 null 两种情况；G2 在集群上确认空 limitrange 返回 "No resources found"。

### 工程项 4：日志观测压缩

- **证据**：get_logs 占工具输出字符 76.6%，占累计请求输入字符 55.7%。每行都重复写一遍标签前缀，标签合并即可无损节省 57.6%。
- **位置**：Holmes 结果转换层。在 `holmes/core/transformers/` 注册确定性 transformer（例如 `loki_log_compact`），同时让 `RemoteMCPTool.create` 能接收来自 toolset 配置的 transformers（当前不传）。也可以放在 `RemoteMCPTool._invoke`（`toolset_mcp.py:439`）中与 content_error_rules 同一层。只对 get_logs 生效；解析失败时原样放行并计数。
- **第一级**：在插入时变换，历史只追加。
  - 先做无损标签合并：同一流的标签只在变化时写一次，行内保留原时间戳。
  - 再做连续同模板折叠：同一流中连续 ≥3 行模板相同（时间戳、UUID、IP、数字已掩码）时，保留首行和末行原文，写出行数和时间范围；去掉 ANSI 转义。
  - 离线测得节省：只做标签合并为 57.6%，全部完成为 84.6%。
- **第二级**：旧观测 masking，仅在批次边界进行（见 C1），不在每步改写历史。
- **不做**：不改 spill 阈值，不启用 bash。
- **验收**：
  - 在 245 份历史 get_logs 上，标签合并可以逐字节还原；
  - 折叠后，原文中每一种模板至少保留一行；
  - E6 最后一步重放非劣；
  - G2 中原生 context_window 标签的 21 个案例非劣；
  - G3 报告每 attempt 的输入 token 与缓存命中率。只作为成本项，不作为诊断提升。

### 工程项 5：离线反事实评测

- **组成**：
  - 任意第 k 步的切点重放：逐字重建第 k 次请求，可以追加观测、改最后一步说明，或强制收口；
  - 工具录制回放：按 (工具, 参数) 精确匹配，并报告未命中率；
  - 离线 judge：使用 SREGym judge 原码，只替换后端；
  - 缓存/成本计算器：从 usage 统计输入、缓存和输出，按可配置的价格与缓存折扣计算；没有账单时费用仍记为未知。
- **位置**：根仓库 `scripts/offline/`。把 `artifacts/offline-20260923/` 中的原型代码化，带记录夹具的测试进入 CI，测试中不调用 API。
- **有效性优先**：
  1. 逐字重放的保真度：E2 已测，`stop` 样本判定一致率 96.0%，多数判定一致 34/34；E2b 待测。
  2. judge 噪声底：E1 已测，一致率 94.4%，NML 3/6 条目不稳定。
  3. 原生 eval grader 的噪声底单独测量：G2 中对同一输出重评 5 次。
  4. 工具回放未命中率：E9。
- **验收**：每个离线结论都附上对应的保真度和噪声底。离线上界不写成诊断提升。

### 工程项 6：机制指标抽取器

- **指标**：
  - 证据覆盖：是否查询过故障对象类，以及该对象是否出现在输出中；
  - 给定覆盖时的归因：已看到证据的 attempt 中，答案是否把该对象类写成故障源（判定独立于 judge）；
  - 工具错误分布：使用工程项 2 的类别。
- **来源**：故障对象类取自第 1.2 节的静态实现映射（带 file:line）。registry 映射变化时，测试必须失败。
- **位置**：`scripts/mechanism_metrics.py`（新增）与对应测试。
- **验收**：在 `diagnosis-20260921` 上精确复现第 1.3、1.4 节的数字，包括 12/8/16 的分解、118 次拒绝及分类。

### 工程项 7：环境复用

- **证据**：deploy 约占 56.2%，cleanup 约占 21.5%，诊断阶段只占 18.9%，平均每 attempt 约 493 s。
- **流程**：inject → diagnose → 调用 benchmark 自身的 `recover_fault` → 对 namespace 做规格哈希（去掉 status 和易变元数据）→ 健康检查（全部 Deployment Ready）。哈希一致且健康检查通过后，才进入下一题；否则回到完整重建。
- **位置**：`scripts/campaign.py` 增加复用模式，调用 SREGym 已有的 problem 接口，不改注入或恢复代码。
- **验收**：先在 G2 做 A/A：同一配置下 fresh 部署与复用各 3 次（service_selector），每次复用前规格哈希一致，成功与机制指标的方向没有差异，之后才能在 G3 及以后使用。每 attempt 墙钟的变化只作为吞吐指标报告。

### 工程项 8：统计

- 功效由实测噪声计算，见第 1.7 节。
- 结果按故障类报告，不跨类合并成一个总成功率。
- holdout 按故障类隔离，见 G5，只导出汇总（`export_campaign_evidence.py --sealed`）。
- **位置**：`scripts/report_campaign.py` 与新的统计模块。
- **验收**：报告中每个比较都附 n、成功数、单侧 Fisher p 和预先登记的阈值。未达阈值时写"未观察到显著差异"。

### 工程项 9：证据哈希

- **证据**：已提交的 `manifest.json` 中的哈希对应 Windows 工作区的 CRLF 字节，与 git 中 LF blob 的哈希不同。干净的 Linux checkout 无法复算出相同结果。
- **实现**：
  - `scripts/export_campaign_evidence.py`（约第 387–449 行）所有写文件处加 `newline="\n"`；
  - `.gitattributes` 固定 `evidence/** text eol=lf`；
  - CI 在干净 checkout 上重算 manifest 哈希；
  - 用新的提交重新生成 manifest，不改写历史。
- **验收**：CI 中复算结果与 manifest 一致，并且在 Windows 与 Linux 上导出的字节相同。

## 3. 候选全集（按层）

字段约定：问题证据 / 改动与位置 / 可能有效 / 可能无效 / 指标（机制、结果、测试面）/ 最快否决 / 淘汰条件 / live 设计 / 简历权重、可行性与关联。标为"工程项"的条目按构造成立，不做结果宣称。实验编号 E* 的定义见第 5 节的预先登记。

### 3.0 能力盘点

**Holmes 已有但关闭或未使用的能力**

| 能力 | 位置 | 当前状态 | 本文处理 |
|---|---|---|---|
| TodoWrite（core_investigation） | `plugins/toolsets/investigator/core_investigation.py` | toolset 被禁用，但指令和提醒仍在渲染 | 工程项 1 关闭相关文本；L2 作为对照臂 |
| 询问用户指令 | `generic_ask.jinja2` 中的 `ask_user_enabled` | `build_initial_ask_messages` 把它固定为 True | 工程项 1 关闭 |
| prompt_component_overrides / ENABLED_PROMPTS | `core/prompt.py:13`、`:90` | 未使用 | 工程项 1 |
| skills（fetch_skill、custom_skill_paths） | `plugins/skills/`、skills toolset | 关闭，内置 skills 目录为空 | S1、S2 |
| skill 建议记忆（frontend SuggestSkills；评测字段 `memories_generated`、`rerun_with_memory`） | `tests/llm/utils/test_case_utils.py:164` | 服务端 frontend tool，未接入 | M2（暂缓） |
| Tool transformers（内置只有 llm_summarize） | `core/transformers/`、`core/tools.py:429`（只对 SUCCESS 结果生效） | MCP 工具不传 transformers | 工程项 4 使用确定性变换；不做 llm_summarize |
| MCP content_error_rules（本项目补丁） | `toolset_mcp.py:152` | 只在 recovery/combined 中启用 | 工程项 2 |
| response_format（结构化输出） | LLM 调用参数 | None | F1 的可选形态 |
| 大结果落盘（spill） | `core/tools_utils/tool_context_window_limiter.py` | 开启，但从未触发；指针依赖 bash | 不改阈值，不开 bash；指针文本纳入工程项 1 的检查 |
| 上下文压缩 | `core/truncation/input_context_window_limiter.py:82` | 95% 阈值，从未触发 | 不调低（见第 7 节） |
| 重复调用保护 | `core/safeguards.py:24` | 开启，25 次拒绝 | L4（低优先） |
| diagnosis review（本项目补丁） | `core/diagnosis_review.py` | 推荐配置中关闭 | 已淘汰 |
| bash、kubernetes/core、connectivity_check、internet 等内置 toolset | `plugins/toolsets/` | 关闭 | 保持关闭：打开会绕过 benchmark 的过滤代理，或违反约束 |
| JsonFilterMixin（jq 参数） | `plugins/toolsets/json_filter_mixin.py` | 由环境变量控制，只作用于内置工具 | 不适用于 MCP 工具 |
| 子 agent | — | Holmes 没有这项能力 | 只能在 driver 层编排（A1、A2） |

**SREGym 接口允许与限制**

| 接口 | 事实 | 对 harness 的含义 |
|---|---|---|
| `/get_app` | 返回 app_name、namespaces、descriptions | driver 只使用这三项，不读取 problem ID 或 root_cause |
| `/submit` | 每个 attempt 只能提交一次 | 即使跑多条轨迹，driver 也只能提交一份答案 |
| `exec_kubectl_cmd_safely` | 只执行单条 kubectl，拒绝 shell 运算符；权限是 SA `sregym:mcp-server` 的 RBAC；过滤代理隐藏 benchmark 自身的 namespace 和带隐藏标签的对象 | 可以使用原生过滤参数；`get all` 必然失败；负载生成器对象返回 403 |
| rollback_command / get_previous_rollbackable_cmd | 可回滚已执行的命令 | 诊断阶段用不到，历史调用 0 次（T5） |
| Prometheus、Loki、Jaeger | 允许 LogQL 行过滤；Jaeger 数据几乎全空 | 日志体积主要来自标签前缀（工程项 4）；Jaeger 空结果见 T6 |
| 评分 | DiagnosisJudge 9 问 checklist：D1 定位、D2 机制、D3 范围 | 机制指标必须独立于 judge（第 1.2 节） |

### 3.1 Prompt 层

**P1 基线 prompt 卫生（工程项，即工程项 1）**：见第 2 节。

**P2 精简 "Disabled & failed Toolsets" 列表（工程项，建议新增）**

- 问题证据：该列表占系统 prompt 的 30.6%（5,267 字符），只列出不可用的 toolset。
- 改动与位置：在 `_toolsets_instructions.jinja2` 中加一个开关，关闭已禁用 toolset 列表的渲染，由 driver 打开这个开关。
- 预期：按构造，系统 prompt 减少约 5.3k 字符。这部分大多命中缓存，所以只是成本项。
- 风险：模型不再知道某些工具已被禁用；对照历史，模型从未尝试调用目录外工具。
- 验收：工程项 1 的渲染检查；G3 中只报告 token 变化。
- 权重：低。

**P3 全程 RCA 原则（system_prompt_additions）**

- 问题证据：8 条归因错误。失败答案的共性是把受害组件，或更早出现且更显眼的错误，当成根因。
- 改动与位置：通过 `build_initial_ask_messages(..., system_prompt_additions=...)` 加入通用原则：区分导致异常的配置对象与受害工作负载；机制要有工具输出支持；用时间戳区分持续错误与已恢复的启动错误。
- 可能有效：原则在调查过程中就起作用，不只影响最后一步。
- 可能无效：已淘汰的 review 使用了相近的"时间戳与反证"措辞，没有带来提分。原则性文字的依从度难以观测。
- 指标：机制指标同 F1；另测下一步动作中查看配置对象的比例。
- 最快否决：作为 E4 和 E8 的"常驻"臂一并测量，不单独立项。
- 淘汰条件：与 F1、S2 共用。
- live 设计：不单独开臂。
- 权重：低中。可行性：高。

### 3.2 工具接口层

**T1 kubectl 错误分类（工程项，即工程项 2）。T2 kubectl 限制写入工具描述（工程项，属于工程项 1）。** 见第 2 节。

**T3 管道命令在客户端透明过滤**

- 问题证据：管道/shell 拒绝 87 次，占全部拒绝的 73.7%；其中单个 grep/findstr 33 次、head/tail 22 次，合计 55/87（63%）可以机械转换。65 次 Pipe 拒绝后，只有 18 次重发了基础命令，说明模型常常直接放弃这条信息需求。
- 改动与位置：在 `RemoteMCPTool._invoke` 前加钩子，由 toolset 配置开关，driver 只为 kubectl 开启。只识别 `kubectl … | grep [-i] 模式` 和 `| head/tail -n N`：通过 MCP 执行 kubectl 部分，权限不变；在本地过滤结果；在结果头写明"已执行 `<kubectl 部分>`，在客户端应用了 grep/head 过滤，没有执行 shell"。其他形态仍然拒绝。
- 可能有效：减少无效步骤，拿到本来会放弃的信息。
- 可能无效：拒绝在成功 attempt 中同样普遍，结果层面可能没有变化；如果 T2 已经足够让模型不写管道，T3 就多余。
- 约束检查：MCP 服务和权限不变，执行的命令与模型可以直接执行的相同；这是透明改写，要作为 harness 改动登记。
- 指标：机制指标为每 attempt 被拒数（当前 3.28，其中管道 2.42）和因拒绝浪费的步数；不宣称结果；测试面为用 87 条历史命令做的单元测试。
- 最快否决：先看 G3 中 T2 的效果（预先登记）。
- 淘汰条件：若 baseline-v2 中管道类拒绝下降 ≥70%，T3 不做。
- live 设计：不单独开臂，随 baseline 的后续版本一起测机制指标。
- 权重：低中；可行性：高；关联：工具网关、命令沙箱与改写（后端）。

**T4 命名空间对象清单**（T4a 为暴露给模型的工具，T4b 为开局由 harness 注入）

- 问题证据：12 条"从未看到证据"是最大的失败类别；network_policy 只有 1/12 查询了 NetworkPolicy。模型的 kubectl 查询集中在 pods、svc、deployment、events、endpoints；`get all` 尝试了 17 次，全部被拒，即使成功也不含策略类对象。
- 改动与位置：
  - 通用清单的做法：`kubectl api-resources --namespaced=true --verbs=list -o name` 得到全部可列出的 namespaced kind，再逐个 `kubectl get <kind> -n <ns> -o name`。只返回非空 kind 的计数和名字，不返回 spec、annotations 或 managedFields。被 403 隐藏的对象视为超出范围，直接剔除。
  - T4b 在 `driver.py` 的 `agent.call` 之前，通过 `agent.tool_executor` 调用同一个 MCP kubectl 工具，把结果追加到首条 user 消息。
  - T4a 是 Holmes 层的组合工具。
  - 不按故障类挑选 kind。
- 依赖：
  - 工程项 3：修复前，空列表在表格路径上会返回 502；`-o name` 路径需要在 G2 验证。
  - `kubectl api-resources` 是否被允许尚未验证：历史上唯一一次调用带了管道。若不允许，退而使用 Kubernetes 内置 namespaced kind 的完整清单，仍然不按故障挑选。
- 可能有效：覆盖按构造达到 100%。如果 E3 显示"看到即可归因"，这就是 network_policy 的直接杠杆。
- 可能无效：
  - #23 看到了 YAML 仍然归因错误，覆盖可能不够。
  - 清单会给上下文加噪声，模型可能继续被日志牵着走。
  - 注入对象的名字本身带有提示性，外部效度要看 holdout。
- 泄漏审计：清单只包含 kind 和名字，不读 managedFields、注解，也不读 benchmark 自身对象（由代理隐藏）。输出来自集群现状，与模型直接调用 kubectl 能看到的一致。
- 指标：机制为故障对象类的覆盖率（T4b 按构造为 100%），以及给定覆盖时的归因率；结果为 network_policy 成功数；测试面为 holdout 故障类。
- 最快否决：
  - E3 预言探针：在最后一步注入真实的 NetworkPolicy 观测；
  - E3b：E3 加上 F1 的答案契约；
  - E3c：只注入名字清单，看下一步动作是否去取该对象；
  - G2 的权限探测。
- 淘汰条件：
  - E3 和 E3b 在 11 条"未看到证据"的 network_policy attempt 上多数成功都 <6/11，则整个覆盖类候选（T4、S1、L1）暂停；
  - E3c 中下一步取回该对象的 <6/11，则 T4a 淘汰，只保留 T4b；
  - live 中成功 ≤1/6 则淘汰。
- live 设计：G4 中 network_policy 做 6 次。≥3/6 时，对合并对照 0/15 的 p=0.015（对历史 0/12 为 0.0245）。2/6 视为不显著，停止，不补做。selector、readiness、NML 各做 3 次，只做非回退的描述统计。
- 权重：高（工具设计、上下文注入、在 floor 类上验证）；可行性：中；关联：K8s discovery/聚合 API（后端），RL 的动作空间与观测设计。

**T5 诊断阶段移除回滚类工具（工程项，建议新增）**

- 问题证据：rollback_command 和 get_previous_rollbackable_cmd 调用 0 次；诊断阶段本就不该修改集群。
- 改动与位置：在 driver 的 `create_agent` 之后，从 tool_executor 中剔除这两个工具，并在启用工具检查中登记。MCP 服务不做任何改动。
- 预期：按构造减少 2 个 schema，并去掉误改集群的可能。结果不变。
- 权重：低。

**T6 空结果显式标注**

- 问题证据：Jaeger 相关的 63 次调用（占全部调用的 5.3%）几乎都没有数据：traces 22/24、依赖图 15/15、services 21/24 为空。
- 改动与位置：用 transformer 把空结果改写为"查询 X 在窗口 Y 内没有返回数据"，不删除工具。
- 预期：机制上减少重复的空查询。结果预期为 0。
- 权重：低；只作为低优先级工程项。

### 3.3 观测处理层

**O1 日志观测压缩（工程项，即工程项 4）。O2 工具结果的观测时间（工程项，属于工程项 1）。** 见第 2 节。

### 3.4 上下文管理层

**C1 旧观测分批 masking（工程项 4 的第二级，有条件实施）**

- 问题证据：上下文从未接近窗口（最大 154.4k，从未触发压缩）；失败 attempt 的上下文反而更短（中位 72.3k，成功者 84.2k）。
- 改动与位置：在 `tool_calling_llm` 中每 N 步按批次，把早于 K 步的 get_logs 结果替换为摘要行，摘要行包含参数、行数、时间范围和错误模板计数。批内历史只追加。
- 可能有效：降低长 episode 的成本和时延。
- 可能无效：关键证据被遮掉；每次按批次改写都会让一次前缀缓存失效。
- 指标：token 与缓存命中率；结果只要求非劣。
- 最快否决：最后一步重放时遮掉 K 步以前的观测，检查非劣。
- 淘汰条件：原成功 attempt 中有任何一条多数判定翻转。
- 启动条件：工程项 4 第一级上线后，若 G3 中仍有 >10% 的 attempt 最大 prompt 超过 60% 窗口，才进入实施。
- 权重：低；可行性：中。

**C2 证据台账**

- 问题证据：8 条归因错误。答案会把后出现、更显眼的日志错误当成根因。
- 改动与位置：Holmes 层在每次工具返回后，确定性地抽取结构化异常，写成台账，每 N 步以一条追加消息附上，历史只追加。抽取内容包括：非 Running/NotReady 对象、Warning 事件、无 endpoints 的 Service、被拒命令，以及已检查和未检查的 namespaced kind。位置在 `tool_calling_llm` 的工具返回之后。
- 可能有效：提高结构性异常的显著度，也能暴露覆盖缺口。
- 可能无效：启发式抽取带有环境特异性；可能放大红鲱鱼，例如 otel DNS 的 Warning。
- 指标：给定覆盖时的归因率。
- 最快否决：在最后一步注入台账并重放（36 × 5）。
- 淘汰条件：与 E4 相同。只有最后一步版本通过时，才在 live 中测逐步版本。
- live 设计：与 T4 同一设计，但只在 E 系列通过时才开臂。
- 权重：中（context engineering）；可行性：中。

### 3.5 记忆层

**M1 环境级工具使用记忆**：例如"管道被拒""`get all` 被拒"。这些是工具的稳定属性，已并入工程项 1 的工具描述，不作为跨 episode 记忆单独实现。

**M2 skill 建议记忆（Holmes 原生 SuggestSkills → SKILL.md → 下次按需获取），暂缓**

- 问题证据：每个 attempt 都会重复踩同样的坑，但故障层面的教训来自同一批故障类。
- 风险：从 dev episode 生成的记忆极易带入对象名和 root_cause 用词，等于在测试集上学习。
- 允许的形态：只从训练故障类生成；生成后做泄漏审计；只在按故障类隔离的 holdout 上评测。原生 eval 271–280 可以作为机制的测试面。
- 启动条件：S1 在 live 中通过之后。M2 是 S1 内容的自动生产管线。
- 权重：高（自我改进的 skills）；当前可行性：低。

### 3.6 Skills 层

**S1 通用 K8s 排障 skill（fetch_skill 按需获取）；S2 同样内容常驻（system_prompt_additions，作为对照臂）**

- 问题证据：12 条未看到证据、8 条归因错误；Holmes skills 能力关闭，内置 skills 目录为空。
- 改动与位置：
  - 新增 `configs/holmes-skills/` 下 1–2 份 SKILL.md。内容是通用流程：列出全部 namespaced 对象，逐个检查会选中或约束受影响工作负载的对象的 spec；区分触发对象与受害者；用时间戳区分持续错误与启动错误。
  - driver 的 `Config` 中设置 `custom_skill_paths`，启用 skills toolset，同步更新启用工具的白名单检查。
- 泄漏审计：`scripts/leakage_audit.py` 自动检查以下几项，不通过就不运行：
  - 全部约 120 个 registry 题目 ID；
  - 全部静态注入实现中的字符串字面量，例如对象名、标签键值、探针路径和端口；
  - 与任一题目 root_cause 描述的 4-gram 重合；
  - managedFields 与注入器注解的键。
  - kind 名只能以"全部 namespaced kind"的通用形式出现，不能按故障类挑选或排序。
- 可能有效：同一份内容同时作用于覆盖和归因；这是 Holmes 原生机制，改动面小。
- 可能无效：模板要求"只在明确匹配时才获取"，依从性不确定；network_policy 的症状（日志里的超时，Pod 都 Running）未必"明确匹配"。
- 指标：机制为 skill 获取率、覆盖率和归因率；结果为 network_policy 成功数；测试面为原生 skills 标签的 30 例（用同一 fixture 只切换 skills toolset，取代 84 与 176 这种不同 fixture 的对比）。
- 最快否决：E8，即 next-action 探针，比较 baseline、S1、S2 三臂。
- 淘汰条件：S1 和 S2 在 11 条未看到证据的 attempt 上，都 <6/11 至少有一个切点的下一步去查询 NetworkPolicy。S2 通过而 S1 未通过，说明是依从性问题，只保留 S2。
- live 设计：与 T4 共用 G4 的设计。T4b 与 S1/S2 的进入顺序按第 5 节预先登记的顺序。
- 权重：高（skills）；可行性：中，泄漏审计工作量大；关联：程序性知识检索，以及 SFT 中 skill 条件化的数据。

### 3.7 循环、规划、停止与验证层

**L1 停止前的确定性覆盖闸门**

- 问题证据：同 T4。已淘汰的 review 使用了泛化的自我反思，本候选改为提供具体的缺失观测。
- 改动与位置：模型第一次正常收口时，harness 执行一次 T4 清单并追加结果，允许模型修正一次，计入原步数预算。实现复用 `tool_calling_llm` 中 diagnosis review 的挂点。
- 可能有效：只在收口时花一步，成本有界。
- 可能无效：与 review 一样，模型可能只是重申原结论。收口时追加观测的效果，E3c 已能近似测量。
- 指标与淘汰：与 T4 共用 E3/E3c。live 中只有在 T4b 因成本或权限不可用时，才用 L1 替代，不与 T4b 同时开臂。
- 权重：中；可行性：中。

**L2 启用 TodoWrite（作为工程项 1 关闭方案的对照）**

- 问题证据：Holmes 默认调查方式依赖 TodoWrite；当前指令存在而工具缺失。
- 可能有效：显式规划可能提升覆盖。
- 可能无效：泛化反思（review）没有带来提分；token 会增加。
- 最快否决：没有有效的离线否决，因为从第 0 步就改变了轨迹。
- 淘汰条件：只在 T4、S1 都被淘汰之后才考虑；live 中 6 次覆盖率不提升，或 token 增加超过 30%，即淘汰。
- 权重：低中；可行性：高。

**L3 多轨迹投票（K 条独立调查，driver 只提交一份），已由现有数据否决**

- 离线上界：用现有每个单元 3 次重复，按多数判定近似投票，成功约为 6/12 个单元（50%），pass@1 为 16/36（44%），提升约 6 个百分点，成本是 3 倍。network_policy 为 0/12，投票帮不上忙。
- 预设门槛是 ≥10 个百分点，未达到，不进入 live。见第 7 节。

**L4 重复调用拒绝时指向已有结果（低优先）**

- 问题证据：25 次重复调用被拒。
- 改动：拒绝文本中写明已有结果在第几步，并附一行摘要，位置在 `core/safeguards.py:24`。
- 指标：只看每 attempt 重复拒绝次数，不宣称结果。
- 权重：低。

**L5 调高 max_steps。** 不做，见第 7 节。

**L6 工具撤回时的收口指令（工程项，2026-09-25 新增）**

- 问题证据：Holmes 在最后一步只把 tools 置为 None（`tool_calling_llm.py:1176`），不附加任何指令。qwen 从未用完预算，所以没有暴露。换成 glm-5.3-flash 后，离线探测中不给工具时，模型常常继续"计划调用工具"，有时一直写到 8192 上限而没有结论。
- 改动与位置：在 `tool_calling_llm.py` 中，当 `tools is None` 且是因预算用完而撤回工具时，追加一条固定的 user 消息（与第 5 节的文本 N 相同）。只在预算用完时触发，所以正常收口的轨迹不受影响。
- 验收：单元测试覆盖"最后一步带收口指令"；E2n 测量无结论输出的比例，作为问题证据。
- 权重：低中；可行性：高。按构造只保证有结论，不宣称提分。

### 3.8 子 agent 层（Holmes 不支持，只能在 driver 编排）

**A1 并行专项子调查（配置、日志、网络），暂缓**

- 问题证据：覆盖失败的本质是"没有列出对象类"，用确定性的 T4 更便宜；上下文从来不是瓶颈。
- 风险：需要从零编排，成本随子 agent 数量线性增加，汇总环节还会引入新的归因错误。
- 启动条件：T4b 在 live 中把覆盖提到 100% 之后，如果归因仍是瓶颈，并且 F1、A2 都已淘汰，才考虑。
- 权重：高（多 agent），但当前证据不支持。

**A2 新上下文结论撰写（证据摘要 → 独立撰写者）**

- 问题证据：8 条归因错误；最后一步的上下文中位 75k token，其中 55.7% 的字符是日志；E2 显示，给定上下文时最后一步的判定是稳定的。所以要改的是"交给结论撰写者的上下文"。
- 改动与位置：模型收口后，driver 用确定性方法构造证据摘要：全部工具调用及其结果，日志先按工程项 4 压缩；被拒命令只保留分类。然后用同一模型在新的上下文中按 F1 契约写出最终答案。这只增加一次调用，位置在 `driver.py` 中 `agent.call` 之后、`submit_once` 之前，两份答案都写入 trace。
- 可能有效：去掉调查过程中的叙述惯性和干扰。
- 可能无效：摘要可能丢掉关键证据；撰写者看不到推理链。
- 指标：给定覆盖时的归因率，以及 D1、D2。
- 最快否决：E10，完全离线，基于 36 条已记录轨迹构造摘要，每条跑 5 次。
- 淘汰条件：与 E4 相同。
- live 设计：只有通过 E10 且优于 F1 单独使用时，才在 NML 与 readiness 上各做 6 次确认；NML 的答案重评 5 次。
- 权重：中高（子 agent、上下文隔离）；可行性：高；关联：摘要器与撰写者分离，对应 RL 的信用分配。

### 3.9 输出契约层

**F1 最终答案契约（区分触发对象与受害者）**

- 问题证据：
  - 8 条归因错误。NML 失败 5/5 的 D1=0，因为它们把 search deployment 写成故障源。
  - readiness 失败的 D2 ≤0.33。network_policy 的 #7、#17、#21 的 D1=1、D2=0。
  - 10/36 答案以调查过程语句开头。
- 改动与位置：最终答案必须包含以下字段：
  - 直接故障对象（kind/name/namespace/字段或值）；
  - 机制；
  - 支撑证据（引用具体工具输出）；
  - 受影响组件（明确标为下游受害者）；
  - 已排除的备选；
  - 未验证项。
  - 措辞保持通用：由配置错误的对象导致工作负载异常时，故障对象是该配置对象。
  - 有两种形态：F1b 只在最后一步追加（harness 在收口时注入，或放在 driver 任务 prompt 的结尾）；F1a 放进 `system_prompt_additions`，全程常驻（即 P3）。可以选用 Holmes 的 `response_format` 做成 JSON。
- 可能有效：失败集中在"选哪个对象"；E2 证明最后一步是低方差的杠杆。
- 可能无效：
  - NML 的 D1 在 judge 侧本身就不稳定；
  - 模型可能机械套用格式，但仍然选错对象；
  - 列出受害者可能被 D3 判为"指责了额外组件"，因此必须写明"受害者"。
- 反刷分约束：只有当 judge 分数和独立于 judge 的"答案中的故障对象类"指标同时提升时，才算有效。
- 指标：机制为答案中故障对象类与第 1.2 节是否一致；结果为 composite、D1、D2（NML 取 5 次重评的均值）；测试面为原生 transparency 标签的 35 例，要求非劣。
- 最快否决：E4 和 EJ（F2，只用 judge）。
- 淘汰条件：
  - 8 条归因错误 attempt 的多数成功数，不比 E2b 多至少 2 条；或者
  - 16 条原成功中，多数成功下降 ≥2 条；或者
  - 故障对象类一致率没有提升。
  - 满足任一条即淘汰。
- live 设计：优先与 T4b 组合开臂（E3b 通过时）。单独使用时，在 NML 和 readiness 上各做 6 次确认。NML 需要达到 ≥5/6 才宣称显著，否则只报告 D1 均值。
- 权重：中高（结构化输出、失败归因分析）；可行性：高（离线即可完整否决）；关联：结构化结论可以作为 SFT 的目标格式，也可以作为 RL 的字段级辅助信号，但奖励仍以官方 judge 为准。

**F2 提交内容抽取**

- 问题证据：10/36 答案以过程语句开头，其中 7 条失败；driver 原样提交 `result.result`。
- 改动与位置：在 `driver.py` 调用 `submit_once` 前，如果答案中存在"Final Diagnosis / Root Cause / 结论"之类的标题，只提交最后一个此类标题之后的内容，否则提交全文。原文与提交内容都写入 trace。
- 可能无效：过程段落里可能含有正确的对象，截掉会造成损失。
- 最快否决：EJ，对 36 份原答案的抽取结果各重评 5 次，与 E1 比较。只用 judge，成本极低。
- 淘汰条件：原成功中有任何一条多数判定翻转为失败，或失败中没有任何一条翻转为成功。
- 权重：低；可行性：高。

### 3.10 运行时与后端层

- R1 代理空列表修复：工程项 3。
- R2 环境复用：工程项 7。
- R4 离线反事实评测：工程项 5。
- R5 机制指标：工程项 6。
- R6 统计与 holdout：工程项 8。
- R7 证据哈希：工程项 9。

**R8 模型与服务切换适配（工程项，2026-09-25 新增，G3 之前必须完成）**

- 问题证据：新网关对 `enable_thinking=false` 返回 400（"该模型始终思考"）。而 driver（`agent.llm.args.update(extra_body={"enable_thinking": False})`）、`run_preflight`、`scripts/model_preflight.py`、`configs/baseline.env` 的 `LLM_EXTRA_BODY_JSON`/`CLASSIFIER_EXTRA_BODY_JSON`、`configs/holmes-models.yaml` 都在使用这个参数。`scripts/campaign.py` 把 judge 模型写死为 `openai/qwen3.8-max`；`scripts/remote.py --bailian` 从百炼密钥文件注入 key。
- 改动与位置：把 thinking 参数改为按服务配置（本网关用 `{"thinking": {"type": "disabled"}}`）；把模型、api_base 和 key 的来源改为新的忽略文件或 secret；新 campaign 使用新的 manifest，不修改冻结的 `configs/campaign-20260921.json`。
- 验收：preflight 通过；首个 model_request 与 judge 请求都记录实际参数和 reasoning_tokens；在 trace 中能区分"关闭思考"与"不可关闭"。
- 边界：这是环境与服务的变更，不是 harness 改进。它会改变 agent 与 judge，因此历史 qwen 结果不能与之后的结果直接比较。

**R3 thinking 开关（只在最后一步，或全程）**

- 问题证据：campaign 固定 `enable_thinking=false`，目前没有任何 thinking 数据。
- 改动与位置：driver 设置 `agent.llm.args` 的 `extra_body`，judge 不变。最后一步单独开启需要 Holmes 在收口时切换参数。
- 可能有效：提高归因推理的质量。
- 可能无效：时延和 token 都增加；没有证据时，推理也无从谈起（对覆盖类失败无效）。
- 最快否决：E5，最后一步开启 thinking，36 × 3。
- 淘汰条件：20 条失败中的多数成功增加 <2 条，或原成功中回退 ≥2 条。
- live 设计：只在 E5 通过后，与 baseline-v2 在 NML 和 readiness 上各做 6 次。
- 权重：低中（这是配置旋钮）；关联：推理轨迹 SFT 与 RL。

### 3.11 成本与时延层

- K1 缓存/成本计算器属于工程项 5，没有账单时费用写"未知"。
- 按构造有成本收益的条目只有工程项 4、P2 和 T5，它们的 token 节省只作为成本报告，不写成诊断提升。
- 时延上的最大杠杆是工程项 7：环境准备与清理约占墙钟的 77.7%。

## 4. 排序与推荐

排序依据依次是：目标失败类别的规模、能否离线否决以及否决成本、是否必须 live、简历权重、可行性。结果宣称只在 floor 类上做。

**表 A：可验证的 harness 改进（按推荐顺序）**

| 序 | 候选 | 目标失败 | 最快否决 | 是否需 live | 简历权重 | 可行性 | 当前状态 |
|---:|---|---|---|---|---|---|---|
| 1 | F1 最终答案契约 | 归因错误 8；network_policy D2=0 | E4、EJ（离线，约 360 次调用） | 仅做确认 | 中高 | 高 | 等待 G1 |
| 2 | T4b 开局对象清单 | 未看到证据 12 | E3、E3b、E3c，加 G2 权限探测 | 必须（network_policy 6 次） | 高 | 中（依赖工程项 3） | 等待 G1 |
| 3 | A2 新上下文结论撰写 | 归因错误 8 | E10（离线） | 做确认 | 中高 | 高 | 等待 G1 |
| 4 | S1/S2 排障 skill | 未看到证据 12，归因错误 8 | E8 与泄漏审计 | 必须 | 高 | 中 | 等待 G1 |
| 5 | C2 证据台账 | 归因错误 8 | 最后一步注入台账并重放 | 必须（逐步版） | 中 | 中 | 等待 G1 |
| 6 | L1 停止前覆盖闸门 | 未看到证据 12 | E3c | 必须 | 中 | 中 | 作为 T4b 的替代形态 |
| 7 | R3 thinking | 全部失败 | E5 | 必须（全程版） | 低中 | 高 | 等待 G1 |
| 8 | F2 提交内容抽取 | 过程语句 10 | EJ | 做确认 | 低 | 高 | 等待 G1 |
| 9 | T3 管道客户端过滤 | 拒绝 87 次 | 由 G3 中 T2 的结果决定 | 只看机制 | 低中 | 高 | 有条件 |
| 10 | L2 TodoWrite | — | 无有效离线否决 | 必须 | 低中 | 高 | 低优先 |
| 11 | C1 分批 masking | — | 重放非劣 | — | 低 | 中 | 有条件 |
| 12 | T6 空结果标注、L4 重复拒绝指针 | — | — | — | 低 | 高 | 低优先 |
| — | A1 并行子调查、M2 skill 记忆 | — | — | — | 高 | 低 | 暂缓（见第 3 节中的启动条件） |
| — | L3 多轨迹投票、review | — | 已由现有数据否决 | — | — | — | 不做 |

推荐：

- 第一优先是 F1，因为它能在离线条件下完整否决，改动面小，而且针对归因错误。
- 同时推进 T4b，它针对最大的失败类别；只有它有机会在 floor 类上给出显著结果，但必须先通过 E3 系列和 G2 的权限探测。
- S1 与 T4b 并行做离线探针；进入 live 的顺序按第 5 节登记。
- A2 与 C2 是归因方向的备选。
- R3 由 E5 决定去留。
- 其余候选暂缓，或只作为工程改进。

**表 B：工程项（单独列出，按实施顺序）**

| 序 | 工程项 | 所需资源 | 简历权重 |
|---:|---|---|---|
| 1 | 9 证据哈希 | 离线 | 低中 |
| 2 | 6 机制指标抽取器 | 离线 | 中 |
| 3 | 5 离线反事实评测（代码化） | 离线；实验需要 API | 高 |
| 4 | 1 prompt 卫生、工具约束、时间、渲染检查 | 离线；重跑 baseline 需要 live | 低中 |
| 5 | 2 kubectl 错误分类 | 离线 | 中 |
| 6 | 3 代理空列表修复（上游 PR） | 离线；验证需要集群 | 中（开源贡献） |
| 7 | 4 日志观测压缩 | 离线；验证需要 API 与原生 eval | 中高 |
| 8 | 8 统计与 holdout | 离线 | 中 |
| 9 | 7 环境复用（先做 A/A） | 集群 | 高（后端与吞吐） |
| 10 | 建议新增：P2 精简禁用列表、T5 移除回滚工具、T6 空结果标注 | 离线 | 低 |
| 11 | 2026-09-25 新增：R8 模型与服务切换适配（G3 之前必须完成）、L6 工具撤回时的收口指令 | 离线；验证需要 API | 低中 |

## 5. 实施顺序与否决闸门

总规则：

- 淘汰即停止。不为挽回不显著的结果追加实验，也不追加重复次数。
- 离线上界、未达显著的差异和缓存 token 节省都不写成诊断提升。
- 每道闸门的结论先写进报告，再进入下一道闸门。

**G0 离线，不需要 API，也不需要集群（现在即可进行）**

- 实施工程项 9、6、5（代码化）、1（代码与检查）、2、3（上游 PR 与本地测试）、4（第一级）、8，以及建议新增的 P2、T5，并实现泄漏审计脚本。
- 退出条件：
  - CI 通过；
  - 机制指标抽取器精确复现第 1.3、1.4 节；
  - 证据包在干净的 Linux checkout 上复算哈希一致；
  - 工程项 4 在 245 份日志上逐字节可还原；
  - 泄漏审计对仓库中全部 skill 和 prompt 附加文本通过。

**G1 离线，需要模型 API（账户恢复后）。预先登记如下：**

以下都用强制收口（tools=None）的最后一步重放，温度 1e-8，thinking 关闭（E5 除外）。每个答案用离线 judge 评一次；NML 的答案重评 3 次取多数。"多数成功"指该 attempt 的样本中过半成功。

| 编号 | 输入 | 读法与淘汰条件 |
|---|---|---|
| E2b | 逐字最后一步，强制收口，36 × 5 | E3–E10 的对照组 |
| E3 | 11 条未看到证据的 network_policy attempt：在最后一步追加一轮 `kubectl get networkpolicy -n hotel-reservation -o yaml`，结果用 #23 的真实对象，creationTimestamp 对齐到该 attempt；每条 5 次。安慰剂：同一位置改为 `kubectl get poddisruptionbudget` →"No resources found"，每条 5 次 | 多数成功 ≥6/11，说明覆盖就足够；<6/11 说明归因同样是瓶颈。安慰剂必须 ≤1/11，否则判为注入格式造成的假象，E3 结论作废 |
| E3b | E3 加 F1 契约 | 覆盖类候选进入 live 的条件是 E3 或 E3b 满足 ≥6/11；两者都不满足，T4、S1、L1 一律暂停 |
| E3c | 只注入名字清单（用该 attempt 已观测到的对象名加 NetworkPolicy 名构造的近似清单），允许一步工具调用 | 下一步动作取回该对象的 <6/11，则 T4a 淘汰、只保留 T4b；之后再给出真实 YAML，强制收口，读法同 E3 |
| E4 | F1b 契约追加在最后一步，36 × 5 | 满足任一条即淘汰：8 条归因错误中多数成功不比 E2b 多至少 2 条；16 条原成功中多数成功下降 ≥2；故障对象类一致率不提升 |
| E5 | 最后一步开启 thinking，36 × 3 | 20 条失败中多数成功增加 <2 条，或原成功回退 ≥2 条，即淘汰 |
| E6 | 最后一步请求中所有 get_logs 消息做标签合并；另一臂做标签合并加模板折叠；各 36 × 3 | 非劣要求：相对 E2b，多数判定变化 ≤1 条。同时从 usage 记录 prompt_tokens 的减少量，只作为成本项 |
| E7 | 跳过 | kubectl 错误分类只有机制指标，离线没有结果面 |
| E8 | 12 条 network_policy attempt 的每个切点做 next-action 探针，分 baseline、S1、S2 三臂，每点 1 次 | S1 与 S2 都 <6/11（未看到证据的 attempt 中，至少一个切点的下一步查询 NetworkPolicy）即淘汰。S2 通过而 S1 未通过时，只保留 S2 |
| E9 | 从第 0 步做完整轨迹录制回放：prompt 逐字，工具按同一 attempt 的 (工具, 参数) 精确匹配提供 | 报告首次未命中前的步数、未命中率，以及零未命中到达收口的比例。若首次未命中步数的中位数 <3，宣布多步离线评测不可用，只使用最后一步和 next-action 探针 |
| E10 | A2：确定性证据摘要加 F1 契约，在新上下文中撰写，36 × 5 | 淘汰条件同 E4；另外必须优于 E4，才能作为独立候选 |
| EJ | F2：对 36 份原答案抽取最终段，各重评 5 次 | 原成功中有多数判定翻转为失败，或失败中没有任何翻转为成功，即淘汰 |

- 估算规模：约 2,500 次 agent 调用和约 2,000 次 judge 调用。强制收口的最后一步输入中位约 75k token，大部分可以命中缓存。
- 退出条件：确定进入 live 的候选，最多 2 个臂，并写入报告。进入顺序预先登记为：
  1. 若 E3 或 E3b 通过且 G2 权限可用，先上 T4b；E3b 优于 E3 时，用 T4b + F1。
  2. 若 T4b 不可用而 E8 通过，用 S1/S2。
  3. 若 E4 或 E10 通过，F1 或 A2 作为归因臂。

**G1 预先登记修订 v2（2026-09-25，写于任何 glm-5.3-flash 实验结果之前）**

修订原因：百炼账户欠费，用户指定后续全部改用 newapi 网关与 `glm-5.3-flash`。修订前只做了服务探测，没有产生任何实验结果。探测结论如下：

- 该模型"始终思考"。传 `enable_thinking=false` 返回 400。`thinking={"type":"disabled"}` 可以使用，但在长请求上仍会产生 100–300 个推理 token；`reasoning_effort` 取 low/high/max 时推理量增加。
- 历史上最长的最终请求（qwen 计 154k token）在 glm 下为 133k token，可以放下。前缀缓存有效：第二次请求几乎全部命中缓存。
- 温度 0 仍不确定：同一请求两次的输出不同。
- 不给工具强制收口时，模型常常继续"计划调用工具"，有时一直写到 8192 上限而没有结论（见 L6）。

协议变更：

1. 模型与参数：agent 与离线 judge 都用 `glm-5.3-flash`，温度 0，`thinking={"type":"disabled"}`，逐次记录 reasoning_tokens。agent 的 max_tokens 为 8192，judge 为 4096。judge 代码仍是 SREGym DiagnosisJudge 原码，只替换后端。
2. 强制收口：一律在最后追加一条 user 消息 N（原文见下）；各处理臂的附加文本接在 N 之后。E2b 即"原上下文 + N"。
3. 新增 E1g：用 glm judge 对 36 份原提交各评 5 次，报告噪声底，以及与官方（qwen judge）判定的一致率。这只是标定，不设淘汰。如果逐样本一致率低于 80%，报告中必须写明：G1 的结论只在 glm judge 的尺度上成立。
4. 新增 E2n：不追加 N 的强制收口（与 Holmes 最后一步的行为一致），36 × 3，报告无结论输出的比例（finish=length，或答案中没有诊断）以及判定结果。只做测量，用来支撑 L6。
5. 集合定义不变：8 条"看到证据但归因错误"、16 条原成功、11 条"未看到证据的 network_policy"，仍按官方结果和第 1.3 节划分。所有比较都相对于 E2b（同样是 glm）。
6. E3c 使用近似清单：在该 attempt 的首条 user 消息后追加名字清单（取 #23 输出中的 Deployment、Service、ConfigMap 名，再加上 NetworkPolicy 名），在最后一个切点允许调用工具，记录下一步动作。如果模型取回 NetworkPolicy，就用 E3 的真实 YAML 作为结果，再追加 N 收口并判分。
7. E8 细化：
   - 切点是每条 network_policy attempt 的每次 model_request。
   - 三臂：base、S1、S2。S1 按 Holmes 模板（`base_user_prompt.jinja2`、`generic_ask.jinja2`）渲染 Skill Usage 段和 Skill Catalog，并加入 fetch_skill 工具；模型获取 skill 时，按 Holmes 的包装格式返回 skill 内容，再看它的下一步。
   - 判据：下一步执行的 kubectl 命令涉及 NetworkPolicy。S1 看取完 skill 之后的那一步。
   - 淘汰条件补充：S1 或 S2 还必须比 base 臂至少多 2 个 attempt。
8. E9 推迟到 G3 之后：用 glm 回放 qwen 的轨迹，只能测跨模型的分歧，测不出回放保真度。
9. E5 改为 `reasoning_effort=high` 对比 E2b（disabled），因为该模型无法完全关闭思考。
10. judge 次数不变：NML 的每个答案 judge 3 次取多数；其余答案 judge 1 次。
11. 文本 N、F1 契约 C、S1/S2 的 skill 全文如下，已通过泄漏审计原型：对 120 个题目 ID、740 个注入实现字面量、93 条 root_cause 描述中的 5,474 个 4-gram，全部 0 命中；阳性对照全部命中。已知缺口：f-string 前缀后面紧跟字母时不会命中，G0 代码化时修复。文件 SHA256：`texts.py` 为 `e068c134bd7ddf76…`，`leakage_audit.py` 为 `996850b59ea7018b…`。

文本 N（收口指令）：

```text
Tool use has ended for this investigation; no further tool calls are possible. Do not describe or plan more tool calls. Using only the evidence above, write your final diagnosis of the faulty component and its root cause.
```

文本 C（F1 契约，接在 N 之后）：

```text
Structure the final diagnosis as follows:
1. Faulty object: the specific Kubernetes object whose configuration or state is wrong (kind, name, namespace, and the field or value at fault). If a configuration object causes other workloads to fail, the faulty object is that configuration object, not the workloads that suffer.
2. Mechanism: how this fault produces the observed symptoms.
3. Evidence: the specific tool outputs that support it.
4. Affected components: workloads impacted downstream, labelled as affected rather than as the root cause.
5. Ruled out: alternatives you considered and why the evidence rejects them, for example errors that only occurred during startup and have since recovered.
6. Unverified: anything you could not confirm.
```

S1/S2 skill（名称 `kubernetes-service-degradation-triage`）：

```text
description: Use when an application on Kubernetes shows failing or timing-out requests, unavailable services, or pods that cannot be created or never reach Ready, while the cause is still unknown.

# Kubernetes service degradation triage

1. Inventory the namespace. List every namespaced resource kind you are allowed to read
   (`kubectl api-resources --namespaced=true -o name`, then `kubectl get <kind> -n <namespace>` for each kind,
   one command per call, no shell pipes). Record every object that exists, not only pods, services and deployments.
2. For each object that selects, admits, routes to, schedules, configures or constrains the affected workloads
   (through label selectors, namespace-wide scope, or references), read its spec with `-o yaml` and decide
   whether it explains the symptoms.
3. Compare what the workloads need with what those objects allow or provide: selectors against pod labels and
   endpoints; probes against container ports and paths; admission and resource requirements against pod specs;
   traffic rules against the communication paths the application uses; referenced ConfigMaps, Secrets, service
   names and DNS against what exists; scheduling constraints against node labels and taints.
4. Use timestamps. Separate errors that persist now from errors that only occurred during startup and have since
   recovered. Errors that also appear in healthy components are weak evidence.
5. In the diagnosis, name the object whose configuration or state is wrong as the faulty component, state the
   mechanism, and list impacted workloads separately as affected.
```

外部效度：离线结果描述的是"glm-5.3-flash 在 qwen 收集的上下文上的行为"，只能用于否决和排序，不能直接外推到 glm 作为 agent 的 live 表现。

**G2 集群，只读探测和原生 eval（不是 campaign）**

- 在集群上验证工程项 3：空 limitrange 返回 "No resources found"。
- T4 的权限探测：`kubectl api-resources --namespaced=true -o name` 能否执行；`kubectl get <kind> -n <ns> -o name` 对空列表的返回（修复前后各测一次）。
- 原生 eval 子集：
  - context_window 21 例、datetime 4 例，用于工程项 1 和 4 的非劣检验；
  - skills 30 例，仅在 S1 进入时运行；
  - 原生 grader 的噪声底：同一输出重评 5 次。
- 工程项 7 的 A/A 对照。
- 退出条件：以上各项有明确结论；A/A 未通过时，G3 及以后继续使用完整重建。

**G3 live：fresh baseline-v2**

- 配置：合入工程项 1、2、3、4（第一级）以及已采纳的 P2、T5。
- 样本：4 个案例各 3 次，共 12 次。
- 检查项：
  - network_policy 必须仍为 0/3，才能把对照合并为 0/15。若 ≥1/3，历史对照作废，G4 改用同期对照：6 对 6，处理组需 ≥4/6，p=0.030。
  - 报告每 attempt 被拒数（历史值：管道加 `get all` 为 2.89，全部为 3.28）、token 和缓存命中率（与 88.4% 相比，允许 ±2 个百分点）。
  - 不做结果宣称。

G3 修订（2026-09-25）：先完成 R8，再在 glm-5.3-flash（agent 与 judge）下重建 baseline-v2。network_policy 是否仍是 floor 类，由 G3 决定：必须为 0/3。历史 qwen 对照不再合并使用。

**G4 live：候选对照（floor 类）**

G4 修订（2026-09-25，取代下文按历史对照计算的阈值）：对照改为 glm 下的 baseline-v2 同期对照 6 次，与 G3 的 0/3 合并为 0/9。处理组每臂 6 次：≥3/6 为显著（单侧 Fisher p=0.044）；4/6 时 p=0.011；2/6 不显著，停止；≤1/6 淘汰。如果同期对照出现成功，就按实际对照重新计算 p，不改阈值、不补做。

- 最多 2 个臂，每臂 network_policy 做 6 次。
- 判定：
  - ≥3/6：对合并对照 0/15 的 p=0.015，宣称"在 floor 类上显著"；
  - 2/6：不显著，停止，如实报告；
  - ≤1/6：淘汰。
  - 功效：真实成功率 50% 时为 0.66，70% 时为 0.93。
- 非回退描述：selector、readiness、NML 各 3 次。NML 的答案重评 5 次，报告 D1 均值与故障对象类一致率。

**G5 holdout（按故障类隔离）**

- 选类：用固定种子从 registry（约 120 题）中抽 4 个故障类，排除 4 个开发类，也排除静态注入作用于同一对象类（NetworkPolicy、ResourceQuota、Service selector、readinessProbe）的题目。种子和清单封存在节点上，文档只记录抽取程序。
- 比较：最终配置对 baseline-v2，每类每臂 3 次，共 24 次。
- 导出：只用 `--sealed` 导出汇总成功率和机制指标，不导出逐类结果。
- 只使用一次，之后不再调参。

**G6 报告**：写入 `docs/reports/`，按故障类列出，包含全部淘汰项和负结果。

## 6. 简历条目草稿

填写规则：

- 结果类占位符只有在达到第 5 节预先登记的显著性阈值后才能填写；未达到时，改写为"未观察到显著差异（x/6 对 0/15，p=…）"。
- token 和缓存类数字只能写成成本，不能写成诊断提升。
- 离线上界不写成效果。

1. 为 HolmesGPT（原生 agent loop）× SREGym 搭建离线反事实评测：切点重放、工具录制回放、离线 judge、缓存成本核算。最后一步重放判定一致率〔A1〕，judge 噪声底〔A2〕；在进入集群前否决了〔A3〕个候选，免去约〔A4〕次 live attempt。
   - 〔A1〕：逐字最后一步重放的 `stop` 样本中，判定与官方一致的比例（E2 / E2b）。
   - 〔A2〕：同一答案重评 5 次，判定与官方一致的比例（E1）。
   - 〔A3〕：G1 中淘汰的候选数。
   - 〔A4〕：被淘汰的候选若按 G4 设计本需进行的 live attempt 数之和。
2. 设计 Loki 日志观测的确定性压缩（标签无损合并加同模板折叠，在插入时变换，历史只追加，保持前缀缓存）：日志观测字符减少〔B1〕，单 attempt 输入 token 减少〔B2〕，缓存命中率〔B3〕，原生 context_window 评测〔B4〕。
   - 〔B1〕：get_logs 结果字符的减少比例（G3 实测）。
   - 〔B2〕：baseline-v2 与旧 baseline 相比，每 attempt `usage.prompt_tokens` 的变化。
   - 〔B3〕：`cached_tokens / prompt_tokens`（G3）。
   - 〔B4〕：21 例中通过的例数，要求非劣。
3. 为 kubectl MCP 工具建立错误语义（NotFound 作为观测返回、未知资源类型、代理 502、隐藏对象 403），并把工具约束写入工具描述：每 attempt 被拒命令数从〔C1〕降到〔C2〕，被误分类的错误从〔C3〕降到 0。
   - 〔C1〕/〔C2〕：旧 baseline 与 baseline-v2 的每 attempt 被拒数。
   - 〔C3〕：用历史 118 条拒绝按新规则复核后得到的误分类数。
4. 定位并修复 SREGym 过滤代理的空列表崩溃（items 或 rows 为 null 时返回 502），向上游提交〔D1〕。
   - 〔D1〕：PR 链接及合并状态。
5. 用对象清单〔加结论契约〕解决覆盖失败：在基线 0/12 的 floor 故障类上达到〔E1〕/6 成功（单侧 Fisher p=〔E2〕），故障对象证据覆盖率从〔E3〕提升到〔E4〕，按故障类隔离的 holdout 汇总为〔E5〕。
   - 〔E1〕/〔E2〕：G4 的成功数与 p。
   - 〔E3〕/〔E4〕：工程项 6 定义的覆盖率（旧、新）。
   - 〔E5〕：G5 的汇总成功率对比。
6. 环境复用（inject → diagnose → recover → 规格哈希加健康检查）把每 attempt 墙钟从〔F1〕降到〔F2〕，A/A 对照〔F3〕。
   - 〔F1〕/〔F2〕：每 attempt 的平均墙钟（历史约 493 s）。
   - 〔F3〕：A/A 中两组成功数和机制指标的差异。
7. 机制指标与统计流程：证据覆盖、给定覆盖的归因率、工具错误分布；按实测噪声做功效分析，holdout 按故障类隔离，只导出汇总。
   - 〔G1〕：holdout 故障类的数量。
   - 〔G2〕：报告中经过预先登记的比较数。
8. 证据包按 LF 固定写出，CI 在干净 checkout 上复算 manifest 哈希，解决跨平台哈希漂移。
   - 〔H1〕：CI 作业名称与首次通过的运行编号。

## 7. 看过但不做

| 方向 | 不做的理由 |
|---|---|
| 删除 `docs/plans/2026-09-23-harness-direction.md` | 做了以下检索，都没有找到该文件，也没有任何引用，所以不需要删除提交：对全部本地分支、远端引用（含 `pr/1`–`pr/6` 与 dependabot 分支）执行 `git ls-tree -r`；执行 `git log --all -- '*harness-direction*'`；对全部引用执行 `git grep harness-direction`；在工作区及被忽略的目录中按文件名查找。本文没有使用该文档的任何内容 |
| 启用 bash 读取落盘结果，或调高 spill 阈值 | 违反本轮约束；spill 从未触发（最大约 19k token，阈值 25k） |
| 启用内置 kubernetes/core 等 toolset | 会绕过 benchmark 的过滤代理和权限模型 |
| 读取 managedFields 的 manager、注入器注解、benchmark 自身对象或 root_cause | 属于评测泄漏 |
| 调高 max_steps | 最大只用了 27/30，预算从未成为约束 |
| 调低上下文压缩阈值 | 上下文最大 154.4k，从未接近阈值；失败 attempt 的上下文反而更短（中位 72.3k，成功者 84.2k）；有损摘要会丢失证据 |
| 用 llm_summarize 摘要日志 | 有损，需要额外模型调用，有丢失证据的风险；确定性压缩已经能减少 57.6%–84.6% |
| 结束前的 diagnosis review（上一轮的 A） | 已由冻结实验淘汰：validation 2/6 对 3/6，token 为 2.51 倍 |
| 多轨迹投票 L3 | 离线上界只提升约 6 个百分点，成本 3 倍，而 network_policy 为 0/12；达不到 ≥10 个百分点的门槛 |
| 背景噪声抑制规则（例如"忽略 consul/otel 错误"） | 这类关键词在失败 20/20、成功 13/16 中都出现，无法区分；而且是环境特定规则，会过拟合 |
| 删掉 -o yaml 输出中的 last-applied-configuration | 它与 live spec 的差异可能正是漂移类故障的证据 |
| 故障层面的跨 episode 记忆（不经 holdout 隔离） | 等于在测试故障类上学习，存在泄漏；按隔离形态实施的 M2 已列为暂缓 |
| LogQL 查询引导 | 245 次 get_logs 中已有 158 次使用行过滤；日志体积主要来自标签前缀，不是没有过滤 |
| 删除 Jaeger 工具 | 属于环境特定的裁剪，泛化性差；改为 T6 空结果标注 |
| 更换 judge 模型或给 judge 开 thinking | 这改变的是评测，不是 harness |
| 为 NML 追加重复以挽回结果 | 违反"淘汰即停止"；NML 的问题在于 judge 噪声，应该用多次重评来处理，而不是增加 attempt |
