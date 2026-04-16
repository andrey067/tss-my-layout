# Guia de Configuração

## Arquivo .env

Copie `.env.example` para `.env` e configure:

```bash
cp .env.example .env
```

### Variáveis Obrigatórias

| Variável | Descrição | Exemplo |
|----------|-----------|---------|
| `DISPLAY_MODE` | Orientação do display | `reverse_landscape` |
| `SERIAL_PORT` | Porta serial do dispositivo | `/dev/ttyACM0` |

### Display Modes

- `landscape` - Paisagem normal
- `reverse_landscape` - Paisagem invertida (180°)
- `portrait` - Retrato
- `reverse_portrait` - Retrato invertido

### Variáveis Opcionais Uptime Kuma

| Variável | Descrição | Padrão |
|----------|-----------|--------|
| `KUMA_ENABLED` | Ativar Uptime Kuma | `true` |
| `KUMA_URL` | URL do Uptime Kuma | `http://127.0.0.1:3002` |
| `KUMA_TOKEN` | Token/API Key | (vazio se disableAuth) |
| `KUMA_TIMEOUT` | Timeout requisições (s) | `8` |
| `KUMA_VERIFY_SSL` | Verificar SSL | `true` |
| `KUMA_POLL_INTERVAL` | Intervalo de polling (s) | `10` |
| `KUMA_MAX_ROWS` | Máximo de monitores | `18` |

### Variáveis Docker

| Variável | Descrição | Padrão |
|----------|-----------|--------|
| `DOCKER_ENABLED` | Ativar info Docker | `true` |
| `DOCKER_SCREEN_SECONDS` | Tempo na tela Docker | `30` |
| `SHOW_DOCKER_PORTS` | Mostrar portas | `true` |
| `HIDE_NO_PORT_ROWS` | Esconder sem porta | `false` |

### Variáveis de Renderização

| Variável | Descrição | Padrão |
|----------|-----------|--------|
| `REFRESH_INTERVAL` | Intervalo de refresh (s) | `1` |
| `RESOURCES_SCREEN_SECONDS` | Tempo tela recursos | `30` |
| `CALIBRATION_MODE` | Modo calibração | `false` |
| `ORIENTATION_MODE` | Modo orientação | `false` |

## Configuração da Porta Serial

O sistema detecta automaticamente a porta serial do display Zima. Se necessário, especifique manualmente:

```bash
SERIAL_PORT=/dev/ttyACM0
```

Para verificar portas disponíveis:
```bash
ls -la /dev/ttyACM* /dev/ttyUSB*
```

## Docker Socket

Para integração com Docker, o socket deve estar acessível:

```bash
docker run -v /var/run/docker.sock:/var/run/docker.sock:ro
```

## Dependências Python

```bash
pip install pyserial Pillow numpy psutil python-socketio
```

Com `uv` (recomendado):

```bash
uv venv .venv
uv pip install --python .venv/bin/python -r requirements.txt
```

## Systemd Service (Opcional)

Para rodar como serviço:

```bash
chmod +x install_systemd_service.sh
sudo ./install_systemd_service.sh install
sudo ./install_systemd_service.sh status
```

### Comportamento do serviço

- Antes de `install`, `start` e `restart`, o script finaliza processos que ainda seguram a porta USB do display.
- O script tenta usar `SERIAL_PORT` do `.env`; sem isso, tenta `/dev/ttyACM0`, `/dev/ttyACM1` e `/dev/ttyUSB0`.
- O unit gerado usa `/usr/bin/python3` para evitar erro `203/EXEC` em alguns hosts.
- O projeto carrega `.env` no runtime, por isso o unit nao precisa de `EnvironmentFile=`.

### Diagnóstico rapido

```bash
systemctl status tss-my-layouts.service --no-pager -l
journalctl -u tss-my-layouts.service -f
```

## Verificação

Após iniciar, um preview é gerado em `current_frame.png`:

```bash
python3 main.py
# Verificar output
ls -la current_frame.png
```
