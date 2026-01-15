# -*- coding: utf-8 -*-
"""
Sensor Visualization Widget - 4 Aging Sensor Types

Provides a visual grid representation of all 4 sensor alarm registers:
- ALARM_F (AM - Accelerated Metal, 32 bits)
- ALARM_RF (LF - Low Frequency, 32 bits)
- ALARM_DM (Debug Module sensors, 32 bits)
- ALARM_OBI_DMX (OBI Demux sensors, variable width displayed as 32 bits)
"""

from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QGridLayout, 
    QLabel, QFrame, QGroupBox, QSizePolicy
)
from PySide6.QtCore import Qt, Signal, Slot, QSize
from PySide6.QtGui import QColor, QPainter, QBrush, QPen, QFont


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
    
    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)
        
        pen = QPen(QColor(80, 80, 80))
        pen.setWidth(1)
        painter.setPen(pen)
        
        if not self.enabled:
            brush = QBrush(QColor(60, 60, 60))  # Dark gray
        elif self.active:
            brush = QBrush(QColor(220, 53, 69))  # Red
        else:
            brush = QBrush(QColor(40, 167, 69))  # Green
        
        painter.setBrush(brush)
        
        margin = 2
        painter.drawRoundedRect(
            margin, margin, 
            self.width() - 2*margin, 
            self.height() - 2*margin,
            3, 3
        )
        
        painter.end()


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
    Main widget displaying all 4 aging sensor registers:
    - ALARM_F (AM sensors)
    - ALARM_RF (LF sensors) 
    - ALARM_DM (Debug Module sensors)
    - ALARM_OBI_DMX (OBI Demux sensors)
    """
    
    data_updated = Signal(dict)  # Emits complete sensor data
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self._setup_ui()
    
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
        
        # Row 2: Secondary sensors (configurable)
        self.alarm_dm_widget = SensorRegisterWidget("ALARM_DM (Debug Module)", enabled=True)
        registers_grid.addWidget(self.alarm_dm_widget, 1, 0)
        
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
        Update all sensor registers from a dictionary.
        
        Expected keys:
            - alarm_f: int (32-bit)
            - alarm_rf: int (32-bit)
            - alarm_dm: int (32-bit, optional)
            - alarm_obi_dmx: int (32-bit, optional)
        """
        alarm_f = data.get('alarm_f', 0)
        alarm_rf = data.get('alarm_rf', 0)
        alarm_dm = data.get('alarm_dm', data.get('obi_dmx', 0))  # Fallback for old naming
        alarm_obi = data.get('alarm_obi_dmx', data.get('uart_alarm', 0))
        
        self.updateSensorData(alarm_f, alarm_rf, alarm_dm, alarm_obi)
    
    def updateSensorData(self, alarm_f: int, alarm_rf: int, alarm_dm: int = 0, alarm_obi: int = 0):
        """Update all sensor registers with new values."""
        # Update primary sensors
        self.alarm_f_widget.setValue(alarm_f)
        self.alarm_rf_widget.setValue(alarm_rf)
        
        # Update secondary sensors
        self.alarm_dm_widget.setValue(alarm_dm)
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
            
        if self.alarm_dm_widget.isRegisterEnabled():
            dm_count = bin(alarm_dm).count('1')
            counts.append(dm_count)
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
        
        # Emit complete data
        sensor_data = {
            'alarm_f': alarm_f,
            'alarm_rf': alarm_rf,
            'alarm_dm': alarm_dm,
            'alarm_obi_dmx': alarm_obi,
            'alarm_f_count': bin(alarm_f).count('1'),
            'alarm_rf_count': bin(alarm_rf).count('1'),
            'alarm_dm_count': bin(alarm_dm).count('1'),
            'alarm_obi_count': bin(alarm_obi).count('1'),
            'total_alarms': total,
            'total_bits': total_bits
        }
        self.data_updated.emit(sensor_data)
    
    def enableSensor(self, sensor_name: str, enabled: bool):
        """
        Enable/disable a specific sensor register.
        
        Args:
            sensor_name: "dm" or "obi_dmx"
            enabled: True to enable, False to disable (gray out)
        """
        if sensor_name.lower() in ["dm", "alarm_dm"]:
            self.alarm_dm_widget.setRegisterEnabled(enabled)
        elif sensor_name.lower() in ["obi", "obi_dmx", "alarm_obi_dmx"]:
            self.alarm_obi_widget.setRegisterEnabled(enabled)
