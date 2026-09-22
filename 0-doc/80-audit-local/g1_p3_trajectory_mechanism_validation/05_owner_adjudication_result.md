# G1-P3 Owner Adjudication Result

**Trajectory Mechanism Validation — DESIGN_DIAGNOSTIC evidence freeze**

---

## 1. Document Status

| Field | Value |
| --- | --- |
| Document | `05_owner_adjudication_result.md` |
| Role | `POST_UNBLIND_EVIDENCE` — official result record for the G1-P3 DESIGN_DIAGNOSTIC set |
| Status | `FROZEN` |
| Run | `g1_design_diagnostic_20260922_135647_69bf2a94` |
| Run stage | `DESIGN_DIAGNOSTIC` |
| Diagnostic set | 20 events / 20 episodes / 10 pairs / Arm A 10 + Arm B 10 |
| Companion history | `05_review_history.csv` (complete append-only review history) |
| Detector | `DETECTOR_MODIFIED = NO` |
| Protocol | `PROTOCOL_PATCH_CREATED = NO` |
| Evaluation set | `EVALUATION_TOUCHED = NO` |

This document freezes two things that must not be re-derived later:

1. the **complete** human review history of the 20 diagnostic boundaries —
   the first blinded review *and* the later owner unblinded adjudication, with
   every intermediate revision preserved;
2. the resulting **two** readouts: the blinded one (as originally reviewed,
   before any unblinding) and the final owner-adjudicated one (the current
   state of the review database).

Both are reported. Neither replaces the other. The blinded readout is the one
that was actually produced under blinding and is therefore the only readout
that speaks to whether the frozen gate would have passed *blind*. The final
readout is the owner's considered judgement *after* the arm/P12/C12 structure
was revealed, and is the state from which the next gate proceeds.

---

## 2. Evidence Sources

All hashes are SHA256 over the file bytes as frozen at this commit.

| # | Source | Path | SHA256 |
| --- | --- | --- | --- |
| 1 | Frozen design | `0-doc/10-design-review/Project2_G1_P3_Trajectory_Mechanism_Validation_Design_FROZEN_v1_20260921.md` | `05f9a9ca8219a0a135027d97cc6091b74f603cdbd5961da4f28e3053d37fbc23` |
| 2 | Internal selection | `0-doc/80-audit-local/g1_p3_trajectory_mechanism_validation/02_selection_internal.csv` | `7588a0650bdf75493d2eec3780fb0e0a7ce6b3a64af667db827faf305473d9f8` |
| 3 | Blinded selection | `0-doc/80-audit-local/g1_p3_trajectory_mechanism_validation/03_selection_blinded.csv` | `bfa63c28c22050a0d9ba64e55e5c9a412ad8be87145322f08f370cde7f86aaee` |
| 4 | P2 review audit export | `0-doc/80-audit-local/g1_p3_trajectory_mechanism_validation/04_p2_review_audit.csv` | `173f12bfa45f38b61b8bb3c2a08ec0c62b77b8ce384bcbe96067e131cb3397ed` |
| 5 | P2 review audit meta | `0-doc/80-audit-local/g1_p3_trajectory_mechanism_validation/04_p2_review_audit_meta.json` | `3b675de2d4ad51ce90f987306256257f73e6de52b20274bcb6d1aabb890cd313` |
| 6 | **Review history (new)** | `0-doc/80-audit-local/g1_p3_trajectory_mechanism_validation/05_review_history.csv` | `3315f84314ef91974f5882bcbe647bcbbd4789917a3d8486256149faad482659` |
| 7 | Production owner review DB | `outputs/g1_audit_web/g1_audit_web_owner.sqlite3` | `83e32b075f6d94ca117ad930a563e1152bb446174a1a84e7870a774978a39430` |

Source 7 lives under `outputs/`, which is **not** version-controlled. Source 6 is
therefore the frozen, reviewable projection of the append-only history and is
the authoritative artifact for this gate. It is deterministically rebuildable
from sources 2 and 7 (see §7).

