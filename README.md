# HolmesGPT × SREGym baseline

## GitHub 工程化与冻结实验

私有工程仓库：<https://github.com/kevinhimself711/sre-agent-project>。2026-09-19 baseline 独立提交为 `0e51e80`；本轮实施计划见 `docs/plans/2026-09-21-engineering-and-harness.md`。新增策略的实验结果见本轮报告，不能把 baseline 小样本结果当作策略收益。

根目录使用 Python 3.12 和 uv：`uv sync --frozen`，然后 `uv run pre-commit install`。本地检查入口为 `uv run pre-commit run --all-files` 和 `uv run pytest`。两个上游仍使用独立环境和锁文件；相关离线测试命令集中在 `scripts/ci_upstream.py`。`uv run python scripts/verify_patches.py --worktree` 验证本地改动均已存入补丁。

PR CI 在 GitHub Linux runner 重建固定上游并执行离线回归，不读取节点或模型凭据。`ci-gate` 汇总检查结果；四个需要真实 Node MCP 服务的 `everything_stdio` 测试不属于此离线子集。私有仓库当前账号不支持分支 rulesets，因此 CI 提供检查证据，尚无平台强制合并门禁。

真实评测通过 `Frozen diagnosis campaign` 手动工作流执行，仅允许 `main` 且要求同一 SHA 的 CI 成功。`dev` 为 24 次，之后 `validation` 搭配 `resume=true` 为 12 次；候选由冻结规则选择。工作流使用 pci-2 专用 runner，运行目录为 `~/sre-agent-eval/workspaces/<commit>`，与开发源码分开。依赖环境仅在锁文件一致时复用；模型上下文由对应源码和镜像运行，构建仍是节点环境打包，尚未声称可独立重建镜像。

当前网络下，在 Windows 启动持久代理 worker。进程与脱敏日志写入忽略的
`artifacts/`，终端或 Codex 回合结束不会断开正在运行的 workflow：

```powershell
uv run python scripts/runner_proxy.py start
uv run python scripts/runner_proxy.py status
# 冻结实验和产物上传全部结束后：
uv run python scripts/runner_proxy.py stop
```

代理 controller 会先确认 runner 已进入 `Listening for Jobs` 再返回；重复启动会拒绝创建第二个 runner。API key 由私有仓库 `BAILIAN_API_KEY` secret 注入，不放入命令或配置。模型与集群参数来自 `configs/baseline.env`，四种策略配置来自 `configs/campaign-20260921.json`。所有入口共享节点文件锁；中断后环境未恢复时拒绝启动下一题。

节点直接运行时，先设置 `SRE_PROJECT_ROOT`、`SRE_AGENT_IMAGE`，再 source 对应 `configs/baseline.env`，使用该工作区 `.venv/bin/python scripts/campaign.py --manifest configs/campaign-20260921.json --phase dev`；已有 campaign 必须显式添加 `--resume`。恢复仅在 episode 边界进行，不能重放结果不确定的提交。

每个 attempt 的原始证据、官方结果和验收位于工作区 `artifacts/campaigns/diagnosis-20260921/`；GitHub 仅上传汇总和产物哈希。使用 `uv run python scripts/collect_artifacts.py --remote-root <绝对工作区路径> --campaign --output artifacts/pci-2-campaign` 收集原始证据。冻结验证集不导出 SFT 样本，复核前草稿不作为正样本目标。

后续镜像 CD 才会从锁文件构建并发布 GHCR digest，本轮不自动部署其他集群。

本工程在固定上游版本上接入 Holmes 原生 Agent Loop 与 SREGym 官方 MCP、runner、diagnosis judge 和复位流程。实现范围是可复现 baseline 与轨迹闭环，本轮不声称 harness 提分，也不训练模型。

- 原始计划：`docs/plans/2026-09-19-baseline-bootstrap.md`。
- 实施报告：`docs/reports/2026-09-19-baseline-bootstrap.md`。本轮原生 2/2 通过；Holmes 外部 1/3 诊断成功，全部评分、复位与轨迹验收完成，导出 9 条 SFT 格式样本。
- 上游版本与开发分支：`configs/upstreams.json`；实现补丁：`patches/`。
- 本地代码：`repos/holmesgpt`、`repos/sregym`，各自保留 Git 历史；根仓库通过补丁保存改动。
- 运行节点：pci-2，`~/sre-agent-project`；四节点 KIND：`sre-agent-dev`。
- Agent 与 judge：百炼内地 `openai/qwen3.8-max`，`enable_thinking=false`，分别通过 AGENT/JUDGE 环境变量配置。
- 故障集群严格串行；两个外部 case 都属于开发集。

## 从固定源码重建

在新的工程目录运行 `python scripts/init_repos.py`。该脚本拒绝覆盖已有 checkout；下载受限时使用本机 Git 代理配置。修改 fork 后用 `python scripts/save_patches.py` 更新补丁，脚本只添加 intent-to-add，不提交或发布代码。

Linux 节点需要 Python 3.12、Docker、Helm、skopeo、Git，以及位于 `tools-venv` 的 uv / Poetry。`scripts/bootstrap_node.sh` 按上游锁文件分别安装两个环境。第一次初始化远端需先克隆两个固定版本、初始化 applications submodule，再同步补丁代码。

