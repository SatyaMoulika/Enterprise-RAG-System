import requests

class LLMService:

    OLLAMA_URL = "http://localhost:11434/api/generate"
    MODEL = "qwen2.5:3b"

    @classmethod
    def generate(cls, question: str, context: str):

        prompt = f"""
            You are an enterprise assistant.
            Answer only using the supplied context.
            If the answer is not present,say:
                "I could not find the answer in the provided documents."

            Context:
            {context}

            Question:
            {question}
        """

        response = requests.post(
            cls.OLLAMA_URL,
            json={
                "model": cls.MODEL,
                "prompt": prompt,
                "stream": False
            }
        )

        return response.json()["response"]