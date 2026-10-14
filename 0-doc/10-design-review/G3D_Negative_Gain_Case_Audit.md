# G3D Negative Gain Case Audit ? 2026-10-14

Source: corrected G3D `full_r3` local immutable run. This audit reads raw requests/responses and the formal local G3C human CSV; it does not rerun a model or modify source assets. Development cases only.

## Exact sets

- New B `object_motion` false positives: `demo_172-S0004`, `demo_71-S0003`.
- A event set correct, B event set wrong: `demo_180-S0001`, `demo_71-S0003`.
- Intersection: `demo_71-S0003`.

## Verified request controls

All 12 actual A/B requests use identical three image data URIs, chronological order, model ID, `max_tokens=512`, `temperature=0`, `seed=1234`, `stream=false`, and JSON-object response format. B text starts with the exact A prompt and appends the state block. Content order in the old request is `[full_text, RGB0, RGB1, RGB2]`. The old v0.2.1 text itself includes a frame table and START/MIDDLE/END roles, so it is false to claim that it has no temporal information. Frozen run metadata pins Qwen3-VL-4B Q4 and mmproj F16; server log confirms loaded Q4 plus mmproj with 4096 context.

## Motion-summary semantics

B received segment-level values over the inclusive `[start_frame,end_frame]` interval, not a full state/action series or state at each RGB time. The M2 fields include EEF start/end (metres), displacement and path (metres), gripper endpoint aperture (source qpos units), endpoint OPEN/CLOSED, normalized action magnitude statistics, and two transition flags. The field `gripper_transition_present` can be true from a left G1 `CANDIDATE_GRIPPER` boundary even when `gripper_state_change_within_segment=false`. Aperture sign/open direction is not explicitly defined in the old block, beyond the endpoint OPEN/CLOSED enum. Neither the two RGB subintervals nor their state differences were supplied. These omissions limit any causal claim about why the model erred.

## Case evidence

### demo_172-S0004

Frozen interval: [166, 169]. RGB frames: 166;167;169. PNG SHA256: `31883f7b7881c8b953eeb7c08492f23edfac71876e42943a1a62ce793abd6160;6f70027306ddd8f8a11e8929ca8993ca11ef64cf20a1d9b4642f5c6c3b0c83b8;eb91e85fe276a3abc29e54781192d655448db3c9094b14319a1af42995cc3978`.
Human: phase `place`; full events `release_attempt`.
A?B: added `['object_motion']`, removed `['grasp_attempt']`.

**Actual B-only text**

```text


# Robot state within this segment (B only)
EEF positions/displacements/path are metres; gripper aperture uses source qpos units. Actions are normalized controller inputs, not observed object motion. EEF movement does not prove object_motion; gripper closure does not prove grasp success. Apply the same visual event and frame evidence rules.
{"action_magnitude_max": 1.0977526426876307, "action_magnitude_mean": 1.0851745314035983, "action_magnitude_std": 0.014394071290280324, "action_semantic": "NORMALIZED_CONTROLLER_INPUT", "eef_displacement_xyz": [0.0005624630951026333, -0.0055390982645446285, 0.013524491759991708], "eef_end_xyz_m": [0.17537224641030838, 0.3355264371602038, 1.0122234459684802], "eef_net_displacement_m": 0.014625657307749193, "eef_path_length_m": 0.014655912166910753, "eef_start_xyz_m": [0.17480978331520575, 0.34106553542474843, 0.9986989542084885], "gripper_end_aperture": 0.07520541370037534, "gripper_end_state": "OPEN", "gripper_start_aperture": 0.06255682122419909, "gripper_start_state": "OPEN", "gripper_state_change_within_segment": false, "gripper_transition_present": true}
```

**A parsed JSON**

```json
{
  "motion_phase": "grasp",
  "object_relation": [
    "gripper_contact_visible"
  ],
  "gripper_state": "closed",
  "event_assessment": "event_visible",
  "events": [
    {
      "event_type": "grasp_attempt",
      "event_outcome": "unclear",
      "evidence_frame_indices": [
        166,
        167,
        169
      ]
    }
  ],
  "evidence_frame_indices": [
    166,
    167,
    169
  ],
  "evidence_quality": "sufficient",
  "observation_note": "夹爪闭合并接触物体，物体位于夹爪正下方；夹爪在三帧中保持闭合状态，无明显位移。"
}
```

