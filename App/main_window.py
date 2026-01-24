# -*- coding: utf-8 -*-
"""
Main Window for CROC FPGA Monitor - INTEGRATED VERSION

Features:
- Visual sensor status grid (4 registers)
- Aging analysis with auto-program on alarm
- Smart logging for long experiments (weeks)
- Telemetry graphs
- FPGA programming controls
- STM32 voltage control

UPDATES:
- Integrated SmartLogger for efficient long-term logging
- Integrated ExperimentController for auto-program
- Support for all 4 sensor types (F, RF, UART, OBI)
"""

import os
import time
from datetime import datetime
from PySide6.QtWidgets import (
    QMainWindow, QWidget, QVBoxLayout, QHBoxLayout, QGridLayout,
    QPushButton, QGroupBox, QLabel, QTextEdit, QLineEdit,
    QDoubleSpinBox, QComboBox, QFileDialog, QProgressBar,
    QTabWidget, QSplitter, QFrame, QSpinBox, QCheckBox,
    QMessageBox, QSizePolicy
)
from PySide6.QtCore import Qt, Signal, Slot, QTimer, QThread
from PySide6.QtGui import QFont, QTextCursor

import config
from router import UARTRouter
from fpga_manager import FPGAManager, BitstreamManager
from sensor_widget import SensorVisualizationWidget
from telemetry_widget import TelemetryWidget, TelemetryData
from serial_thread import get_available_ports
from protocol import (
    build_voltage_command, build_page_command, build_message_command,
    compute_crc16_modbus, CRC_ENDIAN
)

# NEW: Import smart logging and experiment controller
from smart_logger import SmartLogger
from aging_analysis_widget_v2 import AgingAnalysisWidgetV2


