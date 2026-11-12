import os
import requests
BASE_URL = os.environ.get('RAG_API_BASE_URL', 'http://localhost:8000').rstrip('/')

def login(email: str, password: str):
    response = requests.post(f'{BASE_URL}/auth/login', json={'email': email, 'password': password}, timeout=120)
    return response

def register(enterprise_name: str, email: str, password: str):
    response = requests.post(f'{BASE_URL}/auth/register', json={'enterprise_name': enterprise_name, 'email': email, 'password': password}, timeout=120)
    return response
