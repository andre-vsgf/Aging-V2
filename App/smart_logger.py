# -*- coding: utf-8 -*-
"""
Smart Logger - Efficient Logging for Long-Duration Experiments

Designed to minimize log file size during weeks-long experiments while
preserving all important data.

STRATEGIES:
1. Adaptive Sampling - Log more frequently when things change, less when stable
2. Change Detection - Only log when values change significantly  
3. Periodic Summaries - Aggregate data into periodic summaries
4. Compression - Run-length encoding for stable periods
5. Rotation - Automatic file rotation when size limit reached

EXPECTED SIZE REDUCTION:
- Continuous logging: ~100MB/day → With smart logging: ~1-5MB/day
- 4 weeks continuous: ~2.8GB → With smart logging: ~30-150MB

Author: CROC Project
"""

import os
import csv
import json
import gzip
import shutil
from datetime import datetime, timedelta
from typing import Dict, Any, Optional, List, Tuple
from dataclasses import dataclass, asdict
from pathlib import Path
from collections import deque


@dataclass
class DataSnapshot:
    """A single data point snapshot."""
    timestamp: datetime
    alarm_f: int
    alarm_rf: int
    alarm_uart: int
    alarm_obi: int
    fpga_temp: float
    vccint: float
    vcore: float
    iout: float
    
    def to_dict(self) -> dict:
        d = asdict(self)
        d['timestamp'] = self.timestamp.isoformat()
        return d
    
    def to_csv_row(self) -> list:
        return [
            self.timestamp.isoformat(),
            self.alarm_f, self.alarm_rf, self.alarm_uart, self.alarm_obi,
            bin(self.alarm_f).count('1') + bin(self.alarm_rf).count('1') +
            bin(self.alarm_uart).count('1') + bin(self.alarm_obi).count('1'),
            self.fpga_temp, self.vccint, self.vcore, self.iout,
            self.vcore * self.iout  # power
        ]