class MainWindow(QMainWindow):
    """Main application window with integrated smart logging."""
    
    def __init__(self):
        super().__init__()
        self.setWindowTitle("CROC FPGA Sensor Monitor & Programmer")
        self.resize(1400, 900)
        
        # Core components
        self.router = UARTRouter()
        self.fpga_manager = FPGAManager()
        self.bitstream_manager = BitstreamManager()
        
        # State - Tracking all 4 sensor types
        self._last_alarm_f = 0
        self._last_alarm_rf = 0
        self._last_alarm_uart = 0
        self._last_alarm_obi_dmx = 0
        
        # Experiment start time
        self._experiment_start_time = None
        
        # Initialize Smart Logger for efficient long-term logging
        self._init_smart_logger()
        
        # Build UI
        self._init_ui()
        self._connect_signals()
        
        # Timer for periodic updates
        self.update_timer = QTimer()
        self.update_timer.timeout.connect(self._periodic_update)
        self.update_timer.start(1000)
        
        # Auto-connect if port is configured
        QTimer.singleShot(500, self._auto_connect)
    
    def _init_smart_logger(self):
        """Initialize the smart logger for efficient data recording."""
        log_folder = os.path.join(os.getcwd(), "experiment_logs")
        experiment_name = f"croc_aging_{datetime.now().strftime('%Y%m%d')}"
        
        self.smart_logger = SmartLogger(
            log_folder=log_folder,
            experiment_name=experiment_name,
            mode="adaptive",          # Log more during changes, less when stable
            normal_interval_sec=60.0,  # Log every 60s when stable
            change_interval_sec=1.0,   # Log every 1s during changes
            summary_interval_sec=300.0 # Summary every 5 minutes
        )
        
        # Record experiment start
        self._experiment_start_time = datetime.now()
        self.smart_logger.log_event("experiment_start", {
            "timestamp": self._experiment_start_time.isoformat(),
            "app_version": "2.0-smart"
        })

    def _init_ui(self):
        """Initialize the user interface."""
        central = QWidget()
        self.setCentralWidget(central)
        
        main_layout = QVBoxLayout(central)
        main_layout.setContentsMargins(10, 10, 10, 10)
        main_layout.setSpacing(10)
        
        # Top: Status bar
        self._create_status_bar(main_layout)
        
        # Main content: Tab widget with different views
        self.main_tabs = QTabWidget()
        
        # Tab 1: Sensors + Controls
        sensors_tab = self._create_sensors_tab()
        self.main_tabs.addTab(sensors_tab, "🎛 Sensors & Control")
        
        # Tab 2: Aging Analysis (V2 with auto-program)
        self.aging_widget = AgingAnalysisWidgetV2()
        self.main_tabs.addTab(self.aging_widget, "📈 Aging Analysis")
        
        # Tab 3: Telemetry Graphs
        telemetry_tab = self._create_telemetry_tab()
        self.main_tabs.addTab(telemetry_tab, "📊 Telemetry")
        
        # Tab 4: Communication Log
        log_tab = self._create_log_tab()
        self.main_tabs.addTab(log_tab, "📋 Log")
        
        main_layout.addWidget(self.main_tabs, 1)
    
    def _periodic_update(self):
        """Periodic updates for time-dependent displays."""
        self.aging_widget.update_display()
    
    def _create_sensors_tab(self) -> QWidget:
        """Create the sensors and control tab."""
        tab = QWidget()
        layout = QHBoxLayout(tab)
        
        # Left: Sensor visualization
        left_panel = QWidget()
        left_layout = QVBoxLayout(left_panel)
        left_layout.setContentsMargins(0, 0, 0, 0)
        
        self.sensor_widget = SensorVisualizationWidget()
        left_layout.addWidget(self.sensor_widget)
        
        # Control tabs below sensors
        self.control_tabs = QTabWidget()
        self._create_fpga_tab()
        self._create_stm32_tab()
        self._create_settings_tab()
        left_layout.addWidget(self.control_tabs)
        
        layout.addWidget(left_panel, 2)
        
        # Right container
        right_container = QWidget()
        right_layout = QVBoxLayout(right_container)
        right_layout.setContentsMargins(0, 0, 0, 0)
        right_layout.setSpacing(10)

        # Quick Info Panel
        quick_info = self._create_quick_info_panel()
        right_layout.addWidget(quick_info)

        # Reset Button
        self.btn_reset_fpga = QPushButton("⚠️ RESET FPGA (VIO)")
        self.btn_reset_fpga.setMinimumHeight(45)
        self.btn_reset_fpga.setToolTip("Triggers a soft reset via VIO 'vio_reset' probe")
        self.btn_reset_fpga.setStyleSheet("""
            QPushButton {
                background-color: #d32f2f;
                color: white;
                font-weight: bold;
                font-size: 11pt;
                border: 1px solid #b71c1c;
                border-radius: 5px;
            }
            QPushButton:hover { background-color: #f44336; }
            QPushButton:pressed { background-color: #b71c1c; }
        """)
        self.btn_reset_fpga.clicked.connect(self._reset_fpga_action)
        right_layout.addWidget(self.btn_reset_fpga)
        
        # Logging status
        log_status = self._create_logging_status_panel()
        right_layout.addWidget(log_status)
        
        right_layout.addStretch()
        
        layout.addWidget(right_container, 1)
        
        return tab
    
    def _create_logging_status_panel(self) -> QWidget:
        """Create a panel showing logging status."""
        panel = QGroupBox("📊 Logging Status")
        layout = QVBoxLayout(panel)
        
        self.lbl_log_mode = QLabel(f"Mode: {self.smart_logger.mode.upper()}")
        self.lbl_log_mode.setStyleSheet("color: #4fc3f7;")
        layout.addWidget(self.lbl_log_mode)
        
        self.lbl_log_rows = QLabel("Rows: 0")
        layout.addWidget(self.lbl_log_rows)
        
        self.lbl_log_size = QLabel("Size: 0 MB")
        layout.addWidget(self.lbl_log_size)
        
        self.lbl_log_events = QLabel("Events: 0")
        layout.addWidget(self.lbl_log_events)
        
        # Update timer for logging stats
        self.log_stats_timer = QTimer()
        self.log_stats_timer.timeout.connect(self._update_logging_stats)
        self.log_stats_timer.start(5000)  # Update every 5 seconds
        
        return panel
    
    def _update_logging_stats(self):
        """Update the logging statistics display."""
        stats = self.smart_logger.get_statistics()
        self.lbl_log_rows.setText(f"Rows: {stats['rows_logged']:,}")
        self.lbl_log_size.setText(f"Size: {stats['total_size_mb']:.2f} MB")
        self.lbl_log_events.setText(f"Events: {stats['events_logged']}")
    
    def _create_telemetry_tab(self) -> QWidget:
        """Create the telemetry graphs tab."""
        self.telemetry_widget = TelemetryWidget()
        return self.telemetry_widget
    
    def _create_log_tab(self) -> QWidget:
        """Create the communication log tab."""
        return self._create_log_panel()
    
    def _create_quick_info_panel(self) -> QWidget:
        """Create a quick info panel showing current values."""
        panel = QGroupBox("Quick Status")
        layout = QVBoxLayout(panel)
        
        grid = QGridLayout()
        
        # STM32 values
        grid.addWidget(QLabel("STM32 Power:"), 0, 0, 1, 2)
        
        self.lbl_vcore = QLabel("Vcore: ---")
        self.lbl_vcore.setStyleSheet("color: #4fc3f7;")
        grid.addWidget(self.lbl_vcore, 1, 0)
        
        self.lbl_vin = QLabel("Vin: ---")
        self.lbl_vin.setStyleSheet("color: #ffc107;")
        grid.addWidget(self.lbl_vin, 1, 1)
        
        self.lbl_iout = QLabel("Iout: ---")
        self.lbl_iout.setStyleSheet("color: #ff5722;")
        grid.addWidget(self.lbl_iout, 2, 0)
        
        self.lbl_ext_temp = QLabel("Ext T: ---")
        self.lbl_ext_temp.setStyleSheet("color: #4caf50;")
        grid.addWidget(self.lbl_ext_temp, 2, 1)
        
        # FPGA values
        grid.addWidget(QLabel("FPGA Monitor:"), 3, 0, 1, 2)
        
        self.lbl_fpga_temp = QLabel("FPGA T: ---")
        self.lbl_fpga_temp.setStyleSheet("color: #e91e63;")
        grid.addWidget(self.lbl_fpga_temp, 4, 0)
        
        self.lbl_vccint = QLabel("VCCINT: ---")
        self.lbl_vccint.setStyleSheet("color: #9c27b0;")
        grid.addWidget(self.lbl_vccint, 4, 1)
        
        # Power calculation
        self.lbl_power = QLabel("Power: ---")
        self.lbl_power.setStyleSheet("font-weight: bold; color: #fff;")
        grid.addWidget(self.lbl_power, 5, 0, 1, 2)
        
        layout.addLayout(grid)
        layout.addStretch()
        
        return panel

    def _create_status_bar(self, parent_layout):
        """Create the status bar at the top."""
        status_frame = QFrame()
        status_frame.setFrameShape(QFrame.StyledPanel)
        status_frame.setStyleSheet("background-color: #252526; padding: 5px;")
        
        status_layout = QHBoxLayout(status_frame)
        status_layout.setContentsMargins(10, 5, 10, 5)
        
        # Connection status
        self.lbl_connection = QLabel("● Disconnected")
        self.lbl_connection.setStyleSheet("color: #dc3545; font-weight: bold;")
        status_layout.addWidget(self.lbl_connection)
        
        status_layout.addStretch()
        
        # Current bitstream
        self.lbl_bitstream = QLabel("Bitstream: None")
        self.lbl_bitstream.setStyleSheet("color: #888;")
        status_layout.addWidget(self.lbl_bitstream)
        
        status_layout.addStretch()
        
        # Experiment controller state
        self.lbl_exp_state = QLabel("Exp: IDLE")
        self.lbl_exp_state.setStyleSheet("color: #888;")
        status_layout.addWidget(self.lbl_exp_state)
        
        status_layout.addStretch()
        
        # Timestamp
        self.lbl_time = QLabel("")
        self.lbl_time.setStyleSheet("color: #888;")
        status_layout.addWidget(self.lbl_time)
        
        # Timer for clock update
        self.clock_timer = QTimer()
        self.clock_timer.timeout.connect(self._update_clock)
        self.clock_timer.start(1000)
        self._update_clock()
        
        parent_layout.addWidget(status_frame)

    def _create_fpga_tab(self):
        """Create the FPGA programming tab."""
        tab = QWidget()
        layout = QVBoxLayout(tab)
        
        # Bitstream selection group
        bitstream_group = QGroupBox("Bitstream Selection")
        bg_layout = QVBoxLayout(bitstream_group)
        
        # Directory selection
        dir_layout = QHBoxLayout()
        self.txt_bitstream_dir = QLineEdit(config.BITSTREAM_DIR)
        self.txt_bitstream_dir.setPlaceholderText("Bitstream directory...")
        btn_browse = QPushButton("Browse...")
        btn_browse.clicked.connect(self._browse_bitstream_dir)
        dir_layout.addWidget(self.txt_bitstream_dir, 1)
        dir_layout.addWidget(btn_browse)
        bg_layout.addLayout(dir_layout)
        
        # Bitstream list
        list_layout = QHBoxLayout()
        self.cmb_bitstreams = QComboBox()
        self.cmb_bitstreams.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
        btn_refresh = QPushButton("↻")
        btn_refresh.setMaximumWidth(40)
        btn_refresh.setToolTip("Refresh bitstream list")
        btn_refresh.clicked.connect(self._refresh_bitstreams)
        list_layout.addWidget(self.cmb_bitstreams, 1)
        list_layout.addWidget(btn_refresh)
        bg_layout.addLayout(list_layout)
        
        # Navigation buttons
        nav_layout = QHBoxLayout()
        self.btn_prev = QPushButton("◀ Previous")
        self.btn_prev.clicked.connect(self._prev_bitstream)
        self.btn_next = QPushButton("Next ▶")
        self.btn_next.clicked.connect(self._next_bitstream)
        nav_layout.addWidget(self.btn_prev)
        nav_layout.addWidget(self.btn_next)
        bg_layout.addLayout(nav_layout)
        
        layout.addWidget(bitstream_group)
        
        # Programming group
        prog_group = QGroupBox("FPGA Programming")
        pg_layout = QVBoxLayout(prog_group)
        
        # Progress bar
        self.prog_bar = QProgressBar()
        self.prog_bar.setRange(0, 100)
        self.prog_bar.setValue(0)
        pg_layout.addWidget(self.prog_bar)
        
        # Buttons Layout
        btns_layout = QHBoxLayout()
        
        # SRAM Button
        self.btn_program = QPushButton("▶ PROGRAM (SRAM)")
        self.btn_program.setMinimumHeight(50)
        self.btn_program.setToolTip("Fast, volatile programming")
        self.btn_program.setStyleSheet("""
            QPushButton { background-color: #0d6efd; color: white; font-weight: bold; font-size: 11pt; border-radius: 5px; }
            QPushButton:hover { background-color: #0b5ed7; }
            QPushButton:pressed { background-color: #0a58ca; }
        """)
        self.btn_program.clicked.connect(lambda: self._program_fpga(mode="sram"))
        btns_layout.addWidget(self.btn_program)
        
        # FLASH Button
        self.btn_flash = QPushButton("⚡ BURN FLASH")
        self.btn_flash.setMinimumHeight(50)
        self.btn_flash.setToolTip("Slow, persistent programming")
        self.btn_flash.setStyleSheet("""
            QPushButton { background-color: #d63384; color: white; font-weight: bold; font-size: 11pt; border-radius: 5px; }
            QPushButton:hover { background-color: #c2185b; }
            QPushButton:pressed { background-color: #a0134a; }
        """)
        self.btn_flash.clicked.connect(lambda: self._program_fpga(mode="flash"))
        btns_layout.addWidget(self.btn_flash)
        
        pg_layout.addLayout(btns_layout)
        
        # Vivado path display
        vivado_path = config.VIVADO_PATH or "Not found"
        self.lbl_vivado = QLabel(f"Vivado: {vivado_path[:50]}...")
        self.lbl_vivado.setStyleSheet("color: #888; font-size: 9pt;")
        self.lbl_vivado.setToolTip(vivado_path)
        pg_layout.addWidget(self.lbl_vivado)
        
        layout.addWidget(prog_group)
        layout.addStretch()
        
        self.control_tabs.addTab(tab, "FPGA Programming")

    def _create_stm32_tab(self):
        """Create the STM32 control tab."""
        tab = QWidget()
        layout = QVBoxLayout(tab)
        
        # Voltage control group
        volt_group = QGroupBox("Voltage Control (Vcore)")
        vg_layout = QVBoxLayout(volt_group)
        
        volt_layout = QHBoxLayout()
        self.spin_voltage = QDoubleSpinBox()
        self.spin_voltage.setRange(0.0, 1.8)
        self.spin_voltage.setValue(0.85)
        self.spin_voltage.setSingleStep(0.05)
        self.spin_voltage.setSuffix(" V")
        self.spin_voltage.setDecimals(2)
        
        self.btn_set_voltage = QPushButton("Set Voltage")
        self.btn_set_voltage.clicked.connect(self._set_voltage)
        
        volt_layout.addWidget(QLabel("Target:"))
        volt_layout.addWidget(self.spin_voltage)
        volt_layout.addWidget(self.btn_set_voltage)
        vg_layout.addLayout(volt_layout)
        
        # Quick voltage buttons
        quick_layout = QHBoxLayout()
        for v in [0.7, 0.85, 1.0, 1.2]:
            btn = QPushButton(f"{v}V")
            btn.clicked.connect(lambda checked, val=v: self._quick_voltage(val))
            quick_layout.addWidget(btn)
        vg_layout.addLayout(quick_layout)
        
        layout.addWidget(volt_group)
        
        # Display control group
        disp_group = QGroupBox("Display Control")
        dg_layout = QVBoxLayout(disp_group)
        
        page_layout = QHBoxLayout()
        self.cmb_page = QComboBox()
        self.cmb_page.addItems([f"Page {i}" for i in range(1, 7)])
        self.btn_set_page = QPushButton("Set Page")
        self.btn_set_page.clicked.connect(self._set_page)
        page_layout.addWidget(self.cmb_page)
        page_layout.addWidget(self.btn_set_page)
        dg_layout.addLayout(page_layout)
        
        layout.addWidget(disp_group)
        
        # Manual command group
        cmd_group = QGroupBox("Manual Command")
        cg_layout = QVBoxLayout(cmd_group)
        
        self.txt_command = QLineEdit()
        self.txt_command.setPlaceholderText("Enter command...")
        self.txt_command.returnPressed.connect(self._send_command)
        
        cmd_btn_layout = QHBoxLayout()
        self.cmb_target = QComboBox()
        self.cmb_target.addItems(["CROC (Text)", "STM32 (Protocol)"])
        self.btn_send = QPushButton("Send")
        self.btn_send.clicked.connect(self._send_command)
        cmd_btn_layout.addWidget(self.cmb_target)
        cmd_btn_layout.addWidget(self.btn_send)
        
        cg_layout.addWidget(self.txt_command)
        cg_layout.addLayout(cmd_btn_layout)
        
        layout.addWidget(cmd_group)
        layout.addStretch()
        
        self.control_tabs.addTab(tab, "STM32 Control")

    def _create_settings_tab(self):
        """Create the settings tab."""
        tab = QWidget()
        layout = QVBoxLayout(tab)
        
        # Serial port group
        serial_group = QGroupBox("Serial Port")
        sg_layout = QVBoxLayout(serial_group)
        
        port_layout = QHBoxLayout()
        self.cmb_ports = QComboBox()
        self.cmb_ports.setEditable(True)
        self._refresh_ports()
        
        self.btn_refresh_ports = QPushButton("↻")
        self.btn_refresh_ports.setMaximumWidth(40)
        self.btn_refresh_ports.clicked.connect(self._refresh_ports)
        
        port_layout.addWidget(QLabel("Port:"))
        port_layout.addWidget(self.cmb_ports, 1)
        port_layout.addWidget(self.btn_refresh_ports)
        sg_layout.addLayout(port_layout)
        
        baud_layout = QHBoxLayout()
        self.cmb_baud = QComboBox()
        self.cmb_baud.addItems(["9600", "19200", "38400", "57600", "115200", "125000", "230400", "460800", "921600"])
        self.cmb_baud.setCurrentText(str(config.SYSTEM_BAUD))
        baud_layout.addWidget(QLabel("Baud:"))
        baud_layout.addWidget(self.cmb_baud, 1)
        sg_layout.addLayout(baud_layout)
        
        self.btn_connect = QPushButton("Connect")
        self.btn_connect.setCheckable(True)
        self.btn_connect.clicked.connect(self._toggle_connection)
        sg_layout.addWidget(self.btn_connect)
        
        layout.addWidget(serial_group)
        
        # Vivado path group
        vivado_group = QGroupBox("Vivado Path")
        vg_layout = QVBoxLayout(vivado_group)
        
        vivado_layout = QHBoxLayout()
        self.txt_vivado_path = QLineEdit(config.VIVADO_PATH or "")
        self.txt_vivado_path.setPlaceholderText("Path to Vivado executable...")
        btn_browse_vivado = QPushButton("Browse...")
        btn_browse_vivado.clicked.connect(self._browse_vivado)
        vivado_layout.addWidget(self.txt_vivado_path, 1)
        vivado_layout.addWidget(btn_browse_vivado)
        vg_layout.addLayout(vivado_layout)
        
        layout.addWidget(vivado_group)
        
        # Save button
        btn_save = QPushButton("Save Settings")
        btn_save.clicked.connect(self._save_settings)
        layout.addWidget(btn_save)
        
        layout.addStretch()
        
        self.control_tabs.addTab(tab, "Settings")

    def _create_log_panel(self) -> QWidget:
        """Create the log display panel."""
        panel = QWidget()
        layout = QVBoxLayout(panel)
        
        self.log_text = QTextEdit()
        self.log_text.setReadOnly(True)
        self.log_text.setFont(QFont("Consolas", 9))
        layout.addWidget(self.log_text, 1)
        
        ctrl_layout = QHBoxLayout()
        
        self.chk_autoscroll = QCheckBox("Auto-scroll")
        self.chk_autoscroll.setChecked(True)
        ctrl_layout.addWidget(self.chk_autoscroll)
        
        btn_clear = QPushButton("Clear")
        btn_clear.clicked.connect(self.log_text.clear)
        ctrl_layout.addWidget(btn_clear)
        
        ctrl_layout.addStretch()
        
        btn_save_log = QPushButton("Save Log")
        btn_save_log.clicked.connect(self._save_log)
        ctrl_layout.addWidget(btn_save_log)
        
        layout.addLayout(ctrl_layout)
        
        return panel

    def _connect_signals(self):
        """Connect all signals."""
        # Router signals
        self.router.connection_status.connect(self._on_connection_status)
        self.router.log_message.connect(self.log)
        self.router.log_text_received.connect(self.log)
        self.router.aging_data_received.connect(self._on_sensor_data)
        self.router.stm_frame_received.connect(self._on_stm_frame)
        self.router.telemetry_received.connect(self._on_telemetry_data)
        
        # FPGA manager signals
        self.fpga_manager.started.connect(self._on_program_started)
        self.fpga_manager.output.connect(self.log)
        self.fpga_manager.finished.connect(self._on_program_finished)
        self.fpga_manager.progress.connect(self.prog_bar.setValue)
        
        # Aging analysis signals (V2 - uses filepath)
        self.aging_widget.request_reprogram.connect(self._on_auto_reprogram_filepath)
        
        # Experiment controller state changes
        self.aging_widget.controller.state_changed.connect(self._on_experiment_state_changed)
        self.aging_widget.controller.log_message.connect(self.log)

    def _auto_connect(self):
        """Attempt to auto-connect to configured port."""
        if config.FPGA_PORT:
            self.cmb_ports.setCurrentText(config.FPGA_PORT)
            self._toggle_connection(True)
            self.btn_connect.setChecked(True)

    # ========== Slot Handlers ==========

    @Slot(str)
    def _on_experiment_state_changed(self, state: str):
        """Handle experiment state changes."""
        self.lbl_exp_state.setText(f"Exp: {state}")
        
        # Color-code the state
        colors = {
            'IDLE': '#888',
            'RUNNING': '#28a745',
            'ALARM_DETECTED': '#ffc107',
            'REPROGRAMMING': '#17a2b8',
            'COOLDOWN': '#6c757d',
            'PAUSED': '#fd7e14',
            'FINISHED': '#6610f2'
        }
        color = colors.get(state, '#888')
        self.lbl_exp_state.setStyleSheet(f"color: {color}; font-weight: bold;")

    @Slot()
    def _reset_fpga_action(self):
        """Handler for the Reset FPGA button."""
        current_bit = self.bitstream_manager.current()
        ltx_path = None
        
        if current_bit:
            base_path = os.path.splitext(current_bit)[0]
            candidate = base_path + ".ltx"
            
            if os.path.exists(candidate):
                ltx_path = candidate
            else:
                self.router.log_message.emit(f"⚠ Warning: .ltx file not found for {os.path.basename(current_bit)}")

        reply = QMessageBox.question(
            self, "Confirm Reset",
            "Are you sure you want to reset the FPGA logic?\n"
            "This will toggle the VIO reset probe.",
            QMessageBox.Yes | QMessageBox.No, QMessageBox.No
        )
        
        if reply == QMessageBox.Yes:
            self.fpga_manager.reset(ltx_path)
    
    @Slot(str)
    def _on_connection_status(self, status: str):
        """Handle connection status changes."""
        if "Connected" in status or "opened" in status.lower():
            self.lbl_connection.setText(f"● {status}")
            self.lbl_connection.setStyleSheet("color: #28a745; font-weight: bold;")
            self.btn_connect.setText("Disconnect")
            self.btn_connect.setChecked(True)
        else:
            self.lbl_connection.setText("● Disconnected")
            self.lbl_connection.setStyleSheet("color: #dc3545; font-weight: bold;")
            self.btn_connect.setText("Connect")
            self.btn_connect.setChecked(False)

    @Slot(dict)
    def _on_sensor_data(self, data: dict):
        """Handle incoming sensor data from all 4 sensor types."""
        # Extract all 4 sensor values
        alarm_f = data.get('alarm_f', 0)
        alarm_rf = data.get('alarm_rf', 0)
        alarm_uart = data.get('alarm_dm', data.get('alarm_uart', 0))
        alarm_obi_dmx = data.get('alarm_obi_dmx', data.get('alarm_obi', 0))
        
        # Update visualization widget
        self.sensor_widget.updateSensorData(alarm_f, alarm_rf, alarm_uart, alarm_obi_dmx)
        
        # Get current environmental data
        fpga_temp = data.get('fpga_temp', 0)
        vccint = data.get('vccint', 0)
        vcore = data.get('vcore', 0)
        iout = data.get('iout', 0)
        
        # Log to SmartLogger (will filter based on mode)
        logged = self.smart_logger.log_data(
            alarm_f=alarm_f,
            alarm_rf=alarm_rf,
            alarm_uart=alarm_uart,
            alarm_obi=alarm_obi_dmx,
            fpga_temp=fpga_temp,
            vccint=vccint,
            vcore=vcore,
            iout=iout
        )
        
        # Process through aging widget (for auto-program)
        self.aging_widget.process_sensor_data(alarm_f, alarm_rf, alarm_uart, alarm_obi_dmx)
        
        # Check for NEW alarms (for UI logging)
        new_alarm_detected = False
        
        if alarm_f != self._last_alarm_f:
            new_f = alarm_f & ~self._last_alarm_f
            if new_f:
                new_alarm_detected = True
                
        if alarm_rf != self._last_alarm_rf:
            new_rf = alarm_rf & ~self._last_alarm_rf
            if new_rf:
                new_alarm_detected = True
                
        if alarm_uart != self._last_alarm_uart:
            new_uart = alarm_uart & ~self._last_alarm_uart
            if new_uart:
                new_alarm_detected = True
                
        if alarm_obi_dmx != self._last_alarm_obi_dmx:
            new_obi = alarm_obi_dmx & ~self._last_alarm_obi_dmx
            if new_obi:
                new_alarm_detected = True
        
        # Log if new alarms detected
        if new_alarm_detected:
            f_count = bin(alarm_f).count('1')
            rf_count = bin(alarm_rf).count('1')
            uart_count = bin(alarm_uart).count('1')
            obi_count = bin(alarm_obi_dmx).count('1')
            total = f_count + rf_count + uart_count + obi_count
            
            self.log(
                f"[AGING] New alarm detected! Total={total} "
                f"(F={f_count}, RF={rf_count}, UART={uart_count}, OBI={obi_count})"
            )
        
        # Store last values
        self._last_alarm_f = alarm_f
        self._last_alarm_rf = alarm_rf
        self._last_alarm_uart = alarm_uart
        self._last_alarm_obi_dmx = alarm_obi_dmx

    @Slot(object)
    def _on_stm_frame(self, event):
        """Handle STM32 protocol response."""
        if len(event) >= 2:
            evt_type, data = event[0], event[1]
            if evt_type == 'ok':
                self.log(f"[STM32] OK - {data.get('func', 'UNK')}")
            elif evt_type == 'error':
                self.log(f"[STM32] ERROR - {data.get('err', 'UNK')}")

    @Slot(dict)
    def _on_telemetry_data(self, data: dict):
        """Handle telemetry data from router."""
        # Update telemetry widget
        self.telemetry_widget.updateFromDict(data)
        
        # Update quick info labels
        if 'vcore' in data:
            self.lbl_vcore.setText(f"Vcore: {data['vcore']:.3f} V")
        if 'vin' in data:
            self.lbl_vin.setText(f"Vin: {data['vin']:.2f} V")
        if 'iout' in data:
            self.lbl_iout.setText(f"Iout: {data['iout']:.3f} A")
        if 'ext_temp' in data:
            self.lbl_ext_temp.setText(f"Ext T: {data['ext_temp']:.1f} °C")
        if 'fpga_temp' in data:
            self.lbl_fpga_temp.setText(f"FPGA T: {data['fpga_temp']:.2f} °C")
        if 'vccint' in data:
            self.lbl_vccint.setText(f"VCCINT: {data['vccint']:.3f} V")
        
        # Calculate and display power
        vcore = data.get('vcore', 0.0)
        iout = data.get('iout', 0.0)
        power = vcore * iout
        self.lbl_power.setText(f"Power: {power:.3f} W")
        
        # Update aging widget with environmental data
        self.aging_widget.set_environmental_data(
            fpga_temp=data.get('fpga_temp'),
            vccint=data.get('vccint'),
            vcore=data.get('vcore'),
            ambient_temp=data.get('ext_temp')
        )

    @Slot(str)
    def _on_program_started(self, bitstream: str):
        """Handle FPGA programming started."""
        self.btn_program.setEnabled(False)
        self.btn_program.setText("Programming...")
        self.lbl_bitstream.setText(f"Programming: {bitstream}")

    @Slot(bool, str)
    def _on_program_finished(self, success: bool, msg: str):
        """Handle FPGA programming finished."""
        self.btn_program.setEnabled(True)
        self.btn_program.setText("▶ PROGRAM (SRAM)")
        
        bitstream_name = self.bitstream_manager.current_name()
        
        if success:
            self.lbl_bitstream.setText(f"Bitstream: {bitstream_name}")
            
            # Log to SmartLogger
            self.smart_logger.log_event("program_success", {
                "bitstream": bitstream_name
            })
            
            # Notify aging widget
            self.aging_widget.on_reprogram_complete(True)
        else:
            self.lbl_bitstream.setText("Bitstream: Programming failed")
            self.aging_widget.on_reprogram_complete(False)
    
    @Slot(str)
    def _on_auto_reprogram_filepath(self, filepath: str):
        """Handle auto-reprogram request from experiment controller (V2 - filepath)."""
        self.log(f"[AUTO-REPROGRAM] Alarm triggered! Switching to: {os.path.basename(filepath)}")
        
        # Log the transition event
        self.smart_logger.log_event("auto_reprogram", {
            "filepath": filepath,
            "reason": "alarm_triggered"
        })
        
        # Verify file exists
        if not os.path.exists(filepath):
            self.log(f"[ERROR] Bitstream file not found: {filepath}")
            return
        
        # Check if already programming
        if self.fpga_manager.is_programming:
            self.log("[AUTO-PROGRAM] ⚠ Already programming, request queued")
            return
        
        # Start programming
        self.fpga_manager.program(filepath, mode="sram")

    # ========== UI Actions ==========
    
    def _toggle_connection(self, checked: bool):
        """Toggle serial connection."""
        if checked:
            port = self.cmb_ports.currentText()
            baud = int(self.cmb_baud.currentText())
            self.router.connect_serial(port, baud)
        else:
            self.router.disconnect_serial()

    def _refresh_ports(self):
        """Refresh available serial ports."""
        current = self.cmb_ports.currentText()
        self.cmb_ports.clear()
        
        ports = get_available_ports()
        for port, desc in ports:
            self.cmb_ports.addItem(f"{port}", port)
        
        idx = self.cmb_ports.findData(current)
        if idx >= 0:
            self.cmb_ports.setCurrentIndex(idx)

    def _browse_bitstream_dir(self):
        """Browse for bitstream directory."""
        path = QFileDialog.getExistingDirectory(
            self, "Select Bitstream Directory",
            self.txt_bitstream_dir.text()
        )
        if path:
            self.txt_bitstream_dir.setText(path)
            self._refresh_bitstreams()
            self._save_settings()

    def _refresh_bitstreams(self):
        """Refresh bitstream list."""
        path = self.txt_bitstream_dir.text()
        count = self.bitstream_manager.load_directory(path)
        
        self.cmb_bitstreams.clear()
        self.cmb_bitstreams.addItems(self.bitstream_manager.get_all_names())
        
        self.log(f"Found {count} bitstream files in {path}")

    def _prev_bitstream(self):
        """Select previous bitstream."""
        if self.bitstream_manager.back():
            self.cmb_bitstreams.setCurrentIndex(self.bitstream_manager.get_index())

    def _next_bitstream(self):
        """Select next bitstream."""
        if self.bitstream_manager.advance():
            self.cmb_bitstreams.setCurrentIndex(self.bitstream_manager.get_index())

    def _program_fpga(self, mode="sram"):
        """Start FPGA programming."""
        idx = self.cmb_bitstreams.currentIndex()
        self.bitstream_manager.set_index(idx)
        
        current_file = self.bitstream_manager.current()
        if not current_file:
            self.log("No file selected!")
            return
        
        target_file = current_file
        
        if mode == "flash":
            if current_file.lower().endswith('.bit'):
                bin_candidate = current_file[:-4] + ".bin"
                if os.path.exists(bin_candidate):
                    target_file = bin_candidate
                    self.log(f"Auto-selected .bin file for flash: {os.path.basename(target_file)}")
                else:
                    self.log(f"Error: .bin file not found for flash programming.")
                    QMessageBox.warning(self, "Missing File", 
                        f"Flash programming requires a .bin file.\nCould not find: {bin_candidate}")
                    return
        
        self.fpga_manager.program(target_file, mode=mode)

    def _set_voltage(self):
        """Send voltage command to STM32."""
        voltage = self.spin_voltage.value()
        self._send_stm_command(build_voltage_command(voltage))

    def _quick_voltage(self, voltage: float):
        """Quick voltage button handler."""
        self.spin_voltage.setValue(voltage)
        self._set_voltage()

    def _set_page(self):
        """Send page command to STM32."""
        page = self.cmb_page.currentIndex() + 1
        self._send_stm_command(build_page_command(page))

    def _send_command(self):
        """Send manual command."""
        cmd = self.txt_command.text().strip()
        if not cmd:
            return
        
        target = self.cmb_target.currentText()
        
        if "CROC" in target:
            self.router.send_text_to_croc(cmd)
            self.log(f"[TX → CROC] {cmd}")
        else:
            self._send_stm_command(build_message_command(cmd))
        
        self.txt_command.clear()

    def _send_stm_command(self, cmd_tuple):
        """Send command to STM32 with CRC."""
        payload, log_str, _ = cmd_tuple
        
        core = payload[1:]
        crc = compute_crc16_modbus(core)
        final = core + crc.to_bytes(2, CRC_ENDIAN)
        
        self.router.send_to_stm(final)
        self.log(f"[TX → STM32] {log_str}")

    def _browse_vivado(self):
        """Browse for Vivado executable."""
        filter_str = "Vivado (vivado*.bat vivado)" if config.IS_WINDOWS else "Vivado (vivado*)"
        path, _ = QFileDialog.getOpenFileName(
            self, "Select Vivado Executable",
            os.path.dirname(self.txt_vivado_path.text()),
            filter_str
        )
        if path:
            self.txt_vivado_path.setText(path)

    def _save_settings(self):
        """Save current settings."""
        config.save_config(
            fpga_port=self.cmb_ports.currentText(),
            baud_rate=int(self.cmb_baud.currentText()),
            vivado_path=self.txt_vivado_path.text(),
            bitstream_dir=self.txt_bitstream_dir.text()
        )
        self.log("Settings saved!")

    def _save_log(self):
        """Save log to file."""
        path, _ = QFileDialog.getSaveFileName(
            self, "Save Log",
            f"croc_log_{time.strftime('%Y%m%d_%H%M%S')}.txt",
            "Text Files (*.txt)"
        )
        if path:
            with open(path, 'w', encoding='utf-8') as f:
                f.write(self.log_text.toPlainText())
            self.log(f"Log saved to {path}")

    def _update_clock(self):
        """Update clock display."""
        self.lbl_time.setText(time.strftime("%Y-%m-%d %H:%M:%S"))

    def log(self, message: str):
        """Add message to log."""
        timestamp = time.strftime("%H:%M:%S")
        self.log_text.append(f"[{timestamp}] {message}")
        
        if self.chk_autoscroll.isChecked():
            cursor = self.log_text.textCursor()
            cursor.movePosition(QTextCursor.End)
            self.log_text.setTextCursor(cursor)

    def closeEvent(self, event):
        """Handle window close."""
        self.log("Shutting down...")
        
        # Stop timers
        self.clock_timer.stop()
        self.update_timer.stop()
        self.log_stats_timer.stop()
        
        # Save aging analysis data
        try:
            self.aging_widget.save_all()
            self.log("Aging data saved.")
        except Exception as e:
            self.log(f"Warning: Could not save aging data: {e}")
        
        # Close smart logger
        try:
            self.smart_logger.close()
            self.log("Smart logger closed.")
        except Exception as e:
            self.log(f"Warning: Could not close smart logger: {e}")
        
        # Disconnect serial
        self.router.disconnect_serial()
        
        # Cancel any FPGA programming
        if self.fpga_manager.is_programming:
            self.fpga_manager.cancel()
        
        event.accept()
