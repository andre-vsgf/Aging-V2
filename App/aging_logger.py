# -*- coding: utf-8 -*-
"""
Aging Event Logger - 4 SENSOR VERSION

Records sensor alarm events with associated metadata for later analysis:
- Timestamp of alarm activation
- Which sensors triggered (ALL 4 TYPES: F, RF, UART, OBI_DMX)
- Current bitstream and its calibration (slack value)
- Environmental data (temperature, voltage)
- Calculated radiation dose based on experiment timeline

Output format is designed for easy import into analysis tools (CSV, pandas).

UPDATED: Now supports 4 sensor types instead of 2:
- ALARM_F (AM sensors)
- ALARM_RF (LF sensors)
- ALARM_UART (UART sensors)
- ALARM_OBI_DMX (OBI Demux sensors)
"""

import csv
import json
import os
from datetime import datetime
from dataclasses import dataclass, asdict, field
from typing import List, Optional, Dict, Any, Union
from PySide6.QtCore import QObject, Signal


@dataclass
class AgingEvent:
    """
    A single aging/alarm event record.
    
    UPDATED: Now includes all 4 sensor types.
    """
    
    # Timing
    timestamp: Union[datetime, str]
    experiment_time_hours: float
    
    # Radiation (calculated from time)
    radiation_dose_krad: float
    
    # Sensor data - ALL 4 TYPES
    alarm_f: int                      # ALARM_F register value (32-bit)
    alarm_rf: int                     # ALARM_RF register value (32-bit)
    alarm_uart: int = 0               # ALARM_UART register value (32-bit) - NEW
    alarm_obi_dmx: int = 0            # ALARM_OBI_DMX register value (32-bit) - NEW
    
    triggered_sensors_f: List[int] = field(default_factory=list)
    triggered_sensors_rf: List[int] = field(default_factory=list)
    triggered_sensors_uart: List[int] = field(default_factory=list)      # NEW
    triggered_sensors_obi_dmx: List[int] = field(default_factory=list)   # NEW
    
    # Bitstream/Calibration
    bitstream_name: str = ""
    phase_degrees: float = 0.0
    slack_ns: float = 0.0
    
    # Environmental
    fpga_temp_c: float = 0.0
    vccint_v: float = 0.0
    vcore_v: float = 0.0
    ambient_temp_c: float = 0.0
    
    # Additional metadata
    notes: str = ""
    event_type: str = "alarm"
    
    def __post_init__(self):
        # Ensure timestamp is a datetime object if it came as a string
        if isinstance(self.timestamp, str):
            try:
                self.timestamp = datetime.fromisoformat(self.timestamp)
            except ValueError:
                pass
        
        # Ensure lists are actual lists (not None)
        if self.triggered_sensors_f is None:
            self.triggered_sensors_f = []
        if self.triggered_sensors_rf is None:
            self.triggered_sensors_rf = []
        if self.triggered_sensors_uart is None:
            self.triggered_sensors_uart = []
        if self.triggered_sensors_obi_dmx is None:
            self.triggered_sensors_obi_dmx = []

    def to_dict(self) -> dict:
        d = asdict(self)
        if isinstance(self.timestamp, datetime):
            d['timestamp'] = self.timestamp.isoformat()
        return d
    
    @classmethod
    def from_dict(cls, data: dict) -> 'AgingEvent':
        # Handle backwards compatibility - old logs might not have UART/OBI fields
        if 'alarm_uart' not in data:
            data['alarm_uart'] = 0
        if 'alarm_obi_dmx' not in data:
            data['alarm_obi_dmx'] = 0
        if 'triggered_sensors_uart' not in data:
            data['triggered_sensors_uart'] = []
        if 'triggered_sensors_obi_dmx' not in data:
            data['triggered_sensors_obi_dmx'] = []
        return cls(**data)
    
    def to_csv_row(self) -> List[Any]:
        """Convert to flat CSV row - UPDATED for 4 sensors."""
        ts_str = self.timestamp.isoformat() if isinstance(self.timestamp, datetime) else str(self.timestamp)
        return [
            ts_str,
            self.experiment_time_hours,
            self.radiation_dose_krad,
            # F sensors
            f"0x{self.alarm_f:08X}",
            len(self.triggered_sensors_f),
            ','.join(map(str, self.triggered_sensors_f)),
            # RF sensors
            f"0x{self.alarm_rf:08X}",
            len(self.triggered_sensors_rf),
            ','.join(map(str, self.triggered_sensors_rf)),
            # UART sensors (NEW)
            f"0x{self.alarm_uart:08X}",
            len(self.triggered_sensors_uart),
            ','.join(map(str, self.triggered_sensors_uart)),
            # OBI_DMX sensors (NEW)
            f"0x{self.alarm_obi_dmx:08X}",
            len(self.triggered_sensors_obi_dmx),
            ','.join(map(str, self.triggered_sensors_obi_dmx)),
            # Total
            self.total_triggered_count,
            # Calibration
            self.bitstream_name,
            self.phase_degrees,
            self.slack_ns,
            # Environmental
            self.fpga_temp_c,
            self.vccint_v,
            self.vcore_v,
            self.ambient_temp_c,
            # Metadata
            self.event_type,
            self.notes
        ]
    
    @property
    def total_triggered_count(self) -> int:
        """Total number of triggered sensors across all 4 types."""
        return (len(self.triggered_sensors_f) + 
                len(self.triggered_sensors_rf) +
                len(self.triggered_sensors_uart) +
                len(self.triggered_sensors_obi_dmx))
    
    @staticmethod
    def csv_header() -> List[str]:
        """CSV header - UPDATED for 4 sensors."""
        return [
            'timestamp',
            'experiment_time_hours',
            'radiation_dose_krad',
            # F sensors
            'alarm_f_hex',
            'triggered_count_f',
            'triggered_bits_f',
            # RF sensors
            'alarm_rf_hex',
            'triggered_count_rf',
            'triggered_bits_rf',
            # UART sensors (NEW)
            'alarm_uart_hex',
            'triggered_count_uart',
            'triggered_bits_uart',
            # OBI_DMX sensors (NEW)
            'alarm_obi_dmx_hex',
            'triggered_count_obi_dmx',
            'triggered_bits_obi_dmx',
            # Total
            'total_triggered_count',
            # Calibration
            'bitstream_name',
            'phase_degrees',
            'slack_ns',
            # Environmental
            'fpga_temp_c',
            'vccint_v',
            'vcore_v',
            'ambient_temp_c',
            # Metadata
            'event_type',
            'notes'
        ]


