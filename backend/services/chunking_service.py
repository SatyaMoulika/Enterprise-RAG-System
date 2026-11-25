"""Sentence-aware chunks with whole-unit overlap and a bounded oversized-unit fallback."""

import re
from dataclasses import dataclass

from core.config import settings
from core.errors import InvalidDocument, UploadTooLarge

CHUNKER_VERSION = "source-paragraphs-v3"


@dataclass(frozen=True)
class SourceChunk:
    chunk_text: str
    page_start: int | None
    page_end: int | None
    section: str | None
    section_key: str
    start_offset: int
    end_offset: int


_ABBREVIATIONS = {
    "dr.",
    "mr.",
    "mrs.",
    "ms.",
    "prof.",
    "sr.",
    "jr.",
    "e.g.",
    "i.e.",
    "vs.",
    "etc.",
    "fig.",
    "no.",
    "al.",
}
_END = re.compile(r"""[.!?]+["'”’\)\]]*(?=\s|$)""")


@dataclass(frozen=True)
class _Unit:
    text: str
    paragraph: int


def _sentences(paragraph: str):
    start = 0
    for match in _END.finditer(paragraph):
        prefix = paragraph[max(0, match.end() - 256) : match.end()].rstrip("\"'”’)]")
        token = prefix.split()[-1].lower()
        # Avoid splitting names, common academic abbreviations and numbered list prefixes.
        if (
            token in _ABBREVIATIONS
            or re.search(r"\b(?:[A-Z]\.)+$", prefix)
            or re.search(r"(?:^|\n)\s*\d+\.$", prefix)
        ):
            continue
        sentence = paragraph[start : match.end()].strip()
        if sentence:
            yield sentence
        start = match.end()
    if trailing := paragraph[start:].strip():
        yield trailing


def _bounded_units(text: str, paragraph: int, maximum: int):
    while len(text) > maximum:
        boundaries = list(re.finditer(r"\s+", text[: maximum + 1]))
        if not boundaries:
            raise InvalidDocument(
                "Document contains an unbroken text segment longer than the indexing limit"
            )
        boundary = boundaries[-1]
        yield _Unit(text[: boundary.start()].strip(), paragraph)
        text = text[boundary.end() :].lstrip()
    if text:
        yield _Unit(text, paragraph)


def _join(units: list[_Unit]) -> str:
    output = ""
    previous = None
    for unit in units:
        if output:
            output += "\n\n" if unit.paragraph != previous else " "
        output += unit.text
        previous = unit.paragraph
    return output


class ChunkingService:
    @staticmethod
    def chunk_text(text: str) -> list[str]:
        target = settings.CHUNK_SIZE
        maximum = settings.CHUNK_MAX_CHARACTERS
        chunks: list[str] = []
        current: list[_Unit] = []

        def emit():
            if len(chunks) >= settings.MAX_DOCUMENT_CHUNKS:
                raise UploadTooLarge("Document has too many chunks")
            chunks.append(_join(current))

        for number, paragraph in enumerate(re.split(r"\n\s*\n", text.strip())):
            # Tables/list blocks are structural units. Sentence joining must not flatten rows.
            structured = any(
                "\t" in line or "|" in line or re.match(r"\s*(?:[-*•]|\d+[.)])\s", line)
                for line in paragraph.splitlines()
            )
            # Keep a paragraph together when it fits. Only oversized paragraphs
            # need sentence grouping; whitespace splitting is the final hard-limit fallback.
            for sentence in (
                [paragraph] if structured or len(paragraph) <= target else _sentences(paragraph)
            ):
                for unit in _bounded_units(sentence, number, maximum):
                    if current and len(_join([*current, unit])) > target:
                        emit()
                        overlap: list[_Unit] = []
                        if settings.CHUNK_OVERLAP:
                            for previous in reversed(current):
                                overlap.insert(0, previous)
                                if len(_join(overlap)) >= settings.CHUNK_OVERLAP:
                                    break
                        # Carry only whole sentences/units that leave room for new content.
                        while overlap and len(_join([*overlap, unit])) > target:
                            overlap.pop(0)
                        current = overlap
                    current.append(unit)
        if current:
            emit()
        return chunks

    @staticmethod
    def chunk_document(document) -> list[SourceChunk]:
        """Keep page/section boundaries and map each excerpt back to source offsets."""
        chunks = []
        section = None
        section_number = 0
        heading = re.compile(r"^(?:#{1,6}\s+[^\n]+|[A-Z][A-Z \d/&()-]{2,99})[ \t]*$", re.M)
        for page in document.pages:
            boundaries = [
                0,
                *[m.start() for m in heading.finditer(page.text) if m.start()],
                len(page.text),
            ]
            for start, end in zip(boundaries, boundaries[1:]):
                block = page.text[start:end]
                match = heading.match(block)
                if match:
                    section = match.group(0).strip().lstrip("#").strip()
                    section_number += 1
                cursor = 0
                for text in ChunkingService.chunk_text(block):
                    # Whitespace may have been unfolded; cite the exact original source span.
                    pattern = r"\s+".join(re.escape(word) for word in text.split())
                    location = re.search(pattern, block[cursor:])
                    if location is None:
                        raise InvalidDocument("Unable to map a chunk to its source")
                    left, right = cursor + location.start(), cursor + location.end()
                    chunks.append(
                        SourceChunk(
                            block[left:right],
                            page.number,
                            page.number,
                            section,
                            f"section-{section_number}",
                            start + left,
                            start + right,
                        )
                    )
                    # Search after the previous start, allowing whole-unit overlap.
                    cursor = left + 1
                    if len(chunks) > settings.MAX_DOCUMENT_CHUNKS:
                        raise UploadTooLarge("Document has too many chunks")
        return chunks
