"""Conservative cleanup of PDF line wrapping, without inventing missing table layout."""

import re

_LIST_ITEM = re.compile(r"^\s*(?:[-*•]|\d+[.)])\s+")


def normalize_pdf_text(text: str) -> str:
    text = text.replace("\r\n", "\n").replace("\r", "\n")
    # A discretionary soft hyphen at a wrapped line is not a literal compound hyphen.
    text = re.sub(r"\u00ad[ \t]*\n[ \t]*", "", text).replace("\u00ad", "")
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
