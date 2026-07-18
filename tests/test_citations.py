from app.rag.citations import (
    allowed_citations_from_items,
    extract_citations,
    repair_remove_illegal_citations,
)
from app.utils import normalize_citation_order


def test_extract_citations_basic():
    text = "Bitte prüfen nach § 24 SGB X und § 31a SGB II."
    cites = extract_citations(text)
    assert "§ 24 SGB X" in cites
    assert "§ 31A SGB II" in cites or "§ 31a SGB II".upper() in cites


def test_normalize_citation_order():
    t = normalize_citation_order("nach SGB X § 24 und SGB 2")
    assert "§ 24 SGB X" in t
    assert "SGB II" in t


def test_allowed_from_items_and_illegal_strip():
    items = [
        {"law": "SGB X", "paragraph": "§ 24", "text": "..."},
        {"law": "SGB II", "paragraph": "31a", "text": "..."},
    ]
    allowed = allowed_citations_from_items(items)
    assert "§ 24 SGB X" in allowed
    assert "§ 31A SGB II" in allowed

    letter = "Ich berufe mich auf § 24 SGB X und § 99 SGB II."
    used = extract_citations(letter)
    illegal = sorted(list(used - allowed))
    assert any("99" in c for c in illegal)

    fixed = repair_remove_illegal_citations(letter, illegal)
    remaining = extract_citations(fixed)
    assert not any("99" in c for c in remaining)
    assert "§ 24 SGB X" in remaining
