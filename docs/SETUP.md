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

## Systemd Service (Opcional)

Para rodar como serviço:

```bash
# Copiar para ~/.config/systemd/user/
cp install_systemd_service.sh ~/.config/systemd/user/tss.service
systemctl --user enable tss
systemctl --user start tss
```

## Verificação

Após iniciar, um preview é gerado em `current_frame.png`:

```bash
python3 main.py
# Verificar output
ls -la current_frame.png
```
