class PromptService:
    @staticmethod
    def build_context(chunks):
        return "\n\n".join(
            f"[{number}] {chunk['title']} (chunk {chunk['chunk_index']})\n{chunk['chunk_text']}"
            for number, chunk in enumerate(chunks, start=1)
        )
