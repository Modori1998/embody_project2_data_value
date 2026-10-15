import sys
from pathlib import Path

sys.path[:0] = [str(Path(__file__).resolve().parents[1] / "src"), str(Path(__file__).resolve().parents[1] / "scripts")]
from run_g3h_p1b_smoke import CONTEXT_SIZE, MAX_TOKENS, SEGMENT, make_payload
from project2_g3 import g3h_two_stage as H


def test_single_cell_only_changes_output_budget():
    row = {"indices": [63, 84, 106], "images": ["data:image/png;base64,a"] * 3}
    payload = make_payload("8b", row)
    assert SEGMENT == "demo_2-S0003"
    assert CONTEXT_SIZE == 4096 and MAX_TOKENS == 1024
    assert payload["max_tokens"] == 1024
    assert payload["temperature"] == 0 and payload["seed"] == 1234
    assert payload["response_format"]["schema"] == H.fact_schema()
    assert payload["messages"][0]["content"][0]["text"] == H.render_fact_prompt(SEGMENT, row["indices"])
    assert len(payload["messages"][0]["content"]) == 4
