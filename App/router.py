# -*- coding: utf-8 -*-
"""
UART Router for CROC FPGA System - 4 Sensor Types

Handles bidirectional communication and parses:
- CROC firmware output: All 4 sensor types
- STM32 telemetry: Power supply data
- FPGA System Monitor: Temperature and voltage

Sensor Output Formats Supported:
  1. Extended (4 sensors): "F: 0x<hex> | RF: 0x<hex> | OBI: 0x<hex> | UART: 0x<hex>"
  2. Basic (2 sensors): "F: 0x<hex> | RF: 0x<hex>"
  3. System telemetry: "$SYS,FT,XX.XX,VI,X.XXX,AF,XXXXXXXX,AR,XXXXXXXX,AD,XXXXXXXX,AO,XXXXXXXX*CS"
"""

from PySide6.QtCore import QObject, Signal, Slot, QMutex
from serial_thread import SerialThread
from protocol import ProtocolParser
import config
import time
import re


HEADER_CROC = b'\x10'
HEADER_STM  = b'\x20'


class UARTRouter(QObject):
    """
    Central UART routing and parsing manager with 4-sensor support.
    """
    
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
        
        # Latest telemetry values (all 4 sensor types)
        self._telemetry = {
            'vcore': 0.0,
            'vin': 0.0,
            'iout': 0.0,
            'ext_temp': 0.0,
            'mcu_temp': 0.0,
            'fpga_temp': 0.0,
            'vccint': 0.0,
            'alarm_f': 0,
            'alarm_rf': 0,
            'alarm_dm': 0,
            'alarm_obi_dmx': 0,
        }
        
        # =====================================================================
        # REGEX PATTERNS for parsing sensor data
        # =====================================================================
        
        # Pattern 1: FULL 4-sensor format from helloworld.c
        # "F: 0x<hex> | RF: 0x<hex> | OBI: 0x<hex> | UART: 0x<hex>"
        self._sensor_regex_full = re.compile(
            r'F:\s*0x([0-9A-Fa-f]+)\s*\|\s*'
            r'RF:\s*0x([0-9A-Fa-f]+)\s*\|\s*'
            r'OBI:\s*0x([0-9A-Fa-f]+)\s*\|\s*'
            r'UART:\s*0x([0-9A-Fa-f]+)',
            re.IGNORECASE
        )
        
        # Pattern 2: Legacy 2-sensor format (backwards compatibility)
        # "F: 0x<hex> | RF: 0x<hex>"
        self._sensor_regex_basic = re.compile(
            r'F:\s*0x([0-9A-Fa-f]+)\s*\|\s*RF:\s*0x([0-9A-Fa-f]+)',
            re.IGNORECASE
        )
        
        # Pattern 3: STM32 telemetry "$TEL,Vc,X.XXX,Vi,X.XXX,Io,X.XXX,Et,XX.X,Mt,XX.X*CS"
        self._stm_telemetry_regex = re.compile(
            r'\$TEL,Vc,([0-9.]+),Vi,([0-9.]+),Io,([0-9.]+),Et,([0-9.]+),Mt,([0-9.]+)\*([0-9A-Fa-f]{2})',
            re.IGNORECASE
        )
        
        # Pattern 4: FPGA system telemetry (4 sensors)
        # "$SYS,FT,XX.XX,VI,X.XXX,AF,XXXXXXXX,AR,XXXXXXXX,AD,XXXXXXXX,AO,XXXXXXXX*CS"
        self._sys_telemetry_regex = re.compile(
            r'\$SYS,FT,([0-9.]+),VI,([0-9.]+),'
            r'AF,([0-9A-Fa-f]+),AR,([0-9A-Fa-f]+),'
            r'AD,([0-9A-Fa-f]+),AO,([0-9A-Fa-f]+)\*([0-9A-Fa-f]{2})',
            re.IGNORECASE
        )

    def connect_serial(self, port: str = None, baud: int = None):
        """Connect to the FPGA serial port."""
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
        """Disconnect from the serial port."""
        if self.serial:
            self.serial.stop()
            self.serial.wait()
            self.serial = None
            self.is_connected = False

    def is_serial_connected(self) -> bool:
        """Check if serial port is connected."""
        return self.is_connected and self.serial is not None

    def _write_raw(self, data: bytes):
        """Write raw bytes to serial port."""
        if self.serial and self.is_connected:
            self.serial.write_data(data)

    def _send_guarded(self, target_header: bytes, payload: bytes):
        """Send data with routing header and dead-time management."""
        self.route_lock.lock()
        try:
            if self.last_target != target_header:
                time.sleep(self.ROUTER_TIMEOUT_S)
                self.last_target = target_header
            
            packet = target_header + payload
            self._write_raw(packet)
        finally:
            self.route_lock.unlock()

    def send_to_stm(self, payload: bytes):
        """Send data to STM32 with header 0x20."""
        self._send_guarded(HEADER_STM, payload)

    def send_to_croc(self, payload: bytes):
        """Send data to CROC with header 0x10."""
        self._send_guarded(HEADER_CROC, payload)

    def send_text_to_croc(self, text: str):
        """Send text command to CROC (adds newline)."""
        payload = (text + "\n").encode('utf-8')
        self.send_to_croc(payload)

    @Slot(bytes)
    def _on_data_received(self, data: bytes):
        """Process received serial data."""
        self.raw_data_received.emit(data)
        self._rx_buffer.extend(data)
        self._process_buffer()

    def _process_buffer(self):
        """Process the RX buffer, extracting complete lines."""
        while True:
            newline_idx = -1
            for i, byte in enumerate(self._rx_buffer):
                if byte == 0x0A:
                    newline_idx = i
                    break
            
            if newline_idx >= 0:
                line_bytes = bytes(self._rx_buffer[:newline_idx])
                del self._rx_buffer[:newline_idx + 1]
                self._process_line(line_bytes)
                continue
            
            if len(self._rx_buffer) > 0:
                first_byte = self._rx_buffer[0]
                
                if not (32 <= first_byte <= 126) and first_byte not in [0x0A, 0x0D]:
                    events = self.parser.feed(bytes(self._rx_buffer))
                    if events:
                        self._rx_buffer.clear()
                        for evt in events:
                            self._handle_protocol_event(evt)
                        continue
            
            break
        
        if len(self._rx_buffer) > 4096:
            self._rx_buffer = self._rx_buffer[-1024:]

    def _process_line(self, line_bytes: bytes):
        """Process a complete text line from CROC/STM32."""
        try:
            line_str = line_bytes.decode('utf-8', errors='ignore').strip()
        except:
            return
        
        if not line_str:
            return
        
        # =====================================================================
        # 1. Check for STM32 telemetry: $TEL,...*CS
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
        # 2. Check for FPGA system telemetry: $SYS,...*CS (4 sensors)
        # =====================================================================
        sys_match = self._sys_telemetry_regex.search(line_str)
        if sys_match:
            try:
                fpga_temp = float(sys_match.group(1))
                vccint = float(sys_match.group(2))
                alarm_f = int(sys_match.group(3), 16)
                alarm_rf = int(sys_match.group(4), 16)
                alarm_dm = int(sys_match.group(5), 16)
                alarm_obi = int(sys_match.group(6), 16)
                
                self._telemetry.update({
                    'fpga_temp': fpga_temp,
                    'vccint': vccint,
                    'alarm_f': alarm_f,
                    'alarm_rf': alarm_rf,
                    'alarm_dm': alarm_dm,
                    'alarm_obi_dmx': alarm_obi,
                })
                
                self.telemetry_received.emit(self._telemetry.copy())
                
                # Also emit as aging data
                sensor_data = {
                    'alarm_f': alarm_f,
                    'alarm_rf': alarm_rf,
                    'alarm_dm': alarm_dm,
                    'alarm_obi_dmx': alarm_obi,
                    'alarm_f_count': bin(alarm_f).count('1'),
                    'alarm_rf_count': bin(alarm_rf).count('1'),
                    'alarm_dm_count': bin(alarm_dm).count('1'),
                    'alarm_obi_count': bin(alarm_obi).count('1'),
                    'dut_temp': fpga_temp,
                    'dut_volt': vccint,
                    'dut_slack': sum([
                        bin(alarm_f).count('1'),
                        bin(alarm_rf).count('1'),
                        bin(alarm_dm).count('1'),
                        bin(alarm_obi).count('1')
                    ]),
                }
                self.aging_data_received.emit(sensor_data)
                
                total_alarms = sensor_data['dut_slack']
                self.log_text_received.emit(
                    f"[FPGA] T={fpga_temp:.2f}°C VCCINT={vccint:.3f}V "
                    f"Alarms={total_alarms} (F={sensor_data['alarm_f_count']}, "
                    f"RF={sensor_data['alarm_rf_count']}, "
                    f"DM={sensor_data['alarm_dm_count']}, "
                    f"OBI={sensor_data['alarm_obi_count']})"
                )
                return
            except ValueError:
                pass
        
        # =====================================================================
        # 3. Check for FULL 4-sensor format from firmware
        # "F: 0x... | RF: 0x... | OBI: 0x... | UART: 0x..."
        # =====================================================================
        match_full = self._sensor_regex_full.search(line_str)
        if match_full:
            try:
                alarm_f = int(match_full.group(1), 16)
                alarm_rf = int(match_full.group(2), 16)
                alarm_obi = int(match_full.group(3), 16)
                alarm_uart = int(match_full.group(4), 16)
                
                sensor_data = {
                    'alarm_f': alarm_f,
                    'alarm_rf': alarm_rf,
                    'alarm_dm': alarm_obi,      # Map OBI → DM for consistency
                    'alarm_obi_dmx': alarm_uart, # Map UART → OBI_DMX
                    'alarm_f_count': bin(alarm_f).count('1'),
                    'alarm_rf_count': bin(alarm_rf).count('1'),
                    'alarm_dm_count': bin(alarm_obi).count('1'),
                    'alarm_obi_count': bin(alarm_uart).count('1'),
                    'dut_temp': self._telemetry.get('fpga_temp', 0.0),
                    'dut_volt': self._telemetry.get('vccint', 0.0),
                    'dut_slack': sum([
                        bin(alarm_f).count('1'),
                        bin(alarm_rf).count('1'),
                        bin(alarm_obi).count('1'),
                        bin(alarm_uart).count('1')
                    ]),
                }
                
                # Update telemetry alarms
                self._telemetry.update({
                    'alarm_f': alarm_f,
                    'alarm_rf': alarm_rf,
                    'alarm_dm': alarm_obi,
                    'alarm_obi_dmx': alarm_uart
                })
                
                self.aging_data_received.emit(sensor_data)
                return
            except ValueError:
                pass
        
        # =====================================================================
        # 4. Check for BASIC 2-sensor format (backwards compatibility)
        # "F: 0x... | RF: 0x..."
        # =====================================================================
        match_basic = self._sensor_regex_basic.search(line_str)
        if match_basic:
            try:
                alarm_f = int(match_basic.group(1), 16)
                alarm_rf = int(match_basic.group(2), 16)
                
                sensor_data = {
                    'alarm_f': alarm_f,
                    'alarm_rf': alarm_rf,
                    'alarm_dm': 0,
                    'alarm_obi_dmx': 0,
                    'alarm_f_count': bin(alarm_f).count('1'),
                    'alarm_rf_count': bin(alarm_rf).count('1'),
                    'alarm_dm_count': 0,
                    'alarm_obi_count': 0,
                    'dut_temp': self._telemetry.get('fpga_temp', 0.0),
                    'dut_volt': self._telemetry.get('vccint', 0.0),
                    'dut_slack': bin(alarm_f).count('1') + bin(alarm_rf).count('1'),
                }
                
                self._telemetry.update({
                    'alarm_f': alarm_f,
                    'alarm_rf': alarm_rf
                })
                
                self.aging_data_received.emit(sensor_data)
                return
            except ValueError:
                pass
        
        # =====================================================================
        # 5. Regular text line (not telemetry/sensor data)
        # =====================================================================
        if not line_str.startswith('$'):
            self.log_text_received.emit(f"[CROC] {line_str}")

    def _handle_protocol_event(self, evt):
        """Handle parsed protocol events."""
        evt_type = evt[0]
        
        if evt_type in ('ok', 'error'):
            self.stm_frame_received.emit(evt)
        elif evt_type == 'line':
            raw_msg = evt[1]
            clean_msg = "".join(c for c in raw_msg if c.isprintable()).strip()
            if clean_msg:
                self.log_text_received.emit(f"[RX] {clean_msg}")

    @Slot(str)
    def _on_opened(self, port: str):
        self.is_connected = True
        self.connection_status.emit(f"Connected: {port}")
        self.log_message.emit(f"Serial port opened: {port}")

    @Slot()
    def _on_closed(self):
        self.is_connected = False
        self.connection_status.emit("Disconnected")
        self.log_message.emit("Serial port closed")

    @Slot(str)
    def _on_error(self, msg: str):
        self.log_message.emit(f"Serial error: {msg}")
