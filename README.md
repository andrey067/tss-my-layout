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
- `ORIENTATION_MODE` (`true` para rodar o teste de orientação do `screen_orientation.py`)

## Executar

```bash
./.venv/bin/python main.py
```

## Organização do código

- `main.py`: entrypoint
- `screen.py`: loop principal e troca de telas
- `layout.py`: layouts compartilhados (calibração/orientação)
- `system_resource.py`: coleta/render de recursos do sistema
- `uptime_kuma.py`: integração/cache/render do Uptime Kuma
- `docker_info.py`: parse de portas Docker e resolução por monitor
- `shared.py`: driver serial, cores, fontes e helpers de desenho

## Rodar automaticamente no boot (systemd)

Instale o serviço para iniciar em background a cada boot:

```bash
chmod +x install_systemd_service.sh
sudo ./install_systemd_service.sh install
```

Comandos úteis:

```bash
journalctl -u tss-my-layouts.service -f
sudo ./install_systemd_service.sh start
sudo ./install_systemd_service.sh stop
sudo ./install_systemd_service.sh restart
sudo ./install_systemd_service.sh status
```

## Testes

```bash
python3 -m unittest -v test_docker_info.py
```

## Troubleshooting

- **Tela invertida**: ajuste `DISPLAY_MODE` no `.env` (`reverse_landscape` ou `landscape`) e reinicie o serviço.
- **Tela bugando/atualizando errado**: confirme que só existe 1 processo usando `/dev/ttyACM0`.
- **Kuma timeout/401**: use API key em `KUMA_TOKEN` e ajuste `KUMA_TIMEOUT`.
- **Portas Docker vazias**: validar acesso a `docker ps`.

Comandos de diagnóstico rápidos:

```bash
systemctl status tss-my-layouts.service --no-pager -l
journalctl -u tss-my-layouts.service -f
```
