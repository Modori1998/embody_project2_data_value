"""Synthetic-video tests: no RoboMimic, Qwen, GPU or historical output required."""
import hashlib
import json
import shutil
import subprocess
import tempfile
import unittest
import zipfile
from pathlib import Path

from src.project2_g3.flora_video_evidence import (
    CLOCK, VideoEvidenceError, build_video_evidence, sample_uniform,
    validate_g3_reply, verify_pack, read_native_zip,
)


@unittest.skipUnless(shutil.which("ffmpeg") and shutil.which("ffprobe"), "ffmpeg / ffprobe unavailable")
class FloraVideoEvidenceTest(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.video_dir = self.root / "recovery" / "videos"
        self.video_dir.mkdir(parents=True)
        self.video = self.video_dir / "demo_2_agentview_20fps.mp4"
        subprocess.run(["ffmpeg", "-nostdin", "-v", "error", "-f", "lavfi", "-i",
                        "testsrc2=size=64x64:rate=10", "-frames:v", "20",
                        "-c:v", "mpeg4", "-q:v", "5", "-y", str(self.video)],
                       capture_output=True, check=True, timeout=30)
        video_sha = hashlib.sha256(self.video.read_bytes()).hexdigest()
        self.native = {
            "schema_version": "flora_demo_annotation_v1",
            "source_clock": CLOCK,
            "camera_roles": ["main"],
            "input_sha256": {"main": video_sha},
            "duration_s": 2.0,
            "profile": "YAM",
            "segments": [
                {"start_s": 0.0, "end_s": 1.0, "caption": "Pick up a can.", "status": "complete"},
                {"start_s": 1.0, "end_s": 2.0, "caption": "Put the can down.", "status": "complete"},
            ],
            "pipeline": {"unknown_future_field": True},
        }
        self.zip = self.root / "flora.zip"
        self.write_zip()
        self.out = self.root / "out"

    def write_zip(self):
        with zipfile.ZipFile(self.zip, "w") as z:
            z.writestr("raw_json/demo_2.json", json.dumps(self.native))

    def test_evidence_end_to_end(self):
        original = self.zip.read_bytes()
        result = build_video_evidence(self.zip, self.root / "recovery", self.out)
        self.assertEqual((result["processed_episodes"], result["processed_flora_segments"],
                          result["decoded_frames"], result["evidence_packs"]), (1, 2, 20, 6))
        self.assertEqual(result["qwen_inference"], "NOT_RUN")
        self.assertEqual(self.zip.read_bytes(), original)
        packs = [json.loads(line) for line in (self.out / "evidence_packs.jsonl").read_text().splitlines()]
        self.assertEqual([p["sampling"]["actual"] for p in packs], [3, 5, 9, 3, 5, 9])
        self.assertTrue(all(p["video"]["frame_source"] == "MP4_DECODED_RGB24_NOT_P2_CLEAN_RGB" for p in packs))
        self.assertTrue(all(p["target"]["source_episode_id"] == "video/demo_2" for p in packs))
        self.assertTrue(all(all(p["target"]["start_s"] <= f["pts_s"] < p["target"]["end_s"]
                                for f in p["frames"]) for p in packs))
        self.assertTrue(all(verify_pack(p, self.out) for p in packs))
        self.assertEqual(len(list((self.out / "images" / "demo_2").glob("*.png"))), 18)

    def test_validator_valid_and_bad_citation(self):
        build_video_evidence(self.zip, self.root / "recovery", self.out)
        pack = json.loads((self.out / "evidence_packs.jsonl").read_text().splitlines()[0])
        indices = [f["frame_index"] for f in pack["frames"]]
        raw = {"motion_phase": "idle", "object_relation": ["object_static"], "gripper_state": "open",
               "event_assessment": "no_event_visible", "events": [],
               "evidence_frame_indices": indices, "evidence_quality": "sufficient",
               "observation_note": "The gripper and object appear still in sampled frames."}
        valid = validate_g3_reply(json.dumps(raw), pack, self.out)
        self.assertTrue(valid["schema_ok"])
        self.assertFalse(valid["invalid_references"])
        raw["evidence_frame_indices"] = [19]  # exists elsewhere in source video, not supplied in this request
        bad = validate_g3_reply(json.dumps(raw), pack, self.out)
        self.assertEqual(bad["status"], "INVALID_MODEL_OUTPUT")
        self.assertIn(19, bad["invalid_references"])

    def test_video_hash_mismatch_fails(self):
        self.native["input_sha256"]["main"] = "0" * 64
        self.write_zip()
        with self.assertRaisesRegex(VideoEvidenceError, "FLORA_VIDEO_SHA_MISMATCH"):
            build_video_evidence(self.zip, self.root / "recovery", self.out)

    def test_missing_video_fails(self):
        self.video.unlink()
        with self.assertRaisesRegex(VideoEvidenceError, "VIDEO_NOT_FOUND"):
            build_video_evidence(self.zip, self.root / "recovery", self.out)

    def test_empty_segment_fails(self):
        self.native["segments"][0] = {"start_s": 0.01, "end_s": 0.04, "caption": "No frame", "status": "complete"}
        self.write_zip()
        with self.assertRaisesRegex(VideoEvidenceError, "SEGMENT_HAS_NO_DECODED_FRAMES"):
            build_video_evidence(self.zip, self.root / "recovery", self.out)

    def test_output_dir_must_be_empty(self):
        self.out.mkdir()
        (self.out / "stale.txt").write_text("stale")
        with self.assertRaisesRegex(VideoEvidenceError, "OUTPUT_DIR_MUST_BE_EMPTY"):
            build_video_evidence(self.zip, self.root / "recovery", self.out)

    def test_image_tamper_rejected(self):
        build_video_evidence(self.zip, self.root / "recovery", self.out)
        pack = json.loads((self.out / "evidence_packs.jsonl").read_text().splitlines()[0])
        image = self.out / pack["frames"][0]["png_path"]
        image.write_bytes(b"tampered")
        with self.assertRaisesRegex(VideoEvidenceError, "EVIDENCE_PNG_HASH_MISMATCH"):
            verify_pack(pack, self.out)

    def test_native_unknown_field_retained(self):
        self.assertTrue(read_native_zip(self.zip)["demo_2"]["record"]["pipeline"]["unknown_future_field"])

    def test_deterministic_outputs(self):
        build_video_evidence(self.zip, self.root / "recovery", self.out)
        another = self.root / "replay"
        build_video_evidence(self.zip, self.root / "recovery", another)
        for name in ("video_frame_manifest.jsonl", "evidence_packs.jsonl",
                     "sampling_comparison.jsonl", "episode_inventory.jsonl", "summary.json"):
            self.assertEqual((self.out / name).read_bytes(), (another / name).read_bytes())

    def test_short_uniform_sampling(self):
        self.assertEqual(sample_uniform([5, 6], 9), [5, 6])
        self.assertEqual(sample_uniform([5], 9), [5])
        self.assertEqual(sample_uniform(list(range(10)), 3), [0, 5, 9])


if __name__ == "__main__":
    unittest.main()
