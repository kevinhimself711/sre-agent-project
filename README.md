# HolmesGPT × SREGym baseline

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
