"""Browser smoke check for a built G3F-P1 report served on localhost."""
import argparse
from playwright.sync_api import sync_playwright


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("url")
    args = parser.parse_args()
    errors = []
    with sync_playwright() as playwright:
        browser = playwright.chromium.launch(
            executable_path=r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe",
            headless=True,
        )
        page = browser.new_page()
        page.on("pageerror", lambda error: errors.append(str(error)))
        response = page.goto(args.url, wait_until="load")
        assert response and response.status == 200
        assert page.locator("#integrity").inner_text().find("一致") >= 0
        result = page.evaluate("""() => ({
          segments: data.length,
          rgb: images.size,
          gold: humanEvidence.size,
          predictions: rawPredictions.size,
          prompts: prompts.size,
          qc: qcRecords.size,
          scores: Object.fromEntries('ABC'.split('').map(a => [a, {
            f1: stats(a).f1.toFixed(3), exact: stats(a).exact,
            phase: stats(a).phase, motion: stats(a).per.object_motion
          }])),
          cases: Object.fromEntries(data.map(d => [d.id, Object.fromEntries('ABC'.split('').map(a =>
            [a, {phase: rowPred(d,a).phase, events: rowPred(d,a).events}]))]))
        })""")
        assert (result["segments"], result["rgb"], result["gold"], result["predictions"], result["prompts"], result["qc"]) == (12, 36, 12, 36, 36, 36)
        expected = {"A": ("0.636", 5, 7, (0, 0, 3)), "B": ("0.533", 2, 7, (2, 7, 1)), "C": ("0.560", 3, 6, (0, 2, 3))}
        for arm, (f1, exact, phase, motion) in expected.items():
            s = result["scores"][arm]
            m = s["motion"]
            assert (s["f1"], s["exact"], s["phase"], (m["tp"], m["fp"], m["fn"])) == (f1, exact, phase, motion)
        cases = result["cases"]
        assert "grasp_attempt" not in cases["demo_159-S0003"]["B"]["events"]
        assert cases["demo_180-S0001"]["A"]["events"] == []
        assert "object_motion" in cases["demo_180-S0001"]["B"]["events"]
        assert "grasp_attempt" in cases["demo_180-S0001"]["C"]["events"]
        for arm in "ABC":
            assert cases["demo_172-S0004"][arm]["phase"] == "grasp"
            assert "grasp_attempt" in cases["demo_172-S0004"][arm]["events"]
        for sid in ("demo_2-S0003", "demo_4-S0003"):
            for arm in "ABC":
                assert "object_motion" not in cases[sid][arm]["events"] or arm == "B"
        for sid in cases:
            page.evaluate("id => selectCase(id)", sid)
            assert page.locator("#caseDetail .frame img").count() == 3
            assert page.locator("#caseDetail .frame img").evaluate_all("imgs => imgs.every(x => x.complete && x.naturalWidth > 0)")
            assert page.locator("#caseDetail .armcard").count() == 3
            assert page.locator("#caseDetail .armcard details").count() == 9
        assert not errors, errors
        browser.close()
    print("PASS HTTP 200, 12 cases, 36 images, 36 full responses/prompts/QC, scores, key cases, no JS errors")


if __name__ == "__main__":
    main()
