# 评测工作区与代理 runner 可靠性修复

本轮冻结验证暴露两类可复现的工程故障：评测 checkout 创建的运行时符号链接被 Git 判定为未跟踪改动；临时 SSH 代理随终端会话结束，导致 self-hosted runner 无法完成 GitHub Actions 回报或下一次任务。

本次修复范围：

- 将 `bin` 和 `tools-venv` 标记为运行时路径，校验评测 checkout 的目标 SHA，并对受管符号链接执行幂等、目标一致性检查。
- 提供持久化的 runner proxy controller，记录 PID 和脱敏日志，确认 runner 进入 `Listening for Jobs` 后才返回，拒绝重复启动。
- 增加符号链接和进程存活检查的离线测试；不改变冻结实验的提交、镜像、清单、模型、预算或评分。

冻结验证中的已有环境失败继续单独记录，不能通过本修复改写为模型结果。
