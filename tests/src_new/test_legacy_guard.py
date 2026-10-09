"""Guard: src_new must never import the legacy (deprecated) loader."""

from pathlib import Path


SRC_NEW = Path(__file__).resolve().parent.parent.parent / "src_new"

# precise needles that cannot collide with 'src_new.loader' or 'import src_new'
FORBIDDEN = ("src.loader", "from src import loader")


def test_src_new_never_imports_legacy_loader():
    offenders = []
    for py in SRC_NEW.rglob("*.py"):
        text = py.read_text(encoding="utf-8", errors="replace")
        for needle in FORBIDDEN:
            if needle in text:
                offenders.append(f"{py}:{needle}")
    assert offenders == []
