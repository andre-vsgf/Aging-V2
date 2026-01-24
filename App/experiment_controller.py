# -*- coding: utf-8 -*-
"""
Experiment Controller - Auto-Program & Bitstream Queue Manager

Manages aging experiments with:
- Bitstream queue (ordered by phase, decreasing in 5° steps)
- Auto-program on alarm trigger with configurable timeout
- Detailed transition logging (which alarms triggered, timestamps)
- Anti-loop protection (cooldown period after reprogramming)

WORKFLOW:
1. User loads bitstreams into queue (sorted by phase, highest first)
2. Experiment starts with no alarms active
3. When ANY alarm triggers → wait for stabilization → reprogram with next bitstream
4. New bitstream has +5° more "slack" → alarms should clear
5. Repeat until end of queue or experiment stopped

Author: CROC Project
"""

import os
import json
from datetime import datetime, timedelta
from dataclasses import dataclass, asdict, field
from typing import List, Optional, Dict, Any, Callable
from pathlib import Path
from enum import Enum, auto

from PySide6.QtCore import QObject, Signal, Slot, QTimer


class ExperimentState(Enum):
    """State machine for experiment controller."""
    IDLE = auto()           # Not running
    RUNNING = auto()        # Normal operation, monitoring alarms
    ALARM_DETECTED = auto() # Alarm detected, waiting for stabilization
    REPROGRAMMING = auto()  # FPGA being reprogrammed
    COOLDOWN = auto()       # Post-reprogram cooldown (anti-loop)
    PAUSED = auto()         # Temporarily paused
    FINISHED = auto()       # Reached end of bitstream queue


@dataclass
class BitstreamEntry:
    """Entry in the bitstream queue."""
    filepath: str           # Full path to .bit file
    name: str               # Filename only
    phase_degrees: float    # Phase shift in degrees
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
    trigger_alarms: Dict[str, List[int]]  # {sensor_type: [bit_indices]}
    total_alarms: int
    experiment_hours: float
    fpga_temp: float = 0.0
    vccint: float = 0.0
    notes: str = ""
    
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


