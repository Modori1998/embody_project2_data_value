# Project 2 G1 Audit Web — Implementation Batch 1 Result

```text
DATE = 2026-09-16
BATCH = Phase 0–3 only
CONTRACT = P2_G1_AUDIT_FOLDER_V1
DESIGN_SOURCE_MISSING = RESOLVED
G1_AUDIT_WEB_BATCH1 = PASS_READY_FOR_USER_TRIAL
MANDATORY_STOP = YES
```

本批次实现 Versioned G1 Audit Run Contract、Registry + Validator、M07 media/proxy 复用、只读 Single Run Episode View。未实现 Human Review persistence / Batch 2 / G1-P3。

---

## 1. Drive Authority

| 项 | 值 |
| --- | --- |
| Drive file found | YES |
| title | `Project2_G1_Human_Audit_Web_Design_FROZEN_v1_20260916.md` |
| fileId | `1v6ZtopYFfCIWG9kjCOmwJe2C-XWB4xRR` |
| created/modified | `2026-09-16T13:10:39Z` |
| Document status | **FROZEN v1.0** |
| Contract | **P2_G1_AUDIT_FOLDER_V1** |

与此前已读 Master / Roadmap / Readable Design 无冲突：G1-A/B/C/D FROZEN；P2 EXPLORATORY_ONLY；P3 BLOCKED_BY_HUMAN_GT；Web 不调参。

已重点核对：Versioned Audit Run、Run Identity、Config Hash、Signal Contract Identity、Episode/Boundary Identity、Calibration/Evaluation Set Identity、Audit Folder Contract、Run Registry、Human Review SSOT（本批次不实现 persistence）、M07 Reuse Matrix、v1 Implementation Order（Phase 0–3 后 STOP）。

---

## 2. Versioned Bootstrap Run

```text
run_id = g1_exploratory_audit_20260916_214523_1ba11d9d
run_root = outputs/g1_audit_runs/g1_exploratory_audit_20260916_214523_1ba11d9d
run_stage = EXPLORATORY_AUDIT
set_role = EXPLORATORY
parent_run_id = null
episode_count = 6
contract_version = P2_G1_AUDIT_FOLDER_V1
config_version = g1_p2_exploratory_segmentation.v0
config_hash = dde590e759a31cb8c865369e18256ebecbbd01bc94a58e1d3ca695bb50f2a630
signal_contract_version = g1_p1_signal_contract.v0
signal_contract_hash = 24c62aef1f7bdbd14f0c1a075e8ecaafa762d4bcce454ad25842d54a2f34232d
```

Episode 顺序（manifest）：`data/demo_0`, `data/demo_32`, `data/demo_179`, `data/demo_278`, `data/demo_242`, `data/demo_230`。

媒体路径为 run-root-relative，例如 `media/demo_0/video.mp4`。

---

## 3. Legacy Immutability

```text
outputs/g1_p2_boundary_audit
file_count = 42
tree_fingerprint = 9f22745ca60b6840d6a1844f35cfb3a93dbd229b72d5b4d5ee141312ed16d067
before == after
LEGACY_G1_P2_OUTPUT_UNCHANGED = PASS
```

`demo_v15.hdf5` / `low_dim_v15.hdf5`：本批次无写路径，READ ONLY。

未修改 `src/project2_g1` Detector / Signal / Boundary 逻辑，未改 threshold。

---

## 4. Tests

```text
python -m unittest discover -s tests -p "test_g1_audit_web*.py" -v
Ran 18 tests
OK
```

| Gate | 结果 |
| --- | --- |
| Contract valid / wrong version / duplicate / missing plot / path escape / hash mismatch | PASS |
| Hash key-order stable / threshold change | PASS |
| Registry once / duplicate blocked / DISABLED_BY_OWNER / restore / generator registry untouched | PASS |
| 6-episode view / tables / Range 206 / path traversal / proxy identity | PASS |
| Real legacy bootstrap unchanged | PASS |
| Real mp4v → H264_BROWSER_V1 reuse | PASS |

---

## 5. Browser Trial

本地服务：`http://127.0.0.1:8766/`

已验证：

- 首页列出 bootstrap run，契约 `P2_G1_AUDIT_FOLDER_V1`
- Episode 页 `data/demo_0` / `data/demo_32`，队列 6 条
- EXPLORATORY_ONLY 横幅
- Signal Boundary Plot + P1 signal_plot 200
- demo_32 表：candidate=6 / final=3 / decision=6 / segment=4
- video `preload=none`，`needs_proxy=true`，URL = `H264_BROWSER_V1` content-addressed proxy
- proxy Range `bytes=0-15` → **206**，对象大小 52877
- Save / Save & Next / P1 / P2 review 控件禁用

```text
BROWSER_TRIAL = PASS
```

人工点击播放解码未在本环境强制执行；proxy 生成与 Range 已实测。

---

## 6. Local Start Commands

```text
python scripts/bootstrap_g1_legacy_audit_run.py
python scripts/run_g1_audit_web.py
```

默认 `127.0.0.1:8766`。打开后检查：Run 选择、Episode Queue、Video、Signal Plot、Boundary/Candidate/Decision/Segment、中文 CODE｜解释。

---

## 7. Explicit Non-Goals (Batch 1)

未实现：P1/P2 Human Review persistence、SQLite G1 review tables、Add Missed Boundary persistence、Human Calibration Export、G1-P3、Calibration Run vN+1、Evaluation Guard、threshold tuning。

---

## 8. Code Added

新包 `src/project2_g1_audit_web/`：hashes / contract / registry / bootstrap / media adapter / video proxy adapter / view / vocab / FastAPI app / Jinja templates。

CLI：`scripts/bootstrap_g1_legacy_audit_run.py`、`scripts/run_g1_audit_web.py`。

测试：`tests/test_g1_audit_web_*.py`。
