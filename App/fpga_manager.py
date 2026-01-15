# -*- coding: utf-8 -*-
"""
FPGA Programming Manager

Handles FPGA bitstream programming via Vivado in batch mode.
Cross-platform support for Windows and Linux.

Features:
- SRAM Programming (volatile, .bit files)
- FLASH Programming (persistent, .bin files)
- VIO Reset (soft reset via debug probes)
"""

import os
import shutil
import glob
from pathlib import Path
from PySide6.QtCore import QObject, QProcess, Signal, Slot

import config


class FPGAManager(QObject):
    """
    Manages FPGA programming operations using Vivado.
    
    Signals:
        started(str): Emitted when programming starts (bitstream name)
        output(str): Emitted for each line of Vivado output
        finished(bool, str): Emitted when programming completes (success, message)
        progress(int): Emitted with progress percentage (0-100)
    """
    
    started = Signal(str)
    output = Signal(str)
    finished = Signal(bool, str)
    progress = Signal(int)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.process = None
        self.is_programming = False
        self._current_bitstream = ""
        self._current_operation = ""  # "program" or "reset"
        
        # Get TCL script paths (same directory as this module)
        script_dir = Path(__file__).parent
        self._tcl_program = str(script_dir / "program_fpga.tcl")
        self._tcl_reset = str(script_dir / "reset_fpga.tcl")
        
        # Alternative: Check in scripts/ subdirectory
        if not os.path.exists(self._tcl_program):
            self._tcl_program = str(script_dir / "scripts" / "program_fpga.tcl")
        if not os.path.exists(self._tcl_reset):
            self._tcl_reset = str(script_dir / "scripts" / "reset_fpga.tcl")

    def _find_vivado(self) -> str:
        """
        Find the Vivado executable.
        Priority:
        1. Configured path in settings
        2. Auto-detected path
        3. PATH lookup
        """
        # Try configured path first
        if config.VIVADO_PATH and os.path.exists(config.VIVADO_PATH):
            return config.VIVADO_PATH
        
        # Try auto-detection
        detected = config.find_vivado_executable()
        if detected:
            return detected
        
        # Try PATH lookup
        exe_names = ["vivado", "vivado.bat", "vivado_lab", "vivado_lab.bat"]
        if config.IS_WINDOWS:
            exe_names = ["vivado.bat", "vivado_lab.bat", "vivado.exe", "vivado_lab.exe"]
        
        for name in exe_names:
            path = shutil.which(name)
            if path:
                return path
        
        return ""

    def get_vivado_path(self) -> str:
        """Return the current Vivado executable path."""
        return self._find_vivado()

    def is_vivado_available(self) -> bool:
        """Check if Vivado is available for programming."""
        return bool(self._find_vivado())

    def program(self, file_path: str, mode: str = "sram"):
        """
        Start programming the FPGA.
        
        Args:
            file_path: Path to the .bit or .bin file
            mode: "sram" (default, volatile) or "flash" (persistent)
        """
        if self.is_programming:
            self.output.emit("⚠ Another programming operation is in progress.")
            return
        
        # Validate file
        if not os.path.exists(file_path):
            self.output.emit(f"✗ File not found: {file_path}")
            self.finished.emit(False, "File not found")
            return
            
        # Check file extension warning
        if mode == "flash" and not file_path.lower().endswith('.bin'):
            self.output.emit("⚠ Warning: Flash programming usually requires a .bin file.")
        
        # Find Vivado
        vivado_exe = self._find_vivado()
        if not vivado_exe:
            msg = (
                "✗ Vivado executable not found.\n"
                "  Please configure the Vivado path in Settings or ensure it's in your PATH.\n"
                f"  Searched: {config.VIVADO_PATH}"
            )
            self.output.emit(msg)
            self.finished.emit(False, "Vivado not found")
            return
        
        # Validate TCL script
        if not os.path.exists(self._tcl_program):
            self.output.emit(f"✗ TCL script not found: {self._tcl_program}")
            self.finished.emit(False, "TCL script not found")
            return
        
        # Setup process
        self._setup_process()
        
        # Build command arguments
        file_abspath = os.path.abspath(file_path)
        tcl_abspath = os.path.abspath(self._tcl_program)
        
        args = ["-mode", "batch", "-source", tcl_abspath, "-tclargs", file_abspath]
        
        # Add flash flag if needed
        if mode == "flash":
            args.append("-flash")
        
        # UI Updates
        self._current_bitstream = os.path.basename(file_path)
        self._current_operation = "program"
        self.is_programming = True
        
        mode_str = "FLASH (Persistent)" if mode == "flash" else "SRAM (Volatile)"
        
        self.output.emit("=" * 60)
        self.output.emit(f"▶ Starting FPGA Programming [{mode_str}]")
        self.output.emit(f"  Vivado: {vivado_exe}")
        self.output.emit(f"  File:   {self._current_bitstream}")
        self.output.emit(f"  Script: {os.path.basename(tcl_abspath)}")
        self.output.emit("=" * 60)
        
        self.started.emit(self._current_bitstream)
        self.progress.emit(5)
        
        # Start
        self.process.start(vivado_exe, args)

    def reset(self, ltx_path: str = None):
        """
        Trigger FPGA Reset via VIO.
        
        Args:
            ltx_path: Full path to the .ltx debug probes file.
                      If None, the script will try to auto-detect VIO cores.
        """
        if self.is_programming:
            self.output.emit("⚠ Another operation is in progress.")
            return

        vivado_exe = self._find_vivado()
        if not vivado_exe:
            self.output.emit("✗ Vivado executable not found.")
            self.finished.emit(False, "Vivado not found")
            return

        if not os.path.exists(self._tcl_reset):
            self.output.emit(f"✗ Reset script not found: {self._tcl_reset}")
            self.finished.emit(False, "Reset script not found")
            return

        # Setup process
        self._setup_process()

        # Build arguments
        tcl_abspath = os.path.abspath(self._tcl_reset)
        args = ["-mode", "batch", "-source", tcl_abspath]
        
        # Add LTX file if provided and exists
        ltx_info = "(auto-detect)"
        if ltx_path:
            if os.path.exists(ltx_path):
                args.extend(["-tclargs", ltx_path])
                ltx_info = os.path.basename(ltx_path)
            else:
                self.output.emit(f"⚠ Warning: LTX file not found: {ltx_path}")
                self.output.emit("  Will try to auto-detect VIO cores...")
                ltx_info = "(not found, auto-detect)"

        self._current_operation = "reset"
        self.is_programming = True
        
        self.output.emit("=" * 60)
        self.output.emit("▶ STARTING FPGA RESET (VIO)")
        self.output.emit(f"  Vivado: {vivado_exe}")
        self.output.emit(f"  Probes: {ltx_info}")
        self.output.emit(f"  Script: {os.path.basename(tcl_abspath)}")
        self.output.emit("=" * 60)
        
        self.started.emit("Reset Sequence")
        self.progress.emit(10)

        self.process.start(vivado_exe, args)

    def cancel(self):
        """Attempt to cancel the current programming operation."""
        if self.process and self.process.state() != QProcess.NotRunning:
            self.output.emit("⚠ Cancelling operation...")
            self.process.kill()

    def _setup_process(self):
        """Create and configure the QProcess."""
        self.process = QProcess(self)
        self.process.readyReadStandardOutput.connect(self._handle_stdout)
        self.process.readyReadStandardError.connect(self._handle_stderr)
        self.process.finished.connect(self._handle_finished)
        self.process.errorOccurred.connect(self._handle_error)

    def _handle_stdout(self):
        """Handle standard output from Vivado."""
        try:
            raw = self.process.readAllStandardOutput().data()
            lines = raw.decode(errors="replace").strip().split('\n')
            for line in lines:
                line = line.strip()
                if line:
                    self.output.emit(f"  {line}")
                    self._parse_progress(line)
        except Exception as e:
            self.output.emit(f"[Read Error] {e}")

    def _handle_stderr(self):
        """Handle standard error from Vivado."""
        try:
            raw = self.process.readAllStandardError().data()
            lines = raw.decode(errors="replace").strip().split('\n')
            for line in lines:
                line = line.strip()
                if line:
                    # Filter out some common non-error messages
                    if "INFO:" in line:
                        self.output.emit(f"  ℹ {line}")
                    elif "WARNING:" in line:
                        self.output.emit(f"  ⚠ {line}")
                    elif "ERROR:" in line:
                        self.output.emit(f"  ✗ {line}")
                    else:
                        self.output.emit(f"  {line}")
        except Exception as e:
            self.output.emit(f"[Read Error] {e}")

    def _parse_progress(self, line: str):
        """Parse Vivado output to estimate progress."""
        line_lower = line.lower()
        
        # Progress tracking
        if "open_hw_manager" in line_lower:
            self.progress.emit(15)
        elif "connect_hw_server" in line_lower:
            self.progress.emit(25)
        elif "scanning for hardware targets" in line_lower:
            self.progress.emit(30)
        elif "opening target" in line_lower:
            self.progress.emit(40)
        elif "scanning for fpga devices" in line_lower:
            self.progress.emit(50)
        elif "selected device" in line_lower:
            self.progress.emit(55)
        elif "refreshing device" in line_lower:
            self.progress.emit(60)
        elif "programming fpga" in line_lower or "configuring" in line_lower:
            self.progress.emit(70)
        elif "starting flash" in line_lower:
            self.progress.emit(75)
        elif "verifying" in line_lower:
            self.progress.emit(85)
        elif "closing" in line_lower:
            self.progress.emit(90)
        elif "success" in line_lower or "completed" in line_lower:
            self.progress.emit(100)
        elif "executing reset" in line_lower:
            self.progress.emit(70)
        elif "asserting reset" in line_lower:
            self.progress.emit(80)
        elif "de-asserting reset" in line_lower:
            self.progress.emit(90)
        
        # Error detection - highlight important errors
        if "jtag/usb cable is disconnected" in line_lower:
            self.output.emit("")
            self.output.emit("⚠️ ========================================")
            self.output.emit("⚠️  CABLE NOT CONNECTED!")
            self.output.emit("⚠️  Please connect the JTAG/USB cable")
            self.output.emit("⚠️  and try again.")
            self.output.emit("⚠️ ========================================")
        elif "no hardware targets found" in line_lower:
            self.output.emit("❌ No JTAG cable detected!")
        elif "no fpga devices found" in line_lower:
            self.output.emit("❌ FPGA not detected on JTAG chain!")

    def _handle_finished(self, exit_code, exit_status=None):
        """Handle process completion."""
        self.is_programming = False
        
        success = (exit_code == 0)
        
        self.output.emit("=" * 60)
        if success:
            if self._current_operation == "reset":
                msg = "✓ FPGA Reset completed successfully!"
            else:
                msg = f"✓ Programming completed successfully!"
            self.output.emit(msg)
            self.progress.emit(100)
        else:
            if self._current_operation == "reset":
                msg = f"✗ FPGA Reset failed (exit code: {exit_code})"
            else:
                msg = f"✗ Programming failed (exit code: {exit_code})"
            self.output.emit(msg)
            self.output.emit("")
            self.output.emit("━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━")
            self.output.emit("  TROUBLESHOOTING CHECKLIST:")
            self.output.emit("━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━")
            self.output.emit("  □ Is the JTAG/USB cable connected?")
            self.output.emit("  □ Is the FPGA board powered on?")
            self.output.emit("  □ Is the cable properly seated on both ends?")
            self.output.emit("  □ Is Vivado Hardware Manager closed?")
            self.output.emit("  □ Are the USB drivers installed?")
            if self._current_operation == "reset":
                self.output.emit("  □ Is the .ltx file matching the current bitstream?")
                self.output.emit("  □ Does the bitstream have VIO debug core?")
            self.output.emit("━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━")
            self.progress.emit(0)
        self.output.emit("=" * 60)
        
        self.finished.emit(success, msg)

    def _handle_error(self, error):
        """Handle process errors."""
        self.is_programming = False
        
        error_msgs = {
            QProcess.FailedToStart: "Failed to start Vivado process",
            QProcess.Crashed: "Vivado process crashed",
            QProcess.Timedout: "Vivado process timed out",
            QProcess.WriteError: "Write error to Vivado process",
            QProcess.ReadError: "Read error from Vivado process",
            QProcess.UnknownError: "Unknown error occurred",
        }
        
        msg = error_msgs.get(error, f"Process error: {error}")
        self.output.emit(f"✗ {msg}")
        self.finished.emit(False, msg)


