# message.py - Definição da classe Message para o sistema distribuído
from typing import Dict
import time

class Message:
    def __init__(self, id:str, origin:str, seq:int, author:str, content:str, ts:float=None, message_type:str="public"):
        # id: identificador único da mensagem (ex: n1:1)
        # origin: nó de origem
        # seq: número sequencial local
        # author: autor da mensagem
        # content: texto da mensagem
        # ts: timestamp (float, opcional)
        # message_type: "public" ou "private"
        self.id = id
        self.origin = origin
        self.seq = seq
        self.author = author
        self.content = content
        self.ts = ts or time.time()
        self.message_type = message_type  # "public" or "private"
    
    def to_dict(self) -> Dict:
        # Converte a mensagem para dicionário (para serialização)
        return {
            "id": self.id,
            "origin": self.origin,
            "seq": self.seq,
            "author": self.author,
            "content": self.content,
            "ts": self.ts,
            "message_type": self.message_type
        }
    
    @classmethod
    def from_dict(cls, d):
        # Cria uma mensagem a partir de um dicionário
        return cls(d["id"], d["origin"], d["seq"], d["author"], d["content"], d.get("ts"), d.get("message_type","public"))
    
    def is_public(self):
        # Retorna True se a mensagem for pública
        return self.message_type == "public"
    
    def is_private(self):
        # Retorna True se a mensagem for privada
        return self.message_type == "private"
    
    def __str__(self):
        # Representação amigável da mensagem para exibição
        privacy = "🔒" if self.is_private() else "🌐"
        return f"{privacy}[{self.author}] {self.content} ({self.id})"