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
