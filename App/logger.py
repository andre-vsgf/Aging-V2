# -*- coding: utf-8 -*-
"""
Data Logger - 4 SENSOR VERSION

Creates a unique CSV file per test and writes data rows to it.
Designed for continuous logging during burn-in experiments.

UPDATED: Now supports all 4 sensor types:
- ALARM_F (AM sensors)
- ALARM_RF (LF sensors)
- ALARM_UART (UART sensors)
- ALARM_OBI_DMX (OBI Demux sensors)

Also removed Arduino/oven references since they're not used in this project.
"""

import os
import csv
from datetime import datetime
from typing import Dict, Any, Optional


class DataLogger:
    """
    CSV data logger for experiment telemetry - 4 SENSOR VERSION.
    
    Creates a timestamped CSV file and appends data rows during the experiment.
    Optimized for CROC FPGA aging experiments with STM32 power monitoring.
    """
    
    def __init__(self, log_folder: str, test_name: str, include_raw_registers: bool = True):
        """
        Initialize the data logger.
        
        Args:
            log_folder: Directory to store log files
            test_name: Base name for the log file
            include_raw_registers: If True, include hex values of alarm registers
        """
        self.include_raw_registers = include_raw_registers
        self.filepath = self._create_log_file(log_folder, test_name)
        self.csv_writer = None
        self.file_handle = None
        self._row_count = 0
        self._write_header()

    def _create_log_file(self, folder: str, name: str) -> str:
        """Create a unique filename with timestamp."""
        if not os.path.exists(folder):
            os.makedirs(folder)
            
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = f"{name}_{timestamp}.csv"
        return os.path.join(folder, filename)

    def _write_header(self):
        """Write the CSV header with all 4 sensor types."""
        # Open file with line buffering for immediate writes
        self.file_handle = open(self.filepath, 'w', newline='', encoding='utf-8', buffering=1)
        self.csv_writer = csv.writer(self.file_handle)
        
        # Build header based on configuration
        header = [
            # Timing
            'timestamp',
            'time_sec',
            'experiment_hours',
            
            # STM32 Power Data
            'vcore_v',
            'vin_v',
            'iout_a',
            'power_w',
            'ext_temp_c',
            
            # FPGA Data
            'fpga_temp_c',
            'vccint_v',
            
            # Sensor Alarm Counts (4 types)
            'alarm_f_count',
            'alarm_rf_count',
            'alarm_uart_count',
            'alarm_obi_count',
            'total_alarms',
        ]
        
        # Optionally include raw register values
        if self.include_raw_registers:
            header.extend([
                'alarm_f_hex',
                'alarm_rf_hex',
                'alarm_uart_hex',
                'alarm_obi_hex',
            ])
        
        # Calculated values
        header.extend([
            'radiation_dose_krad',
            'bitstream',
            'notes'
        ])
        
        self.csv_writer.writerow(header)

    def write_data_row(self, data: Dict[str, Any]):
        """
        Write a new data row to the CSV.
        
        Args:
            data: Dictionary with telemetry values. Expected keys:
                - time_sec: Elapsed seconds (float)
                - experiment_hours: Elapsed hours (float, optional)
                - vcore, vin, iout: STM32 power readings
                - ext_temp: External temperature from STM32
                - fpga_temp: FPGA die temperature
                - vccint: FPGA VCCINT voltage
                - alarm_f, alarm_rf, alarm_uart, alarm_obi_dmx: Alarm registers
                - radiation_dose_krad: Calculated dose (optional)
                - bitstream: Current bitstream name (optional)
                - notes: Additional notes (optional)
        """
        if not self.csv_writer:
            return
        
        try:
            # Extract alarm values (support both naming conventions)
            alarm_f = data.get('alarm_f', 0)
            alarm_rf = data.get('alarm_rf', 0)
            alarm_uart = data.get('alarm_uart', data.get('alarm_dm', 0))
            alarm_obi = data.get('alarm_obi_dmx', data.get('alarm_obi', 0))
            
            # Calculate counts
            f_count = bin(alarm_f).count('1') if alarm_f else 0
            rf_count = bin(alarm_rf).count('1') if alarm_rf else 0
            uart_count = bin(alarm_uart).count('1') if alarm_uart else 0
            obi_count = bin(alarm_obi).count('1') if alarm_obi else 0
            total = f_count + rf_count + uart_count + obi_count
            
            # Calculate power
            vcore = data.get('vcore', data.get('psu_voltage', 0)) or 0
            iout = data.get('iout', data.get('psu_current', 0)) or 0
            power = vcore * iout
            
            # Build row
            row = [
                datetime.now().isoformat(),
                data.get('time_sec', 0),
                data.get('experiment_hours', 0),
                
                # STM32 Power
                vcore,
                data.get('vin', 0),
                iout,
                power,
                data.get('ext_temp', data.get('ambient_temp', 0)),
                
                # FPGA
                data.get('fpga_temp', data.get('dut_temp', 0)),
                data.get('vccint', data.get('dut_volt', 0)),
                
                # Alarm counts
                f_count,
                rf_count,
                uart_count,
                obi_count,
                total,
            ]
            
            # Raw registers (optional)
            if self.include_raw_registers:
                row.extend([
                    f"0x{alarm_f:08X}",
                    f"0x{alarm_rf:08X}",
                    f"0x{alarm_uart:08X}",
                    f"0x{alarm_obi:08X}",
                ])
            
            # Calculated/metadata
            row.extend([
                data.get('radiation_dose_krad', 0),
                data.get('bitstream', ''),
                data.get('notes', '')
            ])
            
            self.csv_writer.writerow(row)
            self._row_count += 1
            
        except Exception as e:
            print(f"Error writing to CSV: {e}")

    def write_sensor_data(self, alarm_f: int, alarm_rf: int, 
                          alarm_uart: int = 0, alarm_obi_dmx: int = 0,
                          fpga_temp: float = 0, vccint: float = 0,
                          vcore: float = 0, iout: float = 0,
                          time_sec: float = 0, **kwargs):
        """
        Convenience method to write sensor data directly - NEW METHOD.
        
        Args:
            alarm_f: ALARM_F register value
            alarm_rf: ALARM_RF register value
            alarm_uart: ALARM_UART register value
            alarm_obi_dmx: ALARM_OBI_DMX register value
            fpga_temp: FPGA temperature in °C
            vccint: VCCINT voltage in V
            vcore: Core voltage in V
            iout: Output current in A
            time_sec: Elapsed time in seconds
            **kwargs: Additional fields to include
        """
        data = {
            'alarm_f': alarm_f,
            'alarm_rf': alarm_rf,
            'alarm_uart': alarm_uart,
            'alarm_obi_dmx': alarm_obi_dmx,
            'fpga_temp': fpga_temp,
            'vccint': vccint,
            'vcore': vcore,
            'iout': iout,
            'time_sec': time_sec,
            **kwargs
        }
        self.write_data_row(data)

    def get_row_count(self) -> int:
        """Get number of data rows written (excluding header)."""
        return self._row_count

    def get_filepath(self) -> str:
        """Get the full path to the log file."""
        return self.filepath

    def flush(self):
        """Force flush any buffered data to disk."""
        if self.file_handle:
            self.file_handle.flush()

    def close(self):
        """Close the CSV file."""
        if self.file_handle:
            self.file_handle.close()
            self.file_handle = None
            self.csv_writer = None
            print(f"Data log saved: {self.filepath} ({self._row_count} rows)")

    def __enter__(self):
        """Context manager entry."""
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        """Context manager exit."""
        self.close()
        return False


