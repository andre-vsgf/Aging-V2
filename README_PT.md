# 🔬 CROC FPGA Aging Monitor

<p align="center">
  <img src="https://img.shields.io/badge/Python-3.10+-blue.svg" alt="Python">
  <img src="https://img.shields.io/badge/PySide6-6.0+-green.svg" alt="PySide6">
  <img src="https://img.shields.io/badge/Platform-Windows%20%7C%20Linux-lightgrey.svg" alt="Platform">
  <img src="https://img.shields.io/badge/License-MIT-yellow.svg" alt="License">
</p>

Sistema de monitoramento em tempo real para experimentos de envelhecimento de FPGAs sob radiação ionizante. Desenvolvido para automatizar a detecção de degradação de timing e transição entre bitstreams com diferentes margens de slack.

---

## 📋 Índice

- [Visão Geral](#visão-geral)
- [Funcionalidades](#funcionalidades)
- [Estrutura do Repositório](#estrutura-do-repositório)
- [Requisitos](#requisitos)
- [Instalação](#instalação)
- [Uso Rápido](#uso-rápido)
- [Arquitetura](#arquitetura)
- [Configuração](#configuração)
- [Contribuição](#contribuição)
- [Licença](#licença)

---

## Visão Geral

O **CROC FPGA Aging Monitor** é uma ferramenta desenvolvida para experimentos de caracterização de envelhecimento em FPGAs expostos a radiação. O sistema:

- Monitora 4 tipos de sensores de timing (128 sensores no total)
- Detecta automaticamente degradação através de alarmes
- Transiciona entre bitstreams com diferentes margens de slack
- Registra todas as transições com metadados completos
- Projeta tendências de degradação através de regressão linear

### Contexto Científico

FPGAs expostas a radiação ionizante sofrem degradação de timing devido a Total Ionizing Dose (TID). Este sistema permite:

1. Quantificar a taxa de degradação de slack
2. Correlacionar degradação com dose de radiação
3. Automatizar experimentos de longa duração (semanas)

---

## Funcionalidades

### 🎛️ Monitoramento de Sensores
- 4 barramentos de sensores: F, RF, UART, OBI
- 32 bits por barramento (128 sensores total)
- Visualização em tempo real com indicadores coloridos
- Filtros seletivos por tipo de sensor

### 🔄 Auto-Program
- Fila de bitstreams com detecção automática de fase
- Transição automática quando alarmes são detectados
- Tempos configuráveis de estabilização e cooldown
- Programação garantida do primeiro bitstream ao iniciar

### 📊 Análise de Degradação
- Gráfico Slack vs Dose de Radiação
- Gráfico Slack vs Tempo
- Regressão linear com R²
- Projeção de tendência futura

### 📝 Logging Inteligente
- Modo adaptativo (mais dados durante mudanças)
- Compressão automática de logs antigos
- Redução de ~95% no tamanho de arquivos
- Exportação para CSV

### ☢️ Rastreamento de Radiação
- Configuração de dose rate (krad/h)
- Dose inicial acumulada
- Cálculo automático de dose atual

---

## Estrutura do Repositório

```
Aging-V2/
├── App/                          # Código fonte da aplicação
│   ├── main.py                   # Ponto de entrada
│   ├── main_window.py            # Janela principal (ou main_window_v2.py)
│   ├── aging_analysis_widget.py  # Widget de análise de envelhecimento
│   ├── experiment_controller.py  # Controlador de experimento
│   ├── smart_logger.py           # Sistema de logging inteligente
│   ├── sensor_widget.py          # Visualização de sensores
│   ├── telemetry_widget.py       # Gráficos de telemetria
│   ├── router.py                 # Roteador de comunicação serial
│   ├── fpga_manager.py           # Gerenciador de programação FPGA
│   ├── protocol.py               # Protocolo de comunicação
│   ├── config.py                 # Configurações da aplicação
│   └── requirements.txt          # Dependências Python
│
├── out_bitstreams/               # Bitstreams para experimento
│   ├── croc_aging_clkout3phase_m330.bit
│   ├── croc_aging_clkout3phase_m330.ltx
│   ├── croc_aging_clkout3phase_m325.bit
│   ├── croc_aging_clkout3phase_m325.ltx
│   ├── croc_aging_clkout3phase_m320.bit
│   ├── croc_aging_clkout3phase_m320.ltx
│   ├── croc_aging_clkout3phase_m315.bit
│   └── croc_aging_clkout3phase_m315.ltx
│
├── CROC/                         # Projeto Vivado (HDL)
│   └── ...
│
├── Setup/                        # Scripts de configuração
│   └── ...
│
├── experiment_logs/              # Logs gerados (criado em runtime)
│   └── ...
│
├── run.bat                       # Script de execução (Windows)
├── run.sh                        # Script de execução (Linux)
├── README.md                     # Este arquivo
├── MANUAL_USO.md                 # Manual do usuário (PT)
├── USER_MANUAL.md                # Manual do usuário (EN)
└── LICENSE                       # Licença do projeto
```

### Descrição dos Diretórios

| Diretório | Descrição |
|-----------|-----------|
| `App/` | Código fonte Python da aplicação GUI |
| `out_bitstreams/` | Bitstreams pré-gerados para o experimento com diferentes fases |
| `CROC/` | Projeto Vivado com código HDL do sistema |
| `Setup/` | Scripts auxiliares de configuração |
| `experiment_logs/` | Diretório para logs (criado automaticamente) |

### Arquivos Principais

| Arquivo | Descrição |
|---------|-----------|
| `main.py` | Ponto de entrada da aplicação |
| `main_window.py` | Interface principal com todas as abas |
| `experiment_controller.py` | Máquina de estados do experimento |
| `smart_logger.py` | Sistema de logging com amostragem adaptativa |
| `aging_analysis_widget.py` | Widget da aba de análise de envelhecimento |
| `config.py` | Configurações persistentes (porta, paths, etc.) |

---

## Requisitos

### Hardware
- FPGA Xilinx 7-series (Artix-7, Kintex-7, etc.)
- Placa STM32 para controle de tensão
- Cabo USB-Serial
- Cabo JTAG/USB para programação

### Software
| Componente | Versão Mínima |
|------------|---------------|
| Python | 3.10+ |
| PySide6 | 6.0+ |
| Vivado | 2020.1+ |
| Sistema Operacional | Windows 10+ ou Ubuntu 20.04+ |

### Dependências Python
```
PySide6>=6.0.0
pyserial>=3.5
pyqtgraph>=0.13.0
numpy>=1.21.0
```

---

## Instalação

### Método 1: Script Automático (Recomendado)

**Windows:**
```cmd
git clone https://github.com/seu-usuario/Aging-V2.git
cd Aging-V2
run.bat
```

**Linux:**
```bash
git clone https://github.com/seu-usuario/Aging-V2.git
cd Aging-V2
chmod +x run.sh
./run.sh
```

### Método 2: Manual

```bash
git clone https://github.com/seu-usuario/Aging-V2.git
cd Aging-V2

# Criar ambiente virtual
python -m venv .venv

# Ativar ambiente
# Windows:
.venv\Scripts\activate
# Linux:
source .venv/bin/activate

# Instalar dependências
pip install -r App/requirements.txt

# Executar
python App/main.py
```

---

## Uso Rápido

### 1. Primeira Execução
```bash
./run.sh  # ou run.bat no Windows
```

### 2. Configurar Conexão
- Selecione a porta serial do STM32
- Aponte o Vivado path
- Clique "Save Settings"

### 3. Iniciar Experimento
1. Vá para aba "Aging Analysis"
2. Clique "Browse" → selecione `out_bitstreams/`
3. Clique "Load Bitstreams"
4. Configure radiação (dose rate)
5. Marque "Enable Auto-Program"
6. Clique "Start"

### 4. Monitorar
- Observe o estado (RUNNING = verde)
- Acompanhe transições na tabela
- Visualize gráficos de degradação

### 5. Exportar Resultados
- Clique "Export CSV" para salvar dados

---

## Arquitetura

### Diagrama de Componentes

```
┌─────────────────────────────────────────────────────────────┐
│                      MainWindow                             │
│  ┌─────────────┬─────────────┬─────────────┬─────────────┐  │
│  │   Sensors   │   Aging     │  Telemetry  │    Log      │  │
│  │    Tab      │  Analysis   │    Tab      │    Tab      │  │
│  └─────────────┴──────┬──────┴─────────────┴─────────────┘  │
└───────────────────────┼─────────────────────────────────────┘
                        │
          ┌─────────────┴─────────────┐
          │   ExperimentController    │
          │  ┌─────────────────────┐  │
          │  │   State Machine     │  │
          │  │  IDLE→RUNNING→...   │  │
          │  └─────────────────────┘  │
          └─────────────┬─────────────┘
                        │
     ┌──────────────────┼──────────────────┐
     │                  │                  │
     ▼                  ▼                  ▼
┌─────────┐      ┌─────────────┐    ┌─────────────┐
│  UART   │      │    FPGA     │    │   Smart     │
│ Router  │      │   Manager   │    │   Logger    │
└────┬────┘      └──────┬──────┘    └─────────────┘
     │                  │
     ▼                  ▼
┌─────────┐      ┌─────────────┐
│  STM32  │      │   Vivado    │
│  Board  │      │    TCL      │
└─────────┘      └─────────────┘
```

### Fluxo de Dados

```
Sensores FPGA → STM32 → Serial → Router → Controller → UI
                                              ↓
                                         SmartLogger → CSV/JSON
```

---

## Configuração

### Arquivo de Configuração

O sistema salva configurações em `config.json`:

```json
{
  "fpga_port": "COM3",
  "baud_rate": 115200,
  "vivado_path": "C:/Xilinx/Vivado/2023.1/bin/vivado.bat",
  "bitstream_dir": "./out_bitstreams"
}
```

### Variáveis de Ambiente (Opcional)

```bash
export CROC_VIVADO_PATH="/opt/Xilinx/Vivado/2023.1/bin/vivado"
export CROC_SERIAL_PORT="/dev/ttyUSB0"
```

---

## Contribuição

### Como Contribuir

1. Fork o repositório
2. Crie uma branch (`git checkout -b feature/nova-funcionalidade`)
3. Commit suas mudanças (`git commit -am 'Adiciona nova funcionalidade'`)
4. Push para a branch (`git push origin feature/nova-funcionalidade`)
5. Abra um Pull Request

### Padrões de Código

- Python: PEP 8
- Docstrings: Google style
- Commits: Conventional Commits

---

## Licença

Este projeto está licenciado sob a Licença MIT - veja o arquivo [LICENSE](LICENSE) para detalhes.

---

## Autores

- **Equipe CROC** - *Desenvolvimento inicial*

---

## Agradecimentos

- Laboratório de Radiação
- Equipe de suporte Xilinx
- Contribuidores open-source

---

<p align="center">
  <i>CROC FPGA Aging Monitor - Monitorando o futuro dos FPGAs</i>
</p>
