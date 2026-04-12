# Dual LCD Dashboard (Resources + Uptime Kuma)

Baseado em `usb-lcd-dashboard`, reduzido para **2 telas**:

1. **Resources (default landscape)**.
2. **Uptime Kuma** com API key.

## Requisitos

- Python 3.8+
- Display USB 3.5" (Turing Smart Screen Rev A / CH340)

## Instalação

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
```

## Configuração

No `.env`:

- `REFRESH_INTERVAL`
- `RESOURCES_SCREEN_SECONDS`
- `KUMA_SCREEN_SECONDS`
- `KUMA_ENABLED`
- `KUMA_URL`
- `KUMA_TOKEN`
- `KUMA_TIMEOUT`
- `KUMA_POLL_INTERVAL`
- `KUMA_VERIFY_SSL`
- `SHOW_DOCKER_PORTS`
- `DISPLAY_MODE` (`reverse_landscape` recomendado)
- `CALIBRATION_MODE` (`true` para tela de calibração visual)

## Executar

```bash
./.venv/bin/python main.py
```

## Troubleshooting

- **Tela bugando/atualizando errado**: confirme que só existe 1 processo usando `/dev/ttyACM0`.
- **Kuma timeout/401**: use API key em `KUMA_TOKEN` e ajuste `KUMA_TIMEOUT`.
- **Portas Docker vazias**: validar acesso a `docker ps`.
