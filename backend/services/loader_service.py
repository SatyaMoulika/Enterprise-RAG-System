from dataclasses import dataclass, field
from pathlib import Path

from pypdf import PdfReader

from core.config import settings
from core.errors import InvalidDocument, UploadTooLarge
from services.pdf_text import normalize_pdf_text


@dataclass(frozen=True)
class SourcePage:
    number: int | None
    text: str


@dataclass
class ExtractedDocument:
    pages: list[SourcePage]
    warnings: list[str] = field(default_factory=list)

    @property
    def text(self):
        return "\n\n".join(page.text for page in self.pages)


class LoaderService:
    @staticmethod
    def extract(file_path: str | Path) -> ExtractedDocument:
        path = Path(file_path)
        warnings = []
        try:
            if path.suffix.lower() == ".txt":
                pages = [SourcePage(None, path.read_text(encoding="utf-8-sig"))]
            elif path.suffix.lower() == ".pdf":
                reader = PdfReader(path)
                if reader.is_encrypted:
                    raise InvalidDocument("Encrypted PDFs are not supported")
                pages = []
                size = 0
                for number, page in enumerate(reader.pages, 1):
                    part = page.extract_text() or ""
                    size += len(part) + 2
                    if size > settings.MAX_TEXT_CHARACTERS:
                        raise UploadTooLarge("Extracted document exceeds the text limit")
                    if not part.strip():
                        if len(getattr(page, "images", [])):
                            raise InvalidDocument(
                                f"Page {number} contains an image but no extractable text; run OCR before uploading"
                            )
                        warnings.append(
                            f"Page {number} has no extractable text; check for blank pages or missing graphical content."
                        )
                    pages.append(SourcePage(number, normalize_pdf_text(part)))
                warnings.append(
                    "PDF extraction preserves text, not visual layout. Verify tables, columns and image content against the source."
                )
            else:
                raise InvalidDocument("Only UTF-8 .txt and text-based .pdf files are supported")
        except (InvalidDocument, UploadTooLarge):
            raise
        except Exception as exc:
            raise InvalidDocument(
                "The document could not be read; use a valid UTF-8 TXT or text-based PDF"
            ) from exc
        result = ExtractedDocument(pages, warnings)
        if len(result.text) > settings.MAX_TEXT_CHARACTERS:
            raise UploadTooLarge("Extracted document exceeds the text limit")
        if not result.text.strip():
            raise InvalidDocument(
                "Document contains no extractable text; scanned PDFs need OCR first"
            )
        return result

    @staticmethod
    def extract_text(file_path: str | Path) -> str:
        return LoaderService.extract(file_path).text
