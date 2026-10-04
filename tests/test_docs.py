from pathlib import Path

from charts import docs

DOCS = Path(__file__).resolve().parent.parent / "docs" / "csv"


def test_csv_docs_are_up_to_date():
    """Run `python -m charts.docs` if this fails: the docs are generated from the code."""
    for name, text in docs.all_pages().items():
        assert (DOCS / name).read_text(encoding="utf-8") == text, f"{name} is stale"
    assert {p.name for p in DOCS.glob("*.md")} == set(docs.all_pages())
