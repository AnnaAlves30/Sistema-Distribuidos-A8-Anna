# node.py - Nó do sistema distribuído de mensagens
import argparse, json, socket, threading, time, uuid
from typing import List, Dict, Tuple, Any
from message import Message
from auth import AuthManager

# Função utilitária para enviar um objeto JSON pela conexão
def send_json(conn, obj):
    conn.sendall((json.dumps(obj)+"\n").encode("utf-8"))

# Função utilitária para receber um objeto JSON da conexão
def recv_json(conn, timeout=30.0):
    conn.settimeout(timeout)
    buf = b""
    while True:
        ch = conn.recv(1)
        if not ch:
            raise ConnectionError("Conexão encerrada")
        if ch == b"\n":
            break
        buf += ch
    return json.loads(buf.decode("utf-8"))

class Node:
    # Inicializa o nó com configurações e carrega usuários
    def __init__(self, config: dict, users_path: str):
        self.node_id = config["node_id"]
        self.listen_host = config["listen_host"]
        self.listen_port = int(config["listen_port"])
        self.peers = config["peers"]
        with open(users_path,"r",encoding="utf-8") as f:
            users = json.load(f)
        self.auth = AuthManager(users)
        self.tokens = {}  # tokens de autenticação válidos
        self.messages: List[Message] = []  # lista de mensagens
        self.by_id = {}  # indexador por id de mensagem
        self.local_seq = 0  # sequência local de mensagens
        self.replication_paused = False  # controle de replicação
        self.lock = threading.RLock()  # lock para acesso concorrente
        # Threads principais do nó
        self.server_thread = threading.Thread(target=self._serve_forever, daemon=True)
        self.gossip_thread = threading.Thread(target=self._gossip_forever, daemon=True)
        self.stdin_thread = threading.Thread(target=self._stdin_commands, daemon=True)
    # Inicia as threads do nó
    def start(self):
        print(f"[{self.node_id}] Iniciando {self.listen_host}:{self.listen_port}")
        self.server_thread.start()
        self.gossip_thread.start()
        self.stdin_thread.start()
    # Loop principal do servidor TCP
    def _serve_forever(self):
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            s.bind((self.listen_host, self.listen_port))
            s.listen(128)
            while True:
                conn, addr = s.accept()
                threading.Thread(target=self._handle_client, args=(conn,addr), daemon=True).start()
    # Lida com cada conexão de cliente
    def _handle_client(self, conn, addr):
        try:
            req = recv_json(conn, timeout=5.0)
            t = req.get("type")
            if t in ("LOGIN","POST","GET"):
                resp = self._handle_user_request(req)
                send_json(conn, resp)
            elif t and t.startswith("REPL_"):
                resp = self._handle_replication(req)
                if resp is not None:
                    send_json(conn, resp)
            else:
                send_json(conn, {"ok":False,"error":"tipo inválido"})
        except Exception as e:
            try:
                send_json(conn, {"ok":False,"error":str(e)})
            except Exception:
                pass
        finally:
            conn.close()
    # Lida com requisições de usuário (login, post, get)
    def _handle_user_request(self, req):
        if req["type"] == "LOGIN":
            return self._login(req.get("username"), req.get("password"))
        elif req["type"] == "POST":
            return self._post(req.get("token"), req.get("content"), req.get("message_type","public"))
        elif req["type"] == "GET":
            return {"ok":True, "messages": self._get_messages(req.get("token"))}
        return {"ok":False,"error":"tipo desconhecido"}
    # Realiza login, gera token e replica para peers
    def _login(self, username, password):
        if not username or not password:
            return {"ok":False,"error":"credenciais ausentes"}
        if not self.auth.verify(username, password):
            return {"ok":False,"error":"usuário ou senha inválidos"}
        token = str(uuid.uuid4())
        self.tokens[token] = username
        print(f"[{self.node_id}] LOGIN: {username} -> token {token[:8]}...")
        # Replicar token para peers
        threading.Thread(target=self._push_token_to_peers, args=(token, username), daemon=True).start()
        return {"ok":True, "token": token}
    # Envia token recém-criado para os peers
    def _push_token_to_peers(self, token, username):
        payload = {"type": "REPL_TOKEN", "from": self.node_id, "token": token, "username": username}
        for p in self.peers:
            try:
                with socket.create_connection((p["host"], p["port"]), timeout=1.0) as c:
                    send_json(c, payload)
            except Exception:
                pass
    # Posta uma mensagem (pública ou privada) se o token for válido
    def _post(self, token, content, message_type="public"):
        user = self.tokens.get(token)
        if not user:
            return {"ok":False,"error":"não autenticado"}
        if not content or not isinstance(content,str):
            return {"ok":False,"error":"conteúdo inválido"}
        if message_type not in ("public","private"):
            return {"ok":False,"error":"tipo inválido"}
        with self.lock:
            self.local_seq += 1
            mid = f"{self.node_id}:{self.local_seq}"
            m = Message(mid, self.node_id, self.local_seq, user, content, None, message_type)
            self._store_message(m)
        print(f"[{self.node_id}] POST ({message_type}) de {user}: {content} -> {mid}")
        threading.Thread(target=self._push_to_peers, args=([m.to_dict()],), daemon=True).start()
        return {"ok":True, "id": mid}
    # Retorna mensagens públicas ou privadas do usuário autenticado
    def _get_messages(self, token=None):
        with self.lock:
            if token and token in self.tokens:
                username = self.tokens[token]
                return [m.to_dict() for m in self.messages if m.is_public() or m.author==username]
            else:
                return [m.to_dict() for m in self.messages if m.is_public()]
    # Armazena mensagem localmente, evitando duplicatas
    def _store_message(self, msg: Message):
        with self.lock:
            if msg.id in self.by_id:
                return
            self.by_id[msg.id] = msg
            self.messages.append(msg)
            self.messages.sort(key=lambda x:(x.ts,x.id))
    # Lida com mensagens de replicação entre nós
    def _handle_replication(self, req):
        if self.replication_paused:
            return {"ok":False,"error":"replicação pausada"}
        t = req.get("type")
        if t == "REPL_HELLO":
            peer_known = set(req.get("known_ids") or [])
            with self.lock:
                missing = [m.to_dict() for m in self.messages if m.id not in peer_known]
            return {"ok":True, "type":"REPL_SEND", "from": self.node_id, "messages": missing}
        elif t == "REPL_SEND":
            new = 0
            for mm in req.get("messages") or []:
                m = Message.from_dict(mm)
                before = len(self.by_id)
                self._store_message(m)
                after = len(self.by_id)
                if after>before:
                    new += 1
            if new:
                print(f"[{self.node_id}] Replicação: aplicadas {new} novas mensagem(ns)")
            return {"ok":True}
        elif t == "REPL_TOKEN":
            # Recebe token de outro nó
            token = req.get("token")
            username = req.get("username")
            if token and username:
                self.tokens[token] = username
            return {"ok":True}
        else:
            return {"ok":False,"error":"REPL_* desconhecido"}
    # Thread de replicação periódica (gossip)
    def _gossip_forever(self):
        while True:
            time.sleep(2.0)
            if self.replication_paused:
                continue
            try:
                with self.lock:
                    known_ids = [m.id for m in self.messages]
                for p in self.peers:
                    self._gossip_with_peer(p, known_ids)
            except Exception:
                pass
    # Realiza troca de mensagens com peer para sincronizar mensagens
    def _gossip_with_peer(self, peer, known_ids):
        try:
            with socket.create_connection((peer["host"],peer["port"]), timeout=1.0) as c:
                send_json(c, {"type":"REPL_HELLO", "from": self.node_id, "known_ids": known_ids})
                resp = recv_json(c, timeout=3.0)
                if resp.get("type")=="REPL_SEND" and resp.get("messages"):
                    self._handle_replication(resp)
        except Exception:
            pass
    # Envia mensagens novas para peers
    def _push_to_peers(self, messages):
        if self.replication_paused:
            return
        payload = {"type":"REPL_SEND", "from": self.node_id, "messages": messages}
        for p in self.peers:
            try:
                with socket.create_connection((p["host"],p["port"]), timeout=1.0) as c:
                    send_json(c, payload)
            except Exception:
                pass
    # Thread para comandos interativos no terminal do nó
    def _stdin_commands(self):
        help_txt = "Comandos: pause | resume | stats | peers | help | dump"
        print(help_txt)
        while True:
            try:
                line = input().strip().lower()
            except EOFError:
                break
            if line == "pause":
                self.replication_paused = True
                print(f"[{self.node_id}] Replicação PAUSADA.")
            elif line == "resume":
                self.replication_paused = False
                print(f"[{self.node_id}] Replicação ATIVA.")
            elif line == "stats":
                with self.lock:
                    print(f"[{self.node_id}] {len(self.messages)} msgs; tokens: {len(self.tokens)}")
            elif line == "peers":
                for p in self.peers:
                    print(f"- {p['node_id']} @ {p['host']}:{p['port']}")
            elif line == "dump":
                with self.lock:
                    for m in self.messages:
                        print(m)
            elif line == "help":
                print(help_txt)
            elif not line:
                continue
            else:
                print("Comando desconhecido.")
# Função principal: carrega config, inicia o nó e mantém o processo vivo
def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--config", required=True)
    parser.add_argument("--users", required=True)
    args = parser.parse_args()
    with open(args.config, "r", encoding="utf-8") as f:
        cfg = json.load(f)
    node = Node(cfg, users_path=args.users)
    node.start()
    while True:
        time.sleep(1)
if __name__ == "__main__":
    main()