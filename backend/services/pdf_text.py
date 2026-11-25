"""Conservative cleanup of PDF line wrapping, without inventing missing table layout."""

import re

_LIST_ITEM = re.compile(r"^\s*(?:[-*•]|\d+[.)])\s+")


def _unfold_word_runs(text):
    """Repair local word-per-line prose even on a page with headings or lists.

    Punctuation is required so ordinary one-word table columns are not guessed
    into prose. Preserve all surrounding blocks and explicit list/table rows.
    """
    lines = text.splitlines()
    result = []
    index = 0
    while index < len(lines):
        line = lines[index].strip()
        if len(line.split()) != 1 or _LIST_ITEM.match(line) or "\t" in line or "|" in line:
            result.append(lines[index])
            index += 1
            continue
        end = index
        words = []
        while end < len(lines):
            candidate = lines[end].strip()
            if not candidate:
                end += 1
                continue
            if (
                len(candidate.split()) != 1
                or _LIST_ITEM.match(candidate)
                or "\t" in candidate
                or "|" in candidate
            ):
                break
            words.append(candidate)
            end += 1
        if len(words) >= 8 and any(re.search(r'[.!?]["”\')\]]*$', word) for word in words):
            result.append(" ".join(words))
            # End the recovered prose block before a following list, table or paragraph.
            if end < len(lines):
                result.append("")
        else:
            result.extend(lines[index:end])
        index = end
    return "\n".join(result)


def normalize_pdf_text(text: str) -> str:
    text = text.replace("\r\n", "\n").replace("\r", "\n")
    # A discretionary soft hyphen at a wrapped line is not a literal compound hyphen.
    text = re.sub(r"\u00ad[ \t]*\n[ \t]*", "", text).replace("\u00ad", "")
    text = _unfold_word_runs(text)
    lines = [line.strip() for line in text.splitlines() if line.strip()]
    # Some PDF producers put blank lines between individually positioned words.
    # Treat only long, overwhelmingly single-token prose streams as broken wraps.
    # Explicit lists/tables keep their structure; paragraph layout cannot be
    # recovered reliably from a vertical word stream, but sentence punctuation can.
    if (
        len(lines) >= 30
        and sum(len(line.split()) == 1 for line in lines) / len(lines) >= 0.85
        and sum(bool(re.search(r"[.!?]$", line)) for line in lines) >= 2
        and not any("\t" in line or "|" in line or _LIST_ITEM.match(line) for line in lines)
    ):
        text = " ".join(lines)
    paragraphs = []
    for paragraph in re.split(r"\n[ \t]*\n+", text):
        lines = [line.strip() for line in paragraph.splitlines() if line.strip()]
        if not lines:
            continue
        # Retain explicit table columns/Markdown table rows and separate list items.
        if any("\t" in line or "|" in line for line in lines):
            paragraphs.append("\n".join(lines))
            continue
        result = ""
        previous_list = False
        for line in lines:
            item = bool(_LIST_ITEM.match(line))
            if result:
                result += "\n" if item or previous_list else "" if result.endswith("-") else " "
            result += re.sub(r"[ \t]+", " ", line)
            previous_list = item
        paragraphs.append(result)
    return "\n\n".join(paragraphs)
