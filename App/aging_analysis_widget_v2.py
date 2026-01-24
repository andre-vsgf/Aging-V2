# -*- coding: utf-8 -*-
"""
Aging Analysis Widget V2 - Simplified Interface

Complete rewrite with:
- Integrated ExperimentController for auto-program
- Simplified bitstream queue management
- Clear experiment state visualization
- Transition history display

WORKFLOW:
1. Load bitstreams from directory (auto-assigns phases)
2. Configure timeout/cooldown settings
3. Start experiment
4. Monitor as alarms trigger → auto-reprogram → continue

Author: CROC Project
"""

import os
import pyqtgraph as pg
from datetime import datetime
from pathlib import Path

from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QGridLayout,
    QGroupBox, QLabel, QPushButton, QDoubleSpinBox,
    QTableWidget, QTableWidgetItem, QHeaderView,
    QSplitter, QTabWidget, QLineEdit, QSpinBox,
    QFileDialog, QMessageBox, QFrame, QComboBox,
    QTextEdit, QCheckBox, QListWidget, QListWidgetItem,
    QProgressBar
)
from PySide6.QtCore import Qt, Signal, Slot, QTimer
from PySide6.QtGui import QColor, QFont, QBrush

from experiment_controller import ExperimentController, ExperimentState, TransitionEvent
from aging_logger import AgingLogger
from bitstream_calibration import CalibrationManager


class BitstreamQueueWidget(QGroupBox):
    """Widget for managing the bitstream queue."""
    
    bitstream_selected = Signal(str)  # filepath
    
    def __init__(self, controller: ExperimentController, parent=None):
        super().__init__("📁 Bitstream Queue", parent)
        self.controller = controller
        self._setup_ui()
        
        # Connect signals
        self.controller.state_changed.connect(self._update_state)
    
    def _setup_ui(self):
        layout = QVBoxLayout(self)
        
        # Directory selection
        dir_layout = QHBoxLayout()
        
        self.txt_directory = QLineEdit()
        self.txt_directory.setPlaceholderText("Select bitstream directory...")
        self.txt_directory.setReadOnly(True)
        dir_layout.addWidget(self.txt_directory, 1)
        
        self.btn_browse = QPushButton("📂 Browse")
        self.btn_browse.clicked.connect(self._browse_directory)
        dir_layout.addWidget(self.btn_browse)
        
        layout.addLayout(dir_layout)
        
        # Phase configuration
        phase_layout = QHBoxLayout()
        
        phase_layout.addWidget(QLabel("Start Phase:"))
        self.spin_start_phase = QDoubleSpinBox()
        self.spin_start_phase.setRange(-180, 360)
        self.spin_start_phase.setValue(0)
        self.spin_start_phase.setSuffix("°")
        phase_layout.addWidget(self.spin_start_phase)
        
        phase_layout.addWidget(QLabel("Step:"))
        self.spin_phase_step = QDoubleSpinBox()
        self.spin_phase_step.setRange(0.1, 90)
        self.spin_phase_step.setValue(5.0)
        self.spin_phase_step.setSuffix("°")
        phase_layout.addWidget(self.spin_phase_step)
        
        self.btn_load = QPushButton("Load Bitstreams")
        self.btn_load.clicked.connect(self._load_bitstreams)
        phase_layout.addWidget(self.btn_load)
        
        layout.addLayout(phase_layout)
        
        # Queue list
        self.list_queue = QListWidget()
        self.list_queue.setAlternatingRowColors(True)
        self.list_queue.itemClicked.connect(self._on_item_clicked)
        layout.addWidget(self.list_queue)
        
        # Queue info
        self.lbl_queue_info = QLabel("Queue: 0 bitstreams")
        self.lbl_queue_info.setStyleSheet("color: #888;")
        layout.addWidget(self.lbl_queue_info)
    
    def _browse_directory(self):
        """Open directory browser."""
        path = QFileDialog.getExistingDirectory(
            self, "Select Bitstream Directory"
        )
        if path:
            self.txt_directory.setText(path)
    
    def _load_bitstreams(self):
        """Load bitstreams from selected directory."""
        directory = self.txt_directory.text()
        if not directory or not os.path.isdir(directory):
            QMessageBox.warning(self, "Error", "Please select a valid directory")
            return
        
        start_phase = self.spin_start_phase.value()
        phase_step = self.spin_phase_step.value()
        
        count = self.controller.load_from_directory(
            directory, start_phase, phase_step
        )
        
        self._refresh_list()
        
        if count > 0:
            QMessageBox.information(
                self, "Loaded",
                f"Loaded {count} bitstreams\n"
                f"Phase range: {start_phase}° to {start_phase + (count-1)*phase_step}°"
            )
    
    def _refresh_list(self):
        """Refresh the queue list."""
        self.list_queue.clear()
        
        queue_info = self.controller.get_queue_info()
        
        for info in queue_info:
            item = QListWidgetItem(
                f"{info['order']+1}. {info['name']} ({info['phase']:.1f}°)"
            )
            
            if info['current']:
                item.setBackground(QBrush(QColor(42, 130, 218, 100)))
                item.setFont(QFont("", -1, QFont.Bold))
            
            item.setData(Qt.UserRole, info['filepath'])
            self.list_queue.addItem(item)
        
        self.lbl_queue_info.setText(
            f"Queue: {len(queue_info)} bitstreams | "
            f"Position: {self.controller.queue_position + 1}/{self.controller.queue_length}"
        )
    
    def _on_item_clicked(self, item: QListWidgetItem):
        """Handle item click."""
        filepath = item.data(Qt.UserRole)
        if filepath:
            self.bitstream_selected.emit(filepath)
    
    @Slot(str)
    def _update_state(self, state: str):
        """Update display based on controller state."""
        self._refresh_list()


