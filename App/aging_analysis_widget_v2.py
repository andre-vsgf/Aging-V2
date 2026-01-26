# -*- coding: utf-8 -*-
"""
Aging Analysis Widget V2 - Updated Interface with Graphs

Features:
- Bitstream queue with auto-detection of negative phases
- Sensor enable/disable checkboxes (runtime editable)
- Radiation dose configuration (dose rate + initial dose)
- Auto-program with initial bitstream verification
- Transition history with detailed logging
- Slack degradation graphs with projections

Author: CROC Project
"""

import os
import numpy as np
from datetime import datetime
from pathlib import Path

import pyqtgraph as pg

from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QGridLayout,
    QGroupBox, QLabel, QPushButton, QDoubleSpinBox,
    QTableWidget, QTableWidgetItem, QHeaderView,
    QSplitter, QLineEdit, QSpinBox,
    QFileDialog, QMessageBox, QFrame,
    QCheckBox, QListWidget, QListWidgetItem,
    QTabWidget
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
        self.controller.queue_updated.connect(self._refresh_list)
        
        # Try to set default directory from config
        self._set_default_directory()

        # Auto-load bitstreams if directory is valid
        if self.txt_directory.text() and os.path.isdir(self.txt_directory.text()):
            self._load_bitstreams()
    
    def _set_default_directory(self):
        """Set default directory from config or detect out_bitstreams."""
        try:
            import config
            default_dir = getattr(config, 'BITSTREAM_DIR', '')
            if default_dir and os.path.isdir(default_dir):
                self.txt_directory.setText(default_dir)
                return
        except ImportError:
            pass
        
        # Fallback: try to find out_bitstreams relative to current dir
        for path in ['./out_bitstreams', '../out_bitstreams', '../../out_bitstreams']:
            if os.path.isdir(path):
                self.txt_directory.setText(os.path.abspath(path))
                return
    
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
        
        # Load button
        self.btn_load = QPushButton("🔄 Load Bitstreams (Auto-detect phases)")
        self.btn_load.clicked.connect(self._load_bitstreams)
        layout.addWidget(self.btn_load)
        
        # Queue list
        self.list_queue = QListWidget()
        self.list_queue.setAlternatingRowColors(True)
        self.list_queue.setMaximumHeight(120)
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
            # Auto-load bitstreams from new directory
            self._load_bitstreams()
    
    def _load_bitstreams(self):
        """Load bitstreams from selected directory."""
        directory = self.txt_directory.text()
        if not directory or not os.path.isdir(directory):
            QMessageBox.warning(self, "Error", "Please select a valid directory")
            return
        
        count = self.controller.load_from_directory(directory)
        
        if count > 0:
            queue = self.controller.get_queue_info()
            first_phase = queue[0]['phase'] if queue else 0
            last_phase = queue[-1]['phase'] if queue else 0
            
            QMessageBox.information(
                self, "Loaded",
                f"Loaded {count} bitstreams\n\n"
                f"Phase range: {first_phase}° to {last_phase}°\n"
                f"(Phases are negative, starting from most negative)"
            )
        else:
            QMessageBox.warning(self, "No Files", "No .bit files found in directory")
    
    def _refresh_list(self):
        """Refresh the queue list."""
        self.list_queue.clear()
        
        queue_info = self.controller.get_queue_info()
        
        for info in queue_info:
            item = QListWidgetItem(
                f"{info['order']+1}. {info['name']} ({info['phase']}°)"
            )
            
            if info['current']:
                item.setBackground(QBrush(QColor(42, 130, 218, 100)))
                item.setFont(QFont("", -1, QFont.Bold))
            
            item.setData(Qt.UserRole, info['filepath'])
            self.list_queue.addItem(item)
        
        pos = self.controller.queue_position + 1
        total = self.controller.queue_length
        self.lbl_queue_info.setText(f"Queue: {total} bitstreams | Position: {pos}/{total}")
    
    def _on_item_clicked(self, item: QListWidgetItem):
        """Handle item click."""
        filepath = item.data(Qt.UserRole)
        if filepath:
            self.bitstream_selected.emit(filepath)
    
    @Slot(str)
    def _update_state(self, state: str):
        """Update display based on controller state."""
        self._refresh_list()


