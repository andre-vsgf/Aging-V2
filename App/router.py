# -*- coding: utf-8 -*-
"""
UART Router for CROC FPGA System - FINAL CORRECTED VERSION
===========================================================

Handles bidirectional communication and parses:
- CROC firmware output: All 4 sensor types
- STM32 telemetry: Power supply data  
- FPGA System Monitor: Temperature and voltage via $SYS

SENSOR TYPES (4 fixed):
- F (AM sensors) - 32 bits
- RF (LF sensors) - 32 bits
- UART sensors - 32 bits
- OBI_DMX sensors - 32 bits

CRITICAL FIX: $SYS regex now correctly parses HEX format from RTL:
  $SYS,FT,XXXX,VI,XXXX,AF,XXXXXXXX,AR,XXXXXXXX,AU,XXXXXXXX,AO,XXXXXXXX*CS
  Where FT=temp*100 (hex), VI=mV (hex), AF/AR/AU/AO are alarm registers (hex)
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
        
        # Latest telemetry values (all 4 sensor types)
        self._telemetry = {
            # STM32 data
            'vcore': 0.0,
            'vin': 0.0,
            'iout': 0.0,
            'ext_temp': 0.0,
            'mcu_temp': 0.0,
            # FPGA System Monitor data
            'fpga_temp': 0.0,
            'vccint': 0.0,
            # 4 sensor alarms
            'alarm_f': 0,
            'alarm_rf': 0,
            'alarm_uart': 0,
            'alarm_obi_dmx': 0,
        }
        
        # =====================================================================
        # REGEX PATTERNS
        # =====================================================================
        
        # Pattern 1: FULL 4-sensor format from helloworld.c firmware
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
            r'F:\s*0x([0-9A-Fa-f]+)\s*\|\s*RF:\s*0x([0-9A-Fa-f]+)(?:\s*$|\s*\r)',
            re.IGNORECASE
        )
        
        # Pattern 3: STM32 telemetry (decimal format)
        # "$TEL,Vc,X.XXX,Vi,X.XXX,Io,X.XXX,Et,XX.X,Mt,XX.X*CS"
        self._stm_telemetry_regex = re.compile(
            r'\$TEL,Vc,([0-9.]+),Vi,([0-9.]+),Io,([0-9.]+),Et,([0-9.-]+),Mt,([0-9.-]+)\*([0-9A-Fa-f]{2})',
            re.IGNORECASE
        )
        
        # Pattern 4: FPGA system telemetry - HEX FORMAT (CRITICAL FIX!)
        # "$SYS,FT,XXXX,VI,XXXX,AF,XXXXXXXX,AR,XXXXXXXX,AU,XXXXXXXX,AO,XXXXXXXX*CS"
        # FT = temperature * 100 in hex (e.g., 0x0FA0 = 4000 = 40.00°C)
        # VI = voltage in mV in hex (e.g., 0x0352 = 850 = 0.850V)
        # AF/AR/AU/AO = alarm registers in hex (8 digits each)
        #
        # FLEXIBLE REGEX: Allows 1-4 digits for FT/VI and 1-8 digits for alarms
        # This handles cases where leading zeros might be omitted
        self._sys_telemetry_regex = re.compile(
            r'\$SYS,FT,([0-9A-Fa-f]{1,4}),VI,([0-9A-Fa-f]{1,4}),'
            r'AF,([0-9A-Fa-f]{1,8}),AR,([0-9A-Fa-f]{1,8}),'
            r'AU,([0-9A-Fa-f]{1,8}),AO,([0-9A-Fa-f]{1,8})\*([0-9A-Fa-f]{2})',
            re.IGNORECASE
        )
        
        # Debug flag - set to True to log all $SYS messages
        self._debug_telemetry = True

    # =========================================================================
    # Connection Management
    # =========================================================================
    
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
        self.connection_status.emit("Disconnected")

    def is_serial_connected(self) -> bool:
        """Check if serial port is connected."""
        return self.is_connected and self.serial is not None

    # =========================================================================
    # Data Transmission
    # =========================================================================
    
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

    # =========================================================================
    # Data Reception and Parsing
    # =========================================================================

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
            
            # Check for binary protocol data
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
        
        # Prevent buffer overflow
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
        # 2. Check for FPGA system telemetry: $SYS,...*CS (HEX FORMAT)
        # CRITICAL: This is where temperature and VCCINT come from!
        # =====================================================================
        
        # Debug: Log any line starting with $SYS
        if line_str.startswith('$SYS') and self._debug_telemetry:
            self.log_text_received.emit(f"[DEBUG] Raw $SYS: {line_str}")
        
        sys_match = self._sys_telemetry_regex.search(line_str)
        if sys_match:
            try:
                # Parse HEX values
                temp_hex = int(sys_match.group(1), 16)  # temp * 100
                vccint_hex = int(sys_match.group(2), 16)  # mV
                
                # Convert to real values
                fpga_temp = temp_hex / 100.0  # e.g., 4000 -> 40.00°C
                vccint = vccint_hex / 1000.0  # e.g., 850 -> 0.850V
                
                # Parse alarm registers (already hex)
                alarm_f = int(sys_match.group(3), 16)
                alarm_rf = int(sys_match.group(4), 16)
                alarm_uart = int(sys_match.group(5), 16)  # AU = UART
                alarm_obi_dmx = int(sys_match.group(6), 16)  # AO = OBI_DMX
                
                # Update telemetry storage
                self._telemetry.update({
                    'fpga_temp': fpga_temp,
                    'vccint': vccint,
                    'alarm_f': alarm_f,
                    'alarm_rf': alarm_rf,
                    'alarm_uart': alarm_uart,
                    'alarm_obi_dmx': alarm_obi_dmx,
                })
                
                self.telemetry_received.emit(self._telemetry.copy())
                
                # Build and emit aging data
                count_f = bin(alarm_f).count('1')
                count_rf = bin(alarm_rf).count('1')
                count_uart = bin(alarm_uart).count('1')
                count_obi = bin(alarm_obi_dmx).count('1')
                total_alarms = count_f + count_rf + count_uart + count_obi
                sensor_data = {
                    # Alarms (4 fixed registers)
                    'alarm_f': alarm_f,
                    'alarm_rf': alarm_rf,
                    'alarm_uart': alarm_uart,
                    'alarm_obi_dmx': alarm_obi_dmx,
                    'alarm_f_count': count_f,
                    'alarm_rf_count': count_rf,
                    'alarm_uart_count': count_uart,
                    'alarm_obi_count': count_obi,

                    # Environmental / telemetry (explicit keys expected by logger/GUI)
                    'fpga_temp': fpga_temp,
                    'vccint': vccint,
                    'vcore': self._telemetry.get('vcore', 0.0),
                    'vin': self._telemetry.get('vin', 0.0),
                    'iout': self._telemetry.get('iout', 0.0),
                    'ext_temp': self._telemetry.get('ext_temp', 0.0),
                    'mcu_temp': self._telemetry.get('mcu_temp', 0.0),

                    # Legacy aliases used by some older widgets/exports
                    'dut_temp': fpga_temp,
                    'dut_volt': vccint,
                    'dut_slack': total_alarms,
                }
                self.aging_data_received.emit(sensor_data)
                
                self.log_text_received.emit(
                    f"[FPGA] T={fpga_temp:.2f}°C VCCINT={vccint:.3f}V "
                    f"Alarms={total_alarms} (F={count_f}, RF={count_rf}, "
                    f"UART={count_uart}, OBI={count_obi})"
                )
                return
            except ValueError as e:
                self.log_text_received.emit(f"[ERROR] Failed to parse $SYS: {e}")
        
        # =====================================================================
        # 3. Check for FULL 4-sensor format from firmware
        # "F: 0x... | RF: 0x... | OBI: 0x... | UART: 0x..."
        # =====================================================================
        match_full = self._sensor_regex_full.search(line_str)
        if match_full:
            try:
                alarm_f = int(match_full.group(1), 16)
                alarm_rf = int(match_full.group(2), 16)
                alarm_obi_dmx = int(match_full.group(3), 16)  # OBI in firmware
                alarm_uart = int(match_full.group(4), 16)     # UART in firmware
                
                count_f = bin(alarm_f).count('1')
                count_rf = bin(alarm_rf).count('1')
                count_uart = bin(alarm_uart).count('1')
                count_obi = bin(alarm_obi_dmx).count('1')
                total_alarms = count_f + count_rf + count_uart + count_obi
                
                sensor_data = {
                    # Alarms (4 fixed registers)
                    'alarm_f': alarm_f,
                    'alarm_rf': alarm_rf,
                    'alarm_uart': alarm_uart,
                    'alarm_obi_dmx': alarm_obi_dmx,
                    'alarm_f_count': count_f,
                    'alarm_rf_count': count_rf,
                    'alarm_uart_count': count_uart,
                    'alarm_obi_count': count_obi,

                    # Environmental / telemetry (explicit keys expected by logger/GUI)
                    'fpga_temp': self._telemetry.get('fpga_temp', 0.0),
                    'vccint': self._telemetry.get('vccint', 0.0),
                    'vcore': self._telemetry.get('vcore', 0.0),
                    'vin': self._telemetry.get('vin', 0.0),
                    'iout': self._telemetry.get('iout', 0.0),
                    'ext_temp': self._telemetry.get('ext_temp', 0.0),
                    'mcu_temp': self._telemetry.get('mcu_temp', 0.0),

                    # Legacy aliases used by some older widgets/exports
                    'dut_temp': self._telemetry.get('fpga_temp', 0.0),
                    'dut_volt': self._telemetry.get('vccint', 0.0),
                    'dut_slack': total_alarms,
                }
                
                # Update telemetry alarms
                self._telemetry.update({
                    'alarm_f': alarm_f,
                    'alarm_rf': alarm_rf,
                    'alarm_uart': alarm_uart,
                    'alarm_obi_dmx': alarm_obi_dmx,
                })
                
                self.aging_data_received.emit(sensor_data)
                
                self.log_text_received.emit(
                    f"[AGING] Total={total_alarms} (F={count_f}, RF={count_rf}, "
                    f"UART={count_uart}, OBI={count_obi})"
                )
                return
            except ValueError:
                pass
        # =====================================================================
        # 4. Legacy 2-sensor format (DEPRECATED)
        # We intentionally do not parse "F: 0x.. | RF: 0x.." anymore. This prevents
        # mixing old firmware output with the fixed 4-sensor log/telemetry model.
        # =====================================================================
        match_basic = self._sensor_regex_basic.search(line_str) if hasattr(self, "_sensor_regex_basic") else None
        if match_basic:
            self.log_text_received.emit("[WARN] Ignoring legacy 2-sensor alarm frame. Update firmware to 4-sensor format.")
            return
        
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

    # =========================================================================
    # Connection Callbacks
    # =========================================================================

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

    # =========================================================================
    # Utility Methods
    # =========================================================================

    def get_telemetry(self) -> dict:
        """Return current telemetry data."""
        return self._telemetry.copy()
    
    def get_sensor_counts(self) -> dict:
        """Return alarm counts for all 4 sensor types."""
        return {
            'f': bin(self._telemetry.get('alarm_f', 0)).count('1'),
            'rf': bin(self._telemetry.get('alarm_rf', 0)).count('1'),
            'uart': bin(self._telemetry.get('alarm_uart', 0)).count('1'),
            'obi_dmx': bin(self._telemetry.get('alarm_obi_dmx', 0)).count('1'),
        }
