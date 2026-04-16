# Changelog

## [Modificações] - 2026-04-15

### uptime_kuma.py - Migração para Socket.IO

**Problema Original:**
- O Uptime Kuma não respondia corretamente a requisições HTTP
- API retornava HTML (SPA fallback) em vez de JSON
- Timeout em todas as tentativas de conexão

**Solução Implementada:**
- Substituído `urllib` por `python-socketio`
- Conexão via WebSocket em vez de HTTP
- Recebimento de dados via eventos `monitorList` e `heartbeat`

**Mudanças no código:**

```python
# ANTES (não funcionava)
import urllib.request
request = urllib.request.Request(url, headers=headers)
with urllib.request.urlopen(request, timeout=timeout) as response:
    data = json.loads(response.read())

# DEPOIS (funciona)
import socketio
sio = socketio.Client()
sio.connect(url, transports=["polling"])
sio.on("monitorList", handler)
```

**Endpoints não utilizados:**
- `/api/monitors` - Não existe na API
- `/api/monitors-list` - Não existe na API
- `/metrics` - Retorna vazio

**Evento correto:**
- `monitorList` - Enviado após login via Socket.IO
- Formato: `{id: {monitor_data}, id2: {...}}`

### Uptime Kuma - disableAuth

**Configuração necessária:**
- Habilitar `disableAuth=true` no banco de dados
- Usar Socket.IO com login automático

```bash
docker exec uptime-kuma sqlite3 /app/data/kuma.db \
  "INSERT OR REPLACE INTO setting (id, key, value) VALUES (7, 'disableAuth', '1');"
```

### .env - Atualizado

```bash
# Token não é mais necessário com disableAuth
KUMA_TOKEN=

# SSL pode ser desabilitado para ambiente local
KUMA_VERIFY_SSL=false
```

## Estrutura de Arquivos Adicionada

```
docs/
├── README.md        # Visão geral do projeto
├── SETUP.md         # Guia de configuração detalhado
├── UPTIME_KUMA.md   # Configuração específica do Uptime Kuma
└── CHANGELOG.md     # Este arquivo
```

## Dependências Adicionadas

```bash
pip install python-socketio
```

## Testes Realizados

1. ✅ Conexão Socket.IO com Uptime Kuma
2. ✅ Recebimento de 18+ monitores
3. ✅ Status correto (UP/DOWN)
4. ✅ Integração com Docker (portas)
5. ✅ Renderização na tela

## Container Uptime Kuma

Configuração atual do container:
```yaml
image: louislam/uptime-kuma:latest
ports:
  - "3002:3001"
environment:
  - UPTIME_KUMA_DISABLE_AUTH=true  # Variável não utilizada pelo app
  - UPTIME_KUMA_WS_ORIGIN_CHECK=bypass
user: "0:0"
```

**Nota:** `UPTIME_KUMA_DISABLE_AUTH=true` não funciona diretamente - é necessário configurar no banco de dados.
