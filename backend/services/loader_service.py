from pathlib import Path

from langchain_community.document_loaders import (
    PyPDFLoader,
    TextLoader,
)

class LoaderService:

    @staticmethod
    def extract_text(file_path: str) -> str:

        suffix = Path(file_path).suffix.lower()

        if suffix == ".pdf":
            loader = PyPDFLoader(file_path)

        elif suffix == ".txt":
            loader = TextLoader(file_path)

        else:
            raise ValueError(
                f"Unsupported file type: {suffix}"
            )

        docs = loader.load()

        return "\n".join(
            doc.page_content
            for doc in docs
        )