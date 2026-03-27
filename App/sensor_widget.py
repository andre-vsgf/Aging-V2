# -*- coding: utf-8 -*-
"""
Sensor Visualization Widget - 4 Aging Sensor Types (CORRECTED)

Provides a visual grid representation of all 4 sensor alarm registers:
- ALARM_F (AM - Accelerated Metal, 32 bits)
- ALARM_RF (LF - Low Frequency, 32 bits)
- ALARM_UART (UART sensors, 32 bits) - RENAMED from DM
- ALARM_OBI_DMX (OBI Demux sensors, 32 bits)

FIXES:
- Renamed DM to UART throughout
- Consistent naming across all layers
"""

from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QGridLayout, 
    QLabel, QFrame, QGroupBox, QSizePolicy, QScrollArea, QScrollBar
)
from PySide6.QtCore import Qt, Signal, Slot, QSize, QTimer
from PySide6.QtGui import QColor, QPainter, QBrush, QPen, QFont
from enum import Enum, auto


class SensorCellState(Enum):
    """Three-state sensor cell visual state."""
    NORMAL = auto()       # Green - no alarm or divergence
    DIVERGENCE = auto()   # Yellow - transient divergence (500ms timeout)
    ALARM = auto()        # Red - persistent alarm condition


class SensorCell(QWidget):
    """
    A single sensor indicator cell.
    Shows green when inactive (0), red when active (1), gray when disabled.
    """
    
    def __init__(self, index: int, parent=None):
        super().__init__(parent)
        self.index = index
        self.active = False
        self.enabled = True
        self.state = SensorCellState.NORMAL
        self.divergence_timeout_ms = 500
        self.divergence_timer = QTimer(self)
        self.divergence_timer.setSingleShot(True)
        self.divergence_timer.timeout.connect(self._on_divergence_timeout)
        self.setMinimumSize(20, 20)
        self.setMaximumSize(30, 30)
        self.setSizePolicy(QSizePolicy.Fixed, QSizePolicy.Fixed)
        self.setToolTip(f"Bit {index}")
    
    def setActive(self, active: bool):
        """Set the sensor state and trigger repaint."""
        if self.active != active:
            self.active = active
            self.update()
    
    def setEnabled(self, enabled: bool):
        """Set whether the sensor is enabled (gray if disabled)."""
        if self.enabled != enabled:
            self.enabled = enabled
            self.update()
    
    def setState(self, alarm: bool, divergence: bool):
        """
        Set cell state with 3-state logic.
        Priority: alarm > divergence > normal
        
        Args:
            alarm: True if persistent alarm condition
            divergence: True if transient divergence
        """
        # Stop any existing divergence timeout
        if self.divergence_timer.isActive():
            self.divergence_timer.stop()
        
        # Priority: alarm takes precedence
        if alarm:
            new_state = SensorCellState.ALARM
        elif divergence:
            new_state = SensorCellState.DIVERGENCE
            # Auto-timeout divergence back to normal after 500ms
            self.divergence_timer.start(self.divergence_timeout_ms)
        else:
            new_state = SensorCellState.NORMAL
        
        if self.state != new_state:
            self.state = new_state
            self.update()
    
    def _on_divergence_timeout(self):
        """Called when divergence timeout expires - return to normal state."""
        if self.state == SensorCellState.DIVERGENCE:
            self.state = SensorCellState.NORMAL
            self.update()
    
    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)
        
        pen = QPen(QColor(80, 80, 80))
        pen.setWidth(1)
        painter.setPen(pen)
        
        # Select color based on 3-state logic
        if not self.enabled:
            brush = QBrush(QColor(60, 60, 60))  # Dark gray - disabled
        elif self.state == SensorCellState.ALARM:
            brush = QBrush(QColor(220, 53, 69))  # Red - persistent alarm
        elif self.state == SensorCellState.DIVERGENCE:
            brush = QBrush(QColor(255, 193, 7))  # Amber/Yellow - transient divergence
        else:
            brush = QBrush(QColor(40, 167, 69))  # Green - normal
        
        painter.setBrush(brush)
        
        margin = 2
        painter.drawRoundedRect(
            margin, margin, 
            self.width() - 2*margin, 
            self.height() - 2*margin,
            3, 3
        )
        
        painter.end()