### 2.1 Universe validation

Read from `02_selection_internal.csv` and cross-checked against the review
database:

```text
EVENT_COUNT              = 20
DISTINCT_EPISODE_COUNT   = 20
PAIR_COUNT               = 10
ARM_A_COUNT              = 10
ARM_B_COUNT              = 10
```

The 20 `(episode_id, boundary_id)` join keys match the reviewed boundaries
20/20 exactly. There is no fuzzy match, no missing event, no duplicate key, no
frame mismatch and no boundary mismatch.

---

## 3. First Blinded Review

This is the readout as it stood **before unblinding** — the earliest
`FIRST_BLINDED_REVIEW` revision (`reviewer = DESIGN_OWNER`) per event. This is
the state the frozen gate would have been evaluated against had the process
stopped at blinding.

### 3.1 Readout

| Arm | Cohort | Reviewed | REDUNDANT | Rate | MISALIGNED |
| --- | --- | --- | --- | --- | --- |
| A | `LOW_C12_QUARTILE_EPISODE_DIVERSE_TARGET` | 10 | 1 | 10.0% | 0 |
| B | `HIGH_C12_QUARTILE_MIN_MATCH_DISTANCE_CONTROL` | 10 | 1 | 10.0% | 0 |

Arm A REDUNDANT event: `data/demo_208` @116 (`demo_208-B0006`).
Arm B REDUNDANT event: `data/demo_296` @73 (`demo_296-B0002`).

`REDUNDANT_RATE_ARM_A = 0.10`, `REDUNDANT_RATE_ARM_B = 0.10`. The difference is
`0.00`, and `REDUNDANT_RATE_ARM_A <= REDUNDANT_RATE_ARM_B` holds.

### 3.2 Frozen gate evaluation

| Gate item | Requirement | Observed | Verdict |
| --- | --- | --- | --- |
| `N_ARM_A >= 8` | 8 | 10 | PASS |
| `N_ARM_B >= 8` | 8 | 10 | PASS |
| `REDUNDANT_RATE_ARM_A >= 2.0 * REDUNDANT_RATE_ARM_B` | >= 0.20 | 0.10 | FAIL |
| `REDUNDANT_RATE_ARM_A - REDUNDANT_RATE_ARM_B >= 0.25` | >= 0.25 | 0.00 | FAIL |
| `ARM_A_REDUNDANT_DISTINCT_EPISODES >= 3` | 3 | 1 | FAIL |

### 3.3 Result

```text
BLINDED_GATE_RESULT =
NOT_SUPPORTED_AS_GENERAL_ACCEPTANCE_COMPONENT
```

This result is **permanently preserved**. It is not superseded by the owner
adjudication in §4; it records what blinding actually produced. Note that the
`NOT_SUPPORTED` trigger in design §15 is met independently of the three failing
SUPPORTED items: `REDUNDANT_RATE_ARM_A <= REDUNDANT_RATE_ARM_B` is true.

---

## 4. Owner Unblinded Adjudication

After unblinding, the Design Owner re-adjudicated the four events listed in
`TASK = SUBMIT_G1_P3_OWNER_UNBLINDED_FINAL_ADJUDICATION`. Each was submitted
through the existing append-only Web review path with reviewer
`DESIGN_OWNER_UNBLINDED`, producing revisions `review_id` 93–96.

### 4.1 Adjudicated changes

