# auth.py - Gerenciamento de autenticação de usuários
import hashlib
from typing import Dict

class AuthManager:
    # Inicializa o AuthManager com um dicionário de usuários e senhas
    def __init__(self, users_dict):
        self.users_hashed = {}
        for u,p in users_dict.items():
            self.users_hashed[u] = self._hash_password(p)
    # Gera o hash da senha usando SHA-256
    def _hash_password(self, password: str) -> str:
        return hashlib.sha256(password.encode('utf-8')).hexdigest()
    # Verifica se o usuário e senha fornecidos são válidos
    def verify(self, username: str, password: str) -> bool:
        if username not in self.users_hashed:
            return False
        return self.users_hashed[username] == self._hash_password(password)