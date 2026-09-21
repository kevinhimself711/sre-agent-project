**Agent 实习项目计划评估｜2026-09-19**

结论：保留 HolmesGPT 作为工程基座，采用“HolmesGPT 原生评测作快速回归 + SREGym-Lite diagnosis 作外部评测”的主线。这是目前核实的候选中，最符合你“Agent 开发 > 后端开发 > 后训练”优先级的选择；不是已经运行证实的最优组合。11 月目标合理：基于源码、实际运行和评测持续尝试多个 harness 改进，同时围绕真实任务执行链建立完整后端叙事，并贯通轨迹与评测管线。最终改动数量由证据、需求价值和集成成本决定，不预先限定为一个 harness 改动或一个 issue。

本版按用户补充修订：harness 可以多方向探索，争取形成多个有内容的简历条目；后端可优化现有组件，也可为真实需求增加模块，issues 和上游 PR 只作为线索与外部背书。若改动价值无法证实，应撤回不必要的复杂度，保留对原生能力的深入理解、复现、集成与验证成果。这是正式回退策略，不要求为了简历强行制造“优化”。

按 2026 年 9 月 19 日至 11 月中旬约八周、每周 30–40 小时判断，你有约 240–320 小时的投入空间。代码生成可以加速实现，但集群排错、故障复位、模型调用、反复评测、读懂源码仍占实际时间。记录中“年底或者 28 年初”按最终时间线理解为“2026 年底或 2027 年初”；暑期投递按 2027 年 4 月准备。

本次已阅读 docs 的四份对话/调研记录，两份有效算力指南，并通过 SSH 只读检查两台个人节点。在线复核了八个候选仓库的目录和说明，以及 HolmesGPT、SREGym、AIOpsLab、AOI 的关键实现。源码按 commit 固定，证据见文末。此次没有部署故障环境、执行模型评测或训练，因此没有声称 baseline 已跑通、适配已验收或改进已有效。

**算力核实：你的补充基本准确，但“可申请”要与“立即获得”区分。**

新文件《4090-server Slurm 普通用户使用指南》给出了以下规则：

| 项目 | 指南内容 | 对计划的影响 |
|---|---|---|
| 总 GPU | 8 张；0–5 由 Slurm 调度，6–7 保留 | 普通用户共享 6 张，不能把整机 8 卡计入个人资源 |
| 单作业和个人并发 | 每作业 1 或 2 张；每人同时运行 GPU 总数最多 2 张 | 可以一个双卡作业，或两个单卡作业 |
| 单卡显存 | 第 6 页状态示例为 49,140 MiB | 与你说明的 48GB 配置一致；公共节点硬件尚未 SSH 实测 |
| 交互任务 | 默认 4 小时，最长 8 小时 | 适合调试 |
| 批处理任务 | 默认 50 小时，最长 200 小时 | 足以支持分阶段的训练实验与续训 |
| 其他限额 | 默认/最大 CPU 为 16/32 核；内存 32/72GB；最多提交/排队 10 个任务 | 数据预处理和加载也要预算系统内存 |
| 排队 | 忙时排队；交互优先但不抢占正在运行的任务 | 可自助提交，不能承诺随时立即拿到双卡 |
| 使用方式 | `gpu-shell`、`gpu-sbatch`；Docker GPU 使用须先沟通 | 训练走现有 Slurm 与 Python 环境，不把常驻故障集群放这里 |

个人节点的 SSH 实测快照：

| 节点 | CPU 逻辑线程 | 系统内存 | GPU | 根分区可用空间 |
|---|---:|---:|---|---:|
| pci-1 | 32 | 约 62GiB | RTX 4090，24,564MiB | 约 843GB |
| pci-2 | 32 | 约 125GiB | RTX 4090，24,564MiB | 约 684GB |

两台都有可响应的 Docker，发现 k3s 可执行文件，但此次未验证现成 Kubernetes 集群健康；非交互 `sudo -n` 未成功，也不等于账号没有 sudo 权限。历史记录提过 kernel panic，本次短时检查不能证明已经解决。资源容量足够做 Lite 环境，实际稳定性要由后续连续运行和复位确认。

A800 指南确认了 ex02A800、Slurm、每卡配 8 CPU、普通用户没有 sudo 等规则，但**没有确认“必须博士生代提交且个人最多一张”**；文中反而有申请两张卡的参数示例。那可能是课题组另行规定，不能由通用指南证明。按你的决定，当前计划完全不依赖 A800。

建议分工：个人节点承载常驻评测环境、调试及小模型推理；共享双 48GB 卡承载 SFT 和小规模 RL。两台独立 24GB 节点不能当成一台共享 48GB 显存机器，双 48GB 的 DDP 也不会自动让单个模型获得 96GB 连续显存；是否分片及互联效率须按训练框架确定。

**选型：保留 HolmesGPT + SREGym，但把“适配已证实”降为“源码层可行，端到端待验证”。**

