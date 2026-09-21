# Social Network 初始化链路收尾计划

冻结验证已完成，运行证据表明 Social Network 的主要环境失败来自 DeathStarBench 全量 Git clone 经临时 SSH 代理时的连接中断，而非故障注入、Agent 或 judge。实验期间使用同一固定 revision 的 GitHub source archive 恢复了后续初始化。

本次实验后工程修正范围：

- init container 改为下载并解压固定 commit 的 source archive，保留原有复制目标和源码 revision。
- 临时 TCP 转发在空闲窗口继续等待，不主动截断仍可能继续传输的连接。
- Deployment 必须连续多次满足当前 generation 的完整 rollout 条件后才关闭代理，规避状态短暂陈旧导致的过早退出。
- 增加纯离线测试覆盖命令改写、未知命令拒绝和稳定 rollout 判定。

此修正不回写已冻结的 36 条有效实验结果，也不改变 Agent 工具权限、模型、预算、故障注入或评分。验证结果在实施报告中单列为实验后工程修正。
