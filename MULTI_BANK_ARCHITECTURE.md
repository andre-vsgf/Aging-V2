# Multi-Bank TMR Sensor Architecture

**Version**: 1.0 | **March 2026** | **Status**: MVP Complete

---

## Overview

The CROC FPGA Aging Monitor now supports **dynamic multi-bank TMR sensor monitoring**. Instead of the fixed 4×32-bit register layout, the system allows N dynamic 64-bit sensor banks displayed as scrollable 8×8 grids.

**Current Configuration**: 2 TMR banks = 128 sensors (same as legacy 4×32-bit)

---

## Serial Protocol: $TMR Format

### Message Format
```
$TMR,BANK0_AL_HEX,BANK0_DIV_HEX,BANK1_AL_HEX,BANK1_DIV_HEX,...*CHECKSUM
```

### Field Descriptions
- `BANK*_AL`: 64-bit alarm vector (hexadecimal)
- `BANK*_DIV`: 64-bit divergence vector (hexadecimal)  
- `*`: Pair repeats for each bank
- `CHECKSUM`: 2-digit hex CRC validation

### Example (2 banks, all nominal)
```
$TMR,0000000000000000,0000000000000000,0000000000000000,0000000000000000*AB
```

### Example (Bank 1, sensor 5 alarmed)
```
$TMR,0000000000000000,0000000000000000,0000000000000020,0000000000000000*XY
                                             ↑ 0x20 = bit 5 active
```

### Parser Implementation
**File**: `App/router.py` (lines ~120-155)
```python
self._tmr_bank_regex = re.compile(
    r'\$TMR,([0-9A-Fa-f]+(?:,[0-9A-Fa-f]+)*)\*([0-9A-Fa-f]{2})',
    re.IGNORECASE
)
```

---

## Data Structures

### SensorBank (multi_bank_types.py)

```python
@dataclass
class SensorBank:
    bank_id: int                    # Bank identifier (0, 1, 2, ...)
    alarm_vector: int               # 64-bit mask, bit i = alarm on sensor i
    divergence_vector: int          # 64-bit mask, bit i = divergence on sensor i
    
    # Properties
    total_alarms → int              # Count of active alarm bits
    total_divergences → int         # Count of active divergence bits
    get_bits_list(vector) → List[int]  # Returns [0, 5, 12, ...] for active bits
```

### Signal Format
```python
# Emitted by router.multi_bank_data_received
[
    {'bank_id': 0, 'alarm_vector': int, 'divergence_vector': int},
    {'bank_id': 1, 'alarm_vector': int, 'divergence_vector': int},
]
```

---

## Widget Modes

### Legacy Mode (num_banks=0)
- 2×2 grid of 4 registers (F, RF, UART, OBI)
- 32 bits per register
- Total: 128 sensors

### Multi-Bank Mode (num_banks > 0)
- Vertical scrollable container
- Each bank as 8×8 grid (64 bits)
- Per-bank header with counts
- Total: N × 64 sensors

### Switch Modes
```python
# File: main_window.py, line ~160

# Legacy:
self.sensor_widget = SensorVisualizationWidget(num_banks=0)

# Multi-bank (currently active):
self.sensor_widget = SensorVisualizationWidget(num_banks=2)
```

---

## API Reference

### SensorVisualizationWidget

```python
# Initialize
widget = SensorVisualizationWidget(parent=None, num_banks=2)

# Update multi-bank display
widget.updateMultiBankData([
    {'bank_id': 0, 'alarm_vector': 0x1234, 'divergence_vector': 0x0},
    {'bank_id': 1, 'alarm_vector': 0x0, 'divergence_vector': 0x5678},
])

# Legacy updates (still work)
widget.updateSensorData(alarm_f, alarm_rf, alarm_uart, alarm_obi)
widget.enableSensor("f", enabled=True)
```

### SensorBankWidget

```python
# Per-bank widget (created automatically)
bank = widget._bank_widgets[0]

# Read state
bank.bank_id          # int
bank.alarm_vector     # int (0x...)
bank.divergence_vector  # int (0x...)

# Update
bank.setBankData(alarm_vector=0x1234, divergence_vector=0x5678)
```

---

## Files Changed

| File | Type | What |
|------|------|------|
| `multi_bank_types.py` | NEW | SensorBank dataclass |
| `router.py` | MOD | $TMR protocol parser, `multi_bank_data_received` signal |
| `sensor_widget.py` | MOD | Dual-mode support, SensorBankWidget class |
| `main_window.py` | MOD | Initialized with `num_banks=2`, signal wiring |

---

## Backward Compatibility

✅ All legacy methods preserved  
✅ Old 4-sensor signals still work  
✅ Can revert to legacy mode anytime  
✅ No breaking changes to existing code

---

## Color States (Current)

- **Green**: Normal (alarm=0, div=0)
- **Red**: Alarm (alarm=1)
- **Gray**: Disabled

**Future**: Yellow state for divergence + 500ms timeout (Phase 2)

---

## Known Limitations

- [ ] No yellow/divergence timeout yet
- [ ] Experiment controller not processing multi-bank alarms
- [ ] Logging/CSV export not updated for bank metadata
- [ ] All banks share single state machine (by design)

---

## Quick Debug

```python
# Check mode
print(f"Legacy: {widget._legacy_mode}, Banks: {widget._num_banks}")

# Read bank state
if hasattr(widget, '_bank_widgets'):
    for bank in widget._bank_widgets:
        print(f"Bank {bank.bank_id}: A={bank.alarm_vector:064b}")
```

---

## See Also

- `CHANGELOG.md` — Version history and roadmap
- `README_EN.md` — Feature overview
- Code comments in `sensor_widget.py`, `router.py`

---

**Status**: MVP ✅ | Next: Phase 2 (3-state colors)  