class ExperimentControlWidget(QGroupBox):
    """Widget for experiment control and configuration."""
    
    def __init__(self, controller: ExperimentController, parent=None):
        super().__init__("⚙️ Experiment Control", parent)
        self.controller = controller
        self._setup_ui()
        
        # Connect signals
        self.controller.state_changed.connect(self._on_state_changed)
    
    def _setup_ui(self):
        layout = QVBoxLayout(self)
        
        # Auto-program toggle
        self.chk_auto_program = QCheckBox("🔄 Enable Auto-Program on Alarm")
        self.chk_auto_program.setStyleSheet("font-weight: bold; font-size: 11pt;")
        self.chk_auto_program.toggled.connect(self._on_auto_program_toggled)
        layout.addWidget(self.chk_auto_program)
        
        # Timing configuration
        timing_layout = QGridLayout()
        
        timing_layout.addWidget(QLabel("Stabilization Time:"), 0, 0)
        self.spin_stabilization = QSpinBox()
        self.spin_stabilization.setRange(1000, 30000)
        self.spin_stabilization.setValue(3000)
        self.spin_stabilization.setSuffix(" ms")
        self.spin_stabilization.setToolTip("Wait time after alarm before reprogramming")
        self.spin_stabilization.valueChanged.connect(
            lambda v: self.controller.set_stabilization_time(v)
        )
        timing_layout.addWidget(self.spin_stabilization, 0, 1)
        
        timing_layout.addWidget(QLabel("Cooldown Time:"), 1, 0)
        self.spin_cooldown = QSpinBox()
        self.spin_cooldown.setRange(1000, 60000)
        self.spin_cooldown.setValue(10000)
        self.spin_cooldown.setSuffix(" ms")
        self.spin_cooldown.setToolTip("Wait time after reprogram before monitoring")
        self.spin_cooldown.valueChanged.connect(
            lambda v: self.controller.set_cooldown_time(v)
        )
        timing_layout.addWidget(self.spin_cooldown, 1, 1)
        
        layout.addLayout(timing_layout)
        
        # State display
        state_frame = QFrame()
        state_frame.setFrameStyle(QFrame.StyledPanel)
        state_layout = QVBoxLayout(state_frame)
        
        self.lbl_state = QLabel("State: IDLE")
        self.lbl_state.setStyleSheet(
            "font-size: 14pt; font-weight: bold; padding: 10px;"
        )
        self.lbl_state.setAlignment(Qt.AlignCenter)
        state_layout.addWidget(self.lbl_state)
        
        self.lbl_current = QLabel("Current: ---")
        self.lbl_current.setAlignment(Qt.AlignCenter)
        state_layout.addWidget(self.lbl_current)
        
        self.lbl_next = QLabel("Next: ---")
        self.lbl_next.setStyleSheet("color: #888;")
        self.lbl_next.setAlignment(Qt.AlignCenter)
        state_layout.addWidget(self.lbl_next)
        
        layout.addWidget(state_frame)
        
        # Control buttons
        btn_layout = QHBoxLayout()
        
        self.btn_start = QPushButton("▶ Start")
        self.btn_start.setStyleSheet(
            "background-color: #28a745; color: white; font-weight: bold; padding: 10px;"
        )
        self.btn_start.clicked.connect(self._start_experiment)
        btn_layout.addWidget(self.btn_start)
        
        self.btn_stop = QPushButton("⏹ Stop")
        self.btn_stop.setStyleSheet(
            "background-color: #dc3545; color: white; font-weight: bold; padding: 10px;"
        )
        self.btn_stop.clicked.connect(self._stop_experiment)
        self.btn_stop.setEnabled(False)
        btn_layout.addWidget(self.btn_stop)
        
        self.btn_skip = QPushButton("⏭ Skip")
        self.btn_skip.setToolTip("Manually skip to next bitstream")
        self.btn_skip.clicked.connect(self._skip_bitstream)
        self.btn_skip.setEnabled(False)
        btn_layout.addWidget(self.btn_skip)
        
        layout.addLayout(btn_layout)
        
        # Experiment time
        self.lbl_time = QLabel("Experiment Time: 00:00:00")
        self.lbl_time.setAlignment(Qt.AlignCenter)
        layout.addWidget(self.lbl_time)
    
    def _on_auto_program_toggled(self, checked: bool):
        self.controller.auto_program_enabled = checked
    
    def _start_experiment(self):
        if self.controller.queue_length == 0:
            QMessageBox.warning(self, "Error", "Please load bitstreams first")
            return
        
        self.controller.start_experiment()
    
    def _stop_experiment(self):
        reply = QMessageBox.question(
            self, "Stop Experiment",
            "Are you sure you want to stop the experiment?",
            QMessageBox.Yes | QMessageBox.No
        )
        if reply == QMessageBox.Yes:
            self.controller.stop_experiment()
    
    def _skip_bitstream(self):
        self.controller.advance_to_next()
    
    @Slot(str)
    def _on_state_changed(self, state: str):
        """Update UI based on state."""
        state_colors = {
            'IDLE': ('#888', 'background-color: #2d2d30;'),
            'RUNNING': ('#28a745', 'background-color: #1a3d1a;'),
            'ALARM_DETECTED': ('#ffc107', 'background-color: #3d3d1a;'),
            'REPROGRAMMING': ('#17a2b8', 'background-color: #1a2d3d;'),
            'COOLDOWN': ('#6c757d', 'background-color: #2d2d30;'),
            'PAUSED': ('#fd7e14', 'background-color: #3d2d1a;'),
            'FINISHED': ('#6610f2', 'background-color: #2d1a3d;')
        }
        
        color, bg = state_colors.get(state, ('#888', 'background-color: #2d2d30;'))
        self.lbl_state.setText(f"State: {state}")
        self.lbl_state.setStyleSheet(
            f"font-size: 14pt; font-weight: bold; padding: 10px; color: {color}; {bg}"
        )
        
        # Update current/next labels
        current = self.controller.current_bitstream
        next_bs = self.controller.next_bitstream
        
        if current:
            self.lbl_current.setText(f"Current: {current.name} ({current.phase_degrees:.1f}°)")
        else:
            self.lbl_current.setText("Current: ---")
        
        if next_bs:
            self.lbl_next.setText(f"Next: {next_bs.name} ({next_bs.phase_degrees:.1f}°)")
        else:
            self.lbl_next.setText("Next: (end of queue)")
        
        # Update button states
        is_running = state not in ('IDLE', 'FINISHED')
        self.btn_start.setEnabled(not is_running)
        self.btn_stop.setEnabled(is_running)
        self.btn_skip.setEnabled(is_running)
    
    def update_time(self):
        """Update experiment time display."""
        hours = self.controller.experiment_hours
        h = int(hours)
        m = int((hours - h) * 60)
        s = int(((hours - h) * 60 - m) * 60)
        self.lbl_time.setText(f"Experiment Time: {h:02d}:{m:02d}:{s:02d}")


