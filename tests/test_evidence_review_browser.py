import json

import pytest
from playwright.sync_api import sync_playwright

from sentio.evaluation.evidence_corpus import build_corpus
from sentio.evaluation.evidence_features import collect_features
from sentio.evaluation.evidence_review import export_review


@pytest.mark.browser
def test_review_page_is_readable_recovers_and_does_not_label_skips(tmp_path):
    corpus = build_corpus()
    pack = collect_features(corpus)
    output = tmp_path / "review.html"
    export_review(corpus, pack, output)
    assert "proposed_label" not in output.read_text(encoding="utf-8")
    with sync_playwright() as runtime:
        browser = runtime.chromium.launch()
        page = browser.new_page(viewport={"width": 390, "height": 844})
        errors = []
        page.on("pageerror", lambda error: errors.append(str(error)))
        page.goto(output.as_uri())
        assert "0 of" in page.locator("#progress").inner_text()
        first = page.locator("#question").inner_text()
        page.locator("#yes").click()
        assert "reviewer name" in page.locator("#message").inner_text()
        page.locator("#reviewer").fill("synthetic browser fixture")
        page.locator("#rationale").fill("Synthetic browser test; not an actual evidence review.")
        page.locator("#yes").click()
        assert "1 of" in page.locator("#progress").inner_text()
        assert page.locator("#question").inner_text() == first
        page.locator("#skip").click()
        assert "1 of" in page.locator("#progress").inner_text()
        page.reload()
        assert "1 of" in page.locator("#progress").inner_text()
        with page.expect_download() as downloaded:
            page.locator("#download").click()
        annotations = json.loads(downloaded.value.path().read_text(encoding="utf-8"))
        assert len(annotations) == 1
        assert annotations[0]["reviewer"] == "synthetic browser fixture"
        assert page.evaluate("document.documentElement.scrollWidth <= innerWidth")
        assert errors == []
        browser.close()
