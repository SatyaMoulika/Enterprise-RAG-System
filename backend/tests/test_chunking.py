import pytest

from core.config import settings
from core.errors import InvalidDocument, UploadTooLarge
from services.chunking_service import ChunkingService
from services.pdf_text import normalize_pdf_text


@pytest.fixture(autouse=True)
def limits(monkeypatch):
    monkeypatch.setattr(settings, "CHUNK_SIZE", 100)
    monkeypatch.setattr(settings, "CHUNK_OVERLAP", 0)
    monkeypatch.setattr(settings, "CHUNK_MAX_CHARACTERS", 4000)


def test_sentence_boundaries_replace_character_slicing():
    sentences = [
        "First, the framework addresses privacy and accountability.",
        "Second, it considers bias and oversight in healthcare systems.",
        "Finally, it sets expectations for safe and effective evaluation.",
    ]
    chunks = ChunkingService.chunk_text(" ".join(sentences))
    assert chunks == sentences
    assert all(chunk.endswith(".") for chunk in chunks)


def test_sentence_larger_than_soft_target_is_kept_whole():
    sentence = (
        "The framework addresses " + "privacy, fairness, oversight, " * 7 + "and accountability."
    )
    assert len(sentence) > settings.CHUNK_SIZE
    assert ChunkingService.chunk_text(sentence) == [sentence]


def test_whole_sentence_overlap_never_starts_inside_a_word(monkeypatch):
    monkeypatch.setattr(settings, "CHUNK_SIZE", 135)
    monkeypatch.setattr(settings, "CHUNK_OVERLAP", 20)
    sentences = [
        "First sentence includes useful context for the answer.",
        "Second sentence adds a clear supporting explanation.",
        "Third sentence completes the discussion of the topic.",
    ]
    chunks = ChunkingService.chunk_text(" ".join(sentences))
    assert chunks == [" ".join(sentences[:2]), " ".join(sentences[1:])]


def test_common_abbreviations_initials_and_decimals_stay_with_the_sentence():
    sentence = "Dr. A. Smith reviews U.S. guidance, e.g. the 3.14 threshold."
    assert ChunkingService.chunk_text(sentence) == [sentence]


def test_paragraph_structure_is_preserved_when_it_fits(monkeypatch):
    monkeypatch.setattr(settings, "CHUNK_SIZE", 500)
    text = "First paragraph is complete.\n\nSecond paragraph has the details."
    assert ChunkingService.chunk_text(text) == [text]


def test_quoted_sentence_punctuation_and_question_marks():
    sentences = [
        'The policy says "Review every result."',
        "Is this a complete question?",
        "Yes, it is!",
    ]
    assert " ".join(ChunkingService.chunk_text(" ".join(sentences))) == " ".join(sentences)


def test_oversized_sentence_falls_back_at_word_boundaries(monkeypatch):
    monkeypatch.setattr(settings, "CHUNK_MAX_CHARACTERS", 140)
    text = " ".join(f"word{i}" for i in range(80)) + "."
    chunks = ChunkingService.chunk_text(text)
    assert " ".join(chunks) == text
    assert all(len(chunk) <= 140 for chunk in chunks)
    assert all(chunk.startswith("word") for chunk in chunks)


def test_unbroken_token_is_rejected_instead_of_cut_mid_word(monkeypatch):
    monkeypatch.setattr(settings, "CHUNK_MAX_CHARACTERS", 100)
    with pytest.raises(InvalidDocument, match="unbroken text segment"):
        ChunkingService.chunk_text("x" * 101)


def test_chunk_limit_is_enforced(monkeypatch):
    monkeypatch.setattr(settings, "MAX_DOCUMENT_CHUNKS", 1)
    with pytest.raises(UploadTooLarge):
        ChunkingService.chunk_text(
            "A whole sentence "
            + "with context " * 5
            + ". Another whole sentence "
            + "with detail " * 5
            + "."
        )


def test_blank_text_produces_no_chunks():
    assert ChunkingService.chunk_text(" \n\n ") == []


def test_numbered_list_marker_is_not_a_separate_sentence():
    text = "1. Review the document and verify the cited evidence."
    assert ChunkingService.chunk_text(text) == [text]


def test_pdf_wrap_cleanup_preserves_paragraphs_and_lists():
    text = "Regulatory frameworks address\nprivacy, bias and accountability.\n\n- Review sources.\n- Verify results."
    assert (
        normalize_pdf_text(text)
        == "Regulatory frameworks address privacy, bias and accountability.\n\n- Review sources.\n- Verify results."
    )


def test_pdf_soft_hyphen_and_table_columns():
    assert normalize_pdf_text("embed\u00ad\ndings connect ideas.") == "embeddings connect ideas."
    assert normalize_pdf_text("long-\nterm outcomes.") == "long-term outcomes."
    table = "Category\tApplication\nVision\tDetection"
    assert normalize_pdf_text(table) == table


def test_real_pdf_line_wraps_are_normalized(tmp_path):
    from pypdf import PdfWriter
    from pypdf.generic import DecodedStreamObject, DictionaryObject, NameObject

    from services.loader_service import LoaderService

    writer = PdfWriter()
    page = writer.add_blank_page(width=612, height=792)
    font = DictionaryObject(
        {
            NameObject("/Type"): NameObject("/Font"),
            NameObject("/Subtype"): NameObject("/Type1"),
            NameObject("/BaseFont"): NameObject("/Helvetica"),
        }
    )
    page[NameObject("/Resources")] = DictionaryObject(
        {NameObject("/Font"): DictionaryObject({NameObject("/F1"): writer._add_object(font)})}
    )
    stream = DecodedStreamObject()
    stream.set_data(
        b"BT /F1 12 Tf 40 750 Td (Regulatory frameworks address) Tj 0 -16 Td (privacy, bias and accountability.) Tj ET"
    )
    page[NameObject("/Contents")] = writer._add_object(stream)
    path = tmp_path / "wrapped.pdf"
    writer.write(path)
    text = LoaderService.extract_text(path)
    assert text == "Regulatory frameworks address privacy, bias and accountability."
    assert ChunkingService.chunk_text(text) == [text]