class SensorFilterWidget(QGroupBox):
    """Widget for enabling/disabling sensor triggers."""
    
    def __init__(self, controller: ExperimentController, parent=None):
        super().__init__("🎛️ Sensor Trigger Filters", parent)
        self.controller = controller
        self._setup_ui()
    
    def _setup_ui(self):
        layout = QVBoxLayout(self)
        
        # Info label
        info_label = QLabel(
            "Select which sensors can trigger transitions.\n"
            "Disabled sensors are monitored but won't cause auto-reprogram."
        )
        info_label.setStyleSheet("color: #888; font-size: 9pt;")
        info_label.setWordWrap(True)
        layout.addWidget(info_label)
        
        # Checkboxes in a grid
        grid = QGridLayout()
        
        self.chk_f = QCheckBox("F (AM)")
        self.chk_f.setChecked(True)
        self.chk_f.toggled.connect(lambda checked: self.controller.set_sensor_enabled('F', checked))
        grid.addWidget(self.chk_f, 0, 0)
        
        self.chk_rf = QCheckBox("RF (LF)")
        self.chk_rf.setChecked(True)
        self.chk_rf.toggled.connect(lambda checked: self.controller.set_sensor_enabled('RF', checked))
        grid.addWidget(self.chk_rf, 0, 1)
        
        self.chk_uart = QCheckBox("UART")
        self.chk_uart.setChecked(True)
        self.chk_uart.toggled.connect(lambda checked: self.controller.set_sensor_enabled('UART', checked))
        grid.addWidget(self.chk_uart, 1, 0)
        
        self.chk_obi = QCheckBox("OBI")
        self.chk_obi.setChecked(True)
        self.chk_obi.toggled.connect(lambda checked: self.controller.set_sensor_enabled('OBI', checked))
        grid.addWidget(self.chk_obi, 1, 1)
        
        layout.addLayout(grid)
        
        # Quick buttons
        btn_layout = QHBoxLayout()
        
        btn_all = QPushButton("Enable All")
        btn_all.clicked.connect(self._enable_all)
        btn_layout.addWidget(btn_all)
        
        btn_none = QPushButton("Disable All")
        btn_none.clicked.connect(self._disable_all)
        btn_layout.addWidget(btn_none)
        
        layout.addLayout(btn_layout)
    
    def _enable_all(self):
        self.chk_f.setChecked(True)
        self.chk_rf.setChecked(True)
        self.chk_uart.setChecked(True)
        self.chk_obi.setChecked(True)
    
    def _disable_all(self):
        self.chk_f.setChecked(False)
        self.chk_rf.setChecked(False)
        self.chk_uart.setChecked(False)
        self.chk_obi.setChecked(False)


