# Project 2 MVP RGB Runtime Validation Result

```text
DATE = 2026-10-08
DOCUMENT_STATUS = PASS
SOURCE_OF_TRUTH = GITHUB_MAIN
RUNTIME_VALIDATION_SOURCE = LOCAL_CAN_MH_EXECUTION_REPORTED_BY_DESIGN_OWNER

GIT_BASE_AFTER_PULL =
cc42b9b39d72f52f540485411f6d80ff3dd785ae

RGB_CONTRACT_VERSION =
MVP_RGB_SOURCE_AND_ALIGNMENT_CONTRACT_v1

NEW_RGB_CONTRACT_TESTS =
PASS_3_OF_3

G1_VIDEO_ALIGNMENT_REGRESSION =
PASS_1_OF_1

REAL_DATA_EPISODES_VALIDATED =
3

EPISODES =
data/demo_0
data/demo_1
data/demo_2

FORMAL_STATE_LENGTH_MATCH =
PASS

FORMAL_ACTION_LENGTH_MATCH =
PASS

RGB_DTYPE =
uint8

RGB_SHAPE =
128x128x3

RGB_COLOR_SPACE =
RGB

RENDERER_CLASS =
project1_benchmark.robomimic_rgb_materializer.RoboMimicStateRenderer

MUJOCO_GL =
wgl

CAMERA_NAME =
NOT_EXPOSED_BY_RENDERER

NO_EPISODE_TEXT_OVERLAY =
YES

NO_FRAME_NUMBER_OVERLAY =
YES

AUDIT_MP4_USED =
NO

LOSSY_VIDEO_ROUNDTRIP =
NO

PNG_PIXEL_ROUNDTRIP =
PASS_ALL_9_FRAMES_PIXEL_EXACT

SIGLIP2_EXECUTED =
NO

VLM_EXECUTED =
NO

RGB_RUNTIME_VALIDATION =
PASS

READY_FOR_MVP_M2 =
YES
```

## Interpretation

The Formal model-input RGB path is validated locally against real RoboMimic Can/MH episodes.

The validated path is:

```text
source STATE_t
→ P1 RoboMimicStateRenderer
→ direct clean RGB uint8 128x128x3
→ in-memory RGB / lossless PNG
```

The Human Audit MP4 path is not used as Formal model input.

The runtime evidence confirms:

- source-state / Formal action lengths align on the validated episodes;
- direct rendered frames contain no Episode ID or frame-number overlay;
- no lossy video roundtrip is present;
- PNG export roundtrip is pixel-exact for all 9 tested frames;
- the renderer runtime is the existing P1 RoboMimicStateRenderer under MuJoCo WGL.

## Scope boundary

This validation closes only the RGB input P0 prerequisite.

It does not establish:

```text
SigLIP2 representation quality
VLM label quality
retrieval quality
G1 held-out segmentation performance
```

No SigLIP2 or VLM execution occurred.

## Gate result

```text
MVP_P0A_RGB_INPUT_CONTRACT = CLOSED_PASS
RGB_RUNTIME_VALIDATION = PASS
MVP_M2 = OPEN
NEXT = MVP_M2_MINIMAL_KEYFRAME_AND_ROBOT_MOTION_SUMMARY
```
