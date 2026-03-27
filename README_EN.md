# 🔬 CROC FPGA Aging Monitor

<p align="center">
  <img src="https://img.shields.io/badge/Python-3.10+-blue.svg" alt="Python">
  <img src="https://img.shields.io/badge/PySide6-6.0+-green.svg" alt="PySide6">
  <img src="https://img.shields.io/badge/Platform-Windows%20%7C%20Linux-lightgrey.svg" alt="Platform">
  <img src="https://img.shields.io/badge/License-MIT-yellow.svg" alt="License">
</p>

Real-time monitoring system for FPGA aging experiments under ionizing radiation. Developed to automate timing degradation detection and transitions between bitstreams with different slack margins.

---

## 📋 Table of Contents

- [Overview](#overview)
- [Features](#features)
- [Repository Structure](#repository-structure)
- [Requirements](#requirements)
- [Installation](#installation)
- [Quick Start](#quick-start)
- [Architecture](#architecture)
- [Configuration](#configuration)
- [Contributing](#contributing)
- [License](#license)

---

## Overview

The **CROC FPGA Aging Monitor** is a tool developed for aging characterization experiments in FPGAs exposed to radiation. The system:

- Monitors 4 types of timing sensors (128 sensors total)
- Automatically detects degradation through alarms
- Transitions between bitstreams with different slack margins
- Records all transitions with complete metadata
- Projects degradation trends through linear regression

### Scientific Context

FPGAs exposed to ionizing radiation suffer timing degradation due to Total Ionizing Dose (TID). This system enables:

1. Quantifying slack degradation rate
2. Correlating degradation with radiation dose
3. Automating long-duration experiments (weeks)

---

## Features

### 🎛️ Sensor Monitoring
- **Legacy Mode**: 4 sensor buses (F, RF, UART, OBI) × 32 bits = 128 sensors total
- **Multi-Bank Mode** ⭐ **NEW**: N dynamic TMR banks × 64 bits each
  - 2 TMR banks by default (128 sensors total)
  - Scalable to N banks without UI redesign
  - 8×8 grid visualization per bank
  - Scrollable interface for large sensor arrays
- Real-time visualization with colored indicators
- Selective filters by sensor type

### 🔄 Auto-Program
- Bitstream queue with automatic phase detection
- Automatic transition when alarms are detected
- Configurable stabilization and cooldown times
- Guaranteed programming of first bitstream on start

### 📊 Degradation Analysis
- Slack vs Radiation Dose graph
- Slack vs Time graph
- Linear regression with R²
- Future trend projection

### 📝 Smart Logging
- Adaptive mode (more data during changes)
- Automatic compression of old logs
- ~95% file size reduction
- CSV export

### ☢️ Radiation Tracking
- Dose rate configuration (krad/h)
- Initial accumulated dose
- Automatic current dose calculation

---

## Repository Structure

```
Aging-V2/
├── App/                          # Application source code
│   ├── main.py                   # Entry point
│   ├── main_window.py            # Main window (or main_window_v2.py)
│   ├── aging_analysis_widget.py  # Aging analysis widget
│   ├── experiment_controller.py  # Experiment controller
│   ├── smart_logger.py           # Smart logging system
│   ├── sensor_widget.py          # Sensor visualization (legacy + multi-bank)
│   ├── multi_bank_types.py       # Multi-bank TMR data types ⭐ NEW
│   ├── telemetry_widget.py       # Telemetry graphs
│   ├── router.py                 # Serial communication router (updated for $TMR protocol)
│   ├── fpga_manager.py           # FPGA programming manager
│   ├── protocol.py               # Communication protocol
│   ├── config.py                 # Application configuration
│   └── requirements.txt          # Python dependencies
│
├── out_bitstreams/               # Experiment bitstreams
│   ├── croc_aging_clkout3phase_m330.bit
│   ├── croc_aging_clkout3phase_m330.ltx
│   ├── croc_aging_clkout3phase_m325.bit
│   ├── croc_aging_clkout3phase_m325.ltx
│   ├── croc_aging_clkout3phase_m320.bit
│   ├── croc_aging_clkout3phase_m320.ltx
│   ├── croc_aging_clkout3phase_m315.bit
│   └── croc_aging_clkout3phase_m315.ltx
│
├── CROC/                         # Vivado project (HDL)
│   └── ...
│
├── Setup/                        # Setup scripts
│   └── ...
│
├── experiment_logs/              # Generated logs (created at runtime)
│   └── ...
│
├── run.bat                       # Execution script (Windows)
├── run.sh                        # Execution script (Linux)
├── README.md                     # This file
├── MANUAL_USO.md                 # User manual (PT)
├── USER_MANUAL.md                # User manual (EN)
└── LICENSE                       # Project license
```

### Directory Descriptions

| Directory | Description |
|-----------|-------------|
| `App/` | Python GUI application source code |
| `out_bitstreams/` | Pre-generated bitstreams for experiments with different phases |
| `CROC/` | Vivado project with system HDL code |
| `Setup/` | Auxiliary configuration scripts |
| `experiment_logs/` | Log directory (created automatically) |

### Main Files

| File | Description |
|------|-------------|
| `main.py` | Application entry point |
| `main_window.py` | Main interface with all tabs |
| `experiment_controller.py` | Experiment state machine |
| `smart_logger.py` | Logging system with adaptive sampling |
| `aging_analysis_widget.py` | Aging analysis tab widget |
| `config.py` | Persistent configurations (port, paths, etc.) |

---

## Requirements

### Hardware
- Xilinx 7-series FPGA (Artix-7, Kintex-7, etc.)
- STM32 board for voltage control
- USB-Serial cable
- JTAG/USB cable for programming

### Software
| Component | Minimum Version |
|-----------|-----------------|
| Python | 3.10+ |
| PySide6 | 6.0+ |
| Vivado | 2020.1+ |
| Operating System | Windows 10+ or Ubuntu 20.04+ |

### Python Dependencies
```
PySide6>=6.0.0
pyserial>=3.5
pyqtgraph>=0.13.0
numpy>=1.21.0
```

---

## Installation

### Method 1: Automatic Script (Recommended)

**Windows:**
```cmd
git clone https://github.com/your-username/Aging-V2.git
cd Aging-V2
run.bat
```

**Linux:**
```bash
git clone https://github.com/your-username/Aging-V2.git
cd Aging-V2
chmod +x run.sh
./run.sh
```

### Method 2: Manual

```bash
git clone https://github.com/your-username/Aging-V2.git
cd Aging-V2

# Create virtual environment
python -m venv .venv

# Activate environment
# Windows:
.venv\Scripts\activate
# Linux:
source .venv/bin/activate

# Install dependencies
pip install -r App/requirements.txt

# Run
python App/main.py
```

---

## Quick Start

### 1. First Run
```bash
./run.sh  # or run.bat on Windows
```

### 2. Configure Connection
- Select STM32 serial port
- Point to Vivado path
- Click "Save Settings"

### 3. Start Experiment
1. Go to "Aging Analysis" tab
2. Click "Browse" → select `out_bitstreams/`
3. Click "Load Bitstreams"
4. Configure radiation (dose rate)
5. Check "Enable Auto-Program"
6. Click "Start"

### 4. Monitor
- Watch the state (RUNNING = green)
- Track transitions in the table
- View degradation graphs

### 5. Export Results
- Click "Export CSV" to save data

---

## Architecture

### Component Diagram

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

### Data Flow

```
FPGA Sensors → STM32 → Serial → Router → Controller → UI
                                              ↓
                                         SmartLogger → CSV/JSON
```

---

## Configuration

### Configuration File

The system saves settings in `config.json`:

```json
{
  "fpga_port": "COM3",
  "baud_rate": 115200,
  "vivado_path": "C:/Xilinx/Vivado/2023.1/bin/vivado.bat",
  "bitstream_dir": "./out_bitstreams"
}
```

### Environment Variables (Optional)

```bash
export CROC_VIVADO_PATH="/opt/Xilinx/Vivado/2023.1/bin/vivado"
export CROC_SERIAL_PORT="/dev/ttyUSB0"
```

---

## Contributing

### How to Contribute

1. Fork the repository
2. Create a branch (`git checkout -b feature/new-feature`)
3. Commit your changes (`git commit -am 'Add new feature'`)
4. Push to the branch (`git push origin feature/new-feature`)
5. Open a Pull Request

### Code Standards

- Python: PEP 8
- Docstrings: Google style
- Commits: Conventional Commits

---

## License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.

---

## Authors

- **CROC Team** - *Initial development*

---

## Acknowledgments

- Radiation Laboratory
- Xilinx support team
- Open-source contributors

---

<p align="center">
  <i>CROC FPGA Aging Monitor - Monitoring the future of FPGAs</i>
</p>