class RadiationConfigWidget(QGroupBox):
    """Widget for radiation dose configuration."""
    
    def __init__(self, controller: ExperimentController, parent=None):
        super().__init__("☢️ Radiation Configuration", parent)
        self.controller = controller
        self._setup_ui()
    
    def _setup_ui(self):
        layout = QGridLayout(self)
        
        # Dose rate
        layout.addWidget(QLabel("Dose Rate:"), 0, 0)
        self.spin_dose_rate = QDoubleSpinBox()
        self.spin_dose_rate.setRange(0.0, 1000.0)
        self.spin_dose_rate.setDecimals(3)
        self.spin_dose_rate.setValue(0.0)
        self.spin_dose_rate.setSuffix(" krad/h")
        self.spin_dose_rate.valueChanged.connect(
            lambda v: self.controller.set_dose_rate(v)
        )
        layout.addWidget(self.spin_dose_rate, 0, 1)
        
        # Initial dose
        layout.addWidget(QLabel("Initial Dose:"), 1, 0)
        self.spin_initial_dose = QDoubleSpinBox()
        self.spin_initial_dose.setRange(0.0, 100000.0)
        self.spin_initial_dose.setDecimals(2)
        self.spin_initial_dose.setValue(0.0)
        self.spin_initial_dose.setSuffix(" krad")
        self.spin_initial_dose.valueChanged.connect(
            lambda v: self.controller.set_initial_dose(v)
        )
        layout.addWidget(self.spin_initial_dose, 1, 1)
        
        # Current dose display
        layout.addWidget(QLabel("Current Dose:"), 2, 0)
        self.lbl_current_dose = QLabel("0.00 krad")
        self.lbl_current_dose.setStyleSheet("font-weight: bold; color: #ffc107;")
        layout.addWidget(self.lbl_current_dose, 2, 1)
    
    def update_current_dose(self, dose: float):
        """Update current dose display."""
        self.lbl_current_dose.setText(f"{dose:.2f} krad")


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
        self.chk_auto_program.setStyleSheet("font-weight: bold;")
        self.chk_auto_program.toggled.connect(self._on_auto_program_toggled)
        layout.addWidget(self.chk_auto_program)
        
        # Timing configuration
        timing_layout = QGridLayout()
        
        timing_layout.addWidget(QLabel("Stabilization:"), 0, 0)
        self.spin_stabilization = QSpinBox()
        self.spin_stabilization.setRange(1000, 60000)
        self.spin_stabilization.setValue(3000)
        self.spin_stabilization.setSuffix(" ms")
        self.spin_stabilization.valueChanged.connect(
            lambda v: self.controller.set_stabilization_time(v)
        )
        timing_layout.addWidget(self.spin_stabilization, 0, 1)
        
        timing_layout.addWidget(QLabel("Cooldown:"), 1, 0)
        self.spin_cooldown = QSpinBox()
        self.spin_cooldown.setRange(1000, 120000)
        self.spin_cooldown.setValue(10000)
        self.spin_cooldown.setSuffix(" ms")
        self.spin_cooldown.valueChanged.connect(
            lambda v: self.controller.set_cooldown_time(v)
        )
        timing_layout.addWidget(self.spin_cooldown, 1, 1)
        
        layout.addLayout(timing_layout)
        
        # State display
        state_frame = QFrame()
        state_frame.setFrameStyle(QFrame.StyledPanel)
        state_layout = QVBoxLayout(state_frame)
        state_layout.setContentsMargins(5, 5, 5, 5)
        
        self.lbl_state = QLabel("State: IDLE")
        self.lbl_state.setStyleSheet("font-size: 12pt; font-weight: bold;")
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
            "background-color: #28a745; color: white; font-weight: bold; padding: 8px;"
        )
        self.btn_start.clicked.connect(self._start_experiment)
        btn_layout.addWidget(self.btn_start)
        
        self.btn_stop = QPushButton("⏹ Stop")
        self.btn_stop.setStyleSheet(
            "background-color: #dc3545; color: white; font-weight: bold; padding: 8px;"
        )
        self.btn_stop.clicked.connect(self._stop_experiment)
        self.btn_stop.setEnabled(False)
        btn_layout.addWidget(self.btn_stop)
        
        self.btn_skip = QPushButton("⏭ Skip")
        self.btn_skip.clicked.connect(self._skip_bitstream)
        self.btn_skip.setEnabled(False)
        btn_layout.addWidget(self.btn_skip)
        
        layout.addLayout(btn_layout)
        
        # Experiment time
        self.lbl_time = QLabel("Time: 00:00:00")
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
            'PROGRAMMING_INITIAL': ('#17a2b8', 'background-color: #1a2d3d;'),
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
            f"font-size: 12pt; font-weight: bold; padding: 5px; color: {color}; {bg}"
        )
        
        # Update current/next labels
        current = self.controller.current_bitstream
        next_bs = self.controller.next_bitstream
        
        if current:
            self.lbl_current.setText(f"Current: {current.name} ({current.phase_degrees}°)")
        else:
            self.lbl_current.setText("Current: ---")
        
        if next_bs:
            self.lbl_next.setText(f"Next: {next_bs.name} ({next_bs.phase_degrees}°)")
        else:
            self.lbl_next.setText("Next: (end of queue)")
        
        # Update button states
        is_running = state not in ('IDLE', 'FINISHED')
        self.btn_start.setEnabled(not is_running)
        self.btn_stop.setEnabled(is_running)
        self.btn_skip.setEnabled(is_running and state == 'RUNNING')
    
    def update_time(self):
        if self.controller._experiment_start is None:
            self.lbl_time.setText("Time: 00:00:00")
            return

        hours = self.controller.experiment_hours
        h = int(hours)
        m = int((hours - h) * 60)
        s = int(((hours - h) * 60 - m) * 60)
        self.lbl_time.setText(f"Time: {h:02d}:{m:02d}:{s:02d}")


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
        self.table.setColumnCount(7)
        self.table.setHorizontalHeaderLabels([
            "Time", "Hours", "Dose", "From → To", "Phase", "Triggers", "Alarms"
        ])
        self.table.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        self.table.setSelectionBehavior(QTableWidget.SelectRows)
        self.table.setAlternatingRowColors(True)
        self.table.setMaximumHeight(150)
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
        
        self.table.setItem(row, 0, QTableWidgetItem(event.timestamp.strftime("%H:%M:%S")))
        self.table.setItem(row, 1, QTableWidgetItem(f"{event.experiment_hours:.2f}"))
        self.table.setItem(row, 2, QTableWidgetItem(f"{event.radiation_dose_krad:.2f}"))
        self.table.setItem(row, 3, QTableWidgetItem(f"{event.from_bitstream} → {event.to_bitstream}"))
        self.table.setItem(row, 4, QTableWidgetItem(f"{event.from_phase}° → {event.to_phase}°"))
        
        triggers = []
        for sensor, bits in event.trigger_alarms.items():
            if bits:
                triggers.append(f"{sensor}:{len(bits)}")
        self.table.setItem(row, 5, QTableWidgetItem(", ".join(triggers)))
        self.table.setItem(row, 6, QTableWidgetItem(str(event.total_alarms)))
        
        self.table.scrollToBottom()
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