| Event | Episode | Boundary | Frame | First blind | Owner adjudication | Reason code | review_id |
| --- | --- | --- | --- | --- | --- | --- | --- |
| `G1P3-DIAG-009` | `data/demo_211` | `demo_211-B0007` | 169 | VALID | **REDUNDANT** | `REDUNDANT_DIRECTION_JITTER` | 78 → 93 |
| `G1P3-DIAG-011` | `data/demo_217` | `demo_217-B0027` | 518 | VALID | **REDUNDANT** | `REDUNDANT_DIRECTION_JITTER` | 80 → 94 |
| `G1P3-DIAG-012` | `data/demo_220` | `demo_220-B0007` | 238 | VALID | **REDUNDANT** | `REDUNDANT_DIRECTION_JITTER` | 81 → 95 |
| `G1P3-DIAG-016` | `data/demo_296` | `demo_296-B0002` | 73 | REDUNDANT | **VALID** | — | 85 → 96 |

All four are Arm A except `demo_296` (Arm B). The three `VALID → REDUNDANT`
moves strengthen Arm A; the one `REDUNDANT → VALID` move removes Arm B's only
REDUNDANT event.

### 4.2 Intermediate revisions — recorded, not hidden

The adjudication was **not** a single blind-to-final step. Before the owner
unblinded adjudication, the owner had already re-reviewed three of the four
events through the **blind** page, producing intermediate revisions that carry
the same content as the subsequent owner adjudication. These are preserved
verbatim in `05_review_history.csv` and are reproduced here so that the history
cannot be mistaken for a clean two-step transition:

| Event | Episode | review_id | Reviewer | reviewed_at | Decision | Reason code | Note |
| --- | --- | --- | --- | --- | --- | --- | --- |
| `G1P3-DIAG-016` | `data/demo_296` | 90 | `DESIGN_OWNER` | 2026-09-22T20:24:32 | VALID | — | Intermediate blind-page edit; content identical to the later owner adjudication |
| `G1P3-DIAG-011` | `data/demo_217` | 91 | `DESIGN_OWNER` | 2026-09-22T20:30:26 | REDUNDANT | `REDUNDANT_DIRECTION_JITTER` | Intermediate blind-page edit; content identical to the later owner adjudication |
| `G1P3-DIAG-012` | `data/demo_220` | 92 | `DESIGN_OWNER` | 2026-09-22T20:30:50 | REDUNDANT | `REDUNDANT_DIRECTION_JITTER` | Intermediate blind-page edit; content identical to the later owner adjudication |

Two consequences are recorded explicitly:

* The first blinded review of `demo_296` was REDUNDANT (revision 85). The
  blinded readout in §3 therefore counts `demo_296` as Arm B REDUNDANT. Had the
  blinded readout been computed from the *later* `DESIGN_OWNER` revision 90
  instead, Arm B would have shown 0/10. **The blinded readout uses the earliest
  revision (85), not revision 90.** The distinction matters and is stated here
  so it cannot be silently collapsed.
* Because the review store's no-op rule only suppresses a write when the
  *same* reviewer resubmits identical content, the four `DESIGN_OWNER_UNBLINDED`
  submissions each inserted a new row even where the content matched an
  existing `DESIGN_OWNER` row. No revision was overwritten or deleted.

### 4.3 Append-only integrity

Verified by row-by-row comparison against a pre-write backup of the review
database taken before the adjudication and stored outside the project tree:

```text
REVISIONS_ADDED          = 4          (review_id 93, 94, 95, 96)
ROWS_REMOVED             = none
PRE_EXISTING_ROWS_ALTERED= none
OTHER_16_EVENTS_UNCHANGED= 16/16
FIRST_BLIND_REVISIONS    = 78, 80, 81, 85 preserved verbatim
```

The other 16 events were not touched. No `UPDATE`, no `DELETE`, no `VACUUM`, no
manual history rewrite was performed.

---

## 5. Final Current-State Readout

This is the current state of the review database — the highest `review_id` per
event — i.e. the owner-adjudicated result.

### 5.1 Readout

| Arm | Cohort | Reviewed | REDUNDANT | Rate | MISALIGNED |
| --- | --- | --- | --- | --- | --- |
| A | `LOW_C12_QUARTILE_EPISODE_DIVERSE_TARGET` | 10 | 4 | 40.0% | 0 |
| B | `HIGH_C12_QUARTILE_MIN_MATCH_DISTANCE_CONTROL` | 10 | 0 | 0.0% | 0 |

