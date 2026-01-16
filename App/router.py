# -*- coding: utf-8 -*-
"""
UART Router for CROC FPGA System - SIMPLIFIED VERSION
======================================================

Fixed 4 sensor types:
- F (AM sensors) - 32 bits
- RF (LF sensors) - 32 bits  
- UART sensors - 32 bits
- OBI_DMX sensors - 32 bits

Protocols parsed:
- CROC firmware: "F: 0x... | RF: 0x... | OBI: 0x... | UART: 0x..."
- STM32 telemetry: "$TEL,Vc,X.XXX,Vi,X.XXX,Io,X.XXX,Et,XX.X,Mt,XX.X*CS"
- FPGA telemetry: "$SYS,FT,XXXX,VI,XXXX,AF,XXXXXXXX,AR,XXXXXXXX,AU,XXXXXXXX,AO,XXXXXXXX*CS"
                       (temp*100 hex, mV hex, then 4 sensor alarms in hex)
"""

from PySide6.QtCore import QObject, Signal, Slot, QMutex
from serial_thread import SerialThread
from protocol import ProtocolParser
import config
import time
import re


# Routing headers (for sending)
HEADER_CROC = b'\x10'
HEADER_STM  = b'\x20'


class UARTRouter(QObject):
    """
    Central UART routing and parsing manager.
    Simplified for 4 fixed sensor types.
    """
    
    # Signals
    stm_frame_received = Signal(object)
    log_text_received = Signal(str)
    connection_status = Signal(str)
    log_message = Signal(str)
    aging_data_received = Signal(dict)
    telemetry_received = Signal(dict)
    raw_data_received = Signal(bytes)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.serial = None
        self.parser = ProtocolParser()
        self.is_connected = False
        self.last_target = None
        self.ROUTER_TIMEOUT_S = 0.06
        self.route_lock = QMutex()
        
        self._rx_buffer = bytearray()
        
        # Telemetry data storage
        self._telemetry = {
            # STM32 data
            'vcore': 0.0,
            'vin': 0.0,
            'iout': 0.0,
            'ext_temp': 0.0,
            'mcu_temp': 0.0,
            # FPGA data
            'fpga_temp': 0.0,
            'vccint': 0.0,
            # 4 sensor alarms (FIXED)
            'alarm_f': 0,       # AM sensors
            'alarm_rf': 0,      # LF sensors
            'alarm_dm': 0,    # UART sensors
            'alarm_obi_dmx': 0, # OBI DMX sensors
        }
        
        # =====================================================================
        # REGEX PATTERNS
        # =====================================================================
        
        # CROC firmware output (4 sensors)
        # Format: "F: 0x... | RF: 0x... | OBI: 0x... | UART: 0x..."
        self._sensor_regex_4 = re.compile(
            r'F:\s*0x([0-9A-Fa-f]+)\s*\|\s*RF:\s*0x([0-9A-Fa-f]+)\s*\|\s*'
            r'OBI:\s*0x([0-9A-Fa-f]+)\s*\|\s*UART:\s*0x([0-9A-Fa-f]+)',
            re.IGNORECASE
        )
        
        # CROC firmware output (2 sensors - legacy)
        self._sensor_regex_2 = re.compile(
            r'F:\s*0x([0-9A-Fa-f]+)\s*\|\s*RF:\s*0x([0-9A-Fa-f]+)(?:\s*$|\s*\r)',
            re.IGNORECASE
        )
        
        # STM32 telemetry
        # Format: "$TEL,Vc,X.XXX,Vi,X.XXX,Io,X.XXX,Et,XX.X,Mt,XX.X*CS"
        self._stm_telemetry_regex = re.compile(
            r'\$TEL,Vc,([0-9.]+),Vi,([0-9.]+),Io,([0-9.]+),Et,([0-9.-]+),Mt,([0-9.-]+)\*([0-9A-Fa-f]{2})',
            re.IGNORECASE
        )
        
        # FPGA telemetry - HEX format (4 sensors)
        # Format: "$SYS,FT,XXXX,VI,XXXX,AF,XXXXXXXX,AR,XXXXXXXX,AU,XXXXXXXX,AO,XXXXXXXX*CS"
        # FT = temperature * 100 in hex (e.g., 0x0FA0 = 4000 = 40.00°C)
        # VI = voltage in mV in hex (e.g., 0x0352 = 850 = 0.850V)
        # AF = alarm_f, AR = alarm_rf, AU = alarm_uart, AO = alarm_obi_dmx
        self._sys_telemetry_regex = re.compile(
            r'\$SYS,FT,([0-9A-Fa-f]{4}),VI,([0-9A-Fa-f]{4}),'
            r'AF,([0-9A-Fa-f]{8}),AR,([0-9A-Fa-f]{8}),'
            r'AU,([0-9A-Fa-f]{8}),AO,([0-9A-Fa-f]{8})\*([0-9A-Fa-f]{2})',
            re.IGNORECASE
        )

    def connect_serial(self, port: str = None, baud: int = None):
        if port is None:
            port = config.FPGA_PORT
        if baud is None:
            baud = config.SYSTEM_BAUD
        
        if self.serial and self.serial.isRunning():
            self.serial.stop()
            self.serial.wait()

        self.serial = SerialThread(port, baud, rts=True, dtr=True)
        
        self.serial.data_received.connect(self._on_data_received)
        self.serial.error_occurred.connect(self._on_error)
        self.serial.port_opened.connect(self._on_opened)
        self.serial.port_closed.connect(self._on_closed)
        
        self.serial.start()

    def disconnect_serial(self):
        if self.serial:
            self.serial.stop()
            self.serial.wait()
            self.serial = None
        self.is_connected = False
        self.connection_status.emit("Disconnected")

    def send_to_croc(self, data: bytes):
        """Send data to CROC (via router with 0x10 header)"""
        if self.serial and self.is_connected:
            self.route_lock.lock()
            try:
                self.serial.write(HEADER_CROC + data)
                self.last_target = 'croc'
            finally:
                self.route_lock.unlock()

    def send_to_stm(self, data: bytes):
        """Send data to STM32 (via router with 0x20 header)"""
        if self.serial and self.is_connected:
            self.route_lock.lock()
            try:
                self.serial.write(HEADER_STM + data)
                self.last_target = 'stm'
                self.log_text_received.emit(f"[TX → STM32] {data.decode('utf-8', errors='ignore').strip()}")
            finally:
                self.route_lock.unlock()

    def send_raw(self, data: bytes):
        """Send raw data without header (goes to CROC by default)"""
        if self.serial and self.is_connected:
            self.serial.write(data)

    def _on_data_received(self, data: bytes):
        """Handle incoming serial data"""
        self._rx_buffer.extend(data)
        self.raw_data_received.emit(data)
        
        # Process complete lines
        while b'\n' in self._rx_buffer:
            idx = self._rx_buffer.index(b'\n')
            line = bytes(self._rx_buffer[:idx+1])
            self._rx_buffer = self._rx_buffer[idx+1:]
            self._process_line(line)

    def _on_error(self, error_msg: str):
        self.log_text_received.emit(f"[ERROR] {error_msg}")
        self.connection_status.emit(f"Error: {error_msg}")

    def _on_opened(self, port: str):
        self.is_connected = True
        self.connection_status.emit(f"Connected: {port}")
        self.log_text_received.emit(f"Serial port opened: {port}")

    def _on_closed(self):
        self.is_connected = False
        self.connection_status.emit("Disconnected")
        self.log_text_received.emit("Serial port closed")

    def _process_line(self, line: bytes):
        """Process a complete line of data"""
        try:
            line_str = line.decode('utf-8', errors='ignore').strip()
        except:
            return
        
        if not line_str:
            return
        
        # =====================================================================
        # 1. Check STM32 telemetry
        # =====================================================================
        stm_match = self._stm_telemetry_regex.search(line_str)
        if stm_match:
            try:
                vcore = float(stm_match.group(1))
                vin = float(stm_match.group(2))
                iout = float(stm_match.group(3))
                ext_temp = float(stm_match.group(4))
                mcu_temp = float(stm_match.group(5))
                
                self._telemetry.update({
                    'vcore': vcore,
                    'vin': vin,
                    'iout': iout,
                    'ext_temp': ext_temp,
                    'mcu_temp': mcu_temp,
                })
                
                self.telemetry_received.emit(self._telemetry.copy())
                self.log_text_received.emit(
                    f"[STM32] Vc={vcore:.3f}V Vi={vin:.2f}V Io={iout:.3f}A T={ext_temp:.1f}°C"
                )
                return
            except ValueError:
                pass
        
        # =====================================================================
        # 2. Check FPGA telemetry (4 sensors, hex format)
        # =====================================================================
        sys_match = self._sys_telemetry_regex.search(line_str)
        if sys_match:
            try:
                # Temperature: hex value is temp*100 (e.g., 0x0FA0 = 4000 = 40.00°C)
                temp_hex = int(sys_match.group(1), 16)
                fpga_temp = temp_hex / 100.0
                
                # VCCINT: hex value in mV (e.g., 0x0352 = 850 = 0.850V)
                vccint_mv = int(sys_match.group(2), 16)
                vccint = vccint_mv / 1000.0
                
                # 4 sensor alarms
                alarm_f = int(sys_match.group(3), 16)
                alarm_rf = int(sys_match.group(4), 16)
                alarm_uart = int(sys_match.group(5), 16)
                alarm_obi_dmx = int(sys_match.group(6), 16)
                
                self._telemetry.update({
                    'fpga_temp': fpga_temp,
                    'vccint': vccint,
                    'alarm_f': alarm_f,
                    'alarm_rf': alarm_rf,
                    'alarm_dm': alarm_uart,
                    'alarm_obi_dmx': alarm_obi_dmx,
                })
                
                self.telemetry_received.emit(self._telemetry.copy())
                
                # Count alarms per sensor type
                count_f = bin(alarm_f).count('1')
                count_rf = bin(alarm_rf).count('1')
                count_uart = bin(alarm_uart).count('1')
                count_obi = bin(alarm_obi_dmx).count('1')
                total = count_f + count_rf + count_uart + count_obi
                
                sensor_data = {
                    'alarm_f': alarm_f,
                    'alarm_rf': alarm_rf,
                    'alarm_dm': alarm_uart,
                    'alarm_obi_dmx': alarm_obi_dmx,
                    'alarm_f_count': count_f,
                    'alarm_rf_count': count_rf,
                    'alarm_dm_count': count_uart,
                    'alarm_obi_count': count_obi,
                    'dut_temp': fpga_temp,
                    'dut_volt': vccint,
                }
                self.aging_data_received.emit(sensor_data)
                
                self.log_text_received.emit(
                    f"[FPGA] T={fpga_temp:.2f}°C VCCINT={vccint:.3f}V "
                    f"Alarms={total} (F={count_f}, RF={count_rf}, UART={count_uart}, OBI={count_obi})"
                )
                return
            except ValueError:
                pass
        
        # =====================================================================
        # 3. Check CROC firmware output (4 sensors)
        # =====================================================================
        sensor4_match = self._sensor_regex_4.search(line_str)
        if sensor4_match:
            try:
                alarm_f = int(sensor4_match.group(1), 16)
                alarm_rf = int(sensor4_match.group(2), 16)
                alarm_obi_dmx = int(sensor4_match.group(3), 16)  # OBI in firmware = OBI_DMX
                alarm_uart = int(sensor4_match.group(4), 16)     # UART in firmware
                
                self._telemetry.update({
                    'alarm_f': alarm_f,
                    'alarm_rf': alarm_rf,
                    'alarm_dm': alarm_uart,
                    'alarm_obi_dmx': alarm_obi_dmx,
                })
                
                count_f = bin(alarm_f).count('1')
                count_rf = bin(alarm_rf).count('1')
                count_uart = bin(alarm_uart).count('1')
                count_obi = bin(alarm_obi_dmx).count('1')
                total = count_f + count_rf + count_uart + count_obi
                
                sensor_data = {
                    'alarm_f': alarm_f,
                    'alarm_rf': alarm_rf,
                    'alarm_dm': alarm_uart,
                    'alarm_obi_dmx': alarm_obi_dmx,
                    'alarm_f_count': count_f,
                    'alarm_rf_count': count_rf,
                    'alarm_dm_count': count_uart,
                    'alarm_obi_count': count_obi,
                    'dut_temp': self._telemetry.get('fpga_temp', 0),
                    'dut_volt': self._telemetry.get('vccint', 0),
                }
                self.aging_data_received.emit(sensor_data)
                
                self.log_text_received.emit(
                    f"[AGING] Total={total} (F={count_f}, RF={count_rf}, UART={count_uart}, OBI={count_obi})"
                )
                self.log_text_received.emit(
                    f"  F=0x{alarm_f:08X} RF=0x{alarm_rf:08X} "
                    f"UART=0x{alarm_uart:08X} OBI=0x{alarm_obi_dmx:08X}"
                )
                return
            except ValueError:
                pass
        
        # =====================================================================
        # 4. Check CROC firmware output (2 sensors - legacy)
        # =====================================================================
        sensor2_match = self._sensor_regex_2.search(line_str)
        if sensor2_match:
            try:
                alarm_f = int(sensor2_match.group(1), 16)
                alarm_rf = int(sensor2_match.group(2), 16)
                
                self._telemetry.update({
                    'alarm_f': alarm_f,
                    'alarm_rf': alarm_rf,
                })
                
                count_f = bin(alarm_f).count('1')
                count_rf = bin(alarm_rf).count('1')
                total = count_f + count_rf
                
                sensor_data = {
                    'alarm_f': alarm_f,
                    'alarm_rf': alarm_rf,
                    'alarm_dm': 0,
                    'alarm_obi_dmx': 0,
                    'alarm_f_count': count_f,
                    'alarm_rf_count': count_rf,
                    'alarm_dm_count': 0,
                    'alarm_obi_count': 0,
                    'dut_temp': self._telemetry.get('fpga_temp', 0),
                    'dut_volt': self._telemetry.get('vccint', 0),
                }
                self.aging_data_received.emit(sensor_data)
                
                self.log_text_received.emit(
                    f"[AGING] Total={total} (F={count_f}, RF={count_rf})"
                )
                return
            except ValueError:
                pass
        
        # =====================================================================
        # 5. Default: Log as CROC output
        # =====================================================================
        if line_str and not line_str.startswith('$'):
            self.log_text_received.emit(f"[CROC] {line_str}")

    def get_telemetry(self):
        """Return current telemetry data"""
        return self._telemetry.copy()
    
    def get_sensor_counts(self):
        """Return alarm counts for all 4 sensor types"""
        return {
            'f': bin(self._telemetry.get('alarm_f', 0)).count('1'),
            'rf': bin(self._telemetry.get('alarm_rf', 0)).count('1'),
            'uart': bin(self._telemetry.get('alarm_dm', 0)).count('1'),
            'obi_dmx': bin(self._telemetry.get('alarm_obi_dmx', 0)).count('1'),
        }
