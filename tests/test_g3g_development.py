"""Frozen G3G Development decision thresholds."""
from scripts.evaluate_g3g_development import development_gates


def test_all_six_gates_required_and_absolute_f1_gain():
    a = {"event_type_micro_f1": 0.50, "exact_match": 4, "phase_correct": 6}
    b = {"event_type_micro_f1": 0.60, "exact_match": 5, "phase_correct": 5,
         "by_type": {"object_motion": {"tp": 2, "fp": 1}}}
    engineering = {"4B": {"final_valid": 24}, "8B": {"final_valid": 24}}
    assert all(development_gates(a, b, engineering).values())
    b["event_type_micro_f1"] = 0.599
    assert not development_gates(a, b, engineering)["event_micro_f1_gain_ge_0_10"]
    b["event_type_micro_f1"] = 0.60
    b["by_type"]["object_motion"]["tp"] = 1
    assert not development_gates(a, b, engineering)["object_motion_tp_ge_2"]
    engineering["8B"]["final_valid"] = 23
    assert not development_gates(a, b, engineering)["engineering_valid"]