| 组合 | 当前核实到的适配与价值 | 对你的定位 |
|---|---|---|
| HolmesGPT + 原生 eval | 原生调用和评分；当前固定版本有 275 个 `test_ask_holmes/**/test_case.yaml`，并非全部无需外部依赖 | 必备的快速回归层；不能替代外部验证 |
| HolmesGPT + SREGym-Lite | Holmes 支持 SSE MCP 和 headers；SREGym 有 SSE MCP、conductor API、agent 注册与 diagnosis 模式；尚无在册 Holmes driver | 首选外部评测；最符合工程深度与后续训练的组合 |
| SREGym 内置 Stratus + SREGym | 原生集成，适合确认环境和评分链工作 | 环境对照与备选基线；不是当前主工程基座 |
| HolmesGPT + AIOpsLab | AIOpsLab 支持任意 agent class 的 `get_action`，但要适应由它掌控的 action/observation 循环 | 合法备选，适配成本需实测；不能仅凭 registry 没有 Holmes 就判不可行 |
| HolmesGPT + ITBench / ITBench-Lite | 完整 ITBench 有真实 Kubernetes 场景；Lite 是另一种快照路线；Holmes 的配套工具和 runner 尚需验证 | 后续补充，不在八周内同时维护第三套评测 |
| OpenSRE + 自带测试 / SREGym | 当前仍标 public alpha，默认 CLI 有账号激活路径；有 harness 和测试，不等于已经有可复现的 SRE 训练闭环 | 11 月交付前不换这个基座 |
| AOI + AIOpsLab | 有多 agent 平台、Observer/Evolver 的 GRPO 代码和数据入口 | 学习训练与失败轨迹利用的方法，不替代主工程基座 |
| OpenRCA + 其参考 agent | 离线 RCA 数据与参考实现 | 可用于后续诊断泛化，不能当成完全无适配成本的替换 |

这不是按 star 数或“学术更新”作选择。你的主要资产应是：读懂成熟 agent 的执行链，在真实失败模式上做可开关的改进，用冻结的外部环境测出取舍。SREGym 的隔离和 MCP 有利于这一目标；原生评测让环境问题不至于拖垮全部交付。

**此前材料中应修正的关键判断。**

1. **“MCP 都支持，所以 adapter 只是搬字符串、不会有噪声”过强。**传输兼容已有源码证据，但工具 schema、session headers、权限、容器路径、最终提交、超时和 trace 转换都可能影响行为。SREGym 当前 `agents.yaml` 没有 Holmes；不能把其他 agent 的 driver 大小当作工作量证明。
2. **“SREGym 分阶段 oracle = process reward”错误。**diagnosis/mitigation 是阶段结果，不是每个调查动作的监督。当前 LLM diagnosis oracle 已返回 `composite_score`、`dimensions` 和 checklist，所以旧文档“完全没有 scalar / partial credit”也已不准确；但它主要比较最终答案与预期根因，没有逐步验证工具轨迹。
3. **“RL 必须有 process reward”“离线数据不能评 RL”都不成立。**终局奖励可以训练策略；可查询的静态数据也能支持多步检索/分析策略。区别是它不能验证真实系统修复。现成环境无 Gym `step/reset` 也不等于不能训练，只是需要训练框架的 rollout/reset 接入。
4. **“AOI 有 GRPO，所以历史失败轨迹直接解决在线 rollout”不成立。**公开 Evolver 训练场景生成，Observer 路径从保存的轨迹前缀构建 prompt、采样新 completion 并用奖励模型评估；所检查的入口没有逐次执行新动作后重跑 live 环境。它是有价值的参考，不是现成的 SREGym 多轮在线 RL 实现。
5. **“HolmesGPT 没有 memory/上下文层”不能用作创新前提。**当前已有 skills 获取、会话压缩、单工具结果落盘与重复调用相关逻辑。应区分会话工作记忆、持久经验、skills；改进现有机制的具体缺陷，而非笼统宣称首次增加 memory。
6. **“消费事件流就能实现完整 verifier 和 context 控制”不准确。**事件很适合 trace；在下一次模型调用前可靠改变 messages、预算和停止条件，需要适当的 loop hook。直接修改 fork 合理，只要开关、回归与对照清晰。
7. **“上游历史分数可以直接和你比较”不成立。**模型、judge、工具权限、预算、环境、版本不同都会影响分数。论文数字只能作背景；主结论来自你在同一配置下重跑的 baseline。
8. **“复用外部 benchmark 就不会泄漏”过强。**容器和代理降低泄漏风险，仍需避免把故障 ID、原始注入器信息、评分日志或测试题答案写进 prompt、skills 和跨题记忆。
9. **“generator 有三个目录，所以训练样本可无限组合”未证实。**噪声和负载变化不等于新的根因推理任务；组合需要验证注入、健康态、oracle 和可诊断性。变体要继承原始故障家族的数据分组。
10. **“先全量跑绿，再进入外部 benchmark；先拿 merged PR 再做其他”不适合当前工期。**困难 eval 本来可能失败，第三方集成可能缺凭证，PR 合并受上游节奏控制。先跑相关测试与少量有效 case，并提前验证 SREGym 风险；不等待全量成功或 PR 合并。

