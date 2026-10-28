"""Read-only local evidence audit. CPU decoding only; no rendering or inference.

Uses recovered export records and pinned G3 development G1 rows. Does not
reconstruct missing G1 boundaries or promote candidate links to full alignment.
"""
import argparse
import csv
import hashlib
import json
import re
import subprocess
import sys
import zipfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from src.project2_g3.flora_adapter import build_links, EXPECTED_CLOCK


def sha(path):
    h = hashlib.sha256()
    with Path(path).open('rb') as f:
        for b in iter(lambda: f.read(1024 * 1024), b''):
            h.update(b)
    return h.hexdigest()


def write_csv(path, rows):
    with path.open('w', encoding='utf-8-sig', newline='') as f:
        w = csv.DictWriter(f, fieldnames=list(rows[0]))
        w.writeheader()
        w.writerows(rows)


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--flora-zip', type=Path, required=True)
    p.add_argument('--recovery-dir', type=Path, required=True)
    p.add_argument('--g1-targets', type=Path, required=True)
    p.add_argument('--export-script', type=Path, required=True)
    p.add_argument('--output-dir', type=Path, required=True)
    a = p.parse_args()
    if not __debug__:
        raise RuntimeError('Optimized Python disables audit assertions; run without -O')
    import h5py
    import imageio_ffmpeg
    out = a.output_dir
    out.mkdir(parents=True, exist_ok=True)
    export = a.recovery_dir / 'p2_video_export_manifest.json'
    record = json.loads(export.read_text(encoding='utf-8'))
    raw, low = Path(record['source_hdf5']), Path(record['low_dim_hdf5'])
    raw_sha, low_sha = sha(raw), sha(low)
    assert raw_sha == record['source_sha256'], 'RAW_HASH_MISMATCH'
    assert low_sha == record['low_dim_sha256'], 'LOW_DIM_HASH_MISMATCH'
    targets = list(csv.DictReader(a.g1_targets.open(encoding='utf-8-sig', newline='')))
    export_hash = sha(export)
    evidence = {'export_manifest_sha256': export_hash, 'export_script_sha256': sha(a.export_script),
                'g1_targets_sha256': sha(a.g1_targets), 'raw_sha256': raw_sha, 'low_dim_sha256': low_sha,
                'episodes': []}
    mappings, audits, gaps = [], [], []
    before = sha(a.flora_zip)
    with zipfile.ZipFile(a.flora_zip) as z, h5py.File(raw, 'r') as h, h5py.File(low, 'r') as l:
        for member in sorted(n for n in z.namelist() if n.startswith('raw_json/') and n.endswith('.json')):
            ep = Path(member).stem
            obj = json.loads(z.read(member))
            eid = 'data/' + ep
            meta_path = a.recovery_dir / 'metadata' / (ep + '_agentview_20fps.metadata.json')
            meta = json.loads(meta_path.read_text(encoding='utf-8'))
            video = a.recovery_dir / 'videos' / (ep + '_agentview_20fps.mp4')
            video_sha = sha(video)
            assert video_sha == obj['input_sha256']['main'] == meta['export_sha256'], ep + ':VIDEO_SHA'
            assert meta['source_sha256'] == raw_sha and meta['low_dim_sha256'] == low_sha
            assert meta['source_episode_id'] == eid and meta['camera'] == 'agentview'
            assert meta['validated_frozen_rgb_pixel_hashes']['status'] == 'PASS'
            assert obj['camera_roles'] == ['main'] and obj['source_clock'] == EXPECTED_CLOCK
            n = len(h[eid + '/states'])
            assert n == len(h[eid + '/actions']) == len(l[eid + '/actions']) == meta['frame_count']
            cmd = [imageio_ffmpeg.get_ffmpeg_exe(), '-nostdin', '-hwaccel', 'none', '-i', str(video),
                   '-vf', 'showinfo', '-an', '-fps_mode', 'passthrough', '-f', 'null', '-']
            proc = subprocess.run(cmd, capture_output=True, text=True, check=True)
            decoded = [(int(i), float(t)) for i,t in re.findall(r'\bn:\s*(\d+).*?\bpts_time:\s*([-\d.e+]+)', proc.stderr)]
            assert len(decoded) == n and [i for i,t in decoded] == list(range(n)), ep + ':DECODE_COUNT'
            first = decoded[0][1]
            assert first == 0 and all(abs(t - i/20) < 1e-5 for i,t in decoded), ep + ':PTS_OR_OFFSET'
            assert abs(obj['duration_s'] - meta['duration_seconds']) < 1e-5
            chosen = [r for r in targets if r['episode_id'] == eid]
            assert chosen, ep + ':NO_PINNED_G1_TARGET'
            segs = [{'segment_id': r['segment_id'], 'start_frame': int(r['start_frame']),
                     'end_frame': int(r['end_frame'])} for r in chosen]
            covered = {i for r in segs for i in range(r['start_frame'],r['end_frame']+1)}
            assert covered <= set(range(n))
            frame_map = [{'video_frame_index':i, 'relative_pts_s':t-first, 'source_frame_index':i} for i,t in decoded]
            mappings.append({'flora_episode_id':ep, 'source_episode_id':eid, 'source_manifest_sha256':export_hash,
                             'flora_video_sha256':video_sha, 'source_clock':EXPECTED_CLOCK,
                             'frame_map':frame_map, 'g1_segments':segs})
            audits.append({'episode_id':ep, 'source_status':'VERIFIED_EXPORT_LINEAGE',
                           'g1_status':'PARTIAL_PINNED_TARGETS_ONLY', 'video_sha256':video_sha,
                           'source_state_count':n, 'decoded_pts_count':len(decoded), 'pts_zero':first,
                           'camera':'main=agentview', 'crop_resample':'none per export code',
                           'pinned_g1_target_count':len(segs), 'covered_source_frames':len(covered),
                           'uncovered_source_frames':n-len(covered),
                           'reason':'Full existing G1 episode manifest not recovered; do not infer other boundaries'})
            evidence['episodes'].append({'episode_id':ep,'metadata_sha256':sha(meta_path),
                                        'states_shape':list(h[eid+'/states'].shape),
                                        'actions_shape':list(h[eid+'/actions'].shape),
                                        'video_sha256':video_sha,'pts':decoded})
            for i,s in enumerate(obj['segments']):
                text = s['caption'].lower()
                candidates = [v for v in ('align','regrasp','rotate','push','handover','recovery') if v in text]
                phases = []
                if 'pick' in text: phases += ['approach','grasp','lift','transport']
                if 'put' in text or 'place' in text: phases += ['transport','place','retract']
                gaps.append({'episode_id':ep,'flora_segment_index':i,'caption':s['caption'],
                             'candidate_phases':'|'.join(phases), 'gap_terms':'|'.join(candidates),
                             'status':'UNVERIFIED_CAPTION_ONLY',
                             'reason':'Intent window may span phases; other=visible out-of-enum, uncertain=insufficient evidence; no automatic label'})
    mapping_path = out/'recovered_source_mapping.json'
    mapping_path.write_text(json.dumps({'schema_version':'P2_FLORA_G1_SOURCE_MAPPING_V0_1','episodes':mappings},sort_keys=True,indent=2)+'\n',encoding='utf-8')
    summary = build_links(a.flora_zip,out,mapping_path)
    link_path = out / 'flora_g1_links.jsonl'
    links = [json.loads(line) for line in link_path.read_text(encoding='utf-8').splitlines()]
    for link in links:
        target = link['g1_target']
        link['local_source_audit'] = {
            'source_status': 'VERIFIED_EXPORT_LINEAGE',
            'mapping_status': ('VERIFIED_PINNED_TARGET_OVERLAP' if target.get('g1_segment_id') else 'UNALIGNED_MISSING_OTHER_G1_TARGETS'),
            'evidence_file': 'local_evidence_audit.json',
            'export_manifest_sha256': export_hash,
            'g1_targets_sha256': sha(a.g1_targets),
            'scope': 'Partial pinned G1 targets only; original adapter status retained'}
    link_path.write_text(''.join(json.dumps(row,ensure_ascii=False,sort_keys=True)+'\n' for row in links),encoding='utf-8')
    summary['verified_pinned_target_link_count'] = sum(bool(row['g1_target'].get('g1_segment_id')) for row in links)
    summary['unmapped_flora_segment_count'] = sum(not bool(row['g1_target'].get('g1_segment_id')) for row in links)
    summary['covered_source_frames'] = sum(row['covered_source_frames'] for row in audits)
    summary['uncovered_source_frames'] = sum(row['uncovered_source_frames'] for row in audits)
    # Independent audit proves the source chain, but only a subset of G1 targets exists.
    summary.update({'source_recovery_verified_episode_count':len(audits), 'fully_aligned_episode_count':0,
                    'partially_aligned_episode_count':len(audits), 'g1_inference_readiness':'BLOCKED',
                    'blocker':'Full pre-existing G1 episode manifests and complete target evidence packs not recovered',
                    'archive_sha256_before':before,'archive_sha256_after':sha(a.flora_zip)})
    assert summary['archive_sha256_before'] == summary['archive_sha256_after']
    write_csv(out/'alignment_audit.csv',audits)
    write_csv(out/'action_taxonomy_gap_candidates.csv',gaps)
    (out/'local_evidence_audit.json').write_text(json.dumps(evidence,sort_keys=True,indent=2)+'\n',encoding='utf-8')
    (out/'adapter_summary.json').write_text(json.dumps(summary,sort_keys=True,indent=2)+'\n',encoding='utf-8')
    print(json.dumps(summary,indent=2))
    return 3  # partial G1 coverage always blocks the formal gate


if __name__ == '__main__':
    sys.exit(main())