**B parsed JSON**

```json
{
  "motion_phase": "idle",
  "object_relation": [
    "object_static"
  ],
  "gripper_state": "open",
  "event_assessment": "event_visible",
  "events": [
    {
      "event_type": "object_motion",
      "event_outcome": "unclear",
      "evidence_frame_indices": [
        166,
        167,
        169
      ]
    }
  ],
  "evidence_frame_indices": [
    166,
    167,
    169
  ],
  "evidence_quality": "sufficient",
  "observation_note": "夹爪保持打开状态，物体静止，无明显运动或交互。"
}
```

QC: A `REVIEW_REQUIRED`, B `REVIEW_REQUIRED`; A findings `['PHASE_NOTE_MOTION_CONFLICT_CANDIDATE']`; B findings `['PHASE_EVENT_CONFLICT_CANDIDATE']`. Both JSON/schema/frame-reference checks passed.

### demo_71-S0003

Frozen interval: [34, 106]. RGB frames: 34;70;106. PNG SHA256: `f6c98cf55860872ab6f8bfbd3333a204d42ed3d9477dbf181f333f216d5b87a9;305d991e4d2d773f904e8e136a9a3431f36d29e372a3f0d656e1aef1e3a38edb;218f2f4e1bfa5c064eeb29d3718321440c08b3f1a1deda179427f2022c715c2b`.
Human: phase `approach`; full events `grasp_attempt`.
A?B: added `['object_motion']`, removed `['grasp_attempt']`.

**Actual B-only text**

```text


# Robot state within this segment (B only)
EEF positions/displacements/path are metres; gripper aperture uses source qpos units. Actions are normalized controller inputs, not observed object motion. EEF movement does not prove object_motion; gripper closure does not prove grasp success. Apply the same visual event and frame evidence rules.
{"action_magnitude_max": 1.1403323551461055, "action_magnitude_mean": 1.0315062351391513, "action_magnitude_std": 0.030177433353724217, "action_semantic": "NORMALIZED_CONTROLLER_INPUT", "eef_displacement_xyz": [-0.06473024315789047, 0.007986739987379698, -0.14225867025305194], "eef_end_xyz_m": [-0.03539754068078819, -0.08001886629248682, 0.8762801683211414], "eef_net_displacement_m": 0.15649703402004844, "eef_path_length_m": 0.19290954100016441, "eef_start_xyz_m": [0.029332702477102283, -0.08800560627986652, 1.0185388385741934], "gripper_end_aperture": 0.06362181142788756, "gripper_end_state": "OPEN", "gripper_start_aperture": 0.07917858419266692, "gripper_start_state": "OPEN", "gripper_state_change_within_segment": false, "gripper_transition_present": false}
```

**A parsed JSON**

```json
{
  "motion_phase": "grasp",
  "object_relation": [
    "gripper_contact_visible"
  ],
  "gripper_state": "closed",
  "event_assessment": "event_visible",
  "events": [
    {
      "event_type": "grasp_attempt",
      "event_outcome": "unclear",
      "evidence_frame_indices": [
        34,
        70,
        106
      ]
    }
  ],
  "evidence_frame_indices": [
    34,
    70,
    106
  ],
  "evidence_quality": "sufficient",
  "observation_note": "夹爪闭合并接触红色杯子，物体在夹爪下方可见。"
}
```

**B parsed JSON**

```json
{
  "motion_phase": "idle",
  "object_relation": [
    "object_static"
  ],
  "gripper_state": "open",
  "event_assessment": "event_visible",
  "events": [
    {
      "event_type": "object_motion",
      "event_outcome": "unclear",
      "evidence_frame_indices": [
        34,
        70,
        106
      ]
    }
  ],
  "evidence_frame_indices": [
    34,
    70,
    106
  ],
  "evidence_quality": "sufficient",
  "observation_note": "Robot arm is stationary with open gripper. Red can remains on the table, no visible motion or interaction."
}
```