另一个应放下的约束是“工装代码必须少于产品代码 50%”。它容易让代码行数代替目标。更有效的是控制同时尚未验证的复杂改动和环境排错投入，并要求每次开发能连到真实需求、评测证据或数据可用性；这限制的是失控的在制工作，不限制累计尝试和最终有效改动的数量。

**接入 SREGym 时，实际需要完成的一条窄链路。**

`conductor 启动 case → 隔离容器启动 Holmes driver → 等待 diagnosis → 获取公开应用信息 → 通过官方 MCP 调查 → 提交最终诊断 → 宿主保存评分与轨迹 → 清理/复位`。

源码对照表：

| 边界 | 已确认 | 仍要验收 |
|---|---|---|
| 启动 | `agents.yaml`、kickoff command、install script | Holmes 包与 Python 依赖的容器打包；最好独立环境避免与 benchmark 依赖冲突 |
| 题目输入 | `/get_app` 只返回应用名、namespace、应用描述；`/status` 给阶段 | 不向模型传入可直接泄漏故障的 problem ID 或宿主路径 |
| 调查 | SREGym 挂载 `/kubectl/sse`、`/prometheus/sse`、`/loki/sse`、`/jaeger/sse`；Holmes 支持 SSE | 工具发现、实际调用、参数与结果保真；每个 attempt 独立 `sregym_ssid` |
| 可见范围 | SREGym MCP 使用 Kubernetes 过滤代理 | Holmes 内置工具不能绕到宿主管理员 kubeconfig；不能扩大可见权限 |
| 最终提交 | POST `/submit` 接受 `solution` 和 `stage`，有 attempt/stage 检查 | 最终答案完整、提交仅一次；超时先核实状态，不能盲重试推进阶段 |
| 运行成功 | HTTP 200 表示接受提交，进程退出码仅表示进程结束 | 两者均不能代替 oracle 的诊断得分 |
| 复位 | 使用 benchmark 原有清理和 runner | 连续重复同一 case，确认无上轮故障、工具会话和记忆残留 |

适配层不添加额外 planner、答案改写器或看过真值的补救逻辑。相同 driver 用于原版和改进版 Holmes，避免把适配差异算成 harness 收益。若因只读工具限制与官方配置不同，明确报告本地 diagnosis 配置；未确认排行榜规则前不承诺“官方榜单成绩”。当前 README 也提醒单阶段结果不能直接用于按双阶段设计的 difficulty 表。

**Harness：建立多个可验证的候选方向，用实验选择最终组合。**

原版失败轨迹、源码机制、业务约束共同决定尝试顺序。当前可建立以下候选池；“源码中存在该机制”和“该机制已经造成我们的问题”是两种证据，表中后者仍须实测。

| 方向 | 当前源码观察 | 可尝试的改进与验证 |
|---|---|---|
| 上下文与证据保留 | 已有全历史压缩和单工具结果落盘 | 在压缩时保留关键证据引用、已排除原因和待验证问题；比较原生压缩、简单调参及结构化状态方案，测准确率、成本和重复查询 |
| 工具与 skills 选择 | 已有工具目录、schema 注入和 skills 获取 | 若工具描述占用明显或选错工具较多，尝试按任务阶段选择工具、渐进披露、改善 skill 检索；同时检查是否漏掉必要工具，不能按隐藏 case 真值选工具 |
| Agent Loop 与停止策略 | 有 max_steps、最后一轮收口、重复工具调用相关逻辑 | 根据调查进展分配预算、检测循环、改善停止或继续调查决策；额外 verifier 的调用成本计入对照，禁止访问 benchmark oracle |
| 会话工作记忆与跨事故经验 | 会话历史、压缩摘要和 skills 已承担部分记忆功能 | 对比工作状态摘要、结构化假设记录、检索经验等方案；跨事故记忆明确训练/测试边界，每次评测固定记忆快照 |
| 工具输出处理与错误恢复 | 已有结构化结果、结果过滤、MCP 错误返回 | 若证据淹没在大输出或工具失败触发无效循环，尝试保真过滤、查询改写、错误分类后的恢复；测错误下的任务恢复和正常路径回归 |
| 工具执行与调度 | loop 有线程池，同一 MCP server 的调用有锁保护 | 若等待和锁竞争确为瓶颈，评估有界并发、依赖感知调度或会话隔离；不能直接删锁，也不能把遥测缓存当成永远正确的证据 |

这些方向可以连续尝试，也可以组合。实验流程是“观察 → 假设 → 小范围实现 → 单项对照 → 组合及消融 → 决定保留、调整或回退”。直接在 fork 中增加可开关的 loop hook 合理；没有必要为每个想法新建一个通用框架。

