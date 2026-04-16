# Changelog

## [Modificacoes] - 2026-04-16

### docker_screen.py - Migracao para Docker SDK e status simplificado

**Mudancas aplicadas:**
- A coleta da tela Docker deixou de usar Docker CLI e passou a usar Docker SDK (`docker-py`).
- Fonte de dados agora via API do daemon com `client.api.containers(all=True)`.
- Status exibido foi simplificado para apenas dois valores:
  - `RUNNING` para containers ativos
  - `STOP` para qualquer estado nao ativo
- Coluna de porta passou a exibir somente a **porta publica** (`PublicPort`).
- Containers sem porta publicada exibem `-`.

**Resultado visual esperado:**
- Sem mistura de `Up`, `healthy`, `native`.
- Dashboard padronizado com `CONTAINER | STATUS | PORT`.

### docker_screen.py - Coleta de status Docker mais confiavel

**Problema observado:**
- O status na tela Docker nao refletia corretamente alguns containers.
- A leitura usava apenas `docker ps` (somente ativos) e inferencia por string (`"Up" in status`).

**Solucoes implementadas:**
- Troca para `docker ps -a` com campos estruturados:
  - `{{.ID}}|{{.Names}}|{{.State}}|{{.Status}}|{{.Ports}}`
- Uso de `.State` como fonte de verdade para `running`.
- Coleta de health em lote com uma chamada de `docker inspect` para varios IDs.
- Ajuste visual da tela:
  - Cabecalho agora mostra `running / total`.
  - Coluna passou de `HEALTH` para `STATUS`.
  - Quando nao ha healthcheck, exibe o `STATE` real (`RUNNING`, `EXITED`, etc.).

### main.py - Limpeza automatica da porta USB no startup

**Mudanca:**
- Antes de iniciar o dashboard, o `main.py` finaliza processos que ainda seguram a porta serial do display.
- Fluxo aplicado:
  - identifica PIDs com `lsof -t <porta>`
  - envia `SIGTERM`
  - aguarda curto intervalo
  - envia `SIGKILL` para remanescentes

### install_systemd_service.sh - Robustez no start/restart

**Mudancas:**
- O script agora finaliza processos presos na USB antes de `install`, `start` e `restart`.
- Resolucao da porta usada na limpeza:
  1. `SERIAL_PORT` no `.env`
  2. fallback: `/dev/ttyACM0`, `/dev/ttyACM1`, `/dev/ttyUSB0`

**Compatibilidade systemd:**
- Unit atualizado para usar:
  - `ExecStart=/usr/bin/python3 /home/fedora/tss/main.py`
- Removido `EnvironmentFile=` do unit para evitar falha de permissao em alguns hosts.
- O projeto continua carregando `.env` no runtime via Python.

### Documentacao atualizada

- `README.md`:
  - instalacao opcional com `uv`
  - notas de diagnostico systemd
  - detalhes da limpeza de USB
- `docs/SETUP.md`:
  - fluxo de setup com `uv`
  - secao de comportamento do servico
  - comandos de diagnostico rapido

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