Arm A REDUNDANT events (4, over 4 distinct episodes):

```text
data/demo_208  @116  demo_208-B0006
data/demo_211  @169  demo_211-B0007
data/demo_217  @518  demo_217-B0027
data/demo_220  @238  demo_220-B0007
```

Arm B REDUNDANT events: **none**.

`REDUNDANT_RATE_ARM_A = 0.40`, `REDUNDANT_RATE_ARM_B = 0.00`. Difference `0.40`.
`ARM_A_REDUNDANT_DISTINCT_EPISODES = 4`.

MISALIGNED is reported separately and is zero in both arms; it was not folded
into REDUNDANT.

### 5.2 History accounting

```text
TOTAL_HISTORY_ROWS            = 27
FIRST_BLINDED_EVENT_COUNT     = 20
FIRST_BLINDED_REVISION_COUNT  = 23
OWNER_UNBLINDED_REVISION_COUNT= 4
NO_HISTORY_ROW_DROPPED        = YES
```

27 rows = 23 `FIRST_BLINDED_REVIEW` revisions (20 events, three of which carry
an extra `DESIGN_OWNER` intermediate revision) + 4
`OWNER_UNBLINDED_ADJUDICATION` revisions. This equals the 27 rows in the
production database for this run, so no revision was dropped in the export.

---

## 6. Frozen Gate Evaluation (owner-adjudicated current state)

Evaluated item by item against design §15, using the readout in §5.1.

| # | Gate item | Requirement | Observed | Verdict |
| --- | --- | --- | --- | --- |
| 1 | `N_ARM_A >= 8` | >= 8 | 10 | PASS |
| 2 | `N_ARM_B >= 8` | >= 8 | 10 | PASS |
| 3 | `REDUNDANT_RATE_ARM_A >= 2.0 * REDUNDANT_RATE_ARM_B` | >= 0.00 | 0.40 | PASS |
| 4 | `REDUNDANT_RATE_ARM_A - REDUNDANT_RATE_ARM_B >= 0.25` | >= 0.25 | 0.40 | PASS |
| 5 | `ARM_A_REDUNDANT_DISTINCT_EPISODES >= 3` | >= 3 | 4 | PASS |

All five items pass. The `NOT_SUPPORTED` trigger
(`REDUNDANT_RATE_ARM_A <= REDUNDANT_RATE_ARM_B`) does not hold.

```text
OWNER_ADJUDICATED_GATE_RESULT =
SUPPORTED_FOR_PROTOCOL_PATCH_REVIEW
```

Item 3 deserves a note: with `REDUNDANT_RATE_ARM_B = 0.00` the
`>= 2.0 *` requirement degenerates to `>= 0.00` and is satisfied trivially. The
substantive discriminating requirement in this readout is item 4 (a `0.40`
absolute difference against a `0.25` floor), together with item 5's four
distinct episodes. This is stated so that the trivial satisfaction of item 3 is
not read as independent evidence.

---

## 7. Reproducibility

`05_review_history.csv` is generated by:

```text
scripts/export_g1_p3_diagnostic_review_history.py
```

Properties of the exporter:

* opens the owner database with `mode=ro` and never writes to it;
* reads the authoritative 20-event universe from
  `02_selection_internal.csv` and refuses to run if the shape is wrong
  (`EVENT_COUNT`, distinct episodes, pair count, arm counts, duplicate keys);
* keeps **every** revision — not `max(review_id)`;
* derives `review_phase` from the stored reviewer identity only, and raises on
  an unclassified reviewer rather than guessing from timestamps;
* joins `arm` / `pair_id` / `P12` / `C12` from `02_selection_internal.csv`;
  these are **not** read from the human review database;
* enforces frame agreement between the frozen selection table and the reviewed
  boundary, and requires every event to carry at least one
  `FIRST_BLINDED_REVIEW` revision;
