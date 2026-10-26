"""Guard token provenance and refusal to invent observations from cache counts."""
import importlib.util
from pathlib import Path
import sys

SCRIPTS = Path(__file__).resolve().parents[1] / "scripts"
sys.path.insert(0, str(SCRIPTS))
from run_argus_frame_ablation import observe_visual_tokens
from prepare_argus_frame_ablation import schedule
import pytest


def test_cached_retry_requires_prior_actual_same_payload_measurement():
    usage = {"prompt_tokens": 200, "prompt_tokens_details": {"cached_tokens": 199}}
    assert observe_visual_tokens("", usage, 3, []) == ([], [], False)
    assert observe_visual_tokens("", usage, 3, [16, 16, 16]) == ([16, 16, 16], [], True)
    usage["prompt_tokens_details"]["cached_tokens"] = 50
    assert observe_visual_tokens("", usage, 3, [16, 16, 16]) == ([], [], False)


def test_actual_tokens_are_read_from_backend_not_assumed_constant():
    log = "decoding image batch 1/1, n_tokens_batch = 24\ndecoding image batch 1/1, n_tokens_batch = 40"
    assert observe_visual_tokens(log, {}, 2, []) == ([24, 40], [24, 40], False)


def test_nested_time_samples_and_short_segment_refusal():
    anchors = [63, 84, 106]
    assert set(anchors) < set(schedule(anchors, 6)) < set(schedule(anchors, 12))
    assert len(set(schedule(anchors, 12))) == 12
    assert schedule([0, 1, 3], 4) == [0, 1, 2, 3]
    with pytest.raises(ValueError, match="STOP_INSUFFICIENT_UNIQUE_FRAMES"):
        schedule([0, 1, 3], 6)
