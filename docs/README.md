# TSS - Dual Screen Display Dashboard

Sistema de display dual screen com integração Docker e Uptime Kuma para monitoramento de servidores e containers.

## Estrutura do Projeto

```
tss/
├── docs/                    # Documentação
│   ├── SETUP.md            # Guia de configuração
│   ├── UPTIME_KUMA.md     # Configuração do Uptime Kuma
│   └── CHANGELOG.md       # Histórico de modificações
├── screen.py               # Orquestração principal
├── uptime_kuma.py          # Integração Uptime Kuma (Socket.IO)
├── docker_screen.py        # Informações Docker
├── system_resource.py      # Recursos do sistema
├── shared.py               # Driver de tela e helpers
├── main.py                 # Ponto de entrada
├── .env                    # Configurações
├── .env.example            # Template de configuração
└── requirements.txt        # Dependências Python
```

## Screenshots

O sistema alterna automaticamente entre 3 telas:
1. **Resources** - CPU, memória, disco
2. **Docker** - Status dos containers
3. **Uptime Kuma** - Monitores de serviços

## Pré-requisitos

- Python 3.8+
- Porta serial USB conectada (display Zima)
- Docker (para integração com containers)
- Uptime Kuma (opcional, para monitoramento)

## Instalação Rápida

```bash
# 1. Clonar/instalar dependências
pip install -r requirements.txt

# 2. Configurar ambiente
cp .env.example .env
# Editar .env com suas configurações

# 3. Executar
python3 main.py
```

## Configuração

Consulte [SETUP.md](SETUP.md) para detalhes completos de configuração.

## Uptime Kuma

O sistema usa **Socket.IO** para comunicação com Uptime Kuma (não HTTP).

Consulte [UPTIME_KUMA.md](UPTIME_KUMA.md) para detalhes.