class SlackDegradationGraphWidget(QWidget):
    """
    Widget with tabbed graphs for slack degradation analysis.
    
    Contains two graphs:
    1. Slack vs Radiation Dose
    2. Slack vs Time
    
    Both include real-time data points and linear regression projections.
    """
    
    def __init__(self, controller: ExperimentController, parent=None):
        super().__init__(parent)
        self.controller = controller
        
        # Data storage
        self._dose_data = []      # (dose_krad, slack_ns)
        self._time_data = []      # (hours, slack_ns)
        
        # Projection settings
        self._projection_points = 50  # Number of projection points
        self._projection_factor = 1.5  # Project 50% beyond data range
        
        self._setup_ui()
        
        # Connect signals
        self.controller.transition_logged.connect(self._on_transition)
    
    def _setup_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        
        # Tab widget for graphs
        self.tab_widget = QTabWidget()
        
        # Graph 1: Slack vs Dose
        self.dose_graph_widget = pg.PlotWidget()
        self.dose_graph_widget.setBackground('#1e1e1e')
        self.dose_graph_widget.setTitle("Slack Degradation vs Radiation Dose", color='w')
        self.dose_graph_widget.setLabel('left', 'Slack (ns)', color='w')
        self.dose_graph_widget.setLabel('bottom', 'Radiation Dose (krad)', color='w')
        self.dose_graph_widget.showGrid(x=True, y=True, alpha=0.3)
        self.dose_graph_widget.addLegend()
        
        # Data scatter plot
        self.dose_scatter = pg.ScatterPlotItem(
            pen=pg.mkPen(None),
            brush=pg.mkBrush(66, 165, 245, 200),
            size=10,
            name='Measured'
        )
        self.dose_graph_widget.addItem(self.dose_scatter)
        
        # Regression line
        self.dose_regression_line = pg.PlotDataItem(
            pen=pg.mkPen(color=(255, 193, 7), width=2),
            name='Linear Fit'
        )
        self.dose_graph_widget.addItem(self.dose_regression_line)
        
        # Projection line (dashed)
        self.dose_projection_line = pg.PlotDataItem(
            pen=pg.mkPen(color=(255, 87, 34), width=2, style=Qt.DashLine),
            name='Projection'
        )
        self.dose_graph_widget.addItem(self.dose_projection_line)
        
        self.tab_widget.addTab(self.dose_graph_widget, "📊 Slack vs Dose")
        
        # Graph 2: Slack vs Time
        self.time_graph_widget = pg.PlotWidget()
        self.time_graph_widget.setBackground('#1e1e1e')
        self.time_graph_widget.setTitle("Slack Degradation vs Time", color='w')
        self.time_graph_widget.setLabel('left', 'Slack (ns)', color='w')
        self.time_graph_widget.setLabel('bottom', 'Experiment Time (hours)', color='w')
        self.time_graph_widget.showGrid(x=True, y=True, alpha=0.3)
        self.time_graph_widget.addLegend()
        
        # Data scatter plot
        self.time_scatter = pg.ScatterPlotItem(
            pen=pg.mkPen(None),
            brush=pg.mkBrush(76, 175, 80, 200),
            size=10,
            name='Measured'
        )
        self.time_graph_widget.addItem(self.time_scatter)
        
        # Regression line
        self.time_regression_line = pg.PlotDataItem(
            pen=pg.mkPen(color=(255, 193, 7), width=2),
            name='Linear Fit'
        )
        self.time_graph_widget.addItem(self.time_regression_line)
        
        # Projection line (dashed)
        self.time_projection_line = pg.PlotDataItem(
            pen=pg.mkPen(color=(255, 87, 34), width=2, style=Qt.DashLine),
            name='Projection'
        )
        self.time_graph_widget.addItem(self.time_projection_line)
        
        self.tab_widget.addTab(self.time_graph_widget, "⏱️ Slack vs Time")
        
        layout.addWidget(self.tab_widget)
        
        # Info label
        self.lbl_regression_info = QLabel("Regression: No data yet")
        self.lbl_regression_info.setStyleSheet("color: #888; font-size: 9pt;")
        layout.addWidget(self.lbl_regression_info)
    
    def _phase_to_slack_ns(self, phase_degrees: float, clock_period_ns: float = 50.0) -> float:
        """
        Convert phase degrees to slack in nanoseconds.
        
        Phase is negative (e.g., -330°), slack is positive.
        Slack = |phase| * (clock_period / 360)
        """
        return abs(phase_degrees) * (clock_period_ns / 360.0)
    
    @Slot(object)
    def _on_transition(self, event: TransitionEvent):
        """Handle new transition - add data point."""
        # Calculate slack from the "to" phase (the new bitstream)
        slack_ns = self._phase_to_slack_ns(event.to_phase)
        
        # Add to data
        self._dose_data.append((event.radiation_dose_krad, slack_ns))
        self._time_data.append((event.experiment_hours, slack_ns))
        
        # Update graphs
        self._update_graphs()
    
    def _update_graphs(self):
        """Update both graphs with current data."""
        # Update Dose graph
        if self._dose_data:
            doses = [d[0] for d in self._dose_data]
            slacks = [d[1] for d in self._dose_data]
            
            self.dose_scatter.setData(doses, slacks)
            self._update_regression(doses, slacks, 
                                   self.dose_regression_line, 
                                   self.dose_projection_line,
                                   'dose')
        
        # Update Time graph
        if self._time_data:
            times = [d[0] for d in self._time_data]
            slacks = [d[1] for d in self._time_data]
            
            self.time_scatter.setData(times, slacks)
            self._update_regression(times, slacks,
                                   self.time_regression_line,
                                   self.time_projection_line,
                                   'time')
    
    def _update_regression(self, x_data, y_data, reg_line, proj_line, graph_type):
        """Update regression and projection lines."""
        if len(x_data) < 2:
            reg_line.setData([], [])
            proj_line.setData([], [])
            return
        
        x = np.array(x_data)
        y = np.array(y_data)
        
        try:
            # Linear regression: y = mx + b
            coeffs = np.polyfit(x, y, 1)
            m, b = coeffs[0], coeffs[1]
            
            # Regression line (within data range)
            x_fit = np.linspace(x.min(), x.max(), 100)
            y_fit = m * x_fit + b
            reg_line.setData(x_fit, y_fit)
            
            # Projection line (beyond data range)
            x_max = x.max()
            x_proj_end = x_max * self._projection_factor
            
            if x_proj_end > x_max:
                x_proj = np.linspace(x_max, x_proj_end, self._projection_points)
                y_proj = m * x_proj + b
                proj_line.setData(x_proj, y_proj)
            else:
                proj_line.setData([], [])
            
            # Update info label
            if graph_type == 'dose':
                rate_str = f"Slack degradation rate: {m:.4f} ns/krad"
            else:
                rate_str = f"Slack degradation rate: {m:.4f} ns/hour"
            
            r_squared = self._calculate_r_squared(x, y, m, b)
            self.lbl_regression_info.setText(f"{rate_str} | R² = {r_squared:.4f}")
            
        except Exception as e:
            reg_line.setData([], [])
            proj_line.setData([], [])
            self.lbl_regression_info.setText(f"Regression error: {e}")
    
    def _calculate_r_squared(self, x, y, m, b):
        """Calculate R-squared value for the linear fit."""
        y_pred = m * x + b
        ss_res = np.sum((y - y_pred) ** 2)
        ss_tot = np.sum((y - np.mean(y)) ** 2)
        
        if ss_tot == 0:
            return 1.0
        
        return 1 - (ss_res / ss_tot)
    
    def clear_data(self):
        """Clear all graph data."""
        self._dose_data.clear()
        self._time_data.clear()
        
        self.dose_scatter.setData([], [])
        self.dose_regression_line.setData([], [])
        self.dose_projection_line.setData([], [])
        
        self.time_scatter.setData([], [])
        self.time_regression_line.setData([], [])
        self.time_projection_line.setData([], [])
        
        self.lbl_regression_info.setText("Regression: No data yet")


