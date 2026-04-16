# Configuração do Uptime Kuma

## Visão Geral

O TSS usa **Socket.IO** para conectar ao Uptime Kuma (não HTTP). Isso foi necessário porque:

1. A API HTTP do Uptime Kuma não responde corretamente a requisições externas
2. Todos os dados são transmitidos via WebSocket após autenticação
3. O formato dos dados vem como `{id: {...}, id2: {...}}` (dicionário)

## Requisito: disableAuth

O Uptime Kuma deve ter autenticação desabilitada para funcionar com o TSS.

### Como habilitar disableAuth

1. **Acesse o container:**
   ```bash
   docker exec -it uptime-kuma sqlite3 /app/data/kuma.db
   ```

2. **Adicione a configuração:**
   ```sql
   INSERT OR REPLACE INTO setting (id, key, value) VALUES (7, 'disableAuth', '1');
   ```

3. **Reinicie o container:**
   ```bash
   docker restart uptime-kuma
   ```

4. **Verifique nos logs:**
   ```
   [AUTH] INFO: Disabled Auth: auto login to admin
   ```

### Alternativa: Via UI (se disponível)

Se a UI estiver acessível:
1. Vá em Settings > Advanced
2. Ative "Disable Auth"
3. Salve e reinicie

## Configuração no .env

Com `disableAuth=true`, deixe o token vazio:

```bash
KUMA_ENABLED=true
KUMA_URL=http://192.168.68.53:3002
KUMA_TOKEN=
```

## Solução de Problemas

### Token inválido (jwt malformed)

Se ver este erro nos logs:
```
[AUTH] ERROR: Invalid token. IP=xxx
[AUTH] ERROR: jwt malformed
```

**Solução:** O token não é usado com disableAuth. Deixe `KUMA_TOKEN=` vazio.

### API retorna HTML em vez de JSON

Isso é normal! O Uptime Kuma usa Socket.IO, não REST API:
- `/api/monitors` retorna HTML (SPA fallback)
- Os dados reais vêm via Socket.IO após conexão

### Sem monitores recebidos

1. Verifique se o Uptime Kuma está rodando:
   ```bash
   docker ps | grep uptime
   ```

2. Teste a conexão:
   ```bash
   curl -s http://localhost:3002/api/entry-page
   ```

3. Verifique se há monitores configurados na UI

### Porta não exposta

Se o Uptime Kuma está em outro host:
```bash
KUMA_URL=http://IP_DO_HOST:3002
```

## Implementação Técnica

O código em `uptime_kuma.py` usa:

1. **python-socketio** para conexão WebSocket
2. **Login automático** (disableAuth) ou com username/password
3. **Evento monitorList** recebe todos os monitores
4. **Evento heartbeat** para status em tempo real

```python
sio.connect(url, transports=["polling"])
sio.on("monitorList", handler)
sio.on("heartbeat", handler)
```

## Status dos Monitores

O status é determinado por:
1. Campo `status` do monitor
2. Campo `heartbeat.status` se disponível
3. Valores: UP, DOWN, PAUSED, UNKNOWN

Cores na tela:
- Verde: UP
- Vermelho: DOWN
- Laranja: PAUSED
- Cinza: UNKNOWN
