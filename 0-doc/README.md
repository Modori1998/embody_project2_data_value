# Project 2 文档索引与 Drive 同步策略

本目录按文档职责和同步策略分层。不要把 `0-doc` 整目录无差别同步到 Google Drive。

## 1. 根目录：项目权威设计（默认同步）

以下三份文档共同构成 Project 2 的长期权威设计集，代码也依赖这些稳定路径：

| 文档 | 职责 | Drive 策略 |
| --- | --- | --- |
| `Project_2_Engineering_Design_Master_v1_20260914.md` | Engineering SSOT；工程契约、架构、Design Gate 与状态 | **默认同步并维护** |
| `Project2_Development_Roadmap_and_Design_Gate_Plan_v1_20260914.md` | Roadmap / Execution Authority；阶段顺序、验收点与执行边界 | **默认同步并维护** |
| `02_robot_demonstration_mining_autolabel_design.md` | 面向讨论的完整可读设计 | **默认同步并维护** |

这三份文件留在根目录，不移动，以保持 `src/project2_g1/paths.py` 和现有运行报告中的路径契约稳定。

## 2. `10-design-review/`：当前待评审方案（评审期同步）

这里存放尚未冻结、需要网页端 AI 或 Design Owner 讨论和拍板的设计稿。

当前文档：

- `Project2_G1_P3_Calibration_Design_DRAFT_v1_20260917.md`

Drive 策略：**同步当前活跃 DRAFT**。冻结后，应把结论回写到 Engineering Master / Roadmap；该 Draft 可转入历史归档，不应长期与 Master 竞争权威。

## 3. `80-audit-local/`：审计证据（默认不同步）

这里存放事实核查、结构审计、误差归因和 lineage 证据。它们用于证明结论从哪里来，不是新的项目方案或长期权威设计。

Drive 策略：**默认不同步**。仅当网页端 AI 需要复核某个争议事实、定位错误或审查证据链时，按需附上相关单篇，不要整组上传。

当前文档：

- `Project2_G1_Audit_Web_Local_Structure_Audit_20260916.md`
- `Project2_G1_Final_Boundary_Merged_Semantics_Audit_20260917.md`
- `Project2_G1_Human_Review_Error_Attribution_Audit_20260917.md`

其中 Error Attribution Audit 是当前 G1-P3 Draft 的关键输入；评审 P3 时若仅凭 Draft 无法判断，可将它作为唯一优先补充证据。

## 4. `90-implementation-local/`：实施结果与变更记录（不同步）

这里存放批次实现结果、UI patch、语义物化结果和实现级映射。它们记录“做了什么、测了什么”，不是让网页端 AI 重新设计方案的主要上下文。

Drive 策略：**不默认同步**。只有在排查实现与冻结设计是否一致、或需要复现某次变更时，才按问题选择对应单篇。

当前文档：

- `Project2_G1_Audit_Web_Implementation_Batch1_Result_20260916.md`
- `Project2_G1_Audit_Web_Implementation_Batch2_Result_20260916.md`
- `Project2_G1_Audit_Web_P1_Layout_Patch_Result_20260917.md`
- `Project2_G1_Final_Boundary_Semantic_Materialization_Result_20260917.md`
- `Project2_G1_P1_Signal_Subplot_Review_Mapping_20260917.md`

## 5. 给网页端 AI 的最小上下文包

一般方案设计或评审只提供：

1. Engineering Master；
2. Roadmap；
3. Readable Design；
4. 当前 `10-design-review/` 中与问题直接相关的 Draft。

只有出现事实争议时才追加 `80-audit-local/` 的一篇相关证据；只有出现设计与代码不一致时才追加 `90-implementation-local/` 的一篇相关实施记录。

## 6. 新文档落位规则

- 改变长期工程契约或 Gate：更新根目录权威文档，不另造平行 SSOT。
- 尚待拍板的方案：放 `10-design-review/`。
- 只读核查、数据证据、归因结论：放 `80-audit-local/`。
- 实现批次、patch、测试和迁移结果：放 `90-implementation-local/`。
- 运行时自动生成的大体量报告：优先留在 `outputs/`，不要复制进 `0-doc`。
