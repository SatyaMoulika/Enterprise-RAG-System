class PromptService:
    @staticmethod
    def build_context(chunks):
        return "\n\n".join(
            f"[{number}] {chunk['title']}\n{chunk['chunk_text']}"
            for number, chunk in enumerate(chunks, start=1)
        )
