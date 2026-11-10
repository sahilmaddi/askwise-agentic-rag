import pytest

from app.ingestion.chunking import recursive_split, sentence_split, splitter

TEXT = "\n\n".join(
    f"Section {i}. " + " ".join(f"Sentence {i}.{j} talks about policy number {j}." for j in range(8)) for i in range(6)
)


@pytest.mark.parametrize("split", [recursive_split, sentence_split])
def test_chunks_respect_the_size_limit_and_keep_all_text(split):
    chunks = split(TEXT, 300, 50)
    assert len(chunks) > 5
    assert all(len(c) <= 300 for c in chunks)
    for word in ("Section 0.", "Sentence 5.7", "policy number 3"):
        assert any(word in c for c in chunks)


def test_recursive_split_prefers_paragraph_boundaries():
    text = "First paragraph about leave.\n\nSecond paragraph about travel."
    assert recursive_split(text, 50, 0) == ["First paragraph about leave.", "Second paragraph about travel."]


def test_consecutive_chunks_overlap():
    chunks = recursive_split(TEXT, 300, 80)
    assert any(chunks[i][-30:] in chunks[i + 1] for i in range(len(chunks) - 1))


def test_sentence_split_never_cuts_a_sentence():
    chunks = sentence_split(TEXT, 300, 0)
    for chunk in chunks:
        assert chunk.endswith(".")


def test_very_long_words_are_still_split():
    assert all(len(c) <= 60 for c in recursive_split("x" * 500, 60, 10))


def test_invalid_settings_are_rejected():
    with pytest.raises(ValueError):
        recursive_split(TEXT, 100, 100)
    with pytest.raises(ValueError):
        splitter("semantic")