class SummaryLogger:
    """
    Summary logger for experiment statistics - NEW CLASS.
    
    Logs periodic summaries (e.g., every minute) instead of every data point.
    Useful for long-duration experiments where full data logging is too verbose.
    """
    
    def __init__(self, log_folder: str, test_name: str, interval_seconds: float = 60):
        """
        Initialize the summary logger.
        
        Args:
            log_folder: Directory to store log files
            test_name: Base name for the log file
            interval_seconds: Minimum time between log entries
        """
        self.interval = interval_seconds
        self._last_log_time = 0
        
        # Create log file
        if not os.path.exists(log_folder):
            os.makedirs(log_folder)
        
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        self.filepath = os.path.join(log_folder, f"{test_name}_summary_{timestamp}.csv")
        
        self.file_handle = open(self.filepath, 'w', newline='', encoding='utf-8', buffering=1)
        self.csv_writer = csv.writer(self.file_handle)
        
        # Write header
        self.csv_writer.writerow([
            'timestamp',
            'elapsed_hours',
            'dose_krad',
            # Alarm totals
            'total_f',
            'total_rf', 
            'total_uart',
            'total_obi',
            'total_all',
            # Environment
            'fpga_temp_avg',
            'vccint_avg',
            'power_avg',
            # Statistics
            'new_alarms_this_period',
            'bitstream',
            'notes'
        ])
        
        # Accumulator for averaging
        self._samples = []
        self._new_alarms = 0
    
    def add_sample(self, data: Dict[str, Any], new_alarms: int = 0):
        """
        Add a data sample to the accumulator.
        
        Args:
            data: Telemetry data dictionary
            new_alarms: Number of new alarms detected since last sample
        """
        self._samples.append(data)
        self._new_alarms += new_alarms
    
    def maybe_write_summary(self, current_time: float, force: bool = False) -> bool:
        """
        Write summary if interval has elapsed.
        
        Args:
            current_time: Current experiment time in seconds
            force: Force write regardless of interval
            
        Returns:
            True if summary was written
        """
        if not force and (current_time - self._last_log_time) < self.interval:
            return False
        
        if not self._samples:
            return False
        
        # Calculate averages
        def avg(key):
            vals = [s.get(key, 0) for s in self._samples if s.get(key) is not None]
            return sum(vals) / len(vals) if vals else 0
        
        # Get latest values for totals
        latest = self._samples[-1]
        
        alarm_f = latest.get('alarm_f', 0)
        alarm_rf = latest.get('alarm_rf', 0)
        alarm_uart = latest.get('alarm_uart', latest.get('alarm_dm', 0))
        alarm_obi = latest.get('alarm_obi_dmx', latest.get('alarm_obi', 0))
        
        f_count = bin(alarm_f).count('1') if alarm_f else 0
        rf_count = bin(alarm_rf).count('1') if alarm_rf else 0
        uart_count = bin(alarm_uart).count('1') if alarm_uart else 0
        obi_count = bin(alarm_obi).count('1') if alarm_obi else 0
        
        # Write row
        self.csv_writer.writerow([
            datetime.now().isoformat(),
            current_time / 3600,  # Convert to hours
            latest.get('radiation_dose_krad', 0),
            f_count,
            rf_count,
            uart_count,
            obi_count,
            f_count + rf_count + uart_count + obi_count,
            avg('fpga_temp'),
            avg('vccint'),
            avg('vcore') * avg('iout'),  # Power
            self._new_alarms,
            latest.get('bitstream', ''),
            ''
        ])
        
        # Reset accumulators
        self._samples = []
        self._new_alarms = 0
        self._last_log_time = current_time
        
        return True
    
    def close(self):
        """Close the log file."""
        # Write final summary if we have samples
        if self._samples:
            self.maybe_write_summary(float('inf'), force=True)
        
        if self.file_handle:
            self.file_handle.close()
            print(f"Summary log saved: {self.filepath}")