* computes no label, changes no detector, protocol or threshold.

**Sort order (frozen):** `diagnostic_event_id ASC, review_id ASC`.

**Encoding (frozen):** UTF-8 without BOM, LF line endings, frozen column order:

```text
diagnostic_event_id, episode_id, boundary_id, event_frame,
arm, pair_id, P12, C12,
review_id, reviewer, reviewed_at,
human_decision, reason_code, corrected_frame, comment, review_phase
```

Because the sort key, column order, encoding and join sources are all fixed,
the file is byte-deterministic and can be rebuilt byte-for-byte from source 2
and source 7 of §2. `--check` mode performs the full validation and the
completeness gate without writing.

```text
REVIEW_HISTORY_SHA256 =
3315f84314ef91974f5882bcbe647bcbbd4789917a3d8486256149faad482659
```

---

## 8. Interpretation Boundary

Even though the owner-adjudicated readout is `SUPPORTED_FOR_PROTOCOL_PATCH_REVIEW`,
this result supports **one** claim only:

> Low C12 can enrich human-REDUNDANT events among new Direction candidates with
> elevated P12.

The following claims remain **NOT** permitted on the basis of this evidence:

| Claim | Status |
| --- | --- |
| `BLINDED_VALIDATION_SUPPORTED` | **NO** — the blinded readout was `NOT_SUPPORTED_AS_GENERAL_ACCEPTANCE_COMPONENT` |
| `C12_GENERALIZATION_PROVEN` | **NO** |
| `C12_THRESHOLD_FROZEN` | **NO** — no threshold was calibrated or fixed |
| `FINAL_DETECTOR_VALIDATED` | **NO** — no detector was modified or validated |
| `INDEPENDENT_EVALUATION_PASSED` | **NO** — the evaluation set was not touched |
| C12 is the primary feature of all Direction false positives | **NO** |
| Pair12 has generalized | **NO** |

The divergence between §3 and §5 is itself the central finding and must be
carried forward intact: under blinding the hypothesis was **not** supported,
and the support in §5 is the product of a post-unblinding owner adjudication of
four events. The owner adjudication is legitimate and recorded, but it is not
independent of the arm/P12/C12 structure. Any downstream use of
`SUPPORTED_FOR_PROTOCOL_PATCH_REVIEW` must cite both readouts, not §5 alone.

---

## 9. Next Gate

Per design §17, the owner-adjudicated result admits the next step:

```text
CALIBRATION_PROTOCOL_V1_2_PATCH_REVIEW
```

**Status: recorded, NOT created.** This document does not open the patch review,
does not propose a patch, and does not touch the Calibration Protocol. The patch
review, when opened, is where the following would be decided — none of which is
decided here:

* whether P12 becomes a formal post-motion context;
* whether C12 becomes a conditional tail guard;
* the threshold calibration search surface;
* bounded lookahead;
* episode edge clipping.

Because the blinded readout was `NOT_SUPPORTED`, the patch review must also
confront the alternative path in §17: if the blinded result is treated as
dispositive, C12 is downgraded to diagnostic/supporting evidence and does not
enter general Candidate Acceptance, while P12 may continue to a separate Design
Review. Which path applies is a decision for the patch review, not for this
freeze.

---

## 10. Protection Statement

The following were **not** modified in producing this record:

* the frozen design `..._Design_FROZEN_v1_20260921.md`;
* `02_selection_internal.csv` and `03_selection_blinded.csv`;
* the production review database `outputs/g1_audit_web/g1_audit_web_owner.sqlite3`
  (no `UPDATE`, `DELETE`, `VACUUM`, or manual history rewrite);
* the Calibration Protocol (no patch created);
* the detector and all thresholds (no modification, no numeric search);
* the Evaluation set (not used);
* the Canonical GT (no writeback).

The review history was extended only through the append-only Web review path.