Windows 上 `python scripts/sync_workspace.py` 同步本轮修改、脚本和非敏感配置。SSH 凭据由忽略的 `docs/Computing Resources/pci-2 info.txt` 读取；API key 由忽略的 `Bailian API.txt` 读取，`remote.py --bailian` 通过 SSH stdin 注入运行环境。不要将这些文件放入 Git。

## 独立集群与网络

所有操作先 `source ~/sre-agent-project/configs/baseline.env`，检查 context 为 `kind-sre-agent-dev`。`SREGYM_ADMIN_KUBECONFIG` 单独指定宿主管理员配置，agent 仅使用过滤代理。既有 k3s 和其他容器不属于本项目。

pci-2 是 cgroup v1 / Docker cgroupfs；`scripts/generate_kind_config.py` 从上游四节点配置生成 cgroupfs 兼容配置，避免修改宿主 cgroup 或重启 Docker。用 `scripts/create_cluster.sh` 创建集群，Calico 固定 v3.27.0。inotify 要求：`max_user_instances=1024`、`max_user_watches=1048576`；本次只调整运行时，重启后需核实。

Docker Hub 在节点上不可直连。运行部署时可另开 `remote.py --proxy` 会话执行 `warm_cluster_images.py`，通过 SSH 临时转发本机 `127.0.0.1:7897` 代理下载并导入镜像。脚本限时 30 分钟、下载并发 3、空闲 3 分钟退出；不能把代理下载等待算作 Agent 推理时间。GHCR 使用 kubelet 原生拉取。镜像缓存位于忽略的 `artifacts/images/`。

环境验证：`python3 scripts/check_network_policy.py`，验证正常连通、策略阻断、删除策略后恢复，并删除探测 namespace。

Social Network 的两个上游 init container 还会在线克隆 DeathStarBench。当前网络下，等 `media-frontend` / `nginx-thrift` deployment 创建后、故障注入前，在另一个终端运行下列命令。它只给这两个 init container 配置临时代理，固定源码为 `configs/baseline.env` 记录的 commit；初始化完成后监听关闭，不修改 agent 网络权限：

```powershell
python scripts/remote.py --proxy run 'source "$HOME/sre-agent-project/configs/baseline.env"; python3 "$HOME/sre-agent-project/scripts/bootstrap_social_proxy.py"'
```

## 执行固定小规模实验

远端项目根目录下构建一次 agent 镜像：`python3 scripts/build_agent_image.py`。镜像基于固定 SREGym base，Holmes 使用 `/opt/holmes/.venv`，保留上游 Stratus 环境；每次运行前记录镜像 ID 与源码哈希。

Windows 启动方式（每个命令独立运行，确认前一轮官方清理完成后再执行下一条）：

```powershell
python scripts/remote.py --proxy --bailian run 'bash "$HOME/sre-agent-project/scripts/run_native_evals.sh"'
python scripts/remote.py --proxy --bailian run 'bash "$HOME/sre-agent-project/scripts/run_benchmark.sh" stratus network_policy_block 1'
python scripts/remote.py --proxy --bailian run 'bash "$HOME/sre-agent-project/scripts/run_benchmark.sh" holmes network_policy_block 2'
python scripts/remote.py --proxy --bailian run 'bash "$HOME/sre-agent-project/scripts/run_benchmark.sh" holmes wrong_service_selector_social_network 1'
```

配置固定 full profile、diagnosis only、agent 超时 1800 秒、Holmes 30 steps / 每次输出上限 8192。runner 沿用上游有界部署重试。API 接受提交、进程退出或日志显示 complete 均不能代替官方 `Diagnosis.success` / `composite_score`。

## 轨迹、评分与训练格式

Holmes 的记录 hook 默认关闭，仅 driver 设置 `HOLMES_EPISODE_TRACE` 时写 JSONL。记录位置是传入 LiteLLM 的有效请求边界，包含消息、工具 schema、响应、usage、工具结果和耗时；不是 provider 网络报文抓包。摘要/压缩调用同样记录，streaming 无法完整捕获时明确标记不完整。

driver 禁用所有内置工具和跨进程工具状态缓存，仅允许官方 kubectl / Prometheus / Loki / Jaeger MCP；每次 attempt 使用独立会话。driver 负责单次提交，响应丢失只核实状态，不重复 POST。

原始日志是事实来源。ATIF 转换、SQLite 索引和导出复用上游；官方评分仍在宿主结果文件中，不能输入后续模型上下文。清理失败时不继续复用环境。

在远端 `repos/sregym` 下使用其 `.venv/bin/python`：

```bash
python -m sregym.traces.holmes_export results/<batch>/holmes
python -m sregym.traces.store --db results/traces.db ingest results/<batch>
python -m sregym.traces.store --db results/traces.db list
python -m sregym.traces.export --db results/traces.db --out-dir ../../artifacts/trace-export
```

严格验收输出 `data-acceptance.json`、附件哈希清单和 `sft-format-samples.jsonl`。缺消息、缺工具结果、缺附件或未完成运行会使验收失败。只有官方诊断成功且数据完整的轨迹导出正样本；失败轨迹原样保留。SFT 样本保存每次真实上下文和仅监督本次 assistant 的 message mask，tokenizer/chat template 留待选定训练模型后处理，目前仅用于格式验证。

用 `python scripts/collect_artifacts.py` 下载结果与运行日志到本地忽略的 `artifacts/pci-2/`；脚本拒绝下载包含已知 API key / SSH 密码的文件，跳过镜像与构建目录。费用未取得账单时必须记为未知，不能用零费用替代。
