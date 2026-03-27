# Changelog - CROC FPGA Aging Monitor

## [2.1.0] - 2026-03-23

### ⭐ Added
- **Multi-Bank TMR Support**: New scalable architecture for monitoring N dynamic 64-bit sensor banks
  - Default: 2 TMR banks (128 sensors total, same as legacy)
  - Expandable to N banks without UI redesign
  - 8×8 grid visualization per bank in scrollable container
- **New Data Type**: `SensorBank` dataclass in `multi_bank_types.py`
  - Supports `alarm_vector` (64-bit persistent failures)
  - Supports `divergence_vector` (64-bit transient events)
  - Helper methods: `total_alarms`, `total_divergences`, `get_bits_list()`
- **New Serial Protocol**: `$TMR` format for multi-bank data
  - Format: `$TMR,BANK0_AL,BANK0_DIV,BANK1_AL,BANK1_DIV,...*CS`
  - Parsed by updated `router.py`
  - Flexible: supports any number of banks
- **Dual-Mode Sensor Widget**: `SensorVisualizationWidget` now supports both modes
  - Legacy mode (num_banks=0): 4×32-bit registers in 2×2 grid
  - Multi-bank mode (num_banks>0): N×64-bit banks in scrollable view
  - Full backward compatibility with existing code
- **New Widget Class**: `SensorBankWidget` for per-bank 8×8 grid display
  - Per-bank header with alarm/divergence counts
  - Individual cell state management
  - Integrates with main scrollable container
- **New Signal**: `multi_bank_data_received(list)` in `UARTRouter`
  - Emits list of bank dictionaries
  - Triggers widget updates

### 📋 Documentation
- **New File**: `MULTI_BANK_ARCHITECTURE.md`
  - Complete architecture documentation
  - Data flow pipeline
  - Protocol specification
  - API reference
  - Roadmap for future enhancements
- **Updated**: `README_EN.md`
  - New Features section highlights multi-bank support
  - Repository structure includes new files

### 🔧 Modified Files
- **router.py**: Added $TMR protocol parser, `multi_bank_data_received` signal, bank data extraction
- **sensor_widget.py**: 
  - Dual-mode support in `SensorVisualizationWidget.__init__(num_banks=0)`
  - New `SensorBankWidget` class for 8×8 per-bank grids
  - New methods: `setupMultiBankDisplay()`, `updateMultiBankData()`
  - Legacy methods protected with `if not self._legacy_mode` guards
- **main_window.py**: 
  - Initialized widget with `num_banks=2` (multi-bank mode active)
  - Connected `multi_bank_data_received` signal
  - Added `_on_multi_bank_data()` handler slot

### ✅ Backward Compatibility
- All legacy 4-sensor functionality preserved
- Old `updateSensorData(alarm_f, alarm_rf, ...)` method still works
- Can revert to legacy mode by changing `num_banks=0` in main_window.py
- Existing serial protocol ($SYS) still supported

### 📊 Known Issues & Limitations
- [ ] 3-state colors not yet implemented (yellow for divergence)
- [ ] Auto-timeout for divergence not yet implemented
- [ ] Experiment controller not yet processing multi-bank alarms
- [ ] Logging/CSV export not yet updated for bank metadata
- [ ] Hardware protocol finalization pending with FPGA team

### 🚀 Roadmap (Next Phases)
- **Phase 2**: 3-state colors + 500ms divergence timeout
- **Phase 3**: Experiment controller multi-bank alarm processing
- **Phase 4**: Logging and CSV export with per-bank columns
- **Phase 5**: Hardware integration testing and validation

---

## [2.0.0] - 2026-01-XX

### Features
- 4 aging sensor buses (F, RF, UART, OBI) monitoring
- 32-bit alarm registers per bus (128 sensors total)
- Real-time sensor visualization with colored grid
- Auto-program functionality with bitstream transitions
- Degradation analysis with linear regression
- Smart logging with adaptive compression
- Radiation dose tracking and projection
- CSV data export

### Platforms
- Windows 10/11
- Linux (Ubuntu 20.04+)

### Technologies
- Python 3.10+
- PySide6 (Qt 6.x)
- Xilinx Vivado 2020.1+

---

## Notes for Developers

### How to Switch Modes
```python
# Legacy mode (4 registers)
widget = SensorVisualizationWidget(num_banks=0)

# Multi-bank mode (N banks)
widget = SensorVisualizationWidget(num_banks=2)  # or any N > 0
```

### Testing Multi-Bank Locally
1. Start app with `./run.sh`
2. Observe 2 vertical 8×8 grids in sensor panel
3. Grids are stacked in a scrollable container
4. All cells start green (no alarms)

### Hardware Testing
- Requires FPGA to send `$TMR` protocol format
- Ensure firmware supports 64-bit bank vectors
- Test clear-on-read mechanism for divergence_vector
- Validate with 1, 2, and 3+ banks

---

## File Statistics

| File | Status | Lines | Type |
|------|--------|-------|------|
| multi_bank_types.py | NEW | 45 | Python |
| sensor_widget.py | MODIFIED | +150 | Python |
| router.py | MODIFIED | +35 | Python |
| main_window.py | MODIFIED | +10 | Python |
| MULTI_BANK_ARCHITECTURE.md | NEW | 400+ | Documentation |
| README_EN.md | MODIFIED | +5 lines | Documentation |

---

**Release Date**: March 23, 2026  
**Author**: Multi-Bank Refactoring Task Force  
**Status**: ✅ MVP Complete, 🔄 Integration In Progress