class TransitionHistoryWidget(QGroupBox):
    """Widget for displaying transition history."""
    
    def __init__(self, controller: ExperimentController, parent=None):
        super().__init__("📋 Transition History", parent)
        self.controller = controller
        self._setup_ui()
        
        # Connect signals
        self.controller.transition_logged.connect(self._on_transition)
    
    def _setup_ui(self):
        layout = QVBoxLayout(self)
        
        # Summary
        self.lbl_summary = QLabel("Transitions: 0")
        layout.addWidget(self.lbl_summary)
        
        # Table
        self.table = QTableWidget()
        self.table.setColumnCount(6)
        self.table.setHorizontalHeaderLabels([
            "Time", "Hours", "From → To", "Phase", "Triggers", "Alarms"
        ])
        self.table.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        self.table.setSelectionBehavior(QTableWidget.SelectRows)
        self.table.setAlternatingRowColors(True)
        layout.addWidget(self.table)
        
        # Export button
        btn_layout = QHBoxLayout()
        
        btn_export = QPushButton("📁 Export CSV")
        btn_export.clicked.connect(self._export_csv)
        btn_layout.addWidget(btn_export)
        
        btn_layout.addStretch()
        layout.addLayout(btn_layout)
    
    @Slot(object)
    def _on_transition(self, event: TransitionEvent):
        """Add new transition to table."""
        row = self.table.rowCount()
        self.table.insertRow(row)
        
        # Time
        self.table.setItem(row, 0, QTableWidgetItem(
            event.timestamp.strftime("%H:%M:%S")
        ))
        
        # Hours
        self.table.setItem(row, 1, QTableWidgetItem(
            f"{event.experiment_hours:.2f}"
        ))
        
        # From → To
        self.table.setItem(row, 2, QTableWidgetItem(
            f"{event.from_bitstream} → {event.to_bitstream}"
        ))
        
        # Phase
        self.table.setItem(row, 3, QTableWidgetItem(
            f"{event.from_phase:.1f}° → {event.to_phase:.1f}°"
        ))
        
        # Triggers (which sensors)
        triggers = []
        for sensor, bits in event.trigger_alarms.items():
            if bits:
                triggers.append(f"{sensor}:{len(bits)}")
        self.table.setItem(row, 4, QTableWidgetItem(", ".join(triggers)))
        
        # Total alarms
        self.table.setItem(row, 5, QTableWidgetItem(str(event.total_alarms)))
        
        # Scroll to new row
        self.table.scrollToBottom()
        
        # Update summary
        self.lbl_summary.setText(f"Transitions: {row + 1}")
    
    def _export_csv(self):
        """Export transitions to CSV."""
        path, _ = QFileDialog.getSaveFileName(
            self, "Export Transitions",
            f"transitions_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv",
            "CSV Files (*.csv)"
        )
        if path:
            self.controller.export_transitions_csv(path)
            QMessageBox.information(self, "Exported", f"Transitions exported to {path}")