class SensorBankWidget(QWidget):
    """
    Displays a 64-bit TMR sensor bank as an 8x8 grid.
    Shows alarm_vector as red, divergence_vector as yellow.
    """
    
    def __init__(self, bank_id: int, parent=None):
        super().__init__(parent)
        self.bank_id = bank_id
        self.cells = []
        self.alarm_vector = 0
        self.divergence_vector = 0
        self._setup_ui()
    
    def _setup_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(5, 5, 5, 5)
        layout.setSpacing(5)
        
        # Header with bank title and counts
        header_layout = QHBoxLayout()
        self.title_label = QLabel(f"Bank {self.bank_id}")
        self.title_label.setAlignment(Qt.AlignLeft)
        self.title_label.setStyleSheet("font-weight: bold; font-size: 12pt;")
        header_layout.addWidget(self.title_label)
        
        self.counts_label = QLabel("Alarms: 0 | Divergence: 0")
        self.counts_label.setAlignment(Qt.AlignRight)
        self.counts_label.setStyleSheet("color: #888; font-size: 10pt;")
        header_layout.addWidget(self.counts_label)
        
        layout.addLayout(header_layout)
        
        # 8x8 grid of sensor cells (64 bits)
        grid_widget = QWidget()
        grid = QGridLayout(grid_widget)
        grid.setSpacing(1)
        grid.setContentsMargins(2, 2, 2, 2)
        
        for bit_idx in range(64):
            row = bit_idx // 8
            col = bit_idx % 8
            
            cell = SensorCell(bit_idx)
            cell.setMinimumSize(18, 18)
            cell.setMaximumSize(24, 24)
            self.cells.append(cell)
            grid.addWidget(cell, row, col)
        
        layout.addWidget(grid_widget)
    
    def setBankData(self, alarm_vector: int, divergence_vector: int):
        """Update bank with alarm and divergence vectors."""
        self.alarm_vector = alarm_vector & ((1 << 64) - 1)
        self.divergence_vector = divergence_vector & ((1 << 64) - 1)
        
        alarm_count = bin(self.alarm_vector).count('1')
        div_count = bin(self.divergence_vector).count('1')
        
        # Update counts label
        self.counts_label.setText(f"Alarms: {alarm_count} | Divergence: {div_count}")
        
        # Update cell colors: alarm=red (priority), divergence=yellow, else=green
        for i, cell in enumerate(self.cells):
            alarm = bool(self.alarm_vector & (1 << i))
            divergence = bool(self.divergence_vector & (1 << i))
            
            # Set cell 3-state: alarm (red) > divergence (yellow) > normal (green)
            cell.setState(alarm, divergence)


class SensorRegisterWidget(QWidget):
    """
    Displays a 32-bit register as an 8x4 grid of sensor cells.
    Can be set to disabled (gray) state for inactive sensors.
    """
    
    def __init__(self, title: str, enabled: bool = True, parent=None):
        super().__init__(parent)
        self.title = title
        self.cells = []
        self._value = 0
        self._enabled = enabled
        self._setup_ui()
    
    def _setup_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(5, 5, 5, 5)
        layout.setSpacing(5)
        
        # Title with value display
        self.title_label = QLabel(f"{self.title}: 0x00000000")
        self.title_label.setAlignment(Qt.AlignCenter)
        self.title_label.setStyleSheet("font-weight: bold; font-size: 11pt;")
        layout.addWidget(self.title_label)
        
        # Count display
        self.count_label = QLabel("Active: 0 / 32")
        self.count_label.setAlignment(Qt.AlignCenter)
        self.count_label.setStyleSheet("color: #888;")
        layout.addWidget(self.count_label)
        
        # Grid of sensor cells (8 columns x 4 rows = 32 bits)
        grid_widget = QWidget()
        grid = QGridLayout(grid_widget)
        grid.setSpacing(2)
        grid.setContentsMargins(5, 5, 5, 5)
        
        for i in range(32):
            row = i // 8
            col = 7 - (i % 8)
            bit_index = 31 - i
            
            cell = SensorCell(bit_index)
            cell.setEnabled(self._enabled)
            self.cells.append(cell)
            grid.addWidget(cell, row, col)
        
        self.cells = list(reversed(self.cells))
        
        layout.addWidget(grid_widget)
        
        # Bit labels row
        bit_labels = QHBoxLayout()
        for i in [31, 24, 16, 8, 0]:
            lbl = QLabel(str(i))
            lbl.setAlignment(Qt.AlignCenter)
            lbl.setStyleSheet("color: #666; font-size: 8pt;")
            bit_labels.addWidget(lbl)
            if i > 0:
                bit_labels.addStretch()
        layout.addLayout(bit_labels)
        
        if not self._enabled:
            self._apply_disabled_style()
    
    def _apply_disabled_style(self):
        """Apply gray styling for disabled state."""
        self.title_label.setStyleSheet("font-weight: bold; font-size: 11pt; color: #666;")
        self.count_label.setText("Disabled")
        self.count_label.setStyleSheet("color: #555; font-style: italic;")
    
    def setRegisterEnabled(self, enabled: bool):
        """Enable or disable the register display."""
        self._enabled = enabled
        for cell in self.cells:
            cell.setEnabled(enabled)
        
        if not enabled:
            self._apply_disabled_style()
        else:
            self.title_label.setStyleSheet("font-weight: bold; font-size: 11pt;")
            self.setValue(self._value)
    
    def setValue(self, value: int):
        """Update the register value and refresh display."""
        if not self._enabled:
            return
            
        self._value = value & 0xFFFFFFFF
        
        active_count = 0
        for i, cell in enumerate(self.cells):
            bit_active = bool(self._value & (1 << i))
            cell.setActive(bit_active)
            if bit_active:
                active_count += 1
        
        self.title_label.setText(f"{self.title}: 0x{self._value:08X}")
        self.count_label.setText(f"Active: {active_count} / 32")
        
        if active_count == 0:
            self.count_label.setStyleSheet("color: #28a745; font-weight: bold;")
        elif active_count < 8:
            self.count_label.setStyleSheet("color: #ffc107; font-weight: bold;")
        else:
            self.count_label.setStyleSheet("color: #dc3545; font-weight: bold;")
    
    def getValue(self) -> int:
        return self._value
    
    def isRegisterEnabled(self) -> bool:
        return self._enabled


