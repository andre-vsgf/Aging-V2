# 📖 User Manual - CROC FPGA Aging Monitor

**FPGA Aging Monitoring System Under Radiation**

---

## 📋 Table of Contents

1. [Requirements](#requirements)
2. [Installation](#installation)
3. [First Use](#first-use)
4. [Running the Experiment](#running-the-experiment)
5. [User Interface](#user-interface)
6. [Real-Time Manipulation](#real-time-manipulation)
7. [Interpreting Results](#interpreting-results)
8. [Concept of DONE](#concept-of-done)
9. [Data Export](#data-export)
10. [Troubleshooting](#troubleshooting)

---

## Requirements

### Hardware
- Xilinx FPGA (7-series or newer)
- STM32 board for voltage control
- USB cable for serial communication
- JTAG cable for FPGA programming

### Software
- **Windows 10/11** or **Linux (Ubuntu 20.04+)**
- **Python 3.10+**
- **Xilinx Vivado 2020.1+** (for FPGA programming)
- USB-Serial driver installed

---

## Installation

### Step 1: Clone the Repository

```bash
git clone https://github.com/your-username/Aging-V2.git
cd Aging-V2
```

### Step 2: Run the System

#### Windows
Simply execute the `run.bat` script:
```cmd
run.bat
```

The script automatically:
1. Checks if a virtual environment (`.venv`) exists
2. Creates the environment if it doesn't exist
3. Installs dependencies from `requirements.txt`
4. Starts the application

#### Linux
Execute the `run.sh` script:
```bash
chmod +x run.sh
./run.sh
```

### Step 3: Initial Configuration

On first run, configure:

1. **Serial Port**: Select the COM port connected to the STM32
2. **Vivado Path**: Point to the Vivado executable
3. **Bitstream Directory**: Already configured to `out_bitstreams/`
4. Click **"Save Settings"**

---

## First Use

### Checking the Connection

1. Connect the hardware (STM32 + FPGA)
2. In the **"Settings"** tab, select the correct serial port
3. Click **"Connect"**
4. The indicator should change to **"● Connected"** (green)

### Testing Programming

1. In the **"FPGA Programming"** tab, verify that bitstreams appear in the list
2. Select a bitstream (e.g., `croc_aging_clkout3phase_m330.bit`)
3. Click **"▶ PROGRAM (SRAM)"**
4. Wait for the success message

---

## Running the Experiment

### Complete Flow

```
┌─────────────────────────────────────────────────────────────┐
│  1. PREPARATION                                             │
│     ├─ Connect hardware                                     │
│     ├─ Verify serial connection                             │
│     └─ Go to "Aging Analysis" tab                           │
├─────────────────────────────────────────────────────────────┤
│  2. CONFIGURATION                                           │
│     ├─ Load bitstreams (Browse → Load)                      │
│     ├─ Configure sensor filters                             │
│     ├─ Configure radiation (dose rate + initial)            │
│     └─ Adjust timings (stabilization + cooldown)            │
├─────────────────────────────────────────────────────────────┤
│  3. EXECUTION                                               │
│     ├─ Check "Enable Auto-Program on Alarm"                 │
│     ├─ Click "▶ Start"                                      │
│     └─ Monitor the experiment                               │
├─────────────────────────────────────────────────────────────┤
│  4. CONCLUSION                                              │
│     ├─ State "FINISHED" or click "Stop"                     │
│     ├─ Export data (CSV)                                    │
│     └─ Analyze degradation graphs                           │
└─────────────────────────────────────────────────────────────┘
```

### Detailed Step by Step

#### 1. Load Bitstreams

1. Click **"📂 Browse"**
2. Navigate to `Aging-V2/out_bitstreams/`
3. Click **"🔄 Load Bitstreams"**
4. Confirm bitstreams were loaded (e.g., 4 bitstreams, -330° to -315°)

#### 2. Configure Sensor Filters

Select which sensors can trigger transitions:

| Sensor | Description | Recommendation |
|--------|-------------|----------------|
| **F (AM)** | Amplitude modulated sensors | ✅ Enabled |
| **RF (LF)** | Low frequency sensors | ✅ Enabled |
| **UART** | UART sensors | ✅ Enabled |
| **OBI** | OBI Demux sensors | ✅ Enabled |

> 💡 **Tip**: If a specific sensor is causing too many transitions and you want to observe others, temporarily disable it.

#### 3. Configure Radiation

| Field | Description | Example |
|-------|-------------|---------|
| **Dose Rate** | Radiation source rate | `0.300 krad/h` |
| **Initial Dose** | Already accumulated dose | `0.00 krad` |

#### 4. Configure Timings

| Parameter | Description | Default Value |
|-----------|-------------|---------------|
| **Stabilization** | Wait after alarm | `3000 ms` |
| **Cooldown** | Wait after reprogram | `10000 ms` |

#### 5. Start Experiment

1. ✅ Check **"🔄 Enable Auto-Program on Alarm"**
2. Click **"▶ Start"**
3. The system will:
   - Program the first bitstream (if necessary)
   - Start alarm monitoring
   - Automatically transition when alarms are detected

---

## User Interface

### "Sensors & Control" Tab

```
┌─────────────────────────────────────────────────────────────┐
│  SENSOR VISUALIZATION                                       │
│  ┌─────────────┬─────────────┬─────────────┬─────────────┐  │
│  │  F Sensors  │ RF Sensors  │UART Sensors │ OBI Sensors │  │
│  │  [32 bits]  │  [32 bits]  │  [32 bits]  │  [32 bits]  │  │
│  │  ██░░██░░   │  ░░░░░░░░   │  ░░░░░░░░   │  ░░░░░░░░   │  │
│  └─────────────┴─────────────┴─────────────┴─────────────┘  │
│                                                             │
│  ██ = Active alarm    ░░ = Normal                          │
└─────────────────────────────────────────────────────────────┘
```

### "Aging Analysis" Tab

```
┌─────────────────────────┬───────────────────────────────────┐
│  BITSTREAM QUEUE        │  TRANSITION HISTORY               │
│  ┌───────────────────┐  │  ┌─────────────────────────────┐  │
│  │ 1. m330 (-330°)   │  │  │ Time | Dose | Phase Change │  │
│  │ 2. m325 (-325°) ← │  │  │ 12:30| 0.45 | -330→-325    │  │
│  │ 3. m320 (-320°)   │  │  │ 12:45| 0.52 | -325→-320    │  │
│  └───────────────────┘  │  └─────────────────────────────┘  │
│                         │                                   │
│  SENSOR FILTERS         │  GRAPHS                           │
│  ☑ F  ☑ RF              │  [Slack vs Dose] [Slack vs Time]  │
│  ☑ UART  ☑ OBI          │  ┌─────────────────────────────┐  │
│                         │  │     ●                       │  │
│  RADIATION              │  │   ●  ────────────           │  │
│  Rate: 0.3 krad/h       │  │ ●─────────────···(projection)│  │
│  Current: 1.25 krad     │  └─────────────────────────────┘  │
│                         │                                   │
│  CONTROL                │  Rate: 0.023 ns/krad | R²=0.98   │
│  State: RUNNING         │                                   │
│  [Start] [Stop] [Skip]  │                                   │
└─────────────────────────┴───────────────────────────────────┘
```

### State Meanings

| State | Color | Meaning |
|-------|-------|---------|
| **IDLE** | ⚫ Gray | Experiment not started |
| **PROGRAMMING_INITIAL** | 🔵 Blue | Programming first bitstream |
| **RUNNING** | 🟢 Green | Actively monitoring alarms |
| **ALARM_DETECTED** | 🟡 Yellow | Alarm detected, waiting for stabilization |
| **REPROGRAMMING** | 🔵 Blue | Reprogramming FPGA |
| **COOLDOWN** | ⚫ Gray | Waiting after reprogramming |
| **FINISHED** | 🟣 Purple | End of bitstream queue |

---

## Real-Time Manipulation

### Available Actions During Experiment

| Action | How To | Effect |
|--------|--------|--------|
| **Pause/Resume** | Stop/Start button | Interrupts monitoring |
| **Skip Bitstream** | "⏭ Skip" button | Advances to next without alarm |
| **Filter Sensors** | Checkboxes | Enables/disables triggers |
| **Adjust Timings** | Spinboxes | Modifies stabilization/cooldown |

### Modifying Sensor Filters

You can **enable/disable sensors at any time**:

1. Uncheck the sensor you don't want as a trigger
2. The change is **immediate**
3. The sensor continues to be **monitored**, just doesn't cause transitions

**Typical use case:**
> F sensors are causing too many transitions. You want to see when RF or UART trigger.
> → Disable F, keep the others enabled.

---

## Interpreting Results

### Transition History

Each row represents a transition:

| Column | Meaning |
|--------|---------|
| **Time** | Transition timestamp |
| **Hours** | Experiment time |
| **Dose** | Accumulated radiation dose |
| **From → To** | Previous → new bitstream |
| **Phase** | Previous → new phase (degrees) |
| **Triggers** | Sensors that triggered (F:2, RF:1) |
| **Alarms** | Total active alarms |

### Degradation Graphs

#### Slack vs Dose
- **X-axis**: Radiation dose (krad)
- **Y-axis**: Temporal slack (ns)
- **Interpretation**: The steeper the curve, the faster the degradation

#### Slack vs Time
- **X-axis**: Experiment time (hours)
- **Y-axis**: Temporal slack (ns)
- **Interpretation**: Temporal degradation rate

#### Graph Elements
- **Colored points**: Actual measurements
- **Solid yellow line**: Linear regression
- **Dashed orange line**: Future projection

#### Regression Information
```
Slack degradation rate: 0.0234 ns/krad | R² = 0.9856
```
- **Rate**: Degradation rate
- **R²**: Fit quality (1.0 = perfect)

---

## Concept of DONE

### When Does the Experiment End?

The experiment is considered **DONE** when:

1. **End of Queue**: All bitstreams have been used
   - State changes to **FINISHED** (purple)
   - Message: "Experiment completed!"

2. **Manual Stop**: User clicks **"⏹ Stop"**
   - Data is automatically saved
   - Can be resumed later

3. **Fatal Error**: Hardware or communication failure
   - Partial data is preserved

### What Happens When Finished?

```
┌─────────────────────────────────────────────┐
│  🏁 EXPERIMENT FINISHED                     │
│                                             │
│  Total transitions: 4                       │
│  Duration: 12.45 hours                      │
│  Final dose: 3.74 krad                      │
│                                             │
│  [OK]                                       │
└─────────────────────────────────────────────┘
```

### Automatically Saved Data

| File | Content |
|------|---------|
| `experiment_transitions.json` | All transitions with details |
| `experiment_logs/*.csv` | Sensor logs (SmartLogger) |
| `experiment_logs/*.json` | Experiment events |

---

## Data Export

### Export Transitions

1. In the "Aging Analysis" tab, click **"📁 Export CSV"**
2. Choose location and filename
3. The CSV contains all history columns

### Exported CSV Format

```csv
timestamp,experiment_hours,radiation_dose_krad,from_bitstream,from_phase,to_bitstream,to_phase,total_alarms,trigger_f,trigger_rf,trigger_uart,trigger_obi,fpga_temp,vccint
2026-01-24T12:30:15,1.5,0.45,m330.bit,-330,m325.bit,-325,3,[0,14,28],[],[],[],45.2,0.852
```

### Automatic Saving

The system automatically saves:
- On each transition
- When stopping the experiment
- When closing the application

---

## Troubleshooting

### "Cannot connect to serial port"
1. Check if USB driver is installed
2. Verify the port is correct
3. Try disconnecting and reconnecting the cable

### "Bitstreams don't appear in the list"
1. Check if `out_bitstreams/` folder contains `.bit` files
2. Click "🔄 Load Bitstreams" again
3. Check the log for error messages

### "FPGA programming fails"
1. Check if Vivado path is correct
2. Check if JTAG cable is connected
3. Check if FPGA is powered

### "System switches bitstreams too fast"
1. Increase **Cooldown Time** (e.g., 15000 ms)
2. Disable sensors that are causing too many triggers

### "Alarm doesn't trigger transition"
1. Check if the sensor is **enabled** in filters
2. Check if **Auto-Program** is checked
3. Check if state is **RUNNING**

---

## Support

For unresolved issues:

1. Check the log in the **"📋 Log"** tab
2. Export data before closing
3. Consult the repository documentation
4. Open a GitHub issue with:
   - Problem description
   - Error messages from log
   - Operating system version
   - Vivado version

---

*CROC FPGA Aging Monitor - Version 2.1*
*January 2026*