class BitstreamManager:
    """
    Manages a sequence of bitstream files for automated testing.
    
    Features:
    - Load all .bit files from a directory
    - Circular navigation (next/previous wraps around)
    - Track current selection
    """
    
    def __init__(self):
        self.files = []
        self.index = 0
        self._directory = ""

    def load_directory(self, path: str) -> int:
        """
        Load all .bit files from a directory.
        
        Returns:
            Number of bitstream files found
        """
        self._directory = path
        self.files = sorted(list(Path(path).glob("*.bit")))
        self.index = 0
        return len(self.files)

    def get_directory(self) -> str:
        """Get the current bitstream directory."""
        return self._directory

    def current(self) -> str:
        """Get the current bitstream file path."""
        if self.files and 0 <= self.index < len(self.files):
            return str(self.files[self.index])
        return ""

    def current_name(self) -> str:
        """Get the current bitstream filename (without path)."""
        if self.files and 0 <= self.index < len(self.files):
            return self.files[self.index].name
        return ""

    def count(self) -> int:
        """Get the total number of bitstreams."""
        return len(self.files)

    def get_index(self) -> int:
        """Get the current index."""
        return self.index

    def set_index(self, idx: int) -> bool:
        """Set the current index."""
        if 0 <= idx < len(self.files):
            self.index = idx
            return True
        return False

    def advance(self) -> bool:
        """Move to the next bitstream (wraps around)."""
        if not self.files:
            return False
        self.index = (self.index + 1) % len(self.files)
        return True

    def back(self) -> bool:
        """Move to the previous bitstream (wraps around)."""
        if not self.files:
            return False
        self.index = (self.index - 1) % len(self.files)
        return True

    def get_all_names(self) -> list:
        """Get list of all bitstream filenames."""
        return [f.name for f in self.files]

    def find_ltx_for_current(self) -> str:
        """
        Find the .ltx file corresponding to the current bitstream.
        
        Returns:
            Path to .ltx file if found, empty string otherwise
        """
        current = self.current()
        if not current:
            return ""
        
        # Try same name with .ltx extension
        base = os.path.splitext(current)[0]
        ltx_path = base + ".ltx"
        
        if os.path.exists(ltx_path):
            return ltx_path
        
        return ""
