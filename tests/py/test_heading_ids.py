"""Stable heading ids of lesson pages (scripts/content_pipeline.py assign_heading_ids) and the matching check in
scripts/check_rendering.py. Run: python -m pytest -q tests/py"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "scripts"))
from content_pipeline import assign_heading_ids, module_body_span, slugify, _unique  # noqa: E402
from check_rendering import heading_errors  # noqa: E402

# the shape of a built module page: diagnostics cards are nested <article>s inside the body
PAGE = """<article class="module" data-module-page="x"><h1>T</h1>
<div class="gc-prose module-body">
<h2>Теория</h2><h4 class="md-subheading">Шаг 1. Базис</h4>
<h2>Диагностика</h2>
<div class="diag-groups"><article class="diag-item"><h4>Симптом</h4><div><p>x</p></div></article>
<article class="diag-item"><h4>Другой</h4></article></div>
<h2>Чек-лист</h2><ul class="gc-checklist"><li>a</li></ul>
<h2>Источники</h2><h3>Книги</h3><h2>Проверь себя</h2><uav-quiz></uav-quiz>
</div>
<div class="module-done"></div><section class="related"><h2>outside</h2></section>
</article>"""


def test_headings_after_diagnostics_get_ids():
    out, ids = assign_heading_ids(PAGE)
    assert [i for _, i in ids] == ["teoriya", "shag-1-bazis", "diagnostika", "chek-list", "istochniki", "knigi", "prover-sebya"]
    assert "<h2>outside</h2>" in out and "<h4>Симптом</h4>" in out    # outside the body / not a section: untouched
    assert heading_errors(out) == []
    assert any("without a stable build id" in e for e in heading_errors(PAGE))


def test_body_span_ends_at_the_body_div():
    a, b = module_body_span(PAGE)
    assert PAGE[b:].startswith("</div>\n<div class=\"module-done\"")
    assert "Проверь себя" in PAGE[a:b] and "outside" not in PAGE[a:b]


def test_translation_reuse_fresh_and_stale():
    _, src = assign_heading_ids(PAGE)
    en = PAGE.replace("Теория", "Theory").replace("Шаг 1. Базис", "Step 1. Something else")
    _, fresh = assign_heading_ids(en, src, fresh=True)
    assert [i for _, i in fresh] == [i for _, i in src]
    _, stale = assign_heading_ids(en, src, fresh=False)
    assert [i for _, i in stale][:3] == ["teoriya", "step-1-something-else", "diagnostika"]   # h2 shared, sub-headings own


def test_slugs_never_look_like_old_positional_anchors():
    assert slugify("Sec 3") == "sec-3-h"
    assert _unique("sec", {"sec"}) == "sec-h2"
    assert _unique("sec", set()) == "sec"
    assert _unique("a" * 59 + "-b", {"a" * 59 + "-b"}).count("--") == 0
    _, ids = assign_heading_ids('<article data-module-page="x"><div class="module-body"><h2>Sec</h2><h2>Sec</h2></div></article>')
    assert [i for _, i in ids] == ["sec", "sec-h2"]
