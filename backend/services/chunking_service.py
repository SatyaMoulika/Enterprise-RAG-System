from langchain_text_splitters import (
    RecursiveCharacterTextSplitter
)


class ChunkingService:

    @staticmethod
    def chunk_text(text: str) -> list[str]:

        splitter = (
            RecursiveCharacterTextSplitter(
                chunk_size=500,
                chunk_overlap=50,
                separators=[
                    "\n\n",
                    "\n",
                    ". ",
                    " ",
                    "",
                ]
            )
        )

        return splitter.split_text(text)