# -*- coding: utf-8 -*-
"""
History Logger - 4 SENSOR VERSION

Records events for long-duration experiments (24h+ burn-in tests).
Logs programming events, alarms, and system status to a persistent file.

UPDATED: Now supports all 4 sensor types:
- ALARM_F (AM sensors)
- ALARM_RF (LF sensors)
- ALARM_UART (UART sensors)
- ALARM_OBI_DMX (OBI Demux sensors)
"""

import os
from datetime import datetime
from pathlib import Path
from typing import Optional, Dict, Any


class HistoryLogger:
    """
    Persistent event logger for experiment tracking - 4 SENSOR VERSION.
    
    Events are appended to a text file with timestamps.
    Useful for post-analysis of burn-in experiments.
    """
    
    def __init__(self, filename: str = None):
        """
        Initialize the logger.
        
        Args:
            filename: Log file path. Defaults to 'experiment_history.txt'
                     in the current directory.
        """
        if filename is None:
            filename = "experiment_history.txt"
        
        self.filename = filename
        self._ensure_directory()

    def _ensure_directory(self):
        """Create log directory if it doesn't exist."""
        log_dir = Path(self.filename).parent
        if log_dir and not log_dir.exists():
            log_dir.mkdir(parents=True, exist_ok=True)

    def log_event(self, event_type: str, details: str = "", 
                  bitstream: str = "", extra: dict = None):
        """
        Log an event to the history file.
        
        Args:
            event_type: Type of event (e.g., 'TRIGGER', 'PROGRAM', 'ALARM', 'INFO')
            details: Human-readable description
            bitstream: Current bitstream filename (optional)
            extra: Additional key-value data (optional)
        """
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S.%f")[:-3]
        
        # Build log line
        parts = [f"[{timestamp}]", f"[{event_type:8}]"]
        
        if bitstream:
            parts.append(f"[{bitstream}]")
        
        if details:
            parts.append(details)
        
        if extra:
            extra_str = " | ".join(f"{k}={v}" for k, v in extra.items())
            parts.append(f"({extra_str})")
        
        log_line = " ".join(parts)
        
        try:
            with open(self.filename, "a", encoding="utf-8") as f:
                f.write(log_line + "\n")
        except Exception as e:
            print(f"Failed to write to history log: {e}")

    def log_program_start(self, bitstream: str):
        """Log FPGA programming start."""
        self.log_event("PROG_START", "FPGA programming initiated", bitstream)

    def log_program_success(self, bitstream: str):
        """Log successful FPGA programming."""
        self.log_event("PROG_OK", "FPGA programming successful", bitstream)

    def log_program_fail(self, bitstream: str, error: str = ""):
        """Log failed FPGA programming."""
        self.log_event("PROG_FAIL", f"FPGA programming failed: {error}", bitstream)

    def log_alarm(self, alarm_f: int, alarm_rf: int, 
                  alarm_uart: int = 0, alarm_obi_dmx: int = 0,
                  bitstream: str = ""):
        """
        Log sensor alarm detection - UPDATED for 4 sensor types.
        
        Args:
            alarm_f: ALARM_F register value (AM sensors)
            alarm_rf: ALARM_RF register value (LF sensors)
            alarm_uart: ALARM_UART register value (UART sensors)
            alarm_obi_dmx: ALARM_OBI_DMX register value (OBI Demux sensors)
            bitstream: Current bitstream filename
        """
        f_count = bin(alarm_f).count('1')
        rf_count = bin(alarm_rf).count('1')
        uart_count = bin(alarm_uart).count('1')
        obi_count = bin(alarm_obi_dmx).count('1')
        total = f_count + rf_count + uart_count + obi_count
        
        details = (
            f"Total={total} | "
            f"F=0x{alarm_f:08X} ({f_count}), "
            f"RF=0x{alarm_rf:08X} ({rf_count}), "
            f"UART=0x{alarm_uart:08X} ({uart_count}), "
            f"OBI=0x{alarm_obi_dmx:08X} ({obi_count})"
        )
        self.log_event("ALARM", details, bitstream)
    
    def log_alarm_dict(self, data: dict, bitstream: str = ""):
        """
        Log sensor alarm from a dictionary - NEW CONVENIENCE METHOD.
        
        Args:
            data: Dict with keys alarm_f, alarm_rf, alarm_uart, alarm_obi_dmx
            bitstream: Current bitstream filename
        """
        alarm_f = data.get('alarm_f', 0)
        alarm_rf = data.get('alarm_rf', 0)
        # Accept both naming conventions
        alarm_uart = data.get('alarm_uart', data.get('alarm_dm', 0))
        alarm_obi_dmx = data.get('alarm_obi_dmx', data.get('alarm_obi', 0))
        
        self.log_alarm(alarm_f, alarm_rf, alarm_uart, alarm_obi_dmx, bitstream)
    
    def log_new_alarm(self, sensor_type: str, new_bits: int, 
                      total_active: int, bitstream: str = ""):
        """
        Log a new alarm trigger for a specific sensor type - NEW METHOD.
        
        Args:
            sensor_type: One of 'F', 'RF', 'UART', 'OBI_DMX'
            new_bits: Bitmask of newly triggered sensors
            total_active: Total active alarms for this type
            bitstream: Current bitstream filename
        """
        new_count = bin(new_bits).count('1')
        new_indices = [i for i in range(32) if new_bits & (1 << i)]
        
        details = (
            f"{sensor_type}: {new_count} new alarms (total {total_active}) | "
            f"New bits: {new_indices}"
        )
        self.log_event("NEW_ALARM", details, bitstream)

    def log_connection(self, port: str, connected: bool):
        """Log connection state change."""
        state = "connected" if connected else "disconnected"
        self.log_event("CONNECT", f"Serial {state}: {port}")

    def log_voltage_change(self, voltage: float):
        """Log voltage change command."""
        self.log_event("VOLTAGE", f"Vcore set to {voltage:.2f}V")

    def log_temperature(self, fpga_temp: float, ambient_temp: float = None,
                        vccint: float = None):
        """
        Log temperature reading - NEW METHOD.
        
        Args:
            fpga_temp: FPGA die temperature in °C
            ambient_temp: Ambient/external temperature in °C (optional)
            vccint: VCCINT voltage in V (optional)
        """
        parts = [f"FPGA={fpga_temp:.2f}°C"]
        if ambient_temp is not None:
            parts.append(f"Ambient={ambient_temp:.1f}°C")
        if vccint is not None:
            parts.append(f"VCCINT={vccint:.3f}V")
        
        self.log_event("TEMP", " | ".join(parts))

    def log_info(self, message: str):
        """Log general information."""
        self.log_event("INFO", message)

    def log_error(self, message: str):
        """Log error."""
        self.log_event("ERROR", message)
    
    def log_warning(self, message: str):
        """Log warning - NEW METHOD."""
        self.log_event("WARNING", message)
    
    def log_experiment_start(self, dose_rate: float = None, initial_dose: float = None):
        """
        Log experiment start - NEW METHOD.
        
        Args:
            dose_rate: Radiation dose rate in krad/hour
            initial_dose: Initial accumulated dose in krad
        """
        extra = {}
        if dose_rate is not None:
            extra['dose_rate_krad_h'] = dose_rate
        if initial_dose is not None:
            extra['initial_dose_krad'] = initial_dose
        
        self.log_event("EXP_START", "Experiment started", extra=extra or None)
    
    def log_experiment_end(self, total_time_hours: float = None, 
                           total_dose_krad: float = None,
                           total_alarms: int = None):
        """
        Log experiment end - NEW METHOD.
        
        Args:
            total_time_hours: Total experiment duration in hours
            total_dose_krad: Total accumulated dose in krad
            total_alarms: Total number of alarm events
        """
        extra = {}
        if total_time_hours is not None:
            extra['duration_hours'] = f"{total_time_hours:.2f}"
        if total_dose_krad is not None:
            extra['total_dose_krad'] = f"{total_dose_krad:.2f}"
        if total_alarms is not None:
            extra['total_alarms'] = total_alarms
        
        self.log_event("EXP_END", "Experiment ended", extra=extra or None)

    def get_full_path(self) -> str:
        """Get absolute path to log file."""
        return os.path.abspath(self.filename)

    def get_recent_entries(self, count: int = 100) -> list:
        """
        Get the most recent log entries.
        
        Args:
            count: Number of entries to retrieve
            
        Returns:
            List of log lines (most recent last)
        """
        try:
            with open(self.filename, "r", encoding="utf-8") as f:
                lines = f.readlines()
            return lines[-count:] if len(lines) > count else lines
        except FileNotFoundError:
            return []
        except Exception as e:
            print(f"Failed to read history log: {e}")
            return []
    
    def get_entries_by_type(self, event_type: str, count: int = None) -> list:
        """
        Get log entries filtered by event type - NEW METHOD.
        
        Args:
            event_type: Event type to filter (e.g., 'ALARM', 'PROG_OK')
            count: Max number of entries (None = all)
            
        Returns:
            List of matching log lines
        """
        try:
            with open(self.filename, "r", encoding="utf-8") as f:
                lines = f.readlines()
            
            # Filter by event type
            filtered = [l for l in lines if f"[{event_type}" in l]
            
            if count is not None:
                return filtered[-count:]
            return filtered
        except FileNotFoundError:
            return []
        except Exception as e:
            print(f"Failed to read history log: {e}")
            return []

    def clear(self):
        """Clear the log file (with backup)."""
        if os.path.exists(self.filename):
            # Create backup
            backup = f"{self.filename}.backup"
            try:
                os.rename(self.filename, backup)
                self.log_event("INFO", f"Log cleared (backup: {backup})")
            except Exception as e:
                print(f"Failed to backup log: {e}")
    
    def get_statistics(self) -> Dict[str, Any]:
        """
        Get statistics from the log file - NEW METHOD.
        
        Returns:
            Dict with counts of different event types
        """
        stats = {
            'total_entries': 0,
            'alarms': 0,
            'program_success': 0,
            'program_fail': 0,
            'errors': 0,
            'warnings': 0
        }
        
        try:
            with open(self.filename, "r", encoding="utf-8") as f:
                for line in f:
                    stats['total_entries'] += 1
                    if '[ALARM' in line or '[NEW_ALARM' in line:
                        stats['alarms'] += 1
                    elif '[PROG_OK' in line:
                        stats['program_success'] += 1
                    elif '[PROG_FAIL' in line:
                        stats['program_fail'] += 1
                    elif '[ERROR' in line:
                        stats['errors'] += 1
                    elif '[WARNING' in line:
                        stats['warnings'] += 1
        except FileNotFoundError:
            pass
        except Exception as e:
            print(f"Failed to calculate statistics: {e}")
        
        return stats