class RadiationModel:
    """
    Model for calculating radiation dose based on experiment time.
    
    Assumes a linear relationship: dose = rate * time
    Can be configured for different radiation sources/facilities.
    """
    
    def __init__(self):
        self.dose_rate_krad_per_hour: float = 1.0
        self.experiment_start: Optional[datetime] = None
        self.initial_dose_krad: float = 0.0
    
    def set_dose_rate(self, krad_per_hour: float):
        """Set the dose rate in krad/hour."""
        self.dose_rate_krad_per_hour = krad_per_hour
    
    def start_experiment(self, initial_dose: float = 0.0):
        """Mark the experiment start time."""
        self.experiment_start = datetime.now()
        self.initial_dose_krad = initial_dose
    
    def get_experiment_hours(self, timestamp: datetime = None) -> float:
        """Get hours elapsed since experiment start."""
        if self.experiment_start is None:
            return 0.0
        
        timestamp = timestamp or datetime.now()
        delta = timestamp - self.experiment_start
        return delta.total_seconds() / 3600.0
    
    def get_dose(self, timestamp: datetime = None) -> float:
        """Calculate accumulated dose at given time."""
        hours = self.get_experiment_hours(timestamp)
        return self.initial_dose_krad + (hours * self.dose_rate_krad_per_hour)
    
    def to_dict(self) -> dict:
        return {
            'dose_rate_krad_per_hour': self.dose_rate_krad_per_hour,
            'experiment_start': self.experiment_start.isoformat() if self.experiment_start else None,
            'initial_dose_krad': self.initial_dose_krad
        }
    
    def from_dict(self, data: dict):
        self.dose_rate_krad_per_hour = data.get('dose_rate_krad_per_hour', 1.0)
        start_str = data.get('experiment_start')
        if start_str:
            self.experiment_start = datetime.fromisoformat(start_str)
        self.initial_dose_krad = data.get('initial_dose_krad', 0.0)