class SmartLogger:
    """
    Intelligent data logger with adaptive sampling and compression.
    
    Modes:
    - NORMAL: Log every N seconds (configurable)
    - CHANGE: Log only when alarm state changes
    - ADAPTIVE: Combine both - frequent during changes, sparse when stable
    - SUMMARY: Only log periodic summaries (most compact)
    """
    
    # Thresholds for "significant change"
    TEMP_THRESHOLD = 0.5      # °C change to trigger log
    VOLTAGE_THRESHOLD = 0.005  # V change to trigger log
    
    # File size limits
    MAX_FILE_SIZE_MB = 50
    
    def __init__(self, log_folder: str, experiment_name: str,
                 mode: str = "adaptive",
                 normal_interval_sec: float = 60.0,
                 change_interval_sec: float = 1.0,
                 summary_interval_sec: float = 300.0):
        """
        Initialize the smart logger.
        
        Args:
            log_folder: Directory to store log files
            experiment_name: Base name for log files
            mode: "normal", "change", "adaptive", or "summary"
            normal_interval_sec: Interval for periodic logging (seconds)
            change_interval_sec: Minimum interval during changes
            summary_interval_sec: Interval for summary entries
        """
        self.log_folder = log_folder
        self.experiment_name = experiment_name
        self.mode = mode.lower()
        self.normal_interval = normal_interval_sec
        self.change_interval = change_interval_sec
        self.summary_interval = summary_interval_sec
        
        # Create log folder
        os.makedirs(log_folder, exist_ok=True)
        
        # State tracking
        self._last_snapshot: Optional[DataSnapshot] = None
        self._last_log_time: Optional[datetime] = None
        self._last_summary_time: Optional[datetime] = None
        self._last_alarms = (0, 0, 0, 0)
        
        # Accumulator for summaries
        self._accumulator: List[DataSnapshot] = []
        self._row_count = 0
        self._file_index = 0
        
        # Change detection
        self._in_change_period = False
        self._change_start_time: Optional[datetime] = None
        self._stable_count = 0
        self._STABLE_THRESHOLD = 10  # readings before considered stable
        
        # Initialize files
        self._init_files()
    
    def _init_files(self):
        """Initialize log files."""
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        base_name = f"{self.experiment_name}_{timestamp}"
        
        # Main data file (CSV)
        self._data_filepath = os.path.join(
            self.log_folder, f"{base_name}_data.csv"
        )
        
        # Summary file (CSV, more compact)
        self._summary_filepath = os.path.join(
            self.log_folder, f"{base_name}_summary.csv"
        )
        
        # Events file (JSON, only transitions/changes)
        self._events_filepath = os.path.join(
            self.log_folder, f"{base_name}_events.json"
        )
        
        # Initialize data CSV
        self._data_file = open(self._data_filepath, 'w', newline='', encoding='utf-8')
        self._data_writer = csv.writer(self._data_file)
        self._data_writer.writerow([
            'timestamp', 'alarm_f', 'alarm_rf', 'alarm_uart', 'alarm_obi',
            'total_alarms', 'fpga_temp', 'vccint', 'vcore', 'iout', 'power'
        ])
        
        # Initialize summary CSV
        self._summary_file = open(self._summary_filepath, 'w', newline='', encoding='utf-8')
        self._summary_writer = csv.writer(self._summary_file)
        self._summary_writer.writerow([
            'period_start', 'period_end', 'duration_sec',
            'alarm_f_max', 'alarm_rf_max', 'alarm_uart_max', 'alarm_obi_max',
            'total_alarms_max', 'alarm_changes',
            'fpga_temp_avg', 'fpga_temp_min', 'fpga_temp_max',
            'vccint_avg', 'power_avg', 'samples'
        ])
        
        # Initialize events list
        self._events: List[Dict] = []
    
    def log_data(self, alarm_f: int, alarm_rf: int, 
                 alarm_uart: int = 0, alarm_obi: int = 0,
                 fpga_temp: float = 0.0, vccint: float = 0.0,
                 vcore: float = 0.0, iout: float = 0.0,
                 force: bool = False) -> bool:
        """
        Log data with smart filtering.
        
        Args:
            alarm_*: Alarm register values
            fpga_temp: FPGA temperature
            vccint: VCCINT voltage
            vcore: Core voltage
            iout: Output current
            force: Force logging regardless of mode
            
        Returns:
            True if data was actually logged
        """
        now = datetime.now()
        
        # Create snapshot
        snapshot = DataSnapshot(
            timestamp=now,
            alarm_f=alarm_f,
            alarm_rf=alarm_rf,
            alarm_uart=alarm_uart,
            alarm_obi=alarm_obi,
            fpga_temp=fpga_temp,
            vccint=vccint,
            vcore=vcore,
            iout=iout
        )
        
        # Always add to accumulator for summaries
        self._accumulator.append(snapshot)
        
        # Check if we should log based on mode
        should_log = force
        
        if not should_log:
            should_log = self._should_log(snapshot, now)
        
        if should_log:
            self._write_data_row(snapshot)
            self._last_snapshot = snapshot
            self._last_log_time = now
        
        # Update alarm tracking
        current_alarms = (alarm_f, alarm_rf, alarm_uart, alarm_obi)
        if current_alarms != self._last_alarms:
            self._on_alarm_change(snapshot, self._last_alarms, current_alarms)
        self._last_alarms = current_alarms
        
        # Check if we should write summary
        if self._should_write_summary(now):
            self._write_summary()
            self._last_summary_time = now
        
        # Check file rotation
        self._check_rotation()
        
        return should_log
    
    def _should_log(self, snapshot: DataSnapshot, now: datetime) -> bool:
        """Determine if we should log based on mode."""
        
        if self._last_log_time is None:
            return True  # Always log first entry
        
        elapsed = (now - self._last_log_time).total_seconds()
        
        if self.mode == "normal":
            return elapsed >= self.normal_interval
        
        elif self.mode == "change":
            return self._has_significant_change(snapshot)
        
        elif self.mode == "adaptive":
            # During change period: log frequently
            if self._in_change_period:
                if elapsed >= self.change_interval:
                    return True
            # Otherwise: log at normal interval or on change
            else:
                if elapsed >= self.normal_interval:
                    return True
                if self._has_significant_change(snapshot):
                    self._enter_change_period()
                    return True
            return False
        
        elif self.mode == "summary":
            # Only log if alarm changed
            return self._has_alarm_change(snapshot)
        
        return False
    
    def _has_significant_change(self, snapshot: DataSnapshot) -> bool:
        """Check if there's a significant change from last snapshot."""
        if self._last_snapshot is None:
            return True
        
        # Alarm change is always significant
        if self._has_alarm_change(snapshot):
            return True
        
        # Temperature change
        if abs(snapshot.fpga_temp - self._last_snapshot.fpga_temp) > self.TEMP_THRESHOLD:
            return True
        
        # Voltage change
        if abs(snapshot.vccint - self._last_snapshot.vccint) > self.VOLTAGE_THRESHOLD:
            return True
        if abs(snapshot.vcore - self._last_snapshot.vcore) > self.VOLTAGE_THRESHOLD:
            return True
        
        return False
    
    def _has_alarm_change(self, snapshot: DataSnapshot) -> bool:
        """Check if alarm state changed."""
        if self._last_snapshot is None:
            return True
        
        return (snapshot.alarm_f != self._last_snapshot.alarm_f or
                snapshot.alarm_rf != self._last_snapshot.alarm_rf or
                snapshot.alarm_uart != self._last_snapshot.alarm_uart or
                snapshot.alarm_obi != self._last_snapshot.alarm_obi)
    
    def _enter_change_period(self):
        """Enter high-frequency logging mode."""
        if not self._in_change_period:
            self._in_change_period = True
            self._change_start_time = datetime.now()
            self._stable_count = 0
    
    def _check_stable(self, snapshot: DataSnapshot):
        """Check if we've returned to stable state."""
        if self._in_change_period:
            if not self._has_significant_change(snapshot):
                self._stable_count += 1
                if self._stable_count >= self._STABLE_THRESHOLD:
                    self._in_change_period = False
            else:
                self._stable_count = 0
    
    def _on_alarm_change(self, snapshot: DataSnapshot, 
                         old_alarms: Tuple[int, int, int, int],
                         new_alarms: Tuple[int, int, int, int]):
        """Record alarm change event."""
        
        # Find which bits changed
        changes = {}
        sensor_names = ['F', 'RF', 'UART', 'OBI']
        
        for i, name in enumerate(sensor_names):
            old_val = old_alarms[i]
            new_val = new_alarms[i]
            
            if old_val != new_val:
                new_bits = new_val & ~old_val
                cleared_bits = old_val & ~new_val
                
                changes[name] = {
                    'old': f"0x{old_val:08X}",
                    'new': f"0x{new_val:08X}",
                    'new_bits': [i for i in range(32) if new_bits & (1 << i)],
                    'cleared_bits': [i for i in range(32) if cleared_bits & (1 << i)]
                }
        
        event = {
            'timestamp': snapshot.timestamp.isoformat(),
            'type': 'alarm_change',
            'changes': changes,
            'fpga_temp': snapshot.fpga_temp,
            'vccint': snapshot.vccint
        }
        
        self._events.append(event)
        self._enter_change_period()
    
    def _write_data_row(self, snapshot: DataSnapshot):
        """Write a data row to CSV."""
        self._data_writer.writerow(snapshot.to_csv_row())
        self._data_file.flush()
        self._row_count += 1
    
    def _should_write_summary(self, now: datetime) -> bool:
        """Check if we should write a summary."""
        if self._last_summary_time is None:
            return len(self._accumulator) > 0
        
        elapsed = (now - self._last_summary_time).total_seconds()
        return elapsed >= self.summary_interval and len(self._accumulator) > 0
    
    def _write_summary(self):
        """Write summary of accumulated data."""
        if not self._accumulator:
            return
        
        first = self._accumulator[0]
        last = self._accumulator[-1]
        duration = (last.timestamp - first.timestamp).total_seconds()
        
        # Calculate statistics
        temps = [s.fpga_temp for s in self._accumulator]
        vccints = [s.vccint for s in self._accumulator]
        powers = [s.vcore * s.iout for s in self._accumulator]
        
        # Max alarms
        max_f = max(s.alarm_f for s in self._accumulator)
        max_rf = max(s.alarm_rf for s in self._accumulator)
        max_uart = max(s.alarm_uart for s in self._accumulator)
        max_obi = max(s.alarm_obi for s in self._accumulator)
        
        max_total = max(
            bin(s.alarm_f).count('1') + bin(s.alarm_rf).count('1') +
            bin(s.alarm_uart).count('1') + bin(s.alarm_obi).count('1')
            for s in self._accumulator
        )
        
        # Count alarm changes
        changes = 0
        last_alarms = None
        for s in self._accumulator:
            current = (s.alarm_f, s.alarm_rf, s.alarm_uart, s.alarm_obi)
            if last_alarms is not None and current != last_alarms:
                changes += 1
            last_alarms = current
        
        # Write summary row
        self._summary_writer.writerow([
            first.timestamp.isoformat(),
            last.timestamp.isoformat(),
            duration,
            max_f, max_rf, max_uart, max_obi,
            max_total, changes,
            sum(temps) / len(temps), min(temps), max(temps),
            sum(vccints) / len(vccints),
            sum(powers) / len(powers),
            len(self._accumulator)
        ])
        self._summary_file.flush()
        
        # Clear accumulator
        self._accumulator.clear()
    
    def _check_rotation(self):
        """Check if we need to rotate log files."""
        try:
            size_mb = os.path.getsize(self._data_filepath) / (1024 * 1024)
            if size_mb >= self.MAX_FILE_SIZE_MB:
                self._rotate_files()
        except:
            pass
    
    def _rotate_files(self):
        """Rotate log files (compress old, start new)."""
        self._file_index += 1
        
        # Close current files
        self._data_file.close()
        self._summary_file.close()
        
        # Compress old data file
        old_path = self._data_filepath
        gz_path = f"{old_path}.gz"
        
        with open(old_path, 'rb') as f_in:
            with gzip.open(gz_path, 'wb') as f_out:
                shutil.copyfileobj(f_in, f_out)
        
        os.remove(old_path)
        
        # Create new files
        self._init_files()
    
    def log_event(self, event_type: str, details: Dict[str, Any]):
        """Log a custom event."""
        event = {
            'timestamp': datetime.now().isoformat(),
            'type': event_type,
            **details
        }
        self._events.append(event)
    
    def flush(self):
        """Flush all buffers to disk."""
        if self._accumulator:
            self._write_summary()
        
        self._data_file.flush()
        self._summary_file.flush()
        
        # Save events
        events_path = self._events_filepath
        with open(events_path, 'w', encoding='utf-8') as f:
            json.dump(self._events, f, indent=2)
    
    def close(self):
        """Close all files."""
        self.flush()
        self._data_file.close()
        self._summary_file.close()
    
    def get_statistics(self) -> Dict[str, Any]:
        """Get logging statistics."""
        data_size = os.path.getsize(self._data_filepath) if os.path.exists(self._data_filepath) else 0
        summary_size = os.path.getsize(self._summary_filepath) if os.path.exists(self._summary_filepath) else 0
        
        return {
            'mode': self.mode,
            'rows_logged': self._row_count,
            'events_logged': len(self._events),
            'data_file_size_mb': data_size / (1024 * 1024),
            'summary_file_size_mb': summary_size / (1024 * 1024),
            'total_size_mb': (data_size + summary_size) / (1024 * 1024),
            'file_rotations': self._file_index
        }
    
    def __enter__(self):
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        self.close()
        return False