class AgingAnalysisWidgetV2(QWidget):
    """
    Main aging analysis widget - Version 2.
    
    Features:
    - Bitstream queue with negative phase support
    - Sensor enable/disable checkboxes
    - Radiation dose configuration
    - Auto-program with initial bitstream verification
    - Slack degradation graphs with projections
    
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
        
        # Left panel: Queue, Filters, Radiation, Control
        left_panel = QWidget()
        left_layout = QVBoxLayout(left_panel)
        left_layout.setContentsMargins(0, 0, 0, 0)
        left_layout.setSpacing(5)
        
        # Queue widget
        self.queue_widget = BitstreamQueueWidget(self.controller)
        left_layout.addWidget(self.queue_widget)
        
        # Sensor filter widget
        self.sensor_filter = SensorFilterWidget(self.controller)
        left_layout.addWidget(self.sensor_filter)
        
        # Radiation config widget
        self.radiation_config = RadiationConfigWidget(self.controller)
        left_layout.addWidget(self.radiation_config)
        
        # Control widget
        self.control_widget = ExperimentControlWidget(self.controller)
        left_layout.addWidget(self.control_widget)
        
        # Right panel: History + Graphs
        right_panel = QWidget()
        right_layout = QVBoxLayout(right_panel)
        right_layout.setContentsMargins(0, 0, 0, 0)
        right_layout.setSpacing(5)
        
        # Transition history
        self.history_widget = TransitionHistoryWidget(self.controller)
        right_layout.addWidget(self.history_widget)
        
        # Graphs widget (tabbed)
        self.graphs_widget = SlackDegradationGraphWidget(self.controller)
        right_layout.addWidget(self.graphs_widget, 1)  # Stretch factor
        
        # Splitter
        splitter = QSplitter(Qt.Horizontal)
        splitter.addWidget(left_panel)
        splitter.addWidget(right_panel)
        splitter.setSizes([380, 620])
        
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
        self.radiation_config.update_current_dose(self.controller.current_dose_krad)
    
    @Slot()
    def _on_experiment_finished(self):
        """Handle experiment completion."""
        QMessageBox.information(
            self, "Experiment Finished",
            f"Experiment completed!\n"
            f"Total transitions: {len(self.controller.transitions)}\n"
            f"Duration: {self.controller.experiment_hours:.2f} hours\n"
            f"Final dose: {self.controller.current_dose_krad:.2f} krad"
        )
    
    # =========================================================================
    # Public API (for MainWindow integration)
    # =========================================================================
    
    def process_sensor_data(self, alarm_f: int, alarm_rf: int,
                            alarm_uart: int = 0, alarm_obi_dmx: int = 0):
        """Process incoming sensor data."""
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
    
    def set_current_bitstream(self, name: str):
        """Set the currently programmed bitstream."""
        self.controller.set_current_programmed_bitstream(name)
    
    def on_reprogram_complete(self, success: bool, bitstream_name: str = ""):
        """Called when FPGA reprogramming completes."""
        self.controller.on_reprogram_complete(success, bitstream_name)
    
    def check_alarms(self, alarm_f: int, alarm_rf: int,
                     alarm_uart: int = 0, alarm_obi_dmx: int = 0) -> bool:
        """Check for new alarms (compatibility method)."""
        total = (bin(alarm_f).count('1') + bin(alarm_rf).count('1') +
                 bin(alarm_uart).count('1') + bin(alarm_obi_dmx).count('1'))
        
        new_alarms = total > self._last_total_alarms
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