"""Tests for the P2-G3 local VLM probe and its input contract.

These tests are pure-python and need no GPU, no server and no model: they pin
the behaviour that the feasibility report depends on — request construction,
answer parsing, JSON extraction, evidence-limit flagging, and the RGB input
contract that makes a frame legal model input.
"""

from __future__ import annotations

import base64
import csv
import importlib.util
import json
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
PROBE_PATH = ROOT / "scripts" / "probe_g3_local_vlm.py"
MATERIALIZER_PATH = ROOT / "scripts" / "materialize_g3_vlm_rgb_frames.py"


def _load(name: str, path: Path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


@pytest.fixture(scope="module")
def probe():
    return _load("probe_g3_local_vlm", PROBE_PATH)


@pytest.fixture(scope="module")
def materializer():
    return _load("materialize_g3_vlm_rgb_frames", MATERIALIZER_PATH)


# --------------------------------------------------------------------------- #
# request construction
# --------------------------------------------------------------------------- #
class TestBuildPayload:
    def test_single_image_becomes_one_image_url_part(self, probe):
        payload = probe.build_payload(
            model="m", prompt="q", image_uris=["data:image/png;base64,AAA"],
            max_tokens=128, temperature=0.0, seed=7, json_object=False,
            system_prompt=None,
        )
        content = payload["messages"][-1]["content"]
        assert [p["type"] for p in content] == ["text", "image_url"]
        assert payload["max_tokens"] == 128
        assert payload["temperature"] == 0.0
        assert payload["seed"] == 7
        assert payload["stream"] is False

    def test_six_images_preserve_temporal_order(self, probe):
        uris = [f"data:image/png;base64,{i}" for i in range(6)]
        payload = probe.build_payload(
            model="m", prompt="q", image_uris=uris,
            max_tokens=128, temperature=0.0, seed=1, json_object=False,
            system_prompt=None,
        )
        parts = payload["messages"][-1]["content"]
        assert len(parts) == 7
        assert [p["image_url"]["url"] for p in parts[1:]] == uris

    def test_json_object_flag_sets_response_format(self, probe):
        payload = probe.build_payload(
            model="m", prompt="q", image_uris=["data:image/png;base64,AA"],
            max_tokens=64, temperature=0.0, seed=1, json_object=True,
            system_prompt=None,
        )
        assert payload["response_format"] == {"type": "json_object"}

    def test_system_prompt_precedes_user_message(self, probe):
        payload = probe.build_payload(
            model="m", prompt="q", image_uris=["data:image/png;base64,AA"],
            max_tokens=64, temperature=0.0, seed=1, json_object=False,
            system_prompt="be careful",
        )
        assert payload["messages"][0]["role"] == "system"
        assert payload["messages"][-1]["role"] == "user"

    def test_no_seed_key_when_seed_none(self, probe):
        payload = probe.build_payload(
            model="m", prompt="q", image_uris=["data:image/png;base64,AA"],
            max_tokens=64, temperature=0.0, seed=None, json_object=False,
            system_prompt=None,
        )
        assert "seed" not in payload


# --------------------------------------------------------------------------- #
# response parsing
# --------------------------------------------------------------------------- #
class TestParseResponse:
    def test_extracts_text_and_timings(self, probe):
        body = {
            "choices": [{"message": {"content": "hello"}, "finish_reason": "stop"}],
            "usage": {"prompt_tokens": 11, "completion_tokens": 3},
            "timings": {"predicted_ms": 120.5, "predicted_n": 3, "prompt_ms": 40.0, "prompt_n": 11},
        }
        out = probe.parse_response(body)
        assert out["text"] == "hello"
        assert out["finish_reason"] == "stop"
        assert out["prompt_tokens"] == 11
        assert out["completion_tokens"] == 3
        assert out["predicted_ms"] == 120.5

    def test_handles_content_parts_list(self, probe):
        body = {"choices": [{"message": {"content": [{"text": "a"}, {"text": "b"}]}}]}
        assert probe.parse_response(body)["text"] == "ab"

    def test_tolerates_missing_choice(self, probe):
        out = probe.parse_response({})
        assert out["text"] is None
        assert out["finish_reason"] is None


class TestJsonExtraction:
    def test_plain_json_object(self, probe):
        ok, value = probe.try_json('{"a": 1}')
        assert ok and value == {"a": 1}

    def test_fenced_json_block(self, probe):
        ok, value = probe.try_json('```json\n{"arm": "lifted"}\n```')
        assert ok and value == {"arm": "lifted"}

    def test_json_embedded_in_prose(self, probe):
        ok, value = probe.try_json('Here you go: {"gripper": "open"} — done.')
        assert ok and value == {"gripper": "open"}

    def test_non_json_returns_false(self, probe):
        ok, value = probe.try_json("the arm is moving")
        assert ok is False and value is None

    def test_empty_text_is_not_json(self, probe):
        assert probe.try_json("") == (False, None)
        assert probe.try_json(None) == (False, None)


class TestEvidenceFlags:
    def test_chinese_uncertainty_marker(self, probe):
        assert probe.evidence_flags("无法判断夹爪是否闭合")["states_uncertainty"] is True

    def test_english_uncertainty_marker(self, probe):
        assert probe.evidence_flags("I cannot determine this")["states_uncertainty"] is True

    def test_assertive_answer_is_not_flagged(self, probe):
        assert probe.evidence_flags("机械臂抬起并移动")["states_uncertainty"] is False

    def test_neighbour_segment_mention_flagged(self, probe):
        assert probe.evidence_flags("邻段显示了释放")["mentions_neighbour_segment"] is True


class TestOomDetection:
    def test_http_500_with_out_of_memory(self, probe):
        assert probe.is_oom(500, {}, "CUDA error: out of memory") is True

    def test_http_200_is_not_oom(self, probe):
        assert probe.is_oom(200, {"choices": []}, '{"ok": true}') is False

    def test_error_containing_oom_substring_is_not_oom(self, probe):
        """`room`/`zoom` must not be mistaken for OOM."""
        assert probe.is_oom(500, {}, "bad zoom factor in request") is False
        assert probe.is_oom(500, {}, "no room in template") is False

    def test_server_error_without_allocation_failure_is_not_oom(self, probe):
        assert probe.is_oom(500, {}, "model not loaded") is False

    def test_client_error_is_not_oom(self, probe):
        assert probe.is_oom(400, {}, "out of memory") is False


# --------------------------------------------------------------------------- #
# image hashing / data uri
# --------------------------------------------------------------------------- #
class TestImageEncoding:
    def test_sha256_matches_hashlib(self, probe, tmp_path):
        import hashlib

        blob = bytes(range(256)) * 8
        path = tmp_path / "x.png"
        path.write_bytes(blob)
        assert probe.sha256_file(path) == hashlib.sha256(blob).hexdigest()

    def test_data_uri_roundtrips_bytes(self, probe, tmp_path):
        blob = b"\x89PNG\r\n\x1a\n" + b"payload"
        path = tmp_path / "y.png"
        path.write_bytes(blob)
        uri = probe.image_data_uri(path)
        assert uri.startswith("data:image/png;base64,")
        decoded = base64.b64decode(uri.split(",", 1)[1])
        assert decoded == blob


# --------------------------------------------------------------------------- #
# CLI behaviour without a server
# --------------------------------------------------------------------------- #
class TestCliGuards:
    def test_unreachable_server_returns_4(self, probe, tmp_path):
        img = tmp_path / "a.png"
        img.write_bytes(b"\x89PNG")
        code = probe.main([
            "--base-url", "http://127.0.0.1:1",
            "--images", str(img), "--prompt", "x", "--timeout", "2",
        ])
        assert code == 4

    def test_missing_image_returns_2(self, probe, tmp_path):
        code = probe.main([
            "--base-url", "http://127.0.0.1:1",
            "--images", str(tmp_path / "nope.png"), "--prompt", "x", "--timeout", "2",
        ])
        assert code == 2


# --------------------------------------------------------------------------- #
# input contract of the materializer helper
# --------------------------------------------------------------------------- #
class TestMaterializerContract:
    def test_expected_loader_keys_on_frame_index(self, materializer, tmp_path):
        path = tmp_path / "prov.csv"
        with path.open("w", newline="", encoding="utf-8") as fh:
            writer = csv.DictWriter(fh, fieldnames=[
                "target_segment_id", "source_episode_id", "frame_index", "pixel_sha256",
            ])
            writer.writeheader()
            writer.writerow({
                "target_segment_id": "demo_47-S0002", "source_episode_id": "data/demo_47",
                "frame_index": 50, "pixel_sha256": "abc123",
            })
            writer.writerow({
                "target_segment_id": "demo_47-S0003", "source_episode_id": "data/demo_99",
                "frame_index": 7, "pixel_sha256": "deadbeef",
            })
        expected = materializer._load_expected(path, "data/demo_47")
        assert expected == {50: {"abc123"}}

    def test_expected_loader_collects_all_hashes_per_frame(self, materializer, tmp_path):
        """A keyframe of segment X is usually only listed as context of X's neighbour."""
        path = tmp_path / "prov.csv"
        with path.open("w", newline="", encoding="utf-8") as fh:
            writer = csv.DictWriter(fh, fieldnames=[
                "target_segment_id", "source_episode_id", "frame_index", "pixel_sha256",
            ])
            writer.writeheader()
            for seg, sha in (("S0002", "aaaa"), ("S0003", "bbbb")):
                writer.writerow({
                    "target_segment_id": seg, "source_episode_id": "data/demo_47",
                    "frame_index": 50, "pixel_sha256": sha,
                })
        expected = materializer._load_expected(path, "data/demo_47")
        assert expected == {50: {"aaaa", "bbbb"}}

    def test_expected_loader_is_case_insensitive_on_hash(self, materializer, tmp_path):
        path = tmp_path / "prov.csv"
        with path.open("w", newline="", encoding="utf-8") as fh:
            writer = csv.DictWriter(fh, fieldnames=[
                "target_segment_id", "source_episode_id", "frame_index", "pixel_sha256",
            ])
            writer.writeheader()
            writer.writerow({
                "target_segment_id": "S", "source_episode_id": "data/demo_1",
                "frame_index": 1, "pixel_sha256": "ABCDEF",
            })
        assert materializer._load_expected(path, "data/demo_1") == {1: {"abcdef"}}


class TestProbeCsvSchema:
    def test_csv_row_fieldnames_cover_required_metrics(self, probe, tmp_path, monkeypatch):
        """The CSV must carry the resource/latency fields the report cites."""
        img = tmp_path / "a.png"
        img.write_bytes(b"\x89PNG\r\n\x1a\n" + b"x" * 32)

        def fake_http(url, payload, timeout):
            return 200, {
                "choices": [{"message": {"content": '{"ok": true}'}, "finish_reason": "stop"}],
                "usage": {"prompt_tokens": 5, "completion_tokens": 2},
                "timings": {"predicted_ms": 10.0, "predicted_n": 2},
            }, "{}"

        monkeypatch.setattr(probe, "_http_json", fake_http)
        monkeypatch.setattr(probe, "gpu_snapshot", lambda: {
            "gpu_name": "fake", "vram_total_mib": 8188,
            "vram_used_mib": 100, "vram_free_mib": 8088, "gpu_util_pct": 0,
        })
        monkeypatch.setattr(probe, "gpu_processes", lambda: [])

        csv_out = tmp_path / "metrics.csv"
        json_out = tmp_path / "run.json"
        code = probe.main([
            "--images", str(img), "--prompt", "q", "--label", "unit",
            "--csv-out", str(csv_out), "--json-out", str(json_out),
            "--json-object",
        ])
        assert code == 0
        rows = list(csv.DictReader(csv_out.open(encoding="utf-8")))
        assert len(rows) == 1
        row = rows[0]
        for field in ("image_count", "total_image_bytes", "wall_seconds",
                      "prompt_tokens", "completion_tokens", "predicted_ms",
                      "vram_used_before_mib", "oom_detected", "completed_inference",
                      "json_parsed_ok"):
            assert field in row
        assert row["image_count"] == "1"
        assert row["completed_inference"] == "True"
        assert row["json_parsed_ok"] == "True"

        record = json.loads(json_out.read_text(encoding="utf-8"))
        assert record["image_count"] == 1
        assert record["json_value"] == {"ok": True}
        assert record["sampling"]["json_object"] is True
        assert len(record["images"][0]["sha256"]) == 64

    def test_csv_appends_without_duplicating_header(self, probe, tmp_path, monkeypatch):
        img = tmp_path / "a.png"
        img.write_bytes(b"\x89PNG\r\n\x1a\n" + b"x" * 16)

        def fake_http(url, payload, timeout):
            return 200, {"choices": [{"message": {"content": "plain"}}]}, "{}"

        monkeypatch.setattr(probe, "_http_json", fake_http)
        monkeypatch.setattr(probe, "gpu_snapshot", lambda: None)
        monkeypatch.setattr(probe, "gpu_processes", lambda: [])

        csv_out = tmp_path / "multi.csv"
        for label in ("one", "two"):
            probe.main(["--images", str(img), "--prompt", "q", "--label", label,
                        "--csv-out", str(csv_out)])
        lines = csv_out.read_text(encoding="utf-8").strip().splitlines()
        assert lines[0].startswith("timestamp_utc")
        assert len(lines) == 3