class AgingAnalysisWidgetV2(QWidget):
    """
    Main aging analysis widget - Version 2.
    
    Simplified interface focused on:
    - Easy bitstream queue setup
    - Clear experiment control
    - Transition monitoring
    
    Signals:
        request_reprogram(str): Request to reprogram FPGA with filepath
    """
    
    request_reprogram = Signal(str)
    
    def __init__(self, parent=None):
        super().__init__(parent)
        
        # Create experiment controller
        self.controller = ExperimentController()
        
        # Legacy components (for compatibility)
        self.logger = AgingLogger()
        self.cal_manager = CalibrationManager()
        
        # Alarm tracking (for compatibility)
        self._last_total_alarms = 0
        self._last_alarm_f = 0
        self._last_alarm_rf = 0
        self._last_alarm_uart = 0
        self._last_alarm_obi_dmx = 0
        
        self._setup_ui()
        self._connect_signals()
        
        # Update timer
        self._update_timer = QTimer(self)
        self._update_timer.timeout.connect(self._periodic_update)
        self._update_timer.start(1000)
    
    def _setup_ui(self):
        layout = QHBoxLayout(self)
        
        # Left panel: Queue and Control
        left_panel = QWidget()
        left_layout = QVBoxLayout(left_panel)
        left_layout.setContentsMargins(0, 0, 0, 0)
        
        # Queue widget
        self.queue_widget = BitstreamQueueWidget(self.controller)
        left_layout.addWidget(self.queue_widget)
        
        # Control widget
        self.control_widget = ExperimentControlWidget(self.controller)
        left_layout.addWidget(self.control_widget)
        
        # Right panel: History
        right_panel = QWidget()
        right_layout = QVBoxLayout(right_panel)
        right_layout.setContentsMargins(0, 0, 0, 0)
        
        # Transition history
        self.history_widget = TransitionHistoryWidget(self.controller)
        right_layout.addWidget(self.history_widget)
        
        # Splitter
        splitter = QSplitter(Qt.Horizontal)
        splitter.addWidget(left_panel)
        splitter.addWidget(right_panel)
        splitter.setSizes([400, 600])
        
        layout.addWidget(splitter)
    
    def _connect_signals(self):
        """Connect controller signals."""
        # Forward reprogram requests
        self.controller.request_reprogram.connect(self.request_reprogram)
        
        # Handle experiment finished
        self.controller.experiment_finished.connect(self._on_experiment_finished)
    
    def _periodic_update(self):
        """Periodic UI updates."""
        self.control_widget.update_time()
    
    @Slot()
    def _on_experiment_finished(self):
        """Handle experiment completion."""
        QMessageBox.information(
            self, "Experiment Finished",
            f"Experiment completed!\n"
            f"Total transitions: {len(self.controller.transitions)}\n"
            f"Duration: {self.controller.experiment_hours:.2f} hours"
        )
    
    # =========================================================================
    # Public API (for MainWindow integration)
    # =========================================================================
    
    def process_sensor_data(self, alarm_f: int, alarm_rf: int,
                            alarm_uart: int = 0, alarm_obi_dmx: int = 0):
        """
        Process incoming sensor data.
        
        Called by MainWindow when sensor data arrives.
        """
        # Forward to controller
        self.controller.process_alarms(alarm_f, alarm_rf, alarm_uart, alarm_obi_dmx)
        
        # Update tracking (for compatibility)
        self._last_alarm_f = alarm_f
        self._last_alarm_rf = alarm_rf
        self._last_alarm_uart = alarm_uart
        self._last_alarm_obi_dmx = alarm_obi_dmx
        self._last_total_alarms = (
            bin(alarm_f).count('1') + bin(alarm_rf).count('1') +
            bin(alarm_uart).count('1') + bin(alarm_obi_dmx).count('1')
        )
    
    def set_environmental_data(self, fpga_temp: float = None, vccint: float = None, **kwargs):
        """Update environmental readings."""
        self.controller.update_environmental(fpga_temp, vccint)
        self.logger.set_environmental_data(fpga_temp=fpga_temp, vccint=vccint, **kwargs)
    
    def on_reprogram_complete(self, success: bool):
        """Called when FPGA reprogramming completes."""
        self.controller.on_reprogram_complete(success)
    
    def check_alarms(self, alarm_f: int, alarm_rf: int,
                     alarm_uart: int = 0, alarm_obi_dmx: int = 0) -> bool:
        """
        Check for new alarms (compatibility method).
        
        Returns True if new alarms detected.
        """
        total = (bin(alarm_f).count('1') + bin(alarm_rf).count('1') +
                 bin(alarm_uart).count('1') + bin(alarm_obi_dmx).count('1'))
        
        new_alarms = total > self._last_total_alarms
        
        # Process through controller
        self.process_sensor_data(alarm_f, alarm_rf, alarm_uart, alarm_obi_dmx)
        
        return new_alarms
    
    def get_alarm_counts(self) -> dict:
        """Return current alarm counts."""
        return {
            'f': bin(self._last_alarm_f).count('1'),
            'rf': bin(self._last_alarm_rf).count('1'),
            'uart': bin(self._last_alarm_uart).count('1'),
            'obi_dmx': bin(self._last_alarm_obi_dmx).count('1'),
            'total': self._last_total_alarms
        }
    
    def reset_alarm_tracking(self):
        """Reset alarm tracking."""
        self._last_total_alarms = 0
        self._last_alarm_f = 0
        self._last_alarm_rf = 0
        self._last_alarm_uart = 0
        self._last_alarm_obi_dmx = 0
    
    def update_display(self):
        """Update displays (called by timer)."""
        pass  # Handled by internal timer
    
    def save_all(self):
        """Save all data."""
        self.controller.save_transitions()
        self.cal_manager.save()
        self.logger.save_json()


# Alias for backwards compatibility
AgingAnalysisWidget = AgingAnalysisWidgetV2