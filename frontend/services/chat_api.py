import os
import requests
BASE_URL = os.environ.get('RAG_API_BASE_URL', 'http://localhost:8000').rstrip('/')

def ask_question(token, question):
    return requests.post(f'{BASE_URL}/chat/generate', headers={'Authorization': f'Bearer {token}'}, json={'question': question}, timeout=120)
