import json
import sys
import tempfile
import unittest
import zipfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from src.project2_g3.flora_adapter import build_links, AdapterError, EXPECTED_CLOCK


def fixture_zip(path):
    video_sha = "a" * 64
    episode = {"schema_version": "flora_demo_annotation_v1", "source_clock": EXPECTED_CLOCK,
               "duration_s": 1.5, "input_sha256": {"main": video_sha},
               "segments": [{"start_s": 0.0, "end_s": 0.5, "caption": "A", "status": "complete"},
                            {"start_s": 0.5, "end_s": 1.5, "caption": "B", "status": "complete"}],
               "pipeline": {"future_extra": [1]}, "unrecognized": {"keep": True}}
    with zipfile.ZipFile(path, "w") as z:
        z.writestr("raw_json/demo_2.json", json.dumps(episode))
    return episode


def manifest(path, *, video_sha=None, clock=EXPECTED_CLOCK):
    obj = {"schema_version": "P2_FLORA_G1_SOURCE_MAPPING_V0_1", "episodes": [{
        "flora_episode_id": "demo_2", "source_episode_id": "data/demo_2",
        "source_manifest_sha256": "b" * 64, "flora_video_sha256": video_sha or "a" * 64,
        "source_clock": clock, "frame_map": [
            {"video_frame_index": i, "relative_pts_s": i * 0.25, "source_frame_index": i * 5}
            for i in range(6)
        ], "g1_segments": [
            {"segment_id": "S1", "start_frame": 0, "end_frame": 9},
            {"segment_id": "S2", "start_frame": 10, "end_frame": 14},
            {"segment_id": "S3", "start_frame": 15, "end_frame": 25},
        ]}]}
    path.write_text(json.dumps(obj))


class FloraAdapterTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        self.zip = self.root / "native.zip"
        self.flora = fixture_zip(self.zip)

    def read_links(self):
        return [json.loads(x) for x in (self.root / "out/flora_g1_links.jsonl").read_text().splitlines()]

    def test_no_manifest_fail_closed_and_preserve_raw(self):
        original = self.zip.read_bytes()
        result = build_links(self.zip, self.root / "out")
        self.assertEqual((result["episode_count"], result["flora_segment_count"]), (1, 2))
        self.assertTrue(result["missing_source_manifest_is_blocker"])
        self.assertFalse(result["source_alignment_verified"])
        self.assertTrue(all(x["g1_target"]["mapping_status"] == "UNALIGNED" for x in self.read_links()))
        self.assertEqual(self.zip.read_bytes(), original)

    def test_manifest_candidates_not_truth(self):
        p = self.root / "source.json"; manifest(p)
        result = build_links(self.zip, self.root / "out", p)
        self.assertFalse(result["source_alignment_verified"])
        self.assertTrue(result["alignment_blocked"])
        links = self.read_links()
        self.assertEqual(len(links), 3)  # second Flora segment overlaps two G1 spans
        self.assertEqual([v["g1_target"].get("g1_segment_id") for v in links], ["S1", "S2", "S3"])
        self.assertTrue(all(x["g1_target"]["mapping_status"] == "CANDIDATE_SOURCE_UNVERIFIED" for x in links))

    def test_mismatch_hash_does_not_link(self):
        p = self.root / "source.json"; manifest(p, video_sha="f"*64)
        result = build_links(self.zip, self.root / "out", p)
        self.assertEqual(result["mapping_status_counts"], {"VIDEO_SHA_MISMATCH": 1})
        self.assertTrue(all(x["g1_target"]["mapping_status"] == "UNALIGNED" for x in self.read_links()))

    def test_clock_mismatch_does_not_link(self):
        p = self.root / "source.json"; manifest(p, clock="unknown")
        result = build_links(self.zip, self.root / "out", p)
        self.assertEqual(result["mapping_status_counts"], {"SOURCE_CLOCK_MISMATCH": 1})

    def test_cannot_forge_inclusive_endpoint_from_fps(self):
        p = self.root / "source.json"; manifest(p)
        obj = json.loads(p.read_text())
        obj["episodes"][0]["frame_map"][1]["relative_pts_s"] = 0.0
        p.write_text(json.dumps(obj))
        result = build_links(self.zip, self.root / "out", p)
        self.assertTrue(next(iter(result["mapping_status_counts"])).startswith("INVALID_MAPPING_MANIFEST"))

    def test_invalid_interval_stops(self):
        self.flora["segments"][0]["end_s"] = 0.0
        with zipfile.ZipFile(self.zip, "w") as z:
            z.writestr("raw_json/demo_2.json", json.dumps(self.flora))
        with self.assertRaises(AdapterError):
            build_links(self.zip, self.root / "out")

    def test_many_flora_to_one_g1_and_half_open_boundary(self):
        p = self.root / "source.json"
        manifest(p)
        obj = json.loads(p.read_text())
        obj["episodes"][0]["g1_segments"] = [
            {"segment_id": "whole", "start_frame": 0, "end_frame": 25}]
        p.write_text(json.dumps(obj))
        build_links(self.zip, self.root / "out", p)
        links = self.read_links()
        self.assertEqual([x["g1_target"]["matched_video_frame_count"] for x in links], [2, 4])
        self.assertEqual([x["g1_target"]["matched_source_frame_min_max"] for x in links], [[0,5],[10,25]])

    def test_repeat_outputs_identical(self):
        build_links(self.zip, self.root / "out")
        before = {p.name:p.read_bytes() for p in (self.root / "out").iterdir()}
        build_links(self.zip, self.root / "out")
        self.assertEqual(before, {p.name:p.read_bytes() for p in (self.root / "out").iterdir()})


if __name__ == "__main__":
    unittest.main()
