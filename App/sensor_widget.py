# -*- coding: utf-8 -*-
"""
Sensor Display Widget - 4 Sensor Types with Backward Compatibility
===================================================================

Displays 4 sensor grids:
- F (AM sensors) - 32 bits
- RF (LF sensors) - 32 bits
- UART sensors (called DM in legacy interface) - 32 bits
- OBI_DMX sensors (called OBI in legacy interface) - 32 bits

Sensors that are not instantiated are shown in GRAY.
Active sensors show green (OK) or red (ALARM).

BACKWARD COMPATIBILITY:
- updateSensorData(alarm_f, alarm_rf, alarm_dm, alarm_obi) - legacy method
- update_from_data(data_dict) - new method
"""

from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QGridLayout, 
    QLabel, QFrame, QGroupBox, QSizePolicy
)
from PySide6.QtCore import Qt, Signal, Slot
from PySide6.QtGui import QColor, QPalette, QFont


class SensorLED(QFrame):
    """Single sensor LED indicator"""
    
    def __init__(self, sensor_id: int, parent=None):
        super().__init__(parent)
        self.sensor_id = sensor_id
        self._state = 'inactive'  # 'inactive', 'ok', 'alarm'
        
        self.setFixedSize(20, 20)
        self.setFrameStyle(QFrame.Box | QFrame.Plain)
        self.setLineWidth(1)
        self.setToolTip(f"Sensor {sensor_id}")
        
        self._update_color()
    
    def set_state(self, state: str):
        """Set LED state: 'inactive', 'ok', or 'alarm'"""
        if state != self._state:
            self._state = state
            self._update_color()
    
    def _update_color(self):
        if self._state == 'inactive':
            color = QColor(128, 128, 128)  # Gray
        elif self._state == 'ok':
            color = QColor(50, 200, 50)    # Green
        elif self._state == 'alarm':
            color = QColor(255, 50, 50)    # Red
        else:
            color = QColor(128, 128, 128)  # Default gray
        
        palette = self.palette()
        palette.setColor(QPalette.Window, color)
        self.setPalette(palette)
        self.setAutoFillBackground(True)


class SensorGrid(QGroupBox):
    """Grid of 32 sensor LEDs for one sensor type"""
    
    def __init__(self, title: str, sensor_type: str, parent=None):
        super().__init__(title, parent)
        self.sensor_type = sensor_type
        self._is_active = False
        self._alarm_value = 0
        
        self.leds = []
        
        layout = QGridLayout()
        layout.setSpacing(2)
        layout.setContentsMargins(5, 15, 5, 5)
        
        # Create 32 LEDs in 4x8 grid
        for i in range(32):
            row = i // 8
            col = i % 8
            led = SensorLED(i)
            self.leds.append(led)
            layout.addWidget(led, row, col)
        
        # Status label
        self._status_label = QLabel("Inactive")
        self._status_label.setAlignment(Qt.AlignCenter)
        self._status_label.setStyleSheet("color: gray; font-size: 10px;")
        layout.addWidget(self._status_label, 4, 0, 1, 8)
        
        self.setLayout(layout)
        self.setMinimumWidth(180)
        
    def set_active(self, active: bool):
        """Set whether this sensor type is instantiated"""
        self._is_active = active
        self._update_display()
    
    def set_alarm_value(self, value: int):
        """Set the 32-bit alarm register value"""
        self._alarm_value = value
        self._update_display()
    
    def _update_display(self):
        if not self._is_active:
            # All sensors gray (inactive)
            for led in self.leds:
                led.set_state('inactive')
            self._status_label.setText("Not Instantiated")
            self._status_label.setStyleSheet("color: gray; font-size: 10px;")
            self.setStyleSheet("QGroupBox { color: gray; }")
        else:
            # Show alarm states
            alarm_count = 0
            for i, led in enumerate(self.leds):
                if (self._alarm_value >> i) & 1:
                    led.set_state('alarm')
                    alarm_count += 1
                else:
                    led.set_state('ok')
            
            self._status_label.setText(f"Alarms: {alarm_count}/32")
            if alarm_count > 0:
                self._status_label.setStyleSheet("color: red; font-weight: bold; font-size: 10px;")
            else:
                self._status_label.setStyleSheet("color: green; font-size: 10px;")
            self.setStyleSheet("QGroupBox { color: black; }")


