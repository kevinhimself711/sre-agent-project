# Campaign evidence 导出计划

## 目标

把已完成 campaign 的关键可核查信息压缩成可提交的脱敏 evidence 包，供仓库审阅；完整轨迹继续留在忽略的运行目录。

## 本轮范围

- 修正 tool/review/request/prompt/result 的导出字段与时序关联。
- 增加 sealed 聚合导出模式。
- 在 campaign 收尾自动生成 `artifacts/publish/evidence/<campaign_id>/`。
- 增加合成 campaign 测试，覆盖失败格式、请求关联、截断和脱敏边界。
- 用现有已完成 campaign 生成首份 `evidence/diagnosis-20260921/` 并提交。
- 新增 `docs/STATUS.md` 作为审阅入口。

## 不在范围内

不做 vendoring、CI job、看板、数据库、原始轨迹入库或其他评测结构调整。

## 验收

- 根测试及新增 evidence 测试通过。
- 导出包只含 `attempts.jsonl`、`prompt.txt`、`manifest.json` 和必要聚合字段，不含请求全文或工具结果全文。
- `git diff --check`、脱敏检查通过；首份 evidence 可在干净 clone 后直接阅读。
