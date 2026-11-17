"""Every warning and error code is explained in docs/site/docs/warnings.md."""
from __future__ import annotations

import re
from pathlib import Path

from src_new.api.warning_docs import DOCUMENTED, GROUPED, PAGE, docs_url

ROOT = Path(__file__).resolve().parents[3]
PAGE_MD = ROOT / "docs/site/docs/warnings.md"


def test_page_sections_match_the_code_list():
    headings = set(re.findall(r"^### (\S+)\s*$", PAGE_MD.read_text(), re.M))
    assert headings == set(DOCUMENTED) | set(GROUPED)


def test_every_emitted_warning_code_has_a_section():
    emitted = set()
    for py in (ROOT / "src_new").rglob("*.py"):
        emitted |= set(re.findall(r"add_warning\(\s*\n?\s*\"([a-z_]+)\"", py.read_text(errors="ignore")))
    assert emitted, "no add_warning calls found: pattern out of date"
    undocumented = {c for c in emitted if docs_url(c) == PAGE}
    assert not undocumented, f"add a section to warnings.md for {sorted(undocumented)}"


def test_urls():
    assert docs_url("stage_time_budget") == f"{PAGE}#stage_time_budget"
    assert docs_url("render_failed") == f"{PAGE}#render"
    assert docs_url("unhandled_exception") == f"{PAGE}#internal"
    assert docs_url("something_new") == PAGE
