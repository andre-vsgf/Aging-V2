# -*- coding: utf-8 -*-
"""
Experiment Controller V2 - Auto-Program & Bitstream Queue Manager

UPDATED:
- Negative phase support (m330 = -330°, ordering from highest to lowest)
- Sensor filtering (enable/disable which sensors trigger transitions)
- Initial bitstream verification (programs first bitstream on start)
- Radiation dose tracking

WORKFLOW:
1. User loads bitstreams from directory (auto-sorted by phase, descending)
2. Experiment starts - verifies first bitstream is programmed
3. When enabled sensor alarm triggers → wait → reprogram with next bitstream
4. New bitstream has less negative phase (more "slack") → alarms should clear
5. Repeat until end of queue or experiment stopped

Author: CROC Project
"""

import os
import re
import json
from datetime import datetime, timedelta
from dataclasses import dataclass, asdict, field
from typing import List, Optional, Dict, Any, Callable, Set
from pathlib import Path
from enum import Enum, auto

from PySide6.QtCore import QObject, Signal, Slot, QTimer


class ExperimentState(Enum):
    """State machine for experiment controller."""
    IDLE = auto()              # Not running
    PROGRAMMING_INITIAL = auto()  # Programming first bitstream
    RUNNING = auto()           # Normal operation, monitoring alarms
    ALARM_DETECTED = auto()    # Alarm detected, waiting for stabilization
    REPROGRAMMING = auto()     # FPGA being reprogrammed
    COOLDOWN = auto()          # Post-reprogram cooldown (anti-loop)
    PAUSED = auto()            # Temporarily paused
    FINISHED = auto()          # Reached end of bitstream queue


@dataclass
class BitstreamEntry:
    """Entry in the bitstream queue."""
    filepath: str           # Full path to .bit file
    name: str               # Filename only
    phase_degrees: float    # Phase shift in degrees (negative values)
    phase_absolute: int     # Absolute value from filename (e.g., 330)
    order: int              # Position in queue (0 = first)
    
    def to_dict(self) -> dict:
        return asdict(self)
    
    @classmethod
    def from_dict(cls, data: dict) -> 'BitstreamEntry':
        return cls(**data)


@dataclass 
class TransitionEvent:
    """Records a bitstream transition event."""
    timestamp: datetime
    from_bitstream: str
    to_bitstream: str
    from_phase: float
    to_phase: float
    trigger_alarms: Dict[str, List[int]]  # {sensor_type: [bit_indices]} - legacy 4-sensor mode
    total_alarms: int
    experiment_hours: float
    radiation_dose_krad: float = 0.0
    fpga_temp: float = 0.0
    vccint: float = 0.0
    notes: str = ""
    is_multi_bank: bool = False
    banks_state: List[Dict] = field(default_factory=list)  # [{'bank_id': 0, 'alarm_bits': [], ...}, ...]
    
    def to_dict(self) -> dict:
        d = asdict(self)
        d['timestamp'] = self.timestamp.isoformat()
        return d
    
    @classmethod
    def from_dict(cls, data: dict) -> 'TransitionEvent':
        data['timestamp'] = datetime.fromisoformat(data['timestamp'])
        return cls(**data)
    
    def format_log_entry(self) -> str:
        """Format as human-readable log entry."""
        lines = [
            f"{'='*60}",
            f"BITSTREAM TRANSITION @ {self.timestamp.strftime('%Y-%m-%d %H:%M:%S')}",
            f"{'='*60}",
            f"  From: {self.from_bitstream} ({self.from_phase:.1f}°)",
            f"  To:   {self.to_bitstream} ({self.to_phase:.1f}°)",
            f"  Experiment Time: {self.experiment_hours:.2f} hours",
            f"  Radiation Dose: {self.radiation_dose_krad:.2f} krad",
            f"  FPGA Temp: {self.fpga_temp:.2f}°C | VCCINT: {self.vccint:.3f}V",
            f"",
            f"  TRIGGER ALARMS ({self.total_alarms} total):"
        ]
        
        for sensor_type, bits in self.trigger_alarms.items():
            if bits:
                lines.append(f"    {sensor_type}: bits {bits}")
        
        if self.notes:
            lines.append(f"  Notes: {self.notes}")
        
        lines.append(f"{'='*60}")
        return "\n".join(lines)