上下文保留是第一批候选之一，不预先认定它最值得做。若 baseline 很少触发压缩，或简单调参就能解决，就转向更常见的失败。每次增加组件都核算它额外的延迟、token、状态复杂度和维护成本；多项单独有效不代表组合后一定有效。

可以争取形成若干独立的简历条目，例如上下文/记忆、工具选择与循环、可靠执行、评测与训练数据，每项须有可说明的职责与证据。它们不必一一对应新组件，也不要求每项都提升同一个成功率。新增能力可以通过真实使用与功能验收证明价值；性能或质量“优化”则必须有相应对照。不要先规定简历条目数，再倒推出必须实现的架构。

**后端：以诊断任务的完整生命周期组织 storyline，issues 是线索。**

主体是自己能够解释和验证的系统：请求如何进入 Holmes，如何调度模型与工具，结果如何返回和归档，运行中断后如何处理，以及这些运行怎样进入评测与训练管线。既可以改进 Holmes 原生服务端，也可以在真实需求出现时增加实验/rollout 管理模块。两者都沿用现有边界，避免重写原服务。

后端的六个面试问题对应同一条执行链：

| 面试问题 | 需要掌握并形成证据的内容 |
|---|---|
| 设计了什么系统，边界在哪？ | 说明 Holmes 负责模型/工具决策和诊断执行，SREGym 负责故障环境与官方判分，我们负责哪些接入、运行管理、数据处理或策略；明确模型输出、任务完成、环境恢复的责任 |
| 并发模型怎么选？ | 区分请求级、单次调查工具级、独立评测环境级并发；解释同步依赖为何采用线程/进程，何时异步有效，为什么限制并发，为什么同一故障集群不能随意并跑 |
| 数据怎么建模，为什么这样存？ | 区分逻辑任务与实际 attempt、模型/工具事件、轨迹 artifact、评分记录和数据集版本；说明原始轨迹、可重建索引与业务状态的不同责任，不因演示方便重复建设存储 |
| 失败如何处理？ | 说明超时、取消、瞬时失败重试、结果不确定、重复提交、环境复位失败及进程中断的语义；实际验证哪些操作可重复执行、哪些只能核实状态或重新开始 |
| 怎么知道正常工作？ | 关联 run/attempt、LLM call、tool call 与 trace；把任务成功、服务可用、judge 正常和训练数据完整性分别观察；能从异常定位到具体阶段 |
| 瓶颈在哪，怎么定位？ | 拆解排队、模型生成、工具执行、锁等待、环境准备/复位和存储耗时；先测负载与资源曲线，再决定优化哪一段，并保留前后对照 |

一个复杂 issue 可能提供并发、失败或瓶颈方面的素材，但完整叙事来自上述系统理解和实际工作；issue 数和 merge 数不能替代它。探索来源包括源码审查、trace、批量运行故障、性能剖析和新需求，社区 backlog 不决定进度。

目前已确认的原生资产和边界：

- Holmes `server.py` 有 `/api/chat`、SSE 响应及流结束后的存储/trace 清理；loop 有工具线程池；MCP 调用有按 server 的锁。这些适合追踪请求、并发和资源生命周期。
- Holmes `scheduled_prompts/executor.py` 有后台领取和执行任务；`supabase_dal.py` 有 claim、状态更新、事件存取和带 assignee 条件的结果发布。部分能力依赖启用 Supabase DAL 及外部 RPC；仅读客户端不能证明数据库端完整事务语义或本地可部署性，也不要求为讲故事引入这套平台。
- SREGym `main.py`、`results/resume.py` 已有多次 attempt、完成项续跑、超时和清理；`container_runner.py` 已有容器启动/停止；conductor 用 stage 和 generation 约束提交。不能再次把这些现成功能整体包装成自己的新设计。
- SREGym 已有 artifact 归档、ATIF 转换和可重建 SQLite 索引。当前 `traces/postprocess.py` 对无法转换的轨迹采取记录并跳过策略：对 benchmark 容错合理，但我们的训练导出需要另外确认覆盖率和完整性。这个需求不必修改官方诊断判分。

候选工作可沿三条线筛选：Holmes 运行时的可靠性和并发效率；实验/rollout 的管理与恢复；轨迹到训练数据的可追溯处理。每条都先明确已有能力、实际缺口和验收方法，再决定优化、新增或直接复用。

