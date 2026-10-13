import json
import tempfile
import unittest
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'src'))
from project2_g3.simple_review import (a_panel_field, blank, can_view_b, read_csv,
                                       save_review, select, summarize, validate_review)

ROOT = Path(__file__).resolve().parents[1]
MANIFEST = ROOT / '0-doc/90-implementation-local/review_selection.csv'
SOURCE = Path('C:/Users/95611/embody/_p2_g3_phase1b_wt/outputs/g3_phase1b_ab/g3_phase1b_ab_20261012/ab_review_sheet_UNSCORED.csv')


class SimpleReviewTests(unittest.TestCase):
    def setUp(self):
        self.rows = read_csv(MANIFEST)
        self.selected = {r['segment_id']:r for r in self.rows}

    def test_selection_deterministic_and_covered(self):
        if not SOURCE.exists():
            self.skipTest('local Phase 1B images unavailable')
        actual = select(read_csv(SOURCE))
        self.assertEqual([r['segment_id'] for r in actual], [r['segment_id'] for r in self.rows])
        self.assertEqual(len(actual), 10)
        self.assertEqual(len({r['episode_id'] for r in actual}), 10)
        self.assertTrue({'SHORT','NORMAL','FIRST','LAST','INTERIOR','COMPLETE','INCOMPLETE'} <= {s for r in actual for s in r['selection_strata'].split('|')})

    def test_a_panel_mapping_and_b_gate(self):
        self.assertEqual(a_panel_field({'panel1_is':'A','panel2_is':'B'}), 'blinded_panel1')
        self.assertEqual(a_panel_field({'panel1_is':'B','panel2_is':'A'}), 'blinded_panel2')
        with self.assertRaises(ValueError):
            a_panel_field({'panel1_is':'A','panel2_is':'A'})
        self.assertFalse(can_view_b({}))
        self.assertFalse(can_view_b({'a_answer':'UNSCORED'}))
        self.assertTrue(can_view_b({'a_answer':'UNCERTAIN'}))

    def test_empty_has_no_improvement(self):
        result = summarize(self.rows, [])
        self.assertEqual(result['context_decision'], 'PENDING_HUMAN_REVIEW')
        self.assertEqual(result['unfinished'], 10)
        self.assertNotIn('improved', result)

    def test_invalid_answers_and_identity(self):
        d = blank(self.rows[0])
        d['a_answer'] = 'MAYBE'
        with self.assertRaises(ValueError):validate_review(d, self.rows[0])
        d['a_answer'] = 'UNSCORED';d['b_answer'] = 'CAN'
        with self.assertRaises(ValueError):validate_review(d, self.rows[0])
        d['b_answer'] = 'UNSCORED';d['segment_id'] = 'wrong'
        with self.assertRaises(ValueError):validate_review(d, self.rows[0])

    def test_save_resume_edit_skip(self):
        with tempfile.TemporaryDirectory() as tmp:
            d = blank(self.rows[0]);d['a_answer']='CANNOT';d['status']='A_SCORED'
            save_review(tmp,d,self.selected)
            saved = json.loads((Path(tmp)/'simple_review.json').read_text(encoding='utf-8'))
            self.assertEqual(saved[d['segment_id']]['a_answer'],'CANNOT')
            d['b_answer']='CAN';d['status']='B_SCORED';save_review(tmp,d,self.selected)
            d['primary_limitation']='NONE';d['status']='COMPLETE';save_review(tmp,d,self.selected)
            self.assertEqual(json.loads((Path(tmp)/'simple_review.json').read_text(encoding='utf-8'))[d['segment_id']]['status'],'COMPLETE')
            skip=blank(self.rows[1]);skip['status']='SKIPPED';save_review(tmp,skip,self.selected)
            self.assertEqual(len(json.loads((Path(tmp)/'simple_review.json').read_text(encoding='utf-8'))),2)

    def test_statistics_are_ordinal_not_accuracy(self):
        reviews=[]
        for row,a,b in zip(self.rows[:3],('CANNOT','UNCERTAIN','CAN'),('CAN','UNCERTAIN','CANNOT')):
            d=blank(row);d.update(a_answer=a,b_answer=b,primary_limitation='NONE',status='COMPLETE');reviews.append(d)
        result=summarize(self.rows,reviews)
        self.assertEqual((result['improved'],result['unchanged'],result['worse']),(1,1,1))
        self.assertEqual(result['cannot_or_uncertain_to_can'],1)
        self.assertEqual(result['unfinished'],7)
        self.assertEqual(len(result['typical_cases']),3)
        self.assertNotIn('suggested_context_decision',result)


if __name__ == '__main__':unittest.main()
