class PromptService:

    @staticmethod
    def build_context(chunks):

        return "\n\n".join(
            chunk["chunk_text"]
            for chunk in chunks
        )