class SensorWidget(QWidget):
    """Main widget displaying all 4 sensor types"""
    
    # Signal emitted when sensor data changes
    data_changed = Signal(dict)
    
    def __init__(self, parent=None):
        super().__init__(parent)
        
        # Configuration: which sensors are instantiated
        # DEFAULT: UART and OBI_DMX active, F and RF not instantiated
        self._active_sensors = {
            'f': False,
            'rf': False,
            'uart': True,      # Called "DM" in legacy interface
            'obi_dmx': True,   # Called "OBI" in legacy interface
        }
        
        self._setup_ui()
    
    def _setup_ui(self):
        main_layout = QVBoxLayout()
        main_layout.setContentsMargins(5, 5, 5, 5)
        main_layout.setSpacing(10)
        
        # Title
        title = QLabel("Aging Sensors Status")
        title.setAlignment(Qt.AlignCenter)
        title.setFont(QFont("Arial", 12, QFont.Bold))
        main_layout.addWidget(title)
        
        # Sensor grids in 2x2 layout
        grids_layout = QGridLayout()
        grids_layout.setSpacing(10)
        
        # Create sensor grids with display names
        self._grid_f = SensorGrid("F (AM)", "f")
        self._grid_rf = SensorGrid("RF (LF)", "rf")
        self._grid_uart = SensorGrid("UART", "uart")
        self._grid_obi = SensorGrid("OBI_DMX", "obi_dmx")
        
        grids_layout.addWidget(self._grid_f, 0, 0)
        grids_layout.addWidget(self._grid_rf, 0, 1)
        grids_layout.addWidget(self._grid_uart, 1, 0)
        grids_layout.addWidget(self._grid_obi, 1, 1)
        
        main_layout.addLayout(grids_layout)
        
        # Summary label
        self._summary_label = QLabel("Total Alarms: 0")
        self._summary_label.setAlignment(Qt.AlignCenter)
        self._summary_label.setFont(QFont("Arial", 10))
        main_layout.addWidget(self._summary_label)
        
        self.setLayout(main_layout)
        
        # Apply initial active states
        self._apply_active_states()
    
    def _apply_active_states(self):
        """Apply active states to all grids"""
        self._grid_f.set_active(self._active_sensors['f'])
        self._grid_rf.set_active(self._active_sensors['rf'])
        self._grid_uart.set_active(self._active_sensors['uart'])
        self._grid_obi.set_active(self._active_sensors['obi_dmx'])
    
    def set_active_sensors(self, f: bool = False, rf: bool = False, 
                          uart: bool = True, obi_dmx: bool = True):
        """Configure which sensor types are instantiated"""
        self._active_sensors = {
            'f': f,
            'rf': rf,
            'uart': uart,
            'obi_dmx': obi_dmx,
        }
        self._apply_active_states()
    
    # =========================================================================
    # BACKWARD COMPATIBILITY: Legacy method used by main_window.py
    # =========================================================================
    def updateSensorData(self, alarm_f: int, alarm_rf: int, 
                         alarm_dm: int, alarm_obi: int):
        """
        Legacy method for backward compatibility with main_window.py
        
        Parameters:
            alarm_f: F (AM) sensor alarm register (32-bit)
            alarm_rf: RF (LF) sensor alarm register (32-bit)
            alarm_dm: UART sensor alarm register (32-bit) - legacy name "DM"
            alarm_obi: OBI_DMX sensor alarm register (32-bit) - legacy name "OBI"
        """
        # Update grid alarm values
        self._grid_f.set_alarm_value(alarm_f)
        self._grid_rf.set_alarm_value(alarm_rf)
        self._grid_uart.set_alarm_value(alarm_dm)    # DM → UART
        self._grid_obi.set_alarm_value(alarm_obi)    # OBI → OBI_DMX
        
        # Update summary
        self._update_summary(alarm_f, alarm_rf, alarm_dm, alarm_obi)
    
    def _update_summary(self, alarm_f: int, alarm_rf: int, 
                        alarm_uart: int, alarm_obi_dmx: int):
        """Update the summary label"""
        total = 0
        parts = []
        
        if self._active_sensors['f']:
            count = bin(alarm_f).count('1')
            total += count
            parts.append(f"F={count}")
        
        if self._active_sensors['rf']:
            count = bin(alarm_rf).count('1')
            total += count
            parts.append(f"RF={count}")
        
        if self._active_sensors['uart']:
            count = bin(alarm_uart).count('1')
            total += count
            parts.append(f"UART={count}")
        
        if self._active_sensors['obi_dmx']:
            count = bin(alarm_obi_dmx).count('1')
            total += count
            parts.append(f"OBI={count}")
        
        summary = f"Total Alarms: {total}"
        if parts:
            summary += f" ({', '.join(parts)})"
        
        self._summary_label.setText(summary)
        
        if total > 0:
            self._summary_label.setStyleSheet("color: red; font-weight: bold;")
        else:
            self._summary_label.setStyleSheet("color: green;")
    
    # =========================================================================
    # NEW METHOD: Dictionary-based update
    # =========================================================================
    @Slot(dict)
    def update_from_data(self, data: dict):
        """
        Update display from sensor data dictionary
        
        Expected keys:
            alarm_f, alarm_rf, alarm_uart (or alarm_dm), alarm_obi_dmx (or alarm_obi)
        """
        alarm_f = data.get('alarm_f', 0)
        alarm_rf = data.get('alarm_rf', 0)
        # Support both new and legacy naming
        alarm_uart = data.get('alarm_uart', data.get('alarm_dm', 0))
        alarm_obi_dmx = data.get('alarm_obi_dmx', data.get('alarm_obi', 0))
        
        self.updateSensorData(alarm_f, alarm_rf, alarm_uart, alarm_obi_dmx)


# Example usage and test
if __name__ == "__main__":
    import sys
    from PySide6.QtWidgets import QApplication
    
    app = QApplication(sys.argv)
    
    widget = SensorWidget()
    
    # Configure active sensors: only UART and OBI_DMX are instantiated
    widget.set_active_sensors(f=True, rf=True, uart=True, obi_dmx=True)
    
    # Test with legacy method (as main_window.py uses)
    widget.updateSensorData(
        alarm_f=0xFFF7FFF4,      # Would show if active
        alarm_rf=0x00000000,     # Would show if active
        alarm_dm=0x000075C0,     # UART - Active, shows alarms
        alarm_obi=0x0007F800     # OBI_DMX - Active, shows alarms
    )
    
    widget.show()
    
    sys.exit(app.exec())