QC: A `VALID`, B `REVIEW_REQUIRED`; A findings `[]`; B findings `['PHASE_EVENT_CONFLICT_CANDIDATE']`. Both JSON/schema/frame-reference checks passed.

### demo_180-S0001

Frozen interval: [0, 3]. RGB frames: 0;1;3. PNG SHA256: `0496f5fea55c28d1559427f67084b8ebcd93d450209cf4507f67359c7b76ddd9;573b00466eeb4305696a3d912e671cad425a0bd6fabf623ef636530470b4ec93;439cda803840827f8f27f5bd658c279e7d7712abee8874ac5906ad91423bf6a9`.
Human: phase `idle`; full events `[]`.
A?B: added `['grasp_attempt']`, removed `[]`.

**Actual B-only text**

```text


# Robot state within this segment (B only)
EEF positions/displacements/path are metres; gripper aperture uses source qpos units. Actions are normalized controller inputs, not observed object motion. EEF movement does not prove object_motion; gripper closure does not prove grasp success. Apply the same visual event and frame evidence rules.
{"action_magnitude_max": 1.0090119018495372, "action_magnitude_mean": 1.0072703646688481, "action_magnitude_std": 0.0012249953991378291, "action_semantic": "NORMALIZED_CONTROLLER_INPUT", "eef_displacement_xyz": [-0.0023891694827993387, 0.002354116750441365, -0.0016249252190756458], "eef_end_xyz_m": [-0.050983476941978675, -0.10883286058542402, 1.002466833832337], "eef_net_displacement_m": 0.00372697980405533, "eef_path_length_m": 0.004801544689464034, "eef_start_xyz_m": [-0.04859430745917934, -0.11118697733586538, 1.0040917590514127], "gripper_end_aperture": 0.0527227164026368, "gripper_end_state": "CLOSED", "gripper_start_aperture": 0.041666, "gripper_start_state": "CLOSED", "gripper_state_change_within_segment": false, "gripper_transition_present": false}
```

**A parsed JSON**

```json
{
  "motion_phase": "idle",
  "object_relation": [
    "object_static"
  ],
  "gripper_state": "open",
  "event_assessment": "no_event_visible",
  "events": [],
  "evidence_frame_indices": [],
  "evidence_quality": "sufficient",
  "observation_note": "机器人夹爪保持打开状态，红色物体静止在桌面上，未观察到任何动作变化。"
}
```

**B parsed JSON**

```json
{
  "motion_phase": "idle",
  "object_relation": [
    "object_static"
  ],
  "gripper_state": "closed",
  "event_assessment": "event_visible",
  "events": [
    {
      "event_type": "grasp_attempt",
      "event_outcome": "unclear",
      "evidence_frame_indices": [
        0,
        1,
        3
      ]
    }
  ],
  "evidence_frame_indices": [
    0,
    1,
    3
  ],
  "evidence_quality": "partial",
  "observation_note": "夹爪保持闭合，但未观察到向物体移动或抓取动作；物体静止，无明显位移。"
}
```

QC: A `REVIEW_REQUIRED`, B `REVIEW_REQUIRED`; A findings `['EVIDENCE_QUALITY_WITHOUT_CITATION']`; B findings `['PHASE_EVENT_CONFLICT_CANDIDATE']`. Both JSON/schema/frame-reference checks passed.

## Observed error and causal limits

- `demo_172`: B reports `object_motion` while its own note says the object was static; B also misses the human `release_attempt`. Its `gripper_transition_present=true` comes from the left boundary while the internal-change flag is false. The contradiction is observed; whether that flag caused the event is unproven.
- `demo_71`: B replaces a human-supported `grasp_attempt` with false `object_motion` while its own note says no visible movement. Its 0.1565 m EEF displacement is an available misleading cue, but the run cannot prove the model relied on it.
- `demo_180`: B adds `grasp_attempt` despite `gripper_state_change_within_segment=false` and its own note denying a grasp action. Endpoint `CLOSED` could be confused with an event; this is a hypothesis, not a measured internal mechanism.
- The old A/B design cannot separate input order effects, coarse state compression and reliance on EEF/gripper cues. The next experiment must pre-register separate prompt and state-format contrasts without adding RGB or changing event rules.