class TransitionLogger:
    """
    Specialized logger for bitstream transitions only.
    
    Extremely compact - only logs when bitstream changes.
    Perfect for long experiments where only transitions matter.
    """
    
    def __init__(self, filepath: str = "transitions.csv"):
        self.filepath = filepath
        self._file = open(filepath, 'w', newline='', encoding='utf-8')
        self._writer = csv.writer(self._file)
        self._writer.writerow([
            'timestamp', 'experiment_hours', 
            'from_bitstream', 'from_phase',
            'to_bitstream', 'to_phase',
            'trigger_alarms_f', 'trigger_alarms_rf',
            'trigger_alarms_uart', 'trigger_alarms_obi',
            'total_alarms', 'fpga_temp', 'vccint'
        ])
        self._start_time = datetime.now()
    
    def log_transition(self, from_bitstream: str, to_bitstream: str,
                       from_phase: float, to_phase: float,
                       trigger_alarms: Dict[str, List[int]],
                       fpga_temp: float = 0.0, vccint: float = 0.0):
        """Log a bitstream transition."""
        now = datetime.now()
        hours = (now - self._start_time).total_seconds() / 3600
        
        total = sum(len(bits) for bits in trigger_alarms.values())
        
        self._writer.writerow([
            now.isoformat(), f"{hours:.4f}",
            from_bitstream, from_phase,
            to_bitstream, to_phase,
            str(trigger_alarms.get('F', [])),
            str(trigger_alarms.get('RF', [])),
            str(trigger_alarms.get('UART', [])),
            str(trigger_alarms.get('OBI', [])),
            total, fpga_temp, vccint
        ])
        self._file.flush()
    
    def close(self):
        self._file.close()
