"""
Tests for the _hash_text helper in src/tools/data_tools.py

We test only pure behavior:
- Same text -> same hash
- Leading/trailing spaces don't change hash
- Different texts -> different hashes
"""
from src.tools.data_tools import _hash_text

def test_hash_stable_for_same_text():
    """Same text should always give the same hash."""
    text = "Hello agentic world!"
    h1 = _hash_text(text)
    h2 = _hash_text(text)
    assert h1 == h2  # same input -> same output

def test_hash_ignores_leading_trailing_spaces():
    """Stripping behavior: spaces at ends should not change the hash."""
    base = "Hello Threads"
    with_spaces = "    Hello Threads   "

    h1 = _hash_text(base)
    h2 = _hash_text(with_spaces)

    assert h1 == h2


def test_hash_changes_for_different_texts():
    """Different texts should produce different hashes (with overwhelming probability)."""
    t1 = "First diary entry"
    t2 = "Second diary entry"

    h1 = _hash_text(t1)
    h2 = _hash_text(t2)

    assert h1 != h2