class RadiationModel:
    """Simple radiation dose model."""
    
    def __init__(self):
        self.dose_rate_krad_per_hour: float = 0.0
        self.initial_dose_krad: float = 0.0
        self.experiment_start: Optional[datetime] = None
    
    def set_dose_rate(self, rate: float):
        """Set dose rate in krad/hour."""
        self.dose_rate_krad_per_hour = rate
    
    def set_initial_dose(self, dose: float):
        """Set initial accumulated dose in krad."""
        self.initial_dose_krad = dose
    
    def start(self):
        """Start the radiation model timer."""
        self.experiment_start = datetime.now()
    
    def get_current_dose(self) -> float:
        """Calculate current accumulated dose."""
        if self.experiment_start is None:
            return self.initial_dose_krad
        
        hours = (datetime.now() - self.experiment_start).total_seconds() / 3600.0
        return self.initial_dose_krad + (hours * self.dose_rate_krad_per_hour)
    
    def get_experiment_hours(self) -> float:
        """Get experiment duration in hours."""
        if self.experiment_start is None:
            return 0.0
        return (datetime.now() - self.experiment_start).total_seconds() / 3600.0


class ExperimentController(QObject):
    """
    Main experiment controller with auto-program functionality.
    
    Signals:
        state_changed(str): Emitted when state changes
        transition_logged(TransitionEvent): Emitted when bitstream transition occurs
        request_reprogram(str): Request to reprogram FPGA with given bitstream path
        log_message(str): General log messages
        experiment_finished(): Emitted when queue exhausted
        queue_updated(): Emitted when queue changes
    """
    
    state_changed = Signal(str)
    transition_logged = Signal(object)  # TransitionEvent
    request_reprogram = Signal(str)     # filepath
    log_message = Signal(str)
    experiment_finished = Signal()
    queue_updated = Signal()
    
    # Configuration defaults
    DEFAULT_STABILIZATION_TIME_MS = 3000
    DEFAULT_COOLDOWN_TIME_MS = 10000
    DEFAULT_PHASE_STEP = 5.0
    
    # Regex to extract phase from filename (e.g., "m330" or "m175" or "p45")
    PHASE_REGEX = re.compile(r'[_]([mp])(\d+)\.bit$', re.IGNORECASE)
    
    def __init__(self, parent=None):
        super().__init__(parent)
        
        # State
        self._state = ExperimentState.IDLE
        self._queue: List[BitstreamEntry] = []
        self._current_index = 0
        self._transitions: List[TransitionEvent] = []
        
        # Configuration
        self._stabilization_time_ms = self.DEFAULT_STABILIZATION_TIME_MS
        self._cooldown_time_ms = self.DEFAULT_COOLDOWN_TIME_MS
        self._phase_step = self.DEFAULT_PHASE_STEP
        self._auto_program_enabled = False
        
        # Sensor filtering - which sensors can trigger transitions
        self._enabled_sensors: Dict[str, bool] = {
            'F': True,
            'RF': True,
            'UART': True,
            'OBI': True
        }
        
        # Radiation model
        self.radiation_model = RadiationModel()
        
        # Current bitstream tracking
        self._current_programmed_bitstream: Optional[str] = None
        
        # Timing
        self._experiment_start: Optional[datetime] = None
        self._last_reprogram_time: Optional[datetime] = None
        
        # Current alarm state (for detecting NEW alarms)
        self._last_alarm_f = 0
        self._last_alarm_rf = 0
        self._last_alarm_uart = 0
        self._last_alarm_obi = 0
        
        # Multi-bank tracking
        self._last_banks_state = []  # List of SensorBank objects
        
        # Pending alarm info (captured when alarm detected)
        self._pending_trigger_alarms: Dict[str, List[int]] = {}
        self._pending_total_alarms = 0
        self._pending_banks_state = []  # For multi-bank mode
        
        # Environmental data
        self._fpga_temp = 0.0
        self._vccint = 0.0
        
        # Timers
        self._stabilization_timer = QTimer(self)
        self._stabilization_timer.setSingleShot(True)
        self._stabilization_timer.timeout.connect(self._on_stabilization_complete)
        
        self._cooldown_timer = QTimer(self)
        self._cooldown_timer.setSingleShot(True)
        self._cooldown_timer.timeout.connect(self._on_cooldown_complete)
        
        # Log file
        self._log_file = "experiment_transitions.json"
    
    # =========================================================================
    # Properties
    # =========================================================================
    
    @property
    def state(self) -> ExperimentState:
        return self._state
    
    @property
    def state_str(self) -> str:
        return self._state.name
    
    @property
    def is_running(self) -> bool:
        return self._state in (ExperimentState.RUNNING, ExperimentState.ALARM_DETECTED,
                               ExperimentState.REPROGRAMMING, ExperimentState.COOLDOWN,
                               ExperimentState.PROGRAMMING_INITIAL)
    
    @property
    def auto_program_enabled(self) -> bool:
        return self._auto_program_enabled
    
    @auto_program_enabled.setter
    def auto_program_enabled(self, value: bool):
        self._auto_program_enabled = value
        self.log_message.emit(f"Auto-program {'enabled' if value else 'disabled'}")
    
    @property
    def current_bitstream(self) -> Optional[BitstreamEntry]:
        if 0 <= self._current_index < len(self._queue):
            return self._queue[self._current_index]
        return None
    
    @property
    def next_bitstream(self) -> Optional[BitstreamEntry]:
        next_idx = self._current_index + 1
        if next_idx < len(self._queue):
            return self._queue[next_idx]
        return None
    
    @property
    def queue_length(self) -> int:
        return len(self._queue)
    
    @property
    def queue_position(self) -> int:
        return self._current_index
    
    @property
    def experiment_hours(self) -> float:
        return self.radiation_model.get_experiment_hours()
    
    @property
    def current_dose_krad(self) -> float:
        return self.radiation_model.get_current_dose()
    
    @property
    def transitions(self) -> List[TransitionEvent]:
        return self._transitions.copy()
    
    @property
    def enabled_sensors(self) -> Dict[str, bool]:
        return self._enabled_sensors.copy()
    
    # =========================================================================
    # Configuration
    # =========================================================================
    
    def set_stabilization_time(self, ms: int):
        """Set time to wait after alarm before reprogramming."""
        self._stabilization_time_ms = max(1000, ms)
    
    def set_cooldown_time(self, ms: int):
        """Set time to wait after reprogram before monitoring."""
        self._cooldown_time_ms = max(1000, ms)
    
    def set_phase_step(self, degrees: float):
        """Set phase step between bitstreams."""
        self._phase_step = degrees
    
    def set_sensor_enabled(self, sensor: str, enabled: bool):
        """Enable or disable a sensor for triggering transitions."""
        if sensor in self._enabled_sensors:
            self._enabled_sensors[sensor] = enabled
            status = "enabled" if enabled else "disabled"
            self.log_message.emit(f"Sensor {sensor} {status} for transitions")
    
    def set_dose_rate(self, rate: float):
        """Set radiation dose rate in krad/hour."""
        self.radiation_model.set_dose_rate(rate)
        self.log_message.emit(f"Dose rate set to {rate:.3f} krad/h")
    
    def set_initial_dose(self, dose: float):
        """Set initial radiation dose in krad."""
        self.radiation_model.set_initial_dose(dose)
        self.log_message.emit(f"Initial dose set to {dose:.2f} krad")
    
    def set_current_programmed_bitstream(self, name: str):
        """Set the currently programmed bitstream name."""
        self._current_programmed_bitstream = name
    
    # =========================================================================
    # Queue Management
    # =========================================================================
    
    def clear_queue(self):
        """Clear the bitstream queue."""
        self._queue.clear()
        self._current_index = 0
        self.queue_updated.emit()
        self.log_message.emit("Bitstream queue cleared")
    
    def _extract_phase_from_filename(self, filename: str) -> tuple:
        """
        Extract phase information from filename.
        
        Examples:
            croc_aging_clkout3phase_m330.bit → (-330, 330)
            croc_aging_clkout3phase_m175.bit → (-175, 175)
            croc_aging_clkout3phase_p45.bit → (45, 45)
        
        Returns:
            tuple: (phase_degrees, phase_absolute)
        """
        match = self.PHASE_REGEX.search(filename)
        if match:
            sign = match.group(1).lower()
            value = int(match.group(2))
            
            if sign == 'm':  # minus/negative
                return (-value, value)
            else:  # 'p' = positive
                return (value, value)
        
        # Fallback: try to find any number at the end
        numbers = re.findall(r'(\d+)', filename)
        if numbers:
            value = int(numbers[-1])
            # Assume negative if the value is large (> 180)
            if value > 180:
                return (-value, value)
            return (value, value)
        
        return (0, 0)
    
    def add_bitstream(self, filepath: str, phase_degrees: float = None, order: int = -1):
        """Add a bitstream to the queue."""
        name = os.path.basename(filepath)
        
        # Extract phase from filename if not provided
        if phase_degrees is None:
            phase_degrees, phase_absolute = self._extract_phase_from_filename(name)
        else:
            phase_absolute = abs(int(phase_degrees))
        
        if order < 0:
            order = len(self._queue)
        
        entry = BitstreamEntry(
            filepath=filepath,
            name=name,
            phase_degrees=phase_degrees,
            phase_absolute=phase_absolute,
            order=order
        )
        
        self._queue.append(entry)
        self.queue_updated.emit()
        self.log_message.emit(f"Added bitstream: {name} ({phase_degrees}°)")
    
    def load_from_directory(self, directory: str) -> int:
        """
        Load bitstreams from directory, auto-detecting phases from filenames.
        
        Bitstreams are sorted by absolute phase value in DESCENDING order
        (330, 325, 320, 315...) because phases are negative and we start
        with the most negative (least slack) and progress to less negative
        (more slack).
        
        Returns:
            Number of bitstreams loaded
        """
        if not os.path.isdir(directory):
            return 0
        
        self.clear_queue()
        
        # Find all .bit files
        bitstreams = [
            f for f in os.listdir(directory)
            if f.lower().endswith('.bit')
        ]
        
        # Extract phase info and sort by absolute value (descending)
        bitstream_info = []
        for name in bitstreams:
            filepath = os.path.join(directory, name)
            phase_degrees, phase_absolute = self._extract_phase_from_filename(name)
            bitstream_info.append((filepath, name, phase_degrees, phase_absolute))
        
        # Sort by absolute phase value, DESCENDING (330, 325, 320...)
        bitstream_info.sort(key=lambda x: x[3], reverse=True)
        
        # Add to queue
        for i, (filepath, name, phase_degrees, phase_absolute) in enumerate(bitstream_info):
            entry = BitstreamEntry(
                filepath=filepath,
                name=name,
                phase_degrees=phase_degrees,
                phase_absolute=phase_absolute,
                order=i
            )
            self._queue.append(entry)
        
        self.queue_updated.emit()
        
        if self._queue:
            first = self._queue[0]
            last = self._queue[-1]
            self.log_message.emit(
                f"Loaded {len(bitstream_info)} bitstreams from {directory}\n"
                f"  First: {first.name} ({first.phase_degrees}°)\n"
                f"  Last:  {last.name} ({last.phase_degrees}°)"
            )
        
        return len(bitstream_info)
    
    def get_queue_info(self) -> List[Dict]:
        """Get queue information for display."""
        return [
            {
                'name': e.name,
                'phase': e.phase_degrees,
                'phase_abs': e.phase_absolute,
                'order': e.order,
                'current': i == self._current_index,
                'filepath': e.filepath
            }
            for i, e in enumerate(self._queue)
        ]
    
    # =========================================================================
    # Experiment Control
    # =========================================================================
    
    def start_experiment(self):
        """Start the experiment."""
        if not self._queue:
            self.log_message.emit("Cannot start: no bitstreams in queue")
            return False
        
        # Reset state
        self._current_index = 0
        self._transitions.clear()
        
        # Reset alarm tracking
        self._last_alarm_f = 0
        self._last_alarm_rf = 0
        self._last_alarm_uart = 0
        self._last_alarm_obi = 0
        
        # Start radiation model
        self.radiation_model.start()
        self._experiment_start = datetime.now()
        
        # Check if first bitstream is already programmed
        first_bitstream = self._queue[0]
        
        if self._current_programmed_bitstream == first_bitstream.name:
            # Already programmed, go directly to running
            self._set_state(ExperimentState.RUNNING)
            self.log_message.emit(
                f"Experiment started with {len(self._queue)} bitstreams\n"
                f"First bitstream already programmed: {first_bitstream.name}"
            )
        else:
            # Need to program first bitstream
            self._set_state(ExperimentState.PROGRAMMING_INITIAL)
            self.log_message.emit(
                f"Experiment starting - programming first bitstream: {first_bitstream.name}"
            )
            self.request_reprogram.emit(first_bitstream.filepath)
        
        return True
    
    def stop_experiment(self):
        self._stabilization_timer.stop()
        self._cooldown_timer.stop()
        self._set_state(ExperimentState.IDLE)
        self._experiment_start = None  # Crucial: Limpa a referência de tempo
        self._pending_trigger_alarms = {}
        self._pending_total_alarms = 0
        self.log_message.emit("🛑 Experiment stopped and timer cleared.")
        self.save_transitions()
    
    def pause_experiment(self):
        """Pause the experiment."""
        if self.is_running:
            self._stabilization_timer.stop()
            self._cooldown_timer.stop()
            self._set_state(ExperimentState.PAUSED)
            self.log_message.emit("Experiment paused")
    
    def resume_experiment(self):
        """Resume the experiment."""
        if self._state == ExperimentState.PAUSED:
            self._set_state(ExperimentState.RUNNING)
            self.log_message.emit("Experiment resumed")
    
    def advance_to_next(self) -> bool:
        """Manually advance to next bitstream."""
        if self._current_index + 1 < len(self._queue):
            self._current_index += 1
            if self.current_bitstream:
                self.request_reprogram.emit(self.current_bitstream.filepath)
            return True
        return False
    
    def _set_state(self, new_state: ExperimentState):
        """Update state and emit signal."""
        old_state = self._state
        self._state = new_state
        self.state_changed.emit(new_state.name)
        self.log_message.emit(f"State: {old_state.name} → {new_state.name}")
    
    # =========================================================================
    # Alarm Processing
    # =========================================================================
    
    def process_alarms(self, alarm_f: int, alarm_rf: int, 
                       alarm_uart: int = 0, alarm_obi: int = 0):
        """
        Process incoming alarm data.
        
        Triggers on ANY active alarm from enabled sensors (not just new bits).
        After cooldown, if any alarm is still active, triggers transition.
        """
        # Skip if not in running state
        if self._state != ExperimentState.RUNNING:
            # Still update tracking
            self._last_alarm_f = alarm_f
            self._last_alarm_rf = alarm_rf
            self._last_alarm_uart = alarm_uart
            self._last_alarm_obi = alarm_obi
            return
        
        if not self._auto_program_enabled:
            self._last_alarm_f = alarm_f
            self._last_alarm_rf = alarm_rf
            self._last_alarm_uart = alarm_uart
            self._last_alarm_obi = alarm_obi
            return
        
        # Check for ANY active alarms from enabled sensors
        active_f = alarm_f if self._enabled_sensors['F'] else 0
        active_rf = alarm_rf if self._enabled_sensors['RF'] else 0
        active_uart = alarm_uart if self._enabled_sensors['UART'] else 0
        active_obi = alarm_obi if self._enabled_sensors['OBI'] else 0
        
        has_active_alarms = (active_f | active_rf | active_uart | active_obi) != 0
        
        if has_active_alarms:
            # Capture which alarms are active (only enabled sensors)
            self._pending_trigger_alarms = {}
            
            if self._enabled_sensors['F'] and active_f:
                self._pending_trigger_alarms['F'] = [i for i in range(32) if active_f & (1 << i)]
            if self._enabled_sensors['RF'] and active_rf:
                self._pending_trigger_alarms['RF'] = [i for i in range(32) if active_rf & (1 << i)]
            if self._enabled_sensors['UART'] and active_uart:
                self._pending_trigger_alarms['UART'] = [i for i in range(32) if active_uart & (1 << i)]
            if self._enabled_sensors['OBI'] and active_obi:
                self._pending_trigger_alarms['OBI'] = [i for i in range(32) if active_obi & (1 << i)]
            
            # Count total from enabled sensors only
            self._pending_total_alarms = sum(
                len(bits) for bits in self._pending_trigger_alarms.values()
            )
            
            # Log the trigger
            trigger_summary = []
            for sensor, bits in self._pending_trigger_alarms.items():
                if bits:
                    trigger_summary.append(f"{sensor}:{bits}")
            
            self.log_message.emit(
                f"⚠️ ACTIVE ALARMS DETECTED: {', '.join(trigger_summary)}"
            )
            
            # Start stabilization timer
            self._set_state(ExperimentState.ALARM_DETECTED)
            self._stabilization_timer.start(self._stabilization_time_ms)
        
        # Update tracking (always, for all sensors)
        self._last_alarm_f = alarm_f
        self._last_alarm_rf = alarm_rf
        self._last_alarm_uart = alarm_uart
        self._last_alarm_obi = alarm_obi
    
    def update_environmental(self, fpga_temp: float = None, vccint: float = None):
        """Update environmental readings."""
        if fpga_temp is not None:
            self._fpga_temp = fpga_temp
        if vccint is not None:
            self._vccint = vccint
    
    def process_alarms_multi_bank(self, banks_data: list):
        """
        Process incoming multi-bank TMR sensor data.
        
        Triggers on ANY active alarm from any enabled bank.
        After cooldown, if any alarm is still active, triggers transition.
        
        Args:
            banks_data: List of bank dicts or SensorBank objects with alarm_vector info
        """
        # Skip if not in running state
        if self._state != ExperimentState.RUNNING:
            self._last_banks_state = banks_data
            return
        
        if not self._auto_program_enabled:
            self._last_banks_state = banks_data
            return
        
        # Check for ANY active alarms across all banks
        has_active_alarms = False
        total_bank_alarms = 0
        active_banks_list = []
        
        for bank_data in banks_data:
            # Extract alarm vector (handle both dict and object formats)
            if isinstance(bank_data, dict):
                bank_id = bank_data.get('bank_id', 0)
                alarm_vector = bank_data.get('alarm_vector', 0)
            else:
                # Assume it's a SensorBank-like object
                bank_id = getattr(bank_data, 'bank_id', 0)
                alarm_vector = getattr(bank_data, 'alarm_vector', 0)
            
            # Count alarms in this bank
            bank_alarm_count = bin(alarm_vector).count('1')
            total_bank_alarms += bank_alarm_count
            
            if alarm_vector != 0:
                has_active_alarms = True
                # Get indices of active bits
                active_bits = [i for i in range(64) if alarm_vector & (1 << i)]
                active_banks_list.append({
                    'bank_id': bank_id,
                    'alarm_vector': hex(alarm_vector) if not isinstance(alarm_vector, str) else alarm_vector,
                    'alarm_bits': active_bits,
                    'alarm_count': bank_alarm_count
                })
        
        if has_active_alarms:
            # Capture banks state for logging
            self._pending_banks_state = active_banks_list
            self._pending_total_alarms = total_bank_alarms
            
            # For backward compat, also populate legacy trigger_alarms
            # Map banks to sensor types if needed (or use 'bank_X' naming)
            self._pending_trigger_alarms = {}
            for bank_info in active_banks_list:
                bank_id = bank_info['bank_id']
                self._pending_trigger_alarms[f'bank_{bank_id}'] = bank_info['alarm_bits']
            
            # Log the trigger
            trigger_summary = []
            for bank_info in active_banks_list:
                trigger_summary.append(f"Bank{bank_info['bank_id']}:{bank_info['alarm_bits']}")
            
            self.log_message.emit(
                f"⚠️ MULTI-BANK ALARMS DETECTED: {', '.join(trigger_summary)}"
            )
            
            # Start stabilization timer
            self._set_state(ExperimentState.ALARM_DETECTED)
            self._stabilization_timer.start(self._stabilization_time_ms)
        
        # Update tracking
        self._last_banks_state = banks_data
    
    # =========================================================================
    # Timer Callbacks
    # =========================================================================
    
    def _on_stabilization_complete(self):
        """Called after stabilization period - trigger reprogram."""
        if self._state != ExperimentState.ALARM_DETECTED:
            return
        
        # Check if we have a next bitstream
        if self.next_bitstream is None:
            self.log_message.emit("⚠️ No more bitstreams in queue - experiment finished")
            self._set_state(ExperimentState.FINISHED)
            self.experiment_finished.emit()
            self.save_transitions()
            return
        
        # Log the transition
        from_bs = self.current_bitstream
        to_bs = self.next_bitstream
        
        transition = TransitionEvent(
            timestamp=datetime.now(),
            from_bitstream=from_bs.name if from_bs else "None",
            to_bitstream=to_bs.name,
            from_phase=from_bs.phase_degrees if from_bs else 0.0,
            to_phase=to_bs.phase_degrees,
            trigger_alarms=self._pending_trigger_alarms.copy(),
            total_alarms=self._pending_total_alarms,
            experiment_hours=self.experiment_hours,
            radiation_dose_krad=self.current_dose_krad,
            fpga_temp=self._fpga_temp,
            vccint=self._vccint,
            is_multi_bank=len(self._pending_banks_state) > 0,
            banks_state=self._pending_banks_state.copy() if self._pending_banks_state else []
        )
        
        self._transitions.append(transition)
        self.transition_logged.emit(transition)
        
        # Log detailed info
        self.log_message.emit(transition.format_log_entry())
        
        # Advance to next bitstream
        self._current_index += 1
        self._set_state(ExperimentState.REPROGRAMMING)
        
        # Request reprogram
        self.request_reprogram.emit(to_bs.filepath)
    
    def on_reprogram_complete(self, success: bool, bitstream_name: str = ""):
        """Called when FPGA reprogramming completes."""
        
        # Update current programmed bitstream
        if success and bitstream_name:
            self._current_programmed_bitstream = bitstream_name
        
        if self._state == ExperimentState.PROGRAMMING_INITIAL:
            # Initial programming complete
            if success:
                self.log_message.emit("✓ Initial bitstream programmed, starting monitoring")
                self._set_state(ExperimentState.RUNNING)
            else:
                self.log_message.emit("✗ Initial programming failed, experiment stopped")
                self._set_state(ExperimentState.IDLE)
            return
        
        if self._state != ExperimentState.REPROGRAMMING:
            return
        
        if success:
            self.log_message.emit(f"✓ Reprogram successful, entering cooldown ({self._cooldown_time_ms}ms)")
            
            # Reset alarm tracking (expect alarms to clear with new bitstream)
            self._last_alarm_f = 0
            self._last_alarm_rf = 0
            self._last_alarm_uart = 0
            self._last_alarm_obi = 0
            
            # Start cooldown
            self._set_state(ExperimentState.COOLDOWN)
            self._cooldown_timer.start(self._cooldown_time_ms)
        else:
            self.log_message.emit("✗ Reprogram failed, returning to RUNNING state")
            self._set_state(ExperimentState.RUNNING)
    
    def _on_cooldown_complete(self):
        """Called after cooldown period - resume monitoring."""
        if self._state != ExperimentState.COOLDOWN:
            return
        
        self.log_message.emit("Cooldown complete, resuming alarm monitoring")
        self._set_state(ExperimentState.RUNNING)
    
    # =========================================================================
    # Persistence
    # =========================================================================
    
    def save_transitions(self, filepath: str = None):
        """Save transition log to JSON file."""
        filepath = filepath or self._log_file
        
        data = {
            'experiment_start': self._experiment_start.isoformat() if self._experiment_start else None,
            'dose_rate_krad_h': self.radiation_model.dose_rate_krad_per_hour,
            'initial_dose_krad': self.radiation_model.initial_dose_krad,
            'total_transitions': len(self._transitions),
            'enabled_sensors': self._enabled_sensors,
            'queue': [e.to_dict() for e in self._queue],
            'transitions': [t.to_dict() for t in self._transitions]
        }
        
        with open(filepath, 'w', encoding='utf-8') as f:
            json.dump(data, f, indent=2)
        
        self.log_message.emit(f"Transitions saved to {filepath}")
    
    def load_transitions(self, filepath: str = None) -> bool:
        """Load transition log from JSON file."""
        filepath = filepath or self._log_file
        
        if not os.path.exists(filepath):
            return False
        
        try:
            with open(filepath, 'r', encoding='utf-8') as f:
                data = json.load(f)
            
            self._transitions = [
                TransitionEvent.from_dict(t) for t in data.get('transitions', [])
            ]
            
            return True
        except Exception as e:
            self.log_message.emit(f"Error loading transitions: {e}")
            return False
    
    def export_transitions_csv(self, filepath: str):
        """Export transitions to CSV for analysis."""
        import csv
        
        with open(filepath, 'w', newline='', encoding='utf-8') as f:
            writer = csv.writer(f)
            
            # Header
            writer.writerow([
                'timestamp', 'experiment_hours', 'radiation_dose_krad',
                'from_bitstream', 'from_phase',
                'to_bitstream', 'to_phase',
                'total_alarms', 'trigger_f', 'trigger_rf', 'trigger_uart', 'trigger_obi',
                'fpga_temp', 'vccint', 'notes'
            ])
            
            # Data
            for t in self._transitions:
                writer.writerow([
                    t.timestamp.isoformat(),
                    f"{t.experiment_hours:.4f}",
                    f"{t.radiation_dose_krad:.4f}",
                    t.from_bitstream, t.from_phase,
                    t.to_bitstream, t.to_phase,
                    t.total_alarms,
                    str(t.trigger_alarms.get('F', [])),
                    str(t.trigger_alarms.get('RF', [])),
                    str(t.trigger_alarms.get('UART', [])),
                    str(t.trigger_alarms.get('OBI', [])),
                    t.fpga_temp, t.vccint, t.notes
                ])
        
        self.log_message.emit(f"Transitions exported to {filepath}")