[#2365](https://github.com/HolmesGPT/holmesgpt/issues/2365) 保留为候选案例，不作为主线定义。API 查询仍 open，固定版本 `holmes/core/tools.py:660` 的脚本执行没有 timeout；`tool_calling_llm.py:1368` 创建线程池，取消检查在 `as_completed` 返回后发生。运行中的线程不会因 `Future.cancel()` 被终止，线程池上下文退出还会等待。可根据复现结果改善超时、取消与进程组回收，检查挂起请求、遗留进程和并发容量恢复。客户端超时不保证远端 MCP 操作停止，也不能对写操作统一无条件重试。

**Runner 可以成为有价值的后端模块，开发范围由当前评测需求驱动。**

它在 11 月前就可能有用：多个 harness 配置 × case × 重复实验需要追踪，长任务需要可取消/续跑，错误需要分类，轨迹需要进入训练数据。以后 RL 再复用其 episode 执行和数据边界。有没有必要新增模块，取决于这些需求与现有 runner 的实际差距，不必等到 RL，也不预先认定需要独立 HTTP 服务。

| 可能的新增需求 | 最小实现方向 | 能证明的价值 |
|---|---|---|
| 多配置实验可复现 | 配置快照/哈希、实验到 attempt 的关联，调用现有 runner | 可以追溯和重跑某次结果，避免混淆模型、harness、judge、环境版本 |
| 长任务取消和恢复 | 明确任务与 attempt 状态，复用上游取消/清理/续跑，补足跨进程中断的缺口 | 中断演练后完成项不重复计数、失败项有记录、环境恢复确认后再使用 |
| 多个独立环境的资源约束 | 有界调度，环境独占，模型 API 限流与反压 | 测得吞吐/等待与错误率的关系；只有真正需要多 worker 时才引入相应协调机制 |
| 结果与轨迹进入训练集 | 归档后校验、可重试转换、版本化数据清单、幂等导出 | 能发现“任务有分数但轨迹缺失”，重试不会把同一来源样本重复加入同一数据集 |
| 对接 RL trainer | 当前阶段固定执行/结果边界；后续增加策略版本、group、rollout 与奖励接入 | 同一执行和追踪链可以供评测与训练消费，不声称现已完成在线 RL |

首次实现可采用独立 Python 模块/CLI，复用现有结果文件与 SQLite 索引；若需要 durable task 状态，应与可随时重建的轨迹索引区分。大量原文保留为 artifact，小型结构化元数据便于查询。只有实际存在多个调用方、远程提交或跨进程控制需求，再增加 API/worker 服务；多主机多写者需求出现时再评估数据库与协调方式。

幂等要指定对象：创建任务、记录结果、导出样本可以设稳定键；LLM 生成不是确定性重放，故障注入/缓解也不能凭一个数据库唯一键保证 exactly-once。对结果不确定的旧 attempt 先核实和清理，确认环境健康后新建 attempt 重跑。先实现 episode 级恢复，不默认能从任意工具调用之后精确恢复 live 环境。

新增功能不要求虚构旧系统的性能缺陷。验收可以是“原来无法可靠完成的多配置运行或训练导出现在可以完成”，附中断/重复提交/坏样本等真实场景的验证；后续才在有基线时讨论性能收益。

**回退与简历表达：保留真实成果，区分继承、集成和原创。**

优先争取可证明的 harness 和后端改进；收益不稳定、复杂度大于用途的改动回退。即使多次探索没有正收益，也能保留原生功能的深入理解、可复现部署、benchmark 接入、可靠性验证、数据导出与取舍分析，不要求为了满足计划而硬留一项“优化”。

原生组件可以进入项目描述和面试讲解，但使用准确动词：读懂属于“分析/掌握”，真正跑过属于“复现/验证”，完成接入属于“集成/适配”，亲自改造或开发才属于“设计/实现/优化”。只阅读源码不能写成自己设计了完整系统；实际完成的集成项目可以讲清系统架构，以及哪些设计选择由自己作出。上游 PR 是额外背书。

简历可按实际成果选取多个条目：诊断系统与 benchmark 接入、harness 策略与消融、任务执行可靠性/并发优化、轨迹与训练数据管线，后期再增加训练方法与评测。缺少证据的条目合并或删除，不把同一改动拆成多项虚假贡献。

**评测如何支撑“确实有效”。**

先用少量 smoke case 确认环境，再用明确列出的原生相关子集与 Lite diagnosis 评估。当前 Lite 为 21 题，README 全量称 90 题；不要把这两个口径或历史版本混用。适合对外比较的配置保持 `profile=full`；`svelte` 改变观测面，不能混在同一结果表。

| 层面 | 建议保留的指标 |
|---|---|
| 任务质量 | 官方 diagnosis success；官方 composite score 另列，不混成同一个“准确率” |
| 成本 | 每个 attempt 的输入/输出/缓存 token、摘要和 verifier 成本、总耗时、工具调用数 |
| 执行可靠性 | tool timeout、取消耗时、基础设施错误、judge 错误、重复查询情况 |
| 改动归因 | baseline、各候选单项、选中组合，以及从最终组合移除关键模块的消融；同一 driver、模型、预算和 judge |

固定 agent/benchmark commit、模型标识、judge 模型与配置、prompt/skills/tool schema、预算、profile、suite、环境镜像和 memory 版本。SREGym 默认 judge 跟随 agent 模型，比较不同策略模型时尤其要显式固定 judge，避免裁判也变。

先每题每方案约 3 次了解方差，再对关键对照增加重复次数。按 case 成对比较、按故障/案例聚合不确定性，不把同一题的多次重跑当成完全独立的新题。21 题中单次多解一道约 4.8 个百分点，因此一两题波动不能当作稳定大幅提升。

多方向探索先在开发集筛选，记录失败和无收益尝试；最终组合再用未参与选型的保留集验证。反复试验后挑最高分会高估收益，不能把反复调过的 Lite 结果仍称作独立测试。无需穷举所有组件组合，优先测有机制依据的交互和关键消融。

基础设施错误、agent 失败、judge 故障分开保存；预先约定有效运行判据、重试上限，同时报告总尝试数与无效比例。超预算的 agent 不能被当作“环境失效”从分母删掉。并发实验须保持故障环境隔离：namespace 隔离对 node 级故障不足，不宜在同一被测集群上盲目并行。

用过的公开题可以作为 benchmark/regression 继续报告，但不能再声称对这些题完全未见。后训练的训练/开发/测试按故障家族、应用和变体父子关系划分；同一道题的成功轨迹、失败轨迹、改名/换负载变体必须在同一组。AIOpsLab、ITBench 与 SREGym 的任务存在来源重叠，跨仓库不自动等于跨分布。

不要预先承诺一定提高成功率。若质量相近而成本降低，也可能是有效工程改进，但需报告质量差异与不确定性；不能把“不显著”直接等同于“完全无损”。积极争取多项质量、效率、可靠性或新功能上的实质贡献；若优化实验没有成立，保留负结果和原生能力的复现/集成/验证成果，采用上述回退策略，不强行认定存在正收益。

**数据飞轮现在建立，优先完成真实导出与验证，按需求增加后端能力。**

SREGym 当前已有 `sregym/traces/convert.py`、`store.py`、`export.py`：ATIF 轨迹转换、可重建 SQLite 索引、runs/steps/tools 导出。先适配 Holmes 到这些现成能力；它们未必完整记录每次实际模型输入，不能直接假设具备训练所需全部字段。

保留原始事件/模型请求响应为事实来源，ATIF 作统一轨迹视图，训练样本作派生产物。先评估文件和现有索引能满足哪些需求；实验管理、恢复或并发数据处理出现明确缺口时，可以补充对应后端模块。以实际消费者和可靠性要求决定复杂度。

| 记录位置 | 最小必要内容 |
|---|---|
| episode manifest | schema version、run/attempt ID、case 与家族、split、各 commit/hash、模型/采样参数、预算、环境配置 |
| 每次模型请求 | **实际送入模型的 messages 与 tool schemas**，包括压缩、检索和注入后的内容；模型响应、finish reason、usage |
| 工具事件 | tool call ID、参数、结果原文或可持久读取的 artifact 引用、状态、开始结束时间；并行请求与结果的关联 |
| harness 状态变化 | 压缩前后映射、检索记忆/skill ID 与版本、停止原因、摘要来源 |
| 评测侧结果 | 官方 verdict、分维度分数、judge 版本、环境/评分故障；与模型可见内容分离 |
| 训练派生样本 | 来源 episode/step、teacher/student、训练方法、tokenizer/chat template 版本、loss mask、筛选原因 |

最容易导致返工的是只存“最终会话”。经过压缩后，最终历史无法重建每一步真实输入；把后面才得到的证据放回较早的训练 prompt 还会造成时间泄漏。大工具结果不能只存指向临时目录的路径，复位前要归档并记录哈希。摘要由另一个模型生成时也要单独记录来源和成本。

11 月前应完成一次小的导出验收：从真实成功/失败轨迹生成 SFT 样本、检查 tool call/result 配对和 assistant loss mask、确认没有测试题/评分真值串入 prompt。此时不必做大训练。失败轨迹不是直接正样本，需筛选有效片段、纠正后监督或构造可比较的偏好对。

历史 API 模型轨迹可用于蒸馏/SFT，不能直接视作未来学生策略的 on-policy GRPO 轨迹。RL 阶段再补 policy version、生成 token IDs、相应 mask、生成配置、奖励和 trainer 所需的 old logprobs 等；哪些能重算由所选训练器决定，不伪造历史字段。现在保留有效上下文和动作定义，已经能避免主要返工。目标应是“可演进的数据契约”，而不是不现实的“永远无需适配任何训练框架”。

**后训练路线与算力匹配。**

优先把同一个开放权重模型接入已有 Holmes harness，先确认它能正常调用工具且 baseline 不接近全零。API 模型可继续用于开发阶段或教师，不必为了未来训练而让 11 月工程结果受弱模型工具能力拖累。

| 阶段 | 推荐目标 | 资源判断 |
|---|---|---|
| 开放模型 baseline | 先从具备工具能力的 3B–8B 级模型实测 | 个人 24GB 卡适合量化推理与小规模验证；上下文/KV cache 仍受限 |
| SFT | 成功轨迹与纠正轨迹筛选，LoRA/QLoRA，先验证端到端收益 | 双 48GB 为 7B/8B 级提供较充足试验空间；更大模型与长上下文需 profiling |
| RL 入门 | 短 episode、较小 group size 的多轮工具策略优化 | 双 48GB 可作为小规模主资源，但不能仅凭显存保证吞吐或训练时长 |
| 扩展 | 更长 horizon、更大模型或更多并发环境 | 由稳定收益、队列与 A800 实际权限决定，不列为 4 月硬承诺 |

7B/8B 的权重显存不代表训练总显存；优化器、激活、rollout KV cache、reference/policy 布局都会改变容量。双卡还要明确用于两张训练卡，还是一张训练一张推理；不能同时把同两张卡重复计入所有角色。

RL 的主要风险可能是环境吞吐和数据多样性，未必是 GPU 数。粗略计算：live 环境小时数 ≈ 更新次数 × 每次任务数 × 每任务采样数 × 平均 episode 分钟数 / 60 / 真正独立的环境数，另计部署/复位和失败。例如 100 次更新 × 4 个任务 × 4 条采样 × 10 分钟，需要约 267 个环境小时，单环境约 11 天；这是算例，不是对 SREGym 耗时的实测。先测十几个 episode 的真实耗时再定训练规模。

训练起点可用官方终局诊断结果构建 reward，但这仍有 LLM judge 偏差；语法、工具有效性与成本约束可以补充，不能把奖励“多写证据、少调工具”当作过程正确性的保证。保留独立测试、抽查评分、检查奖励上升是否伴随真实任务成功。

训练前后都应回到 live benchmark 跑，至少区分：原始模型、原始模型+harness、SFT 模型+harness、SFT+RL 模型+harness。若要估计训练与 harness 的交互，再补训练模型+原生 harness。仅训练 loss 下降或 reward 曲线上升不够构成算法叙事。

到 2027 年 4 月，“高质量 SFT/蒸馏 + 数据消融 + 独立评测 + 一次可解释的 RL 实验”是合理目标；“完整 SREGym 全量在线 RL 稳定大幅涨分”不应作为求职成败前提。业务算法岗也不只问训练命令，还需要解释采样、奖励、泄漏、失败、效率和泛化。

**按交付阶段安排即可，不需要再建复杂 Gate 体系。**

| 时间 | 核心结果 | 控制范围 |
|---|---|---|
| 现在至 9 月底 | Holmes 相关原生 eval 跑通；SREGym 原生 agent 和 Holmes 各完成同一真实 case；保存第一份有效轨迹和评分 | 立即验证外部适配，不等全量原生评测；环境适配约一周仍无有效结果则收缩排错 |
| 10 月 | 由源码和失败分析驱动多轮 harness 试验；补足真实后端需求或优化已定位瓶颈；贯通轨迹导出 | 候选逐项验证再组合；上游已有能力优先复用，新增模块须有明确用途 |
| 11 月上旬至中旬 | 冻结有效组合、重跑关键对照及消融、整理多个有证据的简历条目和完整后端叙事 | 停止无证据的功能堆积；必要时回退原生方案，准确报告实际完成与验证范围 |
| 11 月中旬至 2027 年 1 月 | 投递并持续收集训练数据；开放模型 baseline 和 SFT | 求职与实习衔接，不把开始训练绑定在 offer 日期上 |
| 2027 年 1–3 月 | 有界的 agentic RL、训练/数据消融、held-out 评测 | 3 月形成稳定材料；A800 可加速但不作为必要条件 |

若 SREGym 接入不顺，优先继续 Holmes 原生相关评测、运行时理解及真实后端需求，保住 11 月交付；不要立刻再花两周串起另一套陌生环境。只有错误明确属于 SREGym 特有限制、且另一组合已有可跑证据时，才切换外部 benchmark。

面试叙事围绕同一条执行链组织：基于 HolmesGPT 做 Kubernetes 故障诊断并接入外部交互评测；依据 trace 和源码探索若干 harness 策略，通过对照选择最终组合；讲清诊断任务的边界、并发、状态/数据、失败处理、观测和瓶颈，展示实际做过的改进或新功能；轨迹可追溯地进入训练样本。到暑期再增加“同一模型训练前后在同一环境中的表现与成本”。上述都是待实际工作支撑的叙事结构，所有 X→Y 等真实实验后填入；无收益改动回退后，按实际复现、集成和验证成果表述。

旧项目的评测失效经验适合简短解释选型，不宜成为主体。主体应是这次已经完成的功能、你的具体修改、可复核证据以及你能解释的设计取舍。

**核实依据与版本。**

| 来源 | 固定 commit / 文件 | 支撑内容 |
|---|---|---|
| HolmesGPT | `3bd44edf04f9587c778ee8e9b244965190c40fdf` | loop、上下文、MCP、skills、eval、超时缺陷 |
| SREGym | `46c853db3a79332ea1c0ada076d888cec7a02f7e` | Lite 21 题、diagnosis、MCP、提交契约、judge、ATIF |
| AIOpsLab | `ccf08d0d1d5fa5b30f120e2e8549662d44411b35` | 框架无关 agent 接口和环境主循环 |
| AOI | `17c8f55a030e8850b93c9d16074c2976b6384619` | Observer/Evolver GRPO 的实际训练边界 |
| ITBench | `1e8647fc124ed168f11a4609c8f9498690d73e3c` | 完整 benchmark 有 live 场景，不能全部归为静态数据 |
| OpenSRE | `ae00def7729382fd9d8a0c95707331b1725ebcd3` | 当前 alpha、自身 harness、默认账号路径 |
| OpenRCA / 独立 Stratus | `c1bd4af7f635171a1c31cdd567c07d698dff6abc` / `4fc9a5b66bebbc5ddf2154c06e97f05db9385183` | 目录与 README 对照，未部署 |
| 私人节点 | 2026-09-19 SSH 只读快照 | CPU、RAM、GPU、磁盘与运行时 |
| 共享 4090 | 本地指南第 1、3、6、8–9 页 | 调度范围、个人配额、时限、显存示例、使用限制 |

关键一手链接：

- [Holmes Agent Loop](https://github.com/HolmesGPT/holmesgpt/blob/3bd44edf04f9587c778ee8e9b244965190c40fdf/holmes/core/tool_calling_llm.py#L1084)、[脚本执行](https://github.com/HolmesGPT/holmesgpt/blob/3bd44edf04f9587c778ee8e9b244965190c40fdf/holmes/core/tools.py#L660)、[上下文机制](https://github.com/HolmesGPT/holmesgpt/blob/3bd44edf04f9587c778ee8e9b244965190c40fdf/docs/reference/context-management.md)、[Skills](https://github.com/HolmesGPT/holmesgpt/blob/3bd44edf04f9587c778ee8e9b244965190c40fdf/docs/reference/skills.md)。
- [SREGym-Lite](https://github.com/SREGym/SREGym/blob/46c853db3a79332ea1c0ada076d888cec7a02f7e/docs/SREGym-Lite.md)、[MCP 路由](https://github.com/SREGym/SREGym/blob/46c853db3a79332ea1c0ada076d888cec7a02f7e/mcp_server/sregym_mcp_server.py)、[提交契约](https://github.com/SREGym/SREGym/blob/46c853db3a79332ea1c0ada076d888cec7a02f7e/sregym/conductor/conductor_api.py)、[诊断评分](https://github.com/SREGym/SREGym/blob/46c853db3a79332ea1c0ada076d888cec7a02f7e/sregym/conductor/oracles/llm_as_a_judge/llm_as_a_judge_oracle.py)、[轨迹存储](https://github.com/SREGym/SREGym/blob/46c853db3a79332ea1c0ada076d888cec7a02f7e/sregym/traces/store.py)。
- [AIOpsLab 接口](https://github.com/microsoft/AIOpsLab/blob/ccf08d0d1d5fa5b30f120e2e8549662d44411b35/aiopslab/orchestrator/orchestrator.py#L93)、[AOI Observer 训练](https://github.com/OpenEdgeHQ/aoi/blob/17c8f55a030e8850b93c9d16074c2976b6384619/grpo/observer/train_grpo.py)、[AOI 数据构造](https://github.com/OpenEdgeHQ/aoi/blob/17c8f55a030e8850b93c9d16074c2976b6384619/grpo/observer/data_loader.py)。
- [ITBench README](https://github.com/itbench-hub/ITBench/blob/1e8647fc124ed168f11a4609c8f9498690d73e3c/README.md)、[OpenSRE README](https://github.com/Tracer-Cloud/opensre/blob/ae00def7729382fd9d8a0c95707331b1725ebcd3/README.md)。
- 本次修订补读：[Holmes 服务入口](https://github.com/HolmesGPT/holmesgpt/blob/3bd44edf04f9587c778ee8e9b244965190c40fdf/server.py)、[后台执行器](https://github.com/HolmesGPT/holmesgpt/blob/3bd44edf04f9587c778ee8e9b244965190c40fdf/holmes/core/scheduled_prompts/executor.py)、[DAL](https://github.com/HolmesGPT/holmesgpt/blob/3bd44edf04f9587c778ee8e9b244965190c40fdf/holmes/core/supabase_dal.py)、[SREGym 主 runner](https://github.com/SREGym/SREGym/blob/46c853db3a79332ea1c0ada076d888cec7a02f7e/main.py)、[续跑判据](https://github.com/SREGym/SREGym/blob/46c853db3a79332ea1c0ada076d888cec7a02f7e/sregym/results/resume.py)、[轨迹后处理](https://github.com/SREGym/SREGym/blob/46c853db3a79332ea1c0ada076d888cec7a02f7e/sregym/traces/postprocess.py)。

本地 `.research/sources` 保存了上述关键源码快照与 metadata，`.research/resources` 保存 PDF 提取文本及个人节点的只读检查结果。原对话记录保留不改，本报告用于区分旧判断、当前事实和下一步待验证事项。