class AgingLogger(QObject):
    """
    Main logging class for aging experiment data - 4 SENSOR VERSION.
    
    Features:
    - Records alarm events with full context for ALL 4 sensor types
    - Calculates radiation dose from experiment time
    - Exports to CSV and JSON formats
    - Tracks which sensors have triggered over the experiment
    """
    
    # Signals
    event_logged = Signal(object)  # AgingEvent
    
    def __init__(self, parent=None):
        super().__init__(parent)
        
        self.events: List[AgingEvent] = []
        self.radiation_model = RadiationModel()
        
        # Track sensors that have triggered - ALL 4 TYPES
        self._triggered_history_f: set = set()
        self._triggered_history_rf: set = set()
        self._triggered_history_uart: set = set()       # NEW
        self._triggered_history_obi_dmx: set = set()    # NEW
        
        # Previous alarm state (for detecting new triggers)
        self._prev_alarm_f: int = 0
        self._prev_alarm_rf: int = 0
        self._prev_alarm_uart: int = 0       # NEW
        self._prev_alarm_obi_dmx: int = 0    # NEW
        
        # Current context (updated by main app)
        self._current_bitstream: str = ""
        self._current_phase: float = 0.0
        self._current_slack: float = 0.0
        self._current_fpga_temp: float = 0.0
        self._current_vccint: float = 0.0
        self._current_vcore: float = 0.0
        self._current_ambient_temp: float = 0.0
        
        # Auto-save settings
        self._log_file = "aging_log.json"
        self._csv_file = "aging_log.csv"
    
    def get_all_events(self) -> List[AgingEvent]:
        """Returns the list of all logged events."""
        return self.events

    def set_current_bitstream(self, name: str, phase_degrees: float, slack_ns: float):
        """Update current bitstream context."""
        self._current_bitstream = name
        self._current_phase = phase_degrees
        self._current_slack = slack_ns
    
    def set_environmental_data(self, fpga_temp: float = None, vccint: float = None,
                                vcore: float = None, ambient_temp: float = None):
        """Update environmental readings."""
        if fpga_temp is not None:
            self._current_fpga_temp = fpga_temp
        if vccint is not None:
            self._current_vccint = vccint
        if vcore is not None:
            self._current_vcore = vcore
        if ambient_temp is not None:
            self._current_ambient_temp = ambient_temp
    
    def check_and_log_alarms(self, alarm_f: int, alarm_rf: int,
                              alarm_uart: int = 0, alarm_obi_dmx: int = 0) -> Optional[AgingEvent]:
        """
        Check for new alarm triggers and log if any detected.
        
        UPDATED: Now supports all 4 sensor types.
        
        Returns:
            AgingEvent if new alarms detected, None otherwise
        """
        # Find newly triggered bits for ALL 4 types
        new_f = alarm_f & ~self._prev_alarm_f
        new_rf = alarm_rf & ~self._prev_alarm_rf
        new_uart = alarm_uart & ~self._prev_alarm_uart
        new_obi_dmx = alarm_obi_dmx & ~self._prev_alarm_obi_dmx
        
        # Update previous state
        self._prev_alarm_f = alarm_f
        self._prev_alarm_rf = alarm_rf
        self._prev_alarm_uart = alarm_uart
        self._prev_alarm_obi_dmx = alarm_obi_dmx
        
        # If any new triggers, log the event
        if new_f or new_rf or new_uart or new_obi_dmx:
            return self.log_event(
                alarm_f, alarm_rf, alarm_uart, alarm_obi_dmx,
                new_f, new_rf, new_uart, new_obi_dmx
            )
        
        return None
    
    def log_event(self, alarm_f: int, alarm_rf: int,
                  alarm_uart: int = 0, alarm_obi_dmx: int = 0,
                  triggered_f: int = None, triggered_rf: int = None,
                  triggered_uart: int = None, triggered_obi_dmx: int = None,
                  event_type: str = "alarm", notes: str = "") -> AgingEvent:
        """
        Log an aging event.
        
        UPDATED: Now supports all 4 sensor types.
        
        Args:
            alarm_f: Current ALARM_F register value
            alarm_rf: Current ALARM_RF register value
            alarm_uart: Current ALARM_UART register value (NEW)
            alarm_obi_dmx: Current ALARM_OBI_DMX register value (NEW)
            triggered_f/rf/uart/obi_dmx: Bits that triggered (if None, uses all active bits)
            event_type: Type of event ("alarm", "bitstream_change", "manual")
            notes: Optional notes
        
        Returns:
            The logged AgingEvent
        """
        now = datetime.now()
        
        # Determine which bits triggered
        if triggered_f is None:
            triggered_f = alarm_f
        if triggered_rf is None:
            triggered_rf = alarm_rf
        if triggered_uart is None:
            triggered_uart = alarm_uart
        if triggered_obi_dmx is None:
            triggered_obi_dmx = alarm_obi_dmx
        
        # Extract triggered bit indices for ALL 4 types
        triggered_sensors_f = [i for i in range(32) if triggered_f & (1 << i)]
        triggered_sensors_rf = [i for i in range(32) if triggered_rf & (1 << i)]
        triggered_sensors_uart = [i for i in range(32) if triggered_uart & (1 << i)]
        triggered_sensors_obi_dmx = [i for i in range(32) if triggered_obi_dmx & (1 << i)]
        
        # Update history
        self._triggered_history_f.update(triggered_sensors_f)
        self._triggered_history_rf.update(triggered_sensors_rf)
        self._triggered_history_uart.update(triggered_sensors_uart)
        self._triggered_history_obi_dmx.update(triggered_sensors_obi_dmx)
        
        # Create event
        event = AgingEvent(
            timestamp=now,
            experiment_time_hours=self.radiation_model.get_experiment_hours(now),
            radiation_dose_krad=self.radiation_model.get_dose(now),
            alarm_f=alarm_f,
            alarm_rf=alarm_rf,
            alarm_uart=alarm_uart,
            alarm_obi_dmx=alarm_obi_dmx,
            triggered_sensors_f=triggered_sensors_f,
            triggered_sensors_rf=triggered_sensors_rf,
            triggered_sensors_uart=triggered_sensors_uart,
            triggered_sensors_obi_dmx=triggered_sensors_obi_dmx,
            bitstream_name=self._current_bitstream,
            phase_degrees=self._current_phase,
            slack_ns=self._current_slack,
            fpga_temp_c=self._current_fpga_temp,
            vccint_v=self._current_vccint,
            vcore_v=self._current_vcore,
            ambient_temp_c=self._current_ambient_temp,
            event_type=event_type,
            notes=notes
        )
        
        self.events.append(event)
        self.event_logged.emit(event)
        
        return event
    
    def log_bitstream_change(self, old_bitstream: str, new_bitstream: str,
                              new_phase: float, new_slack: float) -> AgingEvent:
        """Log a bitstream change event."""
        self.set_current_bitstream(new_bitstream, new_phase, new_slack)
        
        return self.log_event(
            alarm_f=self._prev_alarm_f,
            alarm_rf=self._prev_alarm_rf,
            alarm_uart=self._prev_alarm_uart,
            alarm_obi_dmx=self._prev_alarm_obi_dmx,
            triggered_f=0,
            triggered_rf=0,
            triggered_uart=0,
            triggered_obi_dmx=0,
            event_type="bitstream_change",
            notes=f"Changed from {old_bitstream} to {new_bitstream}"
        )
    
    def get_triggered_history(self) -> Dict[str, set]:
        """Get all sensors that have triggered during experiment - ALL 4 TYPES."""
        return {
            'alarm_f': self._triggered_history_f.copy(),
            'alarm_rf': self._triggered_history_rf.copy(),
            'alarm_uart': self._triggered_history_uart.copy(),
            'alarm_obi_dmx': self._triggered_history_obi_dmx.copy()
        }
    
    def get_events_for_analysis(self) -> List[Dict]:
        """Get events in a format suitable for analysis."""
        return [e.to_dict() for e in self.events]
    
    def get_slack_vs_dose_data(self) -> List[Dict]:
        """
        Get data for slack vs radiation dose plot.
        
        UPDATED: Total now includes all 4 sensor types.
        """
        data = []
        for event in self.events:
            if event.event_type == "alarm":
                ts = event.timestamp.isoformat() if isinstance(event.timestamp, datetime) else str(event.timestamp)
                data.append({
                    'dose_krad': event.radiation_dose_krad,
                    'slack_ns': event.slack_ns,
                    'phase_degrees': event.phase_degrees,
                    'sensors_triggered': event.total_triggered_count,
                    'timestamp': ts
                })
        return data
    
    def get_alarm_summary(self) -> Dict[str, Any]:
        """
        Get a summary of alarm activity - NEW METHOD.
        
        Returns:
            Dict with counts and lists of triggered sensors for each type
        """
        return {
            'f': {
                'total_ever_triggered': len(self._triggered_history_f),
                'current_active': bin(self._prev_alarm_f).count('1'),
                'triggered_bits': sorted(self._triggered_history_f)
            },
            'rf': {
                'total_ever_triggered': len(self._triggered_history_rf),
                'current_active': bin(self._prev_alarm_rf).count('1'),
                'triggered_bits': sorted(self._triggered_history_rf)
            },
            'uart': {
                'total_ever_triggered': len(self._triggered_history_uart),
                'current_active': bin(self._prev_alarm_uart).count('1'),
                'triggered_bits': sorted(self._triggered_history_uart)
            },
            'obi_dmx': {
                'total_ever_triggered': len(self._triggered_history_obi_dmx),
                'current_active': bin(self._prev_alarm_obi_dmx).count('1'),
                'triggered_bits': sorted(self._triggered_history_obi_dmx)
            }
        }
    
    def save_json(self, filepath: str = None):
        """Save log to JSON file - UPDATED for 4 sensors."""
        filepath = filepath or self._log_file
        
        data = {
            'radiation_model': self.radiation_model.to_dict(),
            'events': [e.to_dict() for e in self.events],
            'triggered_history': {
                'alarm_f': list(self._triggered_history_f),
                'alarm_rf': list(self._triggered_history_rf),
                'alarm_uart': list(self._triggered_history_uart),
                'alarm_obi_dmx': list(self._triggered_history_obi_dmx)
            }
        }
        
        with open(filepath, 'w', encoding='utf-8') as f:
            json.dump(data, f, indent=2)
    
    def save_csv(self, filepath: str = None):
        """Save log to CSV file."""
        filepath = filepath or self._csv_file
        
        with open(filepath, 'w', newline='', encoding='utf-8') as f:
            writer = csv.writer(f)
            writer.writerow(AgingEvent.csv_header())
            for event in self.events:
                writer.writerow(event.to_csv_row())
    
    def load_json(self, filepath: str = None) -> bool:
        """Load log from JSON file - UPDATED for backwards compatibility."""
        filepath = filepath or self._log_file
        
        if not os.path.exists(filepath):
            return False
        
        try:
            with open(filepath, 'r', encoding='utf-8') as f:
                data = json.load(f)
            
            self.radiation_model.from_dict(data.get('radiation_model', {}))
            
            self.events.clear()
            for event_data in data.get('events', []):
                self.events.append(AgingEvent.from_dict(event_data))
            
            history = data.get('triggered_history', {})
            self._triggered_history_f = set(history.get('alarm_f', []))
            self._triggered_history_rf = set(history.get('alarm_rf', []))
            # Handle old logs that don't have UART/OBI_DMX
            self._triggered_history_uart = set(history.get('alarm_uart', []))
            self._triggered_history_obi_dmx = set(history.get('alarm_obi_dmx', []))
            
            return True
            
        except Exception as e:
            print(f"Error loading log: {e}")
            return False
    
    def clear(self):
        """Clear all logged events - ALL 4 TYPES."""
        self.events.clear()
        self._triggered_history_f.clear()
        self._triggered_history_rf.clear()
        self._triggered_history_uart.clear()
        self._triggered_history_obi_dmx.clear()
        self._prev_alarm_f = 0
        self._prev_alarm_rf = 0
        self._prev_alarm_uart = 0
        self._prev_alarm_obi_dmx = 0