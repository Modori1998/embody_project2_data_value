| 指标 | v0.1 | v0.2 | 说明 |
| --- | --- | --- | --- |
| JSON 可解析率 | 1.0 | 1.0 |  |
| Schema 合法率 | 0.9333 | 0.9333 | 各自按对应版本的 Schema 判定；v0.1 无 event_assessment 要求 |
| 帧引用合法率 | 1.0 | 1.0 |  |
| 非法帧引用数 | 0 | 0 |  |
| 跨段引用数 | 0 | 0 |  |
| 主要动作类别分布 | approach=9, grasp=6 | approach=5, grasp=6, idle=3, retract=1 |  |
| 声明式动作阶段比例 | 1.0 | 0.8 |  |
| grasp 阶段数 | 6 | 6 |  |
| closed 夹爪数 | 6 | 7 |  |
| grasp 与 closed 同时出现数 | 6 | 6 |  |
| closed→grasp 共变率 | 1.0 | 0.8571 |  |
| 非空事件比例 | 0.0667 | 0.8 |  |
| evidence_quality 分布 | sufficient=15 | sufficient=15 |  |
| motion_phase uncertain 率 | 0.0 | 0.0 |  |
| evidence_quality partial/insufficient 比例 | 0.0 | 0.0 |  |
| 整条标注完全弃权率 | 0.0 | 0.0 |  |
| event_assessment 分布 | NOT_APPLICABLE | event_visible=12, no_event_visible=3 | v0.1 无此字段 → NOT_APPLICABLE，不得跨版本当作同一指标比较 |
| event_visible 比例 | NOT_APPLICABLE | 0.8 |  |
| REVIEW_REQUIRED 比例 | 0.0667 | 0.4 |  |
| 冲突候选总数 | CANDIDATE=2, DETERMINISTIC=1 | CANDIDATE=4, DETERMINISTIC=4 |  |
| 截断次数 | 0 | 0 |  |
| 平均耗时 (s) | 2.817 | 4.516 |  |
| 显存峰值 (MiB) | 4838 | 4838 |  |
| 人工参考符合情况 | NOT_ESTIMABLE | NOT_ESTIMABLE | 无独立人工金标 → NOT_ESTIMABLE |
