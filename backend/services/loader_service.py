from pathlib import Path

from pypdf import PdfReader

from core.config import settings
from core.errors import InvalidDocument, UploadTooLarge


class LoaderService:
    @staticmethod
    def extract_text(file_path: str | Path) -> str:
        path = Path(file_path)
        try:
            if path.suffix.lower() == ".txt":
                text = path.read_text(encoding="utf-8")
            elif path.suffix.lower() == ".pdf":
                reader = PdfReader(path)
                if reader.is_encrypted:
                    raise InvalidDocument("Encrypted PDFs are not supported")
                parts = []
                size = 0
                for page in reader.pages:
                    part = page.extract_text() or ""
                    size += len(part) + 1
                    if size > settings.MAX_TEXT_CHARACTERS:
                        raise UploadTooLarge("Extracted document exceeds the text limit")
                    parts.append(part)
                text = "\n".join(parts)
            else:
                raise InvalidDocument("Only UTF-8 .txt and text-based .pdf files are supported")
        except (InvalidDocument, UploadTooLarge):
            raise
        except Exception as exc:
            raise InvalidDocument(
                "The document could not be read; use a valid UTF-8 TXT or text-based PDF"
            ) from exc
        if len(text) > settings.MAX_TEXT_CHARACTERS:
            raise UploadTooLarge("Extracted document exceeds the text limit")
        if not text.strip():
            raise InvalidDocument(
                "Document contains no extractable text; scanned PDFs need OCR first"
            )
        return text
