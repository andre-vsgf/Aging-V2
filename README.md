# CROC FPGA Aging Sensor Project

Sistema de monitoramento de envelhecimento de circuitos FPGA por radiação, com aplicação Python para análise em tempo real.

## 📁 Estrutura do Projeto

```
MEU_PROJETO/
├── .gitignore              # Ignora a pasta Aging_V2/
├── README.md               # Este arquivo
├── Aging_V2/               # (Gerado) Projeto Vivado
│
├── App/                    # Aplicação Python
│   ├── main_window.py      
│   ├── fpga_manager.py     
│   ├── aging_analysis_widget.py
│   ├── requirements.txt
│   └── ...
│
├── Setup/                  # Scripts de configuração
│   ├── setup_windows.bat
│   └── setup_linux.sh
│
└── CROC/                   # Hardware FPGA
    ├── Constraints/        # Arquivos .xdc
    ├── Generate_project/   # Scripts de build
    │   ├── create_project_win.bat
    │   ├── create_project_linux.sh
    │   ├── master_build.tcl
    │   ├── source_list.tcl
    │   └── setup_ips_and_mem.tcl
    ├── rtl_sensors/        # RTL dos sensores
    ├── scripts/            # Scripts utilitários
    ├── sw/bin/             # Firmware (.mem)
    └── xilinx/hw/          # Top-level
```

## 🚀 Quick Start

### 1. Gerar o Projeto Vivado

**Windows:**
```batch
cd CROC\Generate_project
create_project_win.bat
```

**Linux:**
```bash
cd CROC/Generate_project
chmod +x create_project_linux.sh
./create_project_linux.sh
```

O projeto será criado em `Aging_V2/croc_aging.xpr`.

### 2. Compilar no Vivado

1. Abra `Aging_V2/croc_aging.xpr` no Vivado
2. Execute **Run Synthesis** (F11)
3. Execute **Run Implementation**
4. Execute **Generate Bitstream**

Ou via TCL:
```tcl
launch_runs synth_1 -jobs 4
wait_on_run synth_1
launch_runs impl_1 -to_step write_bitstream -jobs 4
```

### 3. Configurar Aplicação Python

```bash
cd App
pip install -r requirements.txt
python App.py
```

## 🔧 Requisitos

### Hardware
- **FPGA:** Artix UltraScale+ AU15P (xcau15p-ffvb676-2-i)
- **Interface:** JTAG para programação, UART para comunicação

### Software
- **Vivado:** 2023.1 ou superior
- **Python:** 3.8 ou superior
- **Dependências Python:** Ver `App/requirements.txt`

## 📊 IPs Xilinx Gerados Automaticamente

| IP | Função | Configuração |
|----|--------|--------------|
| `clk_wiz` | Clock Wizard | MMCM, 100MHz diff → 3× 20MHz |
| `sysmon_wiz_0` | System Monitor | DRP, Temp + VCCINT, Avg=64 |
| `vio_2` | Virtual I/O | 1 in (1b), 4 out (1b,1b,4b,4b) |

## 🔬 Funcionalidades

### Sistema de Sensores de Envelhecimento
- 2 barramentos de 32 bits ativos (ALARM_F, ALARM_RF)
- 2 barramentos reservados (placeholder, exibidos em cinza)
- Detecção de alarmes em tempo real

### Análise de Envelhecimento (Aba "📈 Aging Analysis")
- Configuração de taxa de radiação (krad/h)
- Mapeamento bitstream → calibração (fase °, slack ns)
- Logging de eventos com timestamp e dose acumulada
- Gráfico de slack vs. dose de radiação
- Auto-reprogram quando alarme dispara

### Telemetria
- Temperatura FPGA (via SYSMON)
- VCCINT (via SYSMON)
- Tensão/Corrente do DUT (via STM32)
- Gráficos em tempo real

## 📝 Detalhes dos IPs

### Clock Wizard (clk_wiz)
```
Entrada: Diferencial 100MHz (clk_in1_p, clk_in1_n)
Primitiva: MMCM
Saídas:
  - soc_clk:       20MHz, fase 0°
  - catcher_clk_i: 20MHz, fase 20°
  - psclk_rf_i:    20MHz, fase -330°
Reset: Active High
Locked: Habilitado
```

### System Monitor (sysmon_wiz_0)
```
Interface: DRP
DCLK: 20MHz
Modo: Continuous Sequence
Canais: Temperature, VCCINT, Calibration
Averaging: 64 samples
⚠️ VP/VN: DESABILITADO (não há portas .vp/.vn)
```

### VIO (vio_2)
```
Probe In:
  - probe_in0[0:0]  : 1 bit (locked)
Probe Out:
  - probe_out0[0:0] : 1 bit (reset)
  - probe_out1[0:0] : 1 bit (fetch_en)
  - probe_out2[3:0] : 4 bits (gpio)
  - probe_out3[3:0] : 4 bits (reserved)
```

## ⚠️ Notas Importantes

### Sobre o System Monitor
O IP `sysmon_wiz_0` está configurado **sem** VP/VN:
```tcl
CONFIG.CHANNEL_ENABLE_VP_VN {false}
```
Isso significa que o módulo `system_monitor_usp.sv` **NÃO** deve conectar portas `.vp` e `.vn`.

### Versioning
A pasta `Aging_V2/` **não é versionada** no Git. Cada usuário deve gerar o projeto localmente usando os scripts em `Generate_project/`.

### Portabilidade
Os scripts detectam automaticamente o Vivado em locais comuns de instalação:
- Windows: `C:\Xilinx\Vivado\202x.x\`
- Linux: `/tools/Xilinx/Vivado/202x.x/` ou `/opt/Xilinx/Vivado/202x.x/`

## 🤝 Contribuição

1. Clone o repositório
2. Gere o projeto Vivado com os scripts
3. Faça suas modificações
4. Atualize os scripts TCL se necessário
5. Teste em Windows e Linux
6. Envie o Pull Request

## 📄 Licença

[Inserir licença aqui]
