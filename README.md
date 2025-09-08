# Serviço de Mensagens Distribuídas (Atualizado)

---

## 📁 Estrutura de Arquivos

```
dist-messages-updated/
├── node.py         # Código do nó servidor
├── client.py       # Cliente para interação
├── auth.py         # Lógica de autenticação
├── message.py      # Lógica de mensagens
├── users.json      # Usuários e senhas (texto simples)
├── node1.json      # Configuração do nó 1
├── node2.json      # Configuração do nó 2
├── node3.json      # Configuração do nó 3
```

- **node.py**: Executa um nó do sistema distribuído.
- **client.py**: Cliente para login, postagem e leitura de mensagens.
- **auth.py**: Gerencia autenticação e tokens.
- **message.py**: Manipula mensagens públicas e privadas.
- **users.json**: Lista de usuários e senhas (texto simples, convertidas para hash internamente).
- **node1.json, node2.json, node3.json**: Configurações individuais de cada nó (porta, id, etc).

---

## 🚀 Passo a Passo

### 1. Organizar os Arquivos

Certifique-se de estar no diretório correto:

```bash
cd dist-messages-updated
```

---

### 2. Iniciar os Nós do Servidor

Abra **três terminais** separados e execute:

**Terminal 1:**
```bash
python node.py --config node1.json --users users.json
```

**Terminal 2:**
```bash
python node.py --config node2.json --users users.json
```

**Terminal 3:**
```bash
python node.py --config node3.json --users users.json
```

Deixe os três terminais abertos.

---

### 3. Interagir com o Cliente

Abra um **quarto terminal** para o cliente.

#### 1. Fazer Login

```bash
python client.py --host 127.0.0.1 --port 5001 login alice alice123
```

Se for bem-sucedido, copie o token retornado.

#### 2. Postar uma Mensagem Pública

```bash
python client.py --host 127.0.0.1 --port 5001 post <seu_token_aqui> "Minha primeira mensagem!"
```

#### 3. Verificar a Replicação

Nos terminais dos nós 2 e 3, digite `dump` para ver a mensagem replicada.

#### 4. Postar uma Mensagem Privada

```bash
python client.py --host 127.0.0.1 --port 5002 post <seu_token_aqui> "Esta é uma mensagem secreta." --private
```

#### 5. Ler as Mensagens

- **Mensagens públicas (sem token):**
  ```bash
  python client.py --host 127.0.0.1 --port 5003 get
  ```
- **Todas as mensagens (com token):**
  ```bash
  python client.py --host 127.0.0.1 --port 5003 get --token <seu_token_aqui>
  ```

---

### 4. Simular uma Falha

1. No terminal do Nó 1, digite `pause`.
2. No cliente, poste novas mensagens:
   ```bash
   python client.py --host 127.0.0.1 --port 5002 post <seu_token_aqui> "Mensagem postada durante a falha."
   ```
3. Use `dump` nos nós para verificar a replicação.
4. No Nó 1, digite `resume` para reativar a comunicação.
5. Use `dump` novamente para ver a reconciliação.

---

## ℹ️ Notas

- Senhas em `users.json` estão em texto simples por fins didáticos; o nó converte para hash internamente.
- Mensagens privadas só são retornadas ao autor se fornecer token válido no GET.