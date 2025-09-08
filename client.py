# client.py - Cliente para interagir com o sistema distribuído
import argparse, socket, json

def send_json(conn,obj):
    # Envia um objeto JSON pela conexão
    conn.sendall((json.dumps(obj)+"\n").encode("utf-8"))

def recv_json(conn):
    # Recebe um objeto JSON da conexão
    buf=b""
    while True:
        ch=conn.recv(1)
        if not ch:
            raise ConnectionError("Conexão encerrada")
        if ch==b"\n":
            break
        buf+=ch
    return json.loads(buf.decode("utf-8"))

def rpc(host,port,payload):
    # Realiza uma chamada remota (RPC) para o nó especificado
    with socket.create_connection((host,port), timeout=3) as c:
        send_json(c,payload)
        return recv_json(c)

def main():
    # Parser de argumentos de linha de comando
    p=argparse.ArgumentParser()
    p.add_argument("--host", default="127.0.0.1")
    p.add_argument("--port", type=int, default=5001)
    sub=p.add_subparsers(dest="cmd", required=True)
    # Subcomando login
    s_login=sub.add_parser("login")
    s_login.add_argument("username")
    s_login.add_argument("password")
    # Subcomando post
    s_post=sub.add_parser("post")
    s_post.add_argument("token")
    s_post.add_argument("content")
    s_post.add_argument("--private", action="store_true")
    # Subcomando get
    s_get=sub.add_parser("get")
    s_get.add_argument("--token", default=None)
    args=p.parse_args()
    # Executa o comando apropriado
    if args.cmd=="login":
        print(rpc(args.host, args.port, {"type":"LOGIN","username":args.username,"password":args.password}))
    elif args.cmd=="post":
        mtype="private" if args.private else "public"
        print(rpc(args.host,args.port, {"type":"POST","token":args.token,"content":args.content,"message_type":mtype}))
    elif args.cmd=="get":
        payload={"type":"GET"}
        if args.token:
            payload["token"]=args.token
        print(json.dumps(rpc(args.host,args.port,payload), indent=2))

if __name__=="__main__":
    main()