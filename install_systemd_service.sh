#!/usr/bin/env bash
set -euo pipefail

SERVICE_NAME="tss-my-layouts.service"
PROJECT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PYTHON_BIN="/usr/bin/python3"
MAIN_FILE="${PROJECT_DIR}/main.py"
ENV_FILE="${PROJECT_DIR}/.env"
UNIT_PATH="/etc/systemd/system/${SERVICE_NAME}"
RUN_USER="${SUDO_USER:-$USER}"
RUN_GROUP="$(id -gn "${RUN_USER}")"
ACTION="${1:-install}"

find_usb_port() {
  local configured_port=""
  if [[ -f "${ENV_FILE}" ]]; then
    configured_port="$(python3 - <<'PY' "${ENV_FILE}"
import sys

env_file = sys.argv[1]
value = ""
with open(env_file, "r", encoding="utf-8") as handle:
    for raw in handle:
        line = raw.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, raw_value = line.split("=", 1)
        if key.strip() == "SERIAL_PORT":
            value = raw_value.strip().strip('"').strip("'")
            break
print(value)
PY
)"
  fi
  if [[ -n "${configured_port}" ]]; then
    printf '%s\n' "${configured_port}"
    return
  fi
  for candidate in /dev/ttyACM0 /dev/ttyACM1 /dev/ttyUSB0; do
    if [[ -e "${candidate}" ]]; then
      printf '%s\n' "${candidate}"
      return
    fi
  done
}

stop_usb_processes() {
  local usb_port
  usb_port="$(find_usb_port)"
  if [[ -z "${usb_port}" ]]; then
    echo "Nenhuma porta USB de display encontrada para limpeza de processos."
    return
  fi

  if ! command -v lsof >/dev/null 2>&1; then
    echo "Aviso: lsof não encontrado; não foi possível finalizar processos da porta ${usb_port}."
    return
  fi

  mapfile -t pids < <(lsof -t "${usb_port}" 2>/dev/null | sort -u)
  if [[ "${#pids[@]}" -eq 0 ]]; then
    echo "Porta ${usb_port} livre."
    return
  fi

  echo "Finalizando processos na porta ${usb_port}: ${pids[*]}"
  for pid in "${pids[@]}"; do
    if [[ "${pid}" =~ ^[0-9]+$ ]] && [[ "${pid}" -ne $$ ]]; then
      kill -TERM "${pid}" 2>/dev/null || true
    fi
  done

  sleep 1

  mapfile -t still_alive < <(lsof -t "${usb_port}" 2>/dev/null | sort -u)
  for pid in "${still_alive[@]}"; do
    if [[ "${pid}" =~ ^[0-9]+$ ]] && [[ "${pid}" -ne $$ ]]; then
      kill -KILL "${pid}" 2>/dev/null || true
    fi
  done
}

if [[ "${EUID}" -ne 0 ]]; then
  echo "Este script precisa de root para gerenciar o serviço."
  echo "Use: sudo ./install_systemd_service.sh [install|start|stop|restart|status]"
  exit 1
fi

write_unit() {
cat > "${UNIT_PATH}" <<EOF
[Unit]
Description=Turing Smart Screen Dashboard
After=network-online.target
Wants=network-online.target

[Service]
Type=simple
User=${RUN_USER}
Group=${RUN_GROUP}
WorkingDirectory=${PROJECT_DIR}
ExecStart=${PYTHON_BIN} ${MAIN_FILE}
Restart=always
RestartSec=3
Environment=PYTHONUNBUFFERED=1

[Install]
WantedBy=multi-user.target
EOF
}

show_status() {
  systemctl status "${SERVICE_NAME}" --no-pager || true
  echo "Active: $(systemctl is-active "${SERVICE_NAME}" 2>/dev/null || echo unknown)"
  echo "Enabled: $(systemctl is-enabled "${SERVICE_NAME}" 2>/dev/null || echo unknown)"
}

install_service() {
  if [[ ! -x "${PYTHON_BIN}" ]]; then
    echo "Erro: Python não encontrado em ${PYTHON_BIN}"
    exit 1
  fi
  if [[ ! -f "${MAIN_FILE}" ]]; then
    echo "Erro: arquivo main.py não encontrado em ${MAIN_FILE}"
    exit 1
  fi
  stop_usb_processes
  write_unit
  systemctl daemon-reload
  systemctl enable --now "${SERVICE_NAME}"
  echo "Serviço instalado e iniciado: ${SERVICE_NAME}"
}

case "${ACTION}" in
  install)
    install_service
    ;;
  start)
    stop_usb_processes
    systemctl start "${SERVICE_NAME}"
    echo "Serviço iniciado: ${SERVICE_NAME}"
    ;;
  stop|pause)
    systemctl stop "${SERVICE_NAME}"
    sleep 1
    if systemctl is-active --quiet "${SERVICE_NAME}"; then
      echo "Erro: serviço ainda está ativo após stop."
      exit 1
    fi
    echo "Serviço pausado: ${SERVICE_NAME}"
    ;;
  restart)
    stop_usb_processes
    systemctl restart "${SERVICE_NAME}"
    echo "Serviço reiniciado: ${SERVICE_NAME}"
    ;;
  status)
    ;;
  *)
    echo "Ação inválida: ${ACTION}"
    echo "Uso: sudo ./install_systemd_service.sh [install|start|stop|restart|status]"
    exit 1
    ;;
esac

show_status
