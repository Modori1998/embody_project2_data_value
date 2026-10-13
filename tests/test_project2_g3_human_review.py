import json
import tempfile
import unittest
from pathlib import Path
import sys
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'src'))
from project2_g3.human_review import METRICS, blank, read_csv, save_review, select, summarize, validate_review

MANIFEST=Path(__file__).resolve().parents[1]/'0-doc/90-implementation-local/phase1c_review_selection_manifest.csv'

class HumanReviewTests(unittest.TestCase):
    def setUp(self):self.rows=read_csv(MANIFEST)
    def test_selection_locked_and_deterministic(self):
        source=read_csv(Path('C:/Users/95611/embody/_p2_g3_phase1b_wt/outputs/g3_phase1b_ab/g3_phase1b_ab_20261012/ab_review_sheet_UNSCORED.csv'))
        a=select(source);self.assertEqual([r['segment_id'] for r in a],[r['segment_id'] for r in self.rows]);self.assertEqual(len(a),24)
        self.assertEqual(len({r['episode_id'] for r in a}),12)
        self.assertTrue({'SHORT','NONSHORT','FIRST','LAST','INTERIOR','COMPLETE','INCOMPLETE'} <= {s for r in a for s in r['selection_strata'].split('|')})
    def test_empty_does_not_claim_improvement(self):
        result=summarize(self.rows,[]);self.assertEqual(result['decision'],'PENDING_HUMAN_REVIEW');self.assertNotIn('metrics',result)
    def test_invalid_and_identity_rejected(self):
        d=blank(self.rows[0],'alice');d['A_release_decidable']='GOOD'
        with self.assertRaises(ValueError):validate_review(d,d['segment_id'],'alice')
        d['A_release_decidable']='UNSCORED'
        with self.assertRaises(ValueError):validate_review(d,'wrong','alice')
        d['status']='SKIPPED'
        with self.assertRaises(ValueError):validate_review(d,d['segment_id'],'alice')
    def test_resume_and_reviewer_isolation(self):
        with tempfile.TemporaryDirectory() as tmp:
            selected={r['segment_id']:r for r in self.rows};a=blank(self.rows[0],'alice');a['status']='SKIPPED';a['skip_reason']='unclear';save_review(tmp,a,selected)
            b=blank(self.rows[0],'bob');save_review(tmp,b,selected)
            self.assertEqual(json.loads((Path(tmp)/'alice.json').read_text())[a['segment_id']]['status'],'SKIPPED')
            self.assertEqual(json.loads((Path(tmp)/'bob.json').read_text())[b['segment_id']]['status'],'UNSCORED')
    def test_outside_event_is_separate_from_target_release(self):
        d=blank(self.rows[0],'alice');d['status']='COMPLETE';d['event_outside_target']='YES'
        for arm in 'AB':
            for m in METRICS:d[f'{arm}_{m}']='INSUFFICIENT'
        result=summarize(self.rows,[d]);self.assertEqual(result['event_outside_target'],1)
        self.assertEqual(result['metrics']['release_decidable']['pairs']['improved'],0)

if __name__=='__main__':unittest.main()