class SensorVisualizationWidget(QWidget):
    """
    Main widget for sensor visualization. Supports two modes:
    
    1. LEGACY MODE (num_banks=0, default):
       - Displays 4 aging sensor registers (32-bit each) in 2x2 grid
       - Sensors: ALARM_F, ALARM_RF, ALARM_UART, ALARM_OBI_DMX
    
    2. MULTI-BANK MODE (num_banks > 0):
       - Displays N banks of 64-bit TMR sensors
       - Each bank renders as 8x8 grid in scrollable view
       - Example: num_banks=2 creates 2 independent 8x8 grids
    """
    
    data_updated = Signal(dict)  # Emits complete sensor data
    
    def __init__(self, parent=None, num_banks: int = 0):
        """
        Initialize sensor visualization widget.
        
        Args:
            parent: Parent widget
            num_banks: Number of 64-bit banks to display (0 = legacy 4-register mode)
        """
        super().__init__(parent)
        self._num_banks = num_banks
        self._legacy_mode = (num_banks == 0)
        
        if self._legacy_mode:
            # Legacy: 4 registers in 2x2 grid
            self._setup_ui()
        else:
            # Multi-bank: scrollable N banks of 8x8 grids
            self.setupMultiBankDisplay(num_banks)
    
    def _setup_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(10, 10, 10, 10)
        
        # Main title
        title = QLabel("Aging Sensor Status - All 4 Sensor Types")
        title.setAlignment(Qt.AlignCenter)
        title.setStyleSheet("font-size: 14pt; font-weight: bold; margin-bottom: 10px;")
        layout.addWidget(title)
        
        # Four register displays in 2x2 grid
        registers_grid = QGridLayout()
        registers_grid.setSpacing(10)
        
        # Row 1: Primary sensors (always active)
        self.alarm_f_widget = SensorRegisterWidget("ALARM_F (AM Sensor)", enabled=True)
        registers_grid.addWidget(self.alarm_f_widget, 0, 0)
        
        self.alarm_rf_widget = SensorRegisterWidget("ALARM_RF (LF Sensor)", enabled=True)
        registers_grid.addWidget(self.alarm_rf_widget, 0, 1)
        
        # Row 2: Secondary sensors - RENAMED DM to UART
        self.alarm_uart_widget = SensorRegisterWidget("ALARM_UART (UART Sensor)", enabled=True)
        registers_grid.addWidget(self.alarm_uart_widget, 1, 0)
        
        self.alarm_obi_widget = SensorRegisterWidget("ALARM_OBI_DMX (OBI Demux)", enabled=True)
        registers_grid.addWidget(self.alarm_obi_widget, 1, 1)
        
        layout.addLayout(registers_grid)
        
        # Summary bar
        summary_layout = QHBoxLayout()
        
        self.total_label = QLabel("Total Active Alarms: 0 / 128")
        self.total_label.setAlignment(Qt.AlignCenter)
        self.total_label.setStyleSheet("""
            font-size: 12pt; 
            font-weight: bold; 
            padding: 10px;
            background-color: #1e1e1e;
            border-radius: 5px;
        """)
        summary_layout.addWidget(self.total_label)
        
        self.status_indicator = QLabel("● NOMINAL")
        self.status_indicator.setAlignment(Qt.AlignCenter)
        self.status_indicator.setStyleSheet("""
            font-size: 12pt;
            font-weight: bold;
            color: #28a745;
            padding: 10px;
            background-color: #1e1e1e;
            border-radius: 5px;
        """)
        summary_layout.addWidget(self.status_indicator)
        
        layout.addLayout(summary_layout)
    
    @Slot(dict)
    def updateFromDict(self, data: dict):
        """
        Update all sensor registers from a dictionary (legacy mode only).
        
        Accepts BOTH naming conventions:
        - New names: alarm_uart, alarm_obi_dmx
        - Old names: alarm_dm, alarm_obi (for backwards compatibility)
        
        In multi-bank mode, use updateMultiBankData() instead.
        """
        if not self._legacy_mode:
            return
        
        alarm_f = data.get('alarm_f', 0)
        alarm_rf = data.get('alarm_rf', 0)
        
        # Accept both naming conventions for UART sensor
        alarm_uart = data.get('alarm_uart', data.get('alarm_dm', 0))
        
        # Accept both naming conventions for OBI_DMX sensor
        alarm_obi = data.get('alarm_obi_dmx', data.get('alarm_obi', 0))
        
        self.updateSensorData(alarm_f, alarm_rf, alarm_uart, alarm_obi)
    
    def updateSensorData(self, alarm_f: int, alarm_rf: int, 
                         alarm_uart: int = 0, alarm_obi: int = 0):
        """Update all sensor registers with new values."""
        # Only works in legacy mode
        if not self._legacy_mode:
            return
        
        # Update primary sensors
        self.alarm_f_widget.setValue(alarm_f)
        self.alarm_rf_widget.setValue(alarm_rf)
        
        # Update secondary sensors
        self.alarm_uart_widget.setValue(alarm_uart)
        self.alarm_obi_widget.setValue(alarm_obi)
        
        # Calculate totals from all active sensors
        counts = []
        total_bits = 0
        
        if self.alarm_f_widget.isRegisterEnabled():
            f_count = bin(alarm_f).count('1')
            counts.append(f_count)
            total_bits += 32
            
        if self.alarm_rf_widget.isRegisterEnabled():
            rf_count = bin(alarm_rf).count('1')
            counts.append(rf_count)
            total_bits += 32
            
        if self.alarm_uart_widget.isRegisterEnabled():
            uart_count = bin(alarm_uart).count('1')
            counts.append(uart_count)
            total_bits += 32
            
        if self.alarm_obi_widget.isRegisterEnabled():
            obi_count = bin(alarm_obi).count('1')
            counts.append(obi_count)
            total_bits += 32
        
        total = sum(counts)
        
        self.total_label.setText(f"Total Active Alarms: {total} / {total_bits}")
        
        # Update status indicator based on percentage
        if total_bits > 0:
            alarm_pct = (total / total_bits) * 100
            
            if alarm_pct == 0:
                self.status_indicator.setText("● NOMINAL")
                self.status_indicator.setStyleSheet("""
                    font-size: 12pt; font-weight: bold; color: #28a745;
                    padding: 10px; background-color: #1e1e1e; border-radius: 5px;
                """)
            elif alarm_pct < 25:
                self.status_indicator.setText("● WARNING")
                self.status_indicator.setStyleSheet("""
                    font-size: 12pt; font-weight: bold; color: #ffc107;
                    padding: 10px; background-color: #1e1e1e; border-radius: 5px;
                """)
            else:
                self.status_indicator.setText("● CRITICAL")
                self.status_indicator.setStyleSheet("""
                    font-size: 12pt; font-weight: bold; color: #dc3545;
                    padding: 10px; background-color: #1e1e1e; border-radius: 5px;
                """)
        
        # Emit complete data (with BOTH naming conventions for compatibility)
        sensor_data = {
            'alarm_f': alarm_f,
            'alarm_rf': alarm_rf,
            'alarm_uart': alarm_uart,
            'alarm_obi_dmx': alarm_obi,
            # Legacy names for backwards compatibility
            'alarm_dm': alarm_uart,
            'alarm_obi': alarm_obi,
            # Counts
            'alarm_f_count': bin(alarm_f).count('1'),
            'alarm_rf_count': bin(alarm_rf).count('1'),
            'alarm_uart_count': bin(alarm_uart).count('1'),
            'alarm_obi_count': bin(alarm_obi).count('1'),
            'total_alarms': total,
            'total_bits': total_bits
        }
        self.data_updated.emit(sensor_data)
    
    def enableSensor(self, sensor_name: str, enabled: bool):
        """
        Enable/disable a specific sensor register (legacy mode only).
        Has no effect in multi-bank mode.
        
        Args:
            sensor_name: "uart", "obi_dmx", "f", or "rf"
            enabled: True to enable, False to disable (gray out)
        """
        if not self._legacy_mode:
            return
        
        name = sensor_name.lower()
        
        if name in ["uart", "alarm_uart", "dm", "alarm_dm"]:
            self.alarm_uart_widget.setRegisterEnabled(enabled)
        elif name in ["obi", "obi_dmx", "alarm_obi_dmx", "alarm_obi"]:
            self.alarm_obi_widget.setRegisterEnabled(enabled)
        elif name in ["f", "alarm_f"]:
            self.alarm_f_widget.setRegisterEnabled(enabled)
        elif name in ["rf", "alarm_rf"]:
            self.alarm_rf_widget.setRegisterEnabled(enabled)
    
    def getAlarmCounts(self) -> dict:
        """Return current alarm counts (legacy mode only). Returns empty dict in multi-bank mode."""
        if not self._legacy_mode:
            return {}
        
        return {
            'f': bin(self.alarm_f_widget.getValue()).count('1'),
            'rf': bin(self.alarm_rf_widget.getValue()).count('1'),
            'uart': bin(self.alarm_uart_widget.getValue()).count('1'),
            'obi_dmx': bin(self.alarm_obi_widget.getValue()).count('1'),
        }
    
    def setupMultiBankDisplay(self, num_banks: int = 2):
        """
        Setup scrollable multi-bank display.
        Called once during initialization if using multi-bank mode.
        """
        # Clear existing layout if this is a re-setup
        if hasattr(self, '_bank_widgets'):
            for i, widget in enumerate(self._bank_widgets):
                widget.deleteLater()
        
        # Create scrollable area for banks
        scroll_area = QScrollArea()
        scroll_area.setWidgetResizable(True)
        scroll_area.setHorizontalScrollBarPolicy(Qt.ScrollBarAsNeeded)
        scroll_area.setVerticalScrollBarPolicy(Qt.ScrollBarAsNeeded)
        
        # Container for all bank widgets
        container = QWidget()
        container_layout = QVBoxLayout(container)
        container_layout.setContentsMargins(5, 5, 5, 5)
        container_layout.setSpacing(10)
        
        # Create bank widgets
        self._bank_widgets = []
        for bank_id in range(num_banks):
            bank_widget = SensorBankWidget(bank_id=bank_id)
            self._bank_widgets.append(bank_widget)
            container_layout.addWidget(bank_widget)
        
        container_layout.addStretch()
        scroll_area.setWidget(container)
        
        # Replace the main layout with the scrollable view
        old_layout = self.layout()
        if old_layout:
            for i in reversed(range(old_layout.count())):
                old_layout.itemAt(i).widget().deleteLater()
        
        new_layout = QVBoxLayout(self)
        new_layout.setContentsMargins(10, 10, 10, 10)
        
        title = QLabel("Multi-Bank TMR Sensor Status")
        title.setAlignment(Qt.AlignCenter)
        title.setStyleSheet("font-size: 14pt; font-weight: bold; margin-bottom: 10px;")
        new_layout.addWidget(title)
        
        new_layout.addWidget(scroll_area)
        
        # Store banks for later reference
        self._num_banks = num_banks
    
    @Slot(list)
    def updateMultiBankData(self, banks_data: list):
        """
        Update multi-bank display from list of bank dicts.
        Expects list of dicts like: [{'alarm_vector': int, 'divergence_vector': int}, ...]
        """
        if not hasattr(self, '_bank_widgets'):
            # Initialize multi-bank display if not already done
            self.setupMultiBankDisplay(len(banks_data))
        
        for i, bank_dict in enumerate(banks_data):
            if i < len(self._bank_widgets):
                alarm_vector = bank_dict.get('alarm_vector', 0)
                divergence_vector = bank_dict.get('divergence_vector', 0)
                self._bank_widgets[i].setBankData(alarm_vector, divergence_vector)