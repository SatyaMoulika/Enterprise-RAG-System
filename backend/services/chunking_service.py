"""Sentence-aware chunks with whole-unit overlap and a bounded oversized-unit fallback."""

import re
from dataclasses import dataclass

from core.config import settings
from core.errors import InvalidDocument, UploadTooLarge

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
            for sentence in _sentences(paragraph):
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
