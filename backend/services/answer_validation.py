"""Structural citation validation. This cannot prove semantic claim support."""

import re

_MARKER = re.compile(r"(?<!!)\[(\d+)\](?!\()")
_REFUSAL = re.compile(
    r"^(?:I (?:could not find|cannot (?:find|determine|establish))|None of the (?:provided|supplied) (?:excerpts|documents) (?:contain|provide)|(?:The |This )?(?:information|answer|take-home pay|net pay) (?:is |was )?not (?:specified|provided|available)|(?:Which|Whose) .+\?$)",
    re.I,
)
UNVERIFIED_ANSWER = "I could not verify the citations in the generated answer. Please inspect the source excerpts or try a more specific question."


def citation_check(answer, excerpt_count):
    markers = [int(m) for m in _MARKER.findall(answer)]
    invalid = [m for m in markers if not 1 <= m <= excerpt_count]
    lines = answer.splitlines()
    uncited = []
    # Ignore Markdown table column headers only when followed by a divider.
    content = []
    for index, line in enumerate(lines):
        if (
            index + 1 < len(lines)
            and "|" in line
            and re.fullmatch(r"[\s|:-]+", lines[index + 1])
            and "-" in lines[index + 1]
        ):
            continue
        content.append(line)
    for block in re.split(r"\n\s*\n|\n(?=\s*(?:[-*•]|\d+[.)])\s|\s*\|)", "\n".join(content)):
        block = block.strip()
        if not block or re.fullmatch(r"[\s|:*-]+", block):
            continue
        # Headings are labels; factual sentences disguised as headings still need citations.
        if block.startswith("#") and not re.search(r"[.!?\d]", block):
            continue
        # Check separate sentences too; a citation in an earlier sentence is not coverage.
        for claim in re.split(r"(?<=[.!?])\s+(?=[A-Z])", block):
            if _MARKER.search(claim):
                continue
            if _REFUSAL.search(claim) and not re.search(r"\d|\bbut\b|\bhowever\b", claim, re.I):
                continue
            uncited.append(claim)
    return {
        "markers": markers,
        "invalid_markers": invalid,
        "uncited_blocks": uncited,
        "valid": not invalid and not uncited,
    }