class ExperimentController(QObject):
    """
    Main experiment controller with auto-program functionality.
    
    Signals:
        state_changed(str): Emitted when state changes
        transition_logged(TransitionEvent): Emitted when bitstream transition occurs
        request_reprogram(str): Request to reprogram FPGA with given bitstream path
        log_message(str): General log messages
        experiment_finished(): Emitted when queue exhausted
    """
    
    state_changed = Signal(str)
    transition_logged = Signal(object)  # TransitionEvent
    request_reprogram = Signal(str)     # filepath
    log_message = Signal(str)
    experiment_finished = Signal()
    
    # Configuration
    DEFAULT_STABILIZATION_TIME_MS = 3000   # Wait 3s after alarm before reprogram
    DEFAULT_COOLDOWN_TIME_MS = 10000       # Wait 10s after reprogram before monitoring
    DEFAULT_PHASE_STEP = 5.0               # Degrees between bitstreams
    
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
        
        # Timing
        self._experiment_start: Optional[datetime] = None
        self._last_reprogram_time: Optional[datetime] = None
        
        # Current alarm state (for detecting NEW alarms)
        self._last_alarm_f = 0
        self._last_alarm_rf = 0
        self._last_alarm_uart = 0
        self._last_alarm_obi = 0
        
        # Pending alarm info (captured when alarm detected)
        self._pending_trigger_alarms: Dict[str, List[int]] = {}
        self._pending_total_alarms = 0
        
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
                               ExperimentState.REPROGRAMMING, ExperimentState.COOLDOWN)
    
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
        if self._experiment_start:
            delta = datetime.now() - self._experiment_start
            return delta.total_seconds() / 3600.0
        return 0.0
    
    @property
    def transitions(self) -> List[TransitionEvent]:
        return self._transitions.copy()
    
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
    
    # =========================================================================
    # Queue Management
    # =========================================================================
    
    def clear_queue(self):
        """Clear the bitstream queue."""
        self._queue.clear()
        self._current_index = 0
        self.log_message.emit("Bitstream queue cleared")
    
    def add_bitstream(self, filepath: str, phase_degrees: float, order: int = -1):
        """Add a bitstream to the queue."""
        name = os.path.basename(filepath)
        
        if order < 0:
            order = len(self._queue)
        
        entry = BitstreamEntry(
            filepath=filepath,
            name=name,
            phase_degrees=phase_degrees,
            order=order
        )
        
        self._queue.append(entry)
        self._sort_queue()
        self.log_message.emit(f"Added bitstream: {name} ({phase_degrees:.1f}°)")
    
    def load_from_directory(self, directory: str, start_phase: float = 0.0, 
                            phase_step: float = None) -> int:
        """
        Load bitstreams from directory, auto-assigning phases.
        
        Assumes files are named in order (alphabetically).
        First bitstream gets start_phase, each subsequent gets +phase_step.
        
        Returns:
            Number of bitstreams loaded
        """
        if phase_step is None:
            phase_step = self._phase_step
        
        if not os.path.isdir(directory):
            return 0
        
        self.clear_queue()
        
        bitstreams = sorted([
            f for f in os.listdir(directory)
            if f.lower().endswith('.bit')
        ])
        
        for i, name in enumerate(bitstreams):
            filepath = os.path.join(directory, name)
            phase = start_phase + (i * phase_step)
            self.add_bitstream(filepath, phase, i)
        
        self.log_message.emit(f"Loaded {len(bitstreams)} bitstreams from {directory}")
        return len(bitstreams)
    
    def _sort_queue(self):
        """Sort queue by order (ascending)."""
        self._queue.sort(key=lambda x: x.order)
    
    def get_queue_info(self) -> List[Dict]:
        """Get queue information for display."""
        return [
            {
                'name': e.name,
                'phase': e.phase_degrees,
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
        
        self._experiment_start = datetime.now()
        self._current_index = 0
        self._transitions.clear()
        
        # Reset alarm tracking
        self._last_alarm_f = 0
        self._last_alarm_rf = 0
        self._last_alarm_uart = 0
        self._last_alarm_obi = 0
        
        self._set_state(ExperimentState.RUNNING)
        self.log_message.emit(f"Experiment started with {len(self._queue)} bitstreams")
        
        # Request initial programming
        if self.current_bitstream:
            self.request_reprogram.emit(self.current_bitstream.filepath)
        
        return True
    
    def stop_experiment(self):
        """Stop the experiment."""
        self._stabilization_timer.stop()
        self._cooldown_timer.stop()
        self._set_state(ExperimentState.IDLE)
        self.log_message.emit("Experiment stopped")
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
        
        Called periodically with current alarm register values.
        Detects NEW alarms and triggers auto-reprogram if enabled.
        """
        # Skip if not running or in special states
        if self._state not in (ExperimentState.RUNNING,):
            return
        
        if not self._auto_program_enabled:
            # Just update tracking
            self._last_alarm_f = alarm_f
            self._last_alarm_rf = alarm_rf
            self._last_alarm_uart = alarm_uart
            self._last_alarm_obi = alarm_obi
            return
        
        # Detect NEW alarm bits
        new_f = alarm_f & ~self._last_alarm_f
        new_rf = alarm_rf & ~self._last_alarm_rf
        new_uart = alarm_uart & ~self._last_alarm_uart
        new_obi = alarm_obi & ~self._last_alarm_obi
        
        has_new_alarms = (new_f | new_rf | new_uart | new_obi) != 0
        
        if has_new_alarms:
            # Capture which alarms triggered
            self._pending_trigger_alarms = {
                'F': [i for i in range(32) if new_f & (1 << i)],
                'RF': [i for i in range(32) if new_rf & (1 << i)],
                'UART': [i for i in range(32) if new_uart & (1 << i)],
                'OBI': [i for i in range(32) if new_obi & (1 << i)]
            }
            
            self._pending_total_alarms = (
                bin(alarm_f).count('1') + bin(alarm_rf).count('1') +
                bin(alarm_uart).count('1') + bin(alarm_obi).count('1')
            )
            
            # Log the trigger
            trigger_summary = []
            for sensor, bits in self._pending_trigger_alarms.items():
                if bits:
                    trigger_summary.append(f"{sensor}:{bits}")
            
            self.log_message.emit(
                f"⚠️ NEW ALARMS DETECTED: {', '.join(trigger_summary)}"
            )
            
            # Start stabilization timer
            self._set_state(ExperimentState.ALARM_DETECTED)
            self._stabilization_timer.start(self._stabilization_time_ms)
        
        # Update tracking
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
            fpga_temp=self._fpga_temp,
            vccint=self._vccint
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
    
    def on_reprogram_complete(self, success: bool):
        """Called when FPGA reprogramming completes."""
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
            'total_transitions': len(self._transitions),
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
                'timestamp', 'experiment_hours', 
                'from_bitstream', 'from_phase',
                'to_bitstream', 'to_phase',
                'total_alarms', 'trigger_f', 'trigger_rf', 'trigger_uart', 'trigger_obi',
                'fpga_temp', 'vccint', 'notes'
            ])
            
            # Data
            for t in self._transitions:
                writer.writerow([
                    t.timestamp.isoformat(),
                    t.experiment_hours,
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
