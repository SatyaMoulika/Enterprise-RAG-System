class PromptService:
    @staticmethod
    def build_context(chunks):
        return "\n\n".join(
            f"[{number}] {chunk['title']}"
            + (
                f" · pages {chunk['page_start']}–{chunk.get('page_end') or chunk['page_start']}"
                if chunk.get("page_start")
                else ""
            )
            + (f" · {chunk['section']}" if chunk.get("section") else "")
            + f"\n{chunk['chunk_text']}"
            for number, chunk in enumerate(chunks, start=1)
        )
