import unittest
from types import SimpleNamespace
import numpy as np
from project2_g1.boundary_engine import BoundaryCandidate, BoundaryDecision, DECISION_KEEP, DECISION_REJECT_ACCEPTANCE, CANDIDATE_DIRECTION, CANDIDATE_GRIPPER
from project2_g1.stage_a12_calibration import derive_context, straightness, breakpoint_candidates, acceptance_callback, StageA12Error

def sig(n=40):
    x=np.arange(n,dtype=float); z=np.zeros(n); speed=np.arange(n,dtype=float)/100
    return SimpleNamespace(n_frames=n,eef_x=x,eef_y=z,eef_z=z,translation_speed=speed,source_episode_id="data/demo_x")
def cand(kind=CANDIDATE_DIRECTION,frame=15):
    return BoundaryCandidate("data/demo_x","x-C1",frame,kind,"r",[],2.0,"PERSISTENT","s","v",extra={"run_length":3})

class StageA12Tests(unittest.TestCase):
    def test_p12_exact_median(self): self.assertEqual(derive_context(sig(),15)["P12"],.23)
    def test_p12_incomplete_fail_open(self):
        c=cand(frame=32); d={c.candidate_id:BoundaryDecision(c.candidate_id,DECISION_KEEP,"x")}; t=[]
        acceptance_callback("P12_ONLY",1.0,None,t)([c],d,sig())
        self.assertEqual(d[c.candidate_id].decision,DECISION_KEEP); self.assertEqual(t[0]["acceptance_decision"],"KEEP_EDGE_CONTEXT_INCOMPLETE")
    def test_straightness_and_degenerate(self):
        self.assertEqual(straightness(sig(),0,11),1.0); s=sig(); s.eef_x[:]=0; self.assertIsNone(straightness(s,0,11))
    def test_c12_windows(self): self.assertEqual(derive_context(sig(),15)["C12"],1.0)
    def test_c12_incomplete_fallback(self):
        c=cand(frame=5); d={c.candidate_id:BoundaryDecision(c.candidate_id,DECISION_KEEP,"x")}; t=[]
        acceptance_callback("P12_C12",0.0,2.0,t)([c],d,sig())
        self.assertEqual(d[c.candidate_id].decision,DECISION_KEEP); self.assertEqual(t[0]["acceptance_decision"],"KEEP_C12_CONTEXT_INCOMPLETE")
    def test_non_direction_never_rejected(self):
        c=cand(CANDIDATE_GRIPPER); d={c.candidate_id:BoundaryDecision(c.candidate_id,DECISION_KEEP,"x")}; t=[]
        acceptance_callback("P12_ONLY",99,None,t)([c],d,sig()); self.assertEqual(d[c.candidate_id].decision,DECISION_KEEP); self.assertFalse(t)
    def test_p12_reject(self):
        c=cand(); d={c.candidate_id:BoundaryDecision(c.candidate_id,DECISION_KEEP,"x")}; t=[]
        acceptance_callback("P12_ONLY",99,None,t)([c],d,sig()); self.assertEqual(d[c.candidate_id].decision,DECISION_REJECT_ACCEPTANCE)
    def test_c12_reject(self):
        c=cand(); d={c.candidate_id:BoundaryDecision(c.candidate_id,DECISION_KEEP,"x")}; t=[]
        acceptance_callback("P12_C12",0,2,t)([c],d,sig()); self.assertEqual(t[0]["acceptance_decision"],"REJECT_C12_TAIL")
    def test_breakpoints_deterministic(self): self.assertEqual(breakpoint_candidates([3,1,2,2]),breakpoint_candidates([2,3,1]))
    def test_diagnostic_forbidden(self):
        with self.assertRaises(StageA12Error): breakpoint_candidates([1,2],sources=["02_selection_internal.csv"])

if __name__=="__main__": unittest.main()
