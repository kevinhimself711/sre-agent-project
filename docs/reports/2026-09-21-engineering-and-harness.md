# GitHub 工程化与 Harness 实验实施报告

状态：实施中；以下阶段事实随验收补充，不代表 36 次实验已经完成。

## 已完成的工程工作

- 创建并验证私有仓库 `kevinhimself711/sre-agent-project`，baseline 保留为 `0e51e80`。私人算力资料、调研对话、凭据和原始轨迹不入库。
- 根目录独立 uv 环境、pre-commit、Ruff、ShellCheck、actionlint、Gitleaks 与补丁完整性检查已运行通过。GitHub Actions 在干净 checkout 重建固定源码，使用上游锁文件执行回归。
- GitHub CI `35579104464` 在 `c6b4839` 上成功；先前一次因 Poetry 继承根目录虚拟环境而失败，已显式隔离修复。后续运行结果以最终提交核验为准。
- 2026-09-21 pci-2 上 Holmes hook 子集 `--no-cov -n 0` 为 5 passed，退出码 0。Harness/MCP/loop 子集为 162 passed、4 deselected；被排除的是需要 Node 服务的 `everything_stdio` 测试。SREGym 轨迹与相关配置隔离回归为 302 passed。
- 根目录 campaign 回归当前 12 passed，覆盖确定性规模、独占锁、中断恢复、完成项去重、复位失败、重试上限、Agent 超时和冻结版本检查。测试数按套件分别报告，不合计为不重复测试数。
- 私有仓库 rulesets API 返回 403，要求 GitHub Pro 或公开仓库；没有升级套餐或更改可见性，因此尚无平台强制分支规则。
- pci-2 已注册仓库专用 runner。受限网络下通过临时 SSH 代理运行单次 worker；工作流使用独立提交目录，不覆盖开发 checkout。当前镜像仍复用节点环境，不是完全独立的供应链构建。

## 实现与边界

诊断复核在原生 loop 第一次正常收口时触发一次，所有新增调查均占用原有步数预算。MCP 恢复在既有结果转换层按 toolset 规则识别 Command Rejected，保留原文并明确错误与提示；不自动重放命令，不调整 benchmark 权限。

campaign 是上游 runner 外的一层有限实验编排，复用原有部署、判分、归档与清理。宿主文件锁同时覆盖手动入口和 workflow；状态不明确时不重放最终提交。官方成功、执行/评分故障和数据完整性独立记录；超预算 Agent 计入失败。

所有测试与部署排错记录保留；实验结果尚待补充。镜像 CD、长期记忆、SFT/RL 不属于本轮交付。

## 手动工作流实际验收

- PR #1 工程化配置已合并；`637d5e6` 的首次评测工作流在源码重建阶段失败，尚未调用模型或创建正式实验 attempt。原因是缓存 checkout 已有同名 baseline 分支，随后节点验证还发现浅克隆不能用作 Git reference。两项修正经完整 CI 后在 PR #4 合并。
- 本轮实验固定项目提交 `f86969a784f939a2a75f1eb42aa8514a81ff2108`，对应 CI `35581916746` 全部成功。开发工作流 `35582115092` 已实际完成独立源码重建、镜像构建及两个原生 smoke case（2 passed，287 deselected，退出码 0）。
- 冻结镜像为 `sha256:6c9300e43e1fcee42535b65138fea6ff592f41b8ce1f388f662cfaafbf674c76`。续跑和验证阶段复用该镜像，若镜像 ID 或源码 commit 不符则拒绝重建，防止阶段间版本漂移。
- 正式实验正在运行。中途审计观察到 kubectl 的管道及 RBAC 拒绝在 recovery 中被正确标为 ERROR，而 baseline 仍返回 SUCCESS；这只证明错误语义差异，不等于诊断提分。

## 运行期间发现的互斥边界

额外的 Linux 进程测试复现：强制终止 supervisor 后，原实现会释放文件锁，但其评测子进程仍可存活。修正在启动子进程时继承同一 flock 文件描述符，让存活的评测进程继续持有锁。原行为的对照测试失败，修正后通过；测试只使用临时锁与模拟进程，不操作 Kubernetes。

此修正在独立分支完成，未替换正在运行的冻结实验版本。报告会明确区分实验版本与最终工程修正；本轮实际运行没有通过强杀 supervisor 测试故障集群。
