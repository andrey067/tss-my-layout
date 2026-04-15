#!/usr/bin/env bash
set -euo pipefail

SERVICE_NAME="tss-my-layouts.service"
PROJECT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PYTHON_BIN="${PROJECT_DIR}/.venv/bin/python"
MAIN_FILE="${PROJECT_DIR}/main.py"
ENV_FILE="${PROJECT_DIR}/.env"
UNIT_PATH="/etc/systemd/system/${SERVICE_NAME}"
RUN_USER="${SUDO_USER:-$USER}"
RUN_GROUP="$(id -gn "${RUN_USER}")"
ACTION="${1:-install}"

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
$( [[ -f "${ENV_FILE}" ]] && printf 'EnvironmentFile=%s\n' "${ENV_FILE}" )

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
    echo "Erro: Python do venv não encontrado em ${PYTHON_BIN}"
    echo "Crie o ambiente virtual e instale as dependências antes de instalar o serviço."
    exit 1
  fi
  if [[ ! -f "${MAIN_FILE}" ]]; then
    echo "Erro: arquivo main.py não encontrado em ${MAIN_FILE}"
    exit 1
  fi
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
