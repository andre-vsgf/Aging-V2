# -*- coding: utf-8 -*-
"""
Aging Analysis Widget - CORRECTED VERSION

Provides UI for:
- Configuring radiation model (dose rate, experiment start)
- Managing bitstream calibrations
- Viewing aging event log
- Plotting slack vs radiation dose

FIXES:
- Corrected 'dose_krad' to 'radiation_dose_krad' to match AgingEvent definition
- Added _last_total_alarms initialization in __init__
- Added _last_alarm_* attributes for individual sensor tracking
- Updated check_alarms() to support 4 sensor types
"""

import pyqtgraph as pg
from datetime import datetime
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QGridLayout,
    QGroupBox, QLabel, QPushButton, QDoubleSpinBox,
    QTableWidget, QTableWidgetItem, QHeaderView,
    QSplitter, QTabWidget, QLineEdit, QSpinBox,
    QFileDialog, QMessageBox, QFrame, QComboBox,
    QTextEdit, QCheckBox
)
from PySide6.QtCore import Qt, Signal, Slot
from PySide6.QtGui import QColor, QFont

from aging_logger import AgingLogger, AgingEvent
from bitstream_calibration import CalibrationManager, BitstreamCalibration


class RadiationConfigWidget(QGroupBox):
    """Widget for configuring radiation model parameters."""
    
    config_changed = Signal()
    experiment_started = Signal()
    
    def __init__(self, logger: AgingLogger, parent=None):
        super().__init__("Radiation Configuration", parent)
        self.logger = logger
        self._setup_ui()
    
    def _setup_ui(self):
        layout = QGridLayout(self)
        
        # Dose rate
        layout.addWidget(QLabel("Dose Rate:"), 0, 0)
        self.spin_dose_rate = QDoubleSpinBox()
        self.spin_dose_rate.setRange(0.001, 1000.0)
        self.spin_dose_rate.setDecimals(3)
        self.spin_dose_rate.setValue(self.logger.radiation_model.dose_rate_krad_per_hour)
        self.spin_dose_rate.setSuffix(" krad/h")
        self.spin_dose_rate.valueChanged.connect(self._on_dose_rate_changed)
        layout.addWidget(self.spin_dose_rate, 0, 1)
        
        # Initial dose
        layout.addWidget(QLabel("Initial Dose:"), 1, 0)
        self.spin_initial_dose = QDoubleSpinBox()
        self.spin_initial_dose.setRange(0.0, 10000.0)
        self.spin_initial_dose.setDecimals(2)
        self.spin_initial_dose.setValue(self.logger.radiation_model.initial_dose_krad)
        self.spin_initial_dose.setSuffix(" krad")
        layout.addWidget(self.spin_initial_dose, 1, 1)
        
        # Experiment start button
        self.btn_start = QPushButton("▶ Start Experiment")
        self.btn_start.setStyleSheet("background-color: #28a745; color: white; font-weight: bold;")
        self.btn_start.clicked.connect(self._start_experiment)
        layout.addWidget(self.btn_start, 2, 0, 1, 2)
        
        # Status
        self.lbl_status = QLabel("Experiment not started")
        self.lbl_status.setStyleSheet("color: #888;")
        layout.addWidget(self.lbl_status, 3, 0, 1, 2)
        
        # Current values
        self.lbl_time = QLabel("Time: --:--:--")
        layout.addWidget(self.lbl_time, 4, 0)
        
        self.lbl_dose = QLabel("Dose: --- krad")
        layout.addWidget(self.lbl_dose, 4, 1)
    
    def _on_dose_rate_changed(self, value):
        self.logger.radiation_model.set_dose_rate(value)
        self.config_changed.emit()
    
    def _start_experiment(self):
        initial = self.spin_initial_dose.value()
        self.logger.radiation_model.start_experiment(initial)
        
        self.btn_start.setText("⏹ Reset Experiment")
        self.btn_start.setStyleSheet("background-color: #dc3545; color: white; font-weight: bold;")
        self.btn_start.clicked.disconnect()
        self.btn_start.clicked.connect(self._reset_experiment)
        
        self.lbl_status.setText(f"Started: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        self.lbl_status.setStyleSheet("color: #28a745; font-weight: bold;")
        
        self.experiment_started.emit()
    
    def _reset_experiment(self):
        reply = QMessageBox.question(
            self, "Reset Experiment",
            "Are you sure you want to reset the experiment timer?\nThis will NOT clear logged events.",
            QMessageBox.Yes | QMessageBox.No
        )
        
        if reply == QMessageBox.Yes:
            self.logger.radiation_model.experiment_start = None
            
            self.btn_start.setText("▶ Start Experiment")
            self.btn_start.setStyleSheet("background-color: #28a745; color: white; font-weight: bold;")
            self.btn_start.clicked.disconnect()
            self.btn_start.clicked.connect(self._start_experiment)
            
            self.lbl_status.setText("Experiment not started")
            self.lbl_status.setStyleSheet("color: #888;")
    
    def update_display(self):
        """Update time and dose display."""
        if self.logger.radiation_model.experiment_start:
            hours = self.logger.radiation_model.get_experiment_hours()
            dose = self.logger.radiation_model.get_dose()
            
            h = int(hours)
            m = int((hours - h) * 60)
            s = int(((hours - h) * 60 - m) * 60)
            
            self.lbl_time.setText(f"Time: {h:02d}:{m:02d}:{s:02d}")
            self.lbl_dose.setText(f"Dose: {dose:.2f} krad")


class CalibrationTableWidget(QGroupBox):
    """Widget for managing bitstream calibrations."""
    
    calibration_selected = Signal(str, float, float)  # name, phase, slack
    
    def __init__(self, cal_manager: CalibrationManager, parent=None):
        super().__init__("Bitstream Calibrations", parent)
        self.cal_manager = cal_manager
        self._setup_ui()
        self._refresh_table()
        
        self.cal_manager.calibration_changed.connect(self._refresh_table)
    
    def _setup_ui(self):
        layout = QVBoxLayout(self)
        
        # Clock period setting
        period_layout = QHBoxLayout()
        period_layout.addWidget(QLabel("Clock Period:"))
        self.spin_period = QDoubleSpinBox()
        self.spin_period.setRange(1.0, 1000.0)
        self.spin_period.setDecimals(2)
        self.spin_period.setValue(self.cal_manager.clock_period_ns)
        self.spin_period.setSuffix(" ns")
        self.spin_period.valueChanged.connect(self._on_period_changed)
        period_layout.addWidget(self.spin_period)
        period_layout.addStretch()
        layout.addLayout(period_layout)
        
        # Table
        self.table = QTableWidget()
        self.table.setColumnCount(4)
        self.table.setHorizontalHeaderLabels(["Bitstream", "Phase (°)", "Slack (ns)", "Order"])
        self.table.horizontalHeader().setSectionResizeMode(0, QHeaderView.Stretch)
        self.table.setSelectionBehavior(QTableWidget.SelectRows)
        self.table.setSelectionMode(QTableWidget.SingleSelection)
        self.table.itemSelectionChanged.connect(self._on_selection_changed)
        layout.addWidget(self.table)
        
        # Add entry
        add_layout = QHBoxLayout()
        self.txt_name = QLineEdit()
        self.txt_name.setPlaceholderText("Bitstream name...")
        add_layout.addWidget(self.txt_name, 2)
        
        self.spin_phase = QDoubleSpinBox()
        self.spin_phase.setRange(-180.0, 360.0)
        self.spin_phase.setDecimals(2)
        self.spin_phase.setSuffix("°")
        add_layout.addWidget(self.spin_phase, 1)
        
        btn_add = QPushButton("+ Add")
        btn_add.clicked.connect(self._add_calibration)
        add_layout.addWidget(btn_add)
        
        btn_remove = QPushButton("- Remove")
        btn_remove.clicked.connect(self._remove_calibration)
        add_layout.addWidget(btn_remove)
        
        layout.addLayout(add_layout)
        
        # Import/Export buttons
        btn_layout = QHBoxLayout()
        
        btn_import = QPushButton("Import from Dir")
        btn_import.clicked.connect(self._import_from_dir)
        btn_layout.addWidget(btn_import)
        
        btn_save = QPushButton("Save")
        btn_save.clicked.connect(lambda: self.cal_manager.save())
        btn_layout.addWidget(btn_save)
        
        btn_load = QPushButton("Load")
        btn_load.clicked.connect(self._load_calibrations)
        btn_layout.addWidget(btn_load)
        
        layout.addLayout(btn_layout)
    
    def _on_period_changed(self, value):
        self.cal_manager.clock_period_ns = value
        self._refresh_table()
    
    def _refresh_table(self):
        self.table.setRowCount(0)
        
        for cal in self.cal_manager.get_all_calibrations():
            row = self.table.rowCount()
            self.table.insertRow(row)
            
            self.table.setItem(row, 0, QTableWidgetItem(cal.name))
            self.table.setItem(row, 1, QTableWidgetItem(f"{cal.phase_degrees:.2f}"))
            self.table.setItem(row, 2, QTableWidgetItem(f"{cal.slack_ns:.3f}"))
            self.table.setItem(row, 3, QTableWidgetItem(str(cal.order)))
    
    def _on_selection_changed(self):
        rows = self.table.selectionModel().selectedRows()
        if rows:
            row = rows[0].row()
            name = self.table.item(row, 0).text()
            phase = float(self.table.item(row, 1).text())
            slack = float(self.table.item(row, 2).text())
            self.calibration_selected.emit(name, phase, slack)
    
    def _add_calibration(self):
        name = self.txt_name.text().strip()
        if not name:
            return
        
        phase = self.spin_phase.value()
        self.cal_manager.add_calibration(name, phase)
        self.txt_name.clear()
    
    def _remove_calibration(self):
        rows = self.table.selectionModel().selectedRows()
        if not rows:
            return
        
        row = rows[0].row()
        name = self.table.item(row, 0).text()
        self.cal_manager.remove_calibration(name)
    
    def _import_from_dir(self):
        path = QFileDialog.getExistingDirectory(self, "Select Bitstream Directory")
        if path:
            count = self.cal_manager.import_from_directory(path)
            QMessageBox.information(self, "Import", f"Imported {count} bitstreams")
    
    def _load_calibrations(self):
        self.cal_manager.load()
        self._refresh_table()


class AgingEventLogWidget(QGroupBox):
    """Widget for displaying aging event log."""
    
    def __init__(self, logger: AgingLogger, parent=None):
        super().__init__("Aging Event Log", parent)
        self.logger = logger
        self._setup_ui()
        
        self.logger.event_logged.connect(self._on_event_logged)
    
    def _setup_ui(self):
        layout = QVBoxLayout(self)
        
        # Summary
        self.lbl_summary = QLabel("Events: 0 | Bitstream changes: 0")
        self.lbl_summary.setStyleSheet("color: #888;")
        layout.addWidget(self.lbl_summary)
        
        # Table
        self.table = QTableWidget()
        self.table.setColumnCount(6)
        self.table.setHorizontalHeaderLabels([
            "Time", "Dose (krad)", "Bitstream", "Phase (°)", "Slack (ns)", "Type"
        ])
        self.table.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        self.table.setSelectionBehavior(QTableWidget.SelectRows)
        layout.addWidget(self.table)
        
        # Controls
        ctrl_layout = QHBoxLayout()
        
        btn_refresh = QPushButton("🔄 Refresh")
        btn_refresh.clicked.connect(self._refresh_log)
        ctrl_layout.addWidget(btn_refresh)
        
        btn_export = QPushButton("📁 Export CSV")
        btn_export.clicked.connect(self._export_csv)
        ctrl_layout.addWidget(btn_export)
        
        btn_clear = QPushButton("🗑 Clear")
        btn_clear.clicked.connect(self._clear_log)
        ctrl_layout.addWidget(btn_clear)
        
        ctrl_layout.addStretch()
        layout.addLayout(ctrl_layout)
        
        self._refresh_log()
    
    @Slot()
    def _on_event_logged(self):
        self._refresh_log()
    
    def _refresh_log(self):
        self.table.setRowCount(0)
        
        for event in self.logger.get_all_events():
            row = self.table.rowCount()
            self.table.insertRow(row)
            
            # Format timestamp safely
            if isinstance(event.timestamp, datetime):
                time_str = event.timestamp.strftime("%H:%M:%S")
            else:
                time_str = str(event.timestamp)

            self.table.setItem(row, 0, QTableWidgetItem(time_str))
            
            # FIX: Use correct attribute name 'radiation_dose_krad'
            self.table.setItem(row, 1, QTableWidgetItem(f"{event.radiation_dose_krad:.2f}"))
            
            self.table.setItem(row, 2, QTableWidgetItem(event.bitstream_name))
            self.table.setItem(row, 3, QTableWidgetItem(f"{event.phase_degrees:.2f}"))
            self.table.setItem(row, 4, QTableWidgetItem(f"{event.slack_ns:.3f}"))
            self.table.setItem(row, 5, QTableWidgetItem(event.event_type))
        
        self._update_summary()
    
    def _update_summary(self):
        events = self.logger.get_all_events()
        bitstream_changes = sum(1 for e in events if e.event_type == "bitstream_change")
        self.lbl_summary.setText(f"Events: {len(events)} | Bitstream changes: {bitstream_changes}")
    
    def _export_csv(self):
        path, _ = QFileDialog.getSaveFileName(
            self, "Export Log",
            f"aging_log_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv",
            "CSV Files (*.csv)"
        )
        if path:
            self.logger.save_csv(path)
            QMessageBox.information(self, "Export", f"Log exported to {path}")
    
    def _clear_log(self):
        reply = QMessageBox.question(
            self, "Clear Log",
            "Are you sure you want to clear all logged events?",
            QMessageBox.Yes | QMessageBox.No
        )
        if reply == QMessageBox.Yes:
            self.logger.clear()
            self.table.setRowCount(0)
            self._update_summary()


class AgingPlotWidget(QGroupBox):
    """Widget for plotting slack vs radiation dose."""
    
    def __init__(self, logger: AgingLogger, parent=None):
        super().__init__("Aging Analysis Plot", parent)
        self.logger = logger
        self._setup_ui()
        
        self.logger.event_logged.connect(self._update_plot)
    
    def _setup_ui(self):
        layout = QVBoxLayout(self)
        
        # Plot widget
        pg.setConfigOptions(antialias=True)
        self.plot_widget = pg.PlotWidget()
        self.plot_widget.setBackground('#1e1e1e')
        self.plot_widget.setLabel('left', 'Slack', units='ns')
        self.plot_widget.setLabel('bottom', 'Radiation Dose', units='krad')
        self.plot_widget.setTitle('Slack Degradation vs Radiation Dose')
        self.plot_widget.showGrid(x=True, y=True, alpha=0.3)
        
        # Data scatter
        self.scatter = pg.ScatterPlotItem(
            pen=pg.mkPen(None),
            brush=pg.mkBrush(79, 195, 247, 200),
            size=10
        )
        self.plot_widget.addItem(self.scatter)
        
        # Trend line
        self.trend_line = pg.PlotDataItem(
            pen=pg.mkPen('#ff5722', width=2, style=Qt.DashLine)
        )
        self.plot_widget.addItem(self.trend_line)
        
        layout.addWidget(self.plot_widget)
        
        # Controls
        ctrl_layout = QHBoxLayout()
        
        btn_refresh = QPushButton("🔄 Refresh")
        btn_refresh.clicked.connect(self._update_plot)
        ctrl_layout.addWidget(btn_refresh)
        
        self.chk_trend = QCheckBox("Show Trend Line")
        self.chk_trend.setChecked(True)
        self.chk_trend.stateChanged.connect(self._update_plot)
        ctrl_layout.addWidget(self.chk_trend)
        
        ctrl_layout.addStretch()
        layout.addLayout(ctrl_layout)
    
    @Slot()
    def _update_plot(self):
        data = self.logger.get_slack_vs_dose_data()
        
        if not data:
            self.scatter.setData([], [])
            self.trend_line.setData([], [])
            return
        
        doses = [d['dose_krad'] for d in data]
        slacks = [d['slack_ns'] for d in data]
        
        # Update scatter
        self.scatter.setData(doses, slacks)
        
        # Update trend line (simple linear fit)
        if self.chk_trend.isChecked() and len(doses) > 1:
            import numpy as np
            try:
                coeffs = np.polyfit(doses, slacks, 1)
                x_fit = np.linspace(min(doses), max(doses), 100)
                y_fit = np.polyval(coeffs, x_fit)
                self.trend_line.setData(x_fit, y_fit)
            except:
                self.trend_line.setData([], [])
        else:
            self.trend_line.setData([], [])


class AgingAnalysisWidget(QWidget):
    """
    Main widget combining all aging analysis components.
    
    CRITICAL FIX: Added _last_total_alarms and individual alarm trackers
    in __init__ to prevent AttributeError.
    """
    
    # Signal for auto-reprogram
    request_reprogram = Signal(str)  # bitstream name
    
    def __init__(self, parent=None):
        super().__init__(parent)
        
        # Create managers
        self.logger = AgingLogger()
        self.cal_manager = CalibrationManager()
        
        # =====================================================================
        # CRITICAL FIX: Initialize alarm tracking attributes
        # =====================================================================
        self._last_total_alarms = 0
        self._last_alarm_f = 0
        self._last_alarm_rf = 0
        self._last_alarm_uart = 0
        self._last_alarm_obi_dmx = 0
        # =====================================================================
        
        # Try to load saved data
        self.cal_manager.load()
        self.logger.load_json()
        
        self._setup_ui()
    
    def _setup_ui(self):
        layout = QHBoxLayout(self)
        
        # Left side: Configuration
        left_panel = QWidget()
        left_layout = QVBoxLayout(left_panel)
        left_layout.setContentsMargins(0, 0, 0, 0)
        
        # Radiation config
        self.radiation_config = RadiationConfigWidget(self.logger)
        left_layout.addWidget(self.radiation_config)
        
        # Calibration table
        self.calibration_table = CalibrationTableWidget(self.cal_manager)
        left_layout.addWidget(self.calibration_table)
        
        # Auto-reprogram settings
        auto_group = QGroupBox("Auto-Reprogram on Alarm")
        auto_layout = QVBoxLayout(auto_group)
        
        self.chk_auto_reprogram = QCheckBox("Enable auto-reprogram when alarm triggers")
        auto_layout.addWidget(self.chk_auto_reprogram)
        
        self.lbl_next_bitstream = QLabel("Next bitstream: ---")
        self.lbl_next_bitstream.setStyleSheet("color: #888;")
        auto_layout.addWidget(self.lbl_next_bitstream)
        
        left_layout.addWidget(auto_group)
        
        # Right side: Log and Plot
        right_panel = QWidget()
        right_layout = QVBoxLayout(right_panel)
        right_layout.setContentsMargins(0, 0, 0, 0)
        
        # Event log
        self.event_log = AgingEventLogWidget(self.logger)
        right_layout.addWidget(self.event_log, 1)
        
        # Plot
        self.plot = AgingPlotWidget(self.logger)
        right_layout.addWidget(self.plot, 1)
        
        # Add to main layout
        splitter = QSplitter(Qt.Horizontal)
        splitter.addWidget(left_panel)
        splitter.addWidget(right_panel)
        splitter.setSizes([400, 600])
        
        layout.addWidget(splitter)
    
    def set_current_bitstream(self, name: str):
        """Update current bitstream and associated calibration."""
        cal = self.cal_manager.get_calibration(name)
        if cal:
            self.logger.set_current_bitstream(name, cal.phase_degrees, cal.slack_ns)
        else:
            self.logger.set_current_bitstream(name, 0.0, 0.0)
        
        # Update next bitstream display
        next_bs = self.cal_manager.get_next_bitstream(name)
        if next_bs:
            self.lbl_next_bitstream.setText(f"Next bitstream: {next_bs}")
        else:
            self.lbl_next_bitstream.setText("Next bitstream: (end of sequence)")
    
    def set_environmental_data(self, **kwargs):
        """Update environmental readings."""
        self.logger.set_environmental_data(**kwargs)
    
    def check_alarms(self, alarm_f: int, alarm_rf: int, 
                     alarm_uart: int = 0, alarm_obi_dmx: int = 0) -> bool:
        """
        Check all 4 sensor types for new alarms.
        
        Args:
            alarm_f: AM sensor alarm register (32-bit)
            alarm_rf: LF sensor alarm register (32-bit)
            alarm_uart: UART sensor alarm register (32-bit)
            alarm_obi_dmx: OBI DMX sensor alarm register (32-bit)
            
        Returns:
            bool: True if any new alarms were detected
        """
        # Calculate total alarms across all 4 sensor types
        count_f = bin(alarm_f).count('1')
        count_rf = bin(alarm_rf).count('1')
        count_uart = bin(alarm_uart).count('1')
        count_obi = bin(alarm_obi_dmx).count('1')
        total_alarms = count_f + count_rf + count_uart + count_obi
        
        # Check for new alarms (any increase in alarm count)
        new_alarms_detected = total_alarms > self._last_total_alarms
        
        # Check for new alarm bits (not just count increase)
        new_f_bits = alarm_f & ~self._last_alarm_f
        new_rf_bits = alarm_rf & ~self._last_alarm_rf
        new_uart_bits = alarm_uart & ~self._last_alarm_uart
        new_obi_bits = alarm_obi_dmx & ~self._last_alarm_obi_dmx
        
        has_new_bits = (new_f_bits | new_rf_bits | new_uart_bits | new_obi_bits) != 0
        
        # Update tracking
        self._last_total_alarms = total_alarms
        self._last_alarm_f = alarm_f
        self._last_alarm_rf = alarm_rf
        self._last_alarm_uart = alarm_uart
        self._last_alarm_obi_dmx = alarm_obi_dmx
        
        # Return True if either total increased OR new bits appeared
        return new_alarms_detected or has_new_bits
    
    def get_alarm_counts(self) -> dict:
        """Return current alarm counts for all 4 sensor types."""
        return {
            'f': bin(self._last_alarm_f).count('1'),
            'rf': bin(self._last_alarm_rf).count('1'),
            'uart': bin(self._last_alarm_uart).count('1'),
            'obi_dmx': bin(self._last_alarm_obi_dmx).count('1'),
            'total': self._last_total_alarms
        }
    
    def reset_alarm_tracking(self):
        """Reset alarm tracking (e.g., after bitstream reprogram)."""
        self._last_total_alarms = 0
        self._last_alarm_f = 0
        self._last_alarm_rf = 0
        self._last_alarm_uart = 0
        self._last_alarm_obi_dmx = 0
    
    def update_display(self):
        """Update time-dependent displays."""
        self.radiation_config.update_display()
    
    def save_all(self):
        """Save all configuration and log data."""
        self.cal_manager.save()
        self.logger.save_json()
        self.logger.save_csv()