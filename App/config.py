# -*- coding: utf-8 -*-
"""
Configuration Module for CROC FPGA Monitor

Handles persistent settings storage and default values.
Default bitstream directory is set to 'out_bitstreams' in the repository root.
"""

import os
import sys
import json
from pathlib import Path

# ============================================================================
# Platform Detection
# ============================================================================

IS_WINDOWS = sys.platform.startswith('win')
IS_LINUX = sys.platform.startswith('linux')

# ============================================================================
# Path Utilities
# ============================================================================

def get_app_dir() -> Path:
    """Get the application directory (where main.py is located)."""
    if getattr(sys, 'frozen', False):
        # Running as compiled executable
        return Path(sys.executable).parent
    else:
        # Running as script
        return Path(__file__).parent


def get_repo_root() -> Path:
    """Get the repository root directory (parent of App/)."""
    app_dir = get_app_dir()
    # Assume App/ is inside the repository root
    if app_dir.name == 'App':
        return app_dir.parent
    return app_dir


def get_default_bitstream_dir() -> str:
    """
    Get the default bitstream directory.
    
    Returns the path to 'out_bitstreams' folder in the repository root.
    If not found, returns the current working directory.
    """
    repo_root = get_repo_root()
    out_bitstreams = repo_root / 'out_bitstreams'
    
    if out_bitstreams.exists() and out_bitstreams.is_dir():
        return str(out_bitstreams)
    
    # Fallback: try from current working directory
    cwd_bitstreams = Path.cwd() / 'out_bitstreams'
    if cwd_bitstreams.exists() and cwd_bitstreams.is_dir():
        return str(cwd_bitstreams)
    
    # Last resort: current directory
    return str(Path.cwd())


def find_vivado() -> str:
    """
    Attempt to find Vivado installation.

    Searches common installation paths on Windows and Linux,
    including legacy explicit paths.
    """
    explicit_candidates = []

    if IS_WINDOWS:
        # Explicit known Windows Vivado paths (legacy + current)
        explicit_candidates.extend([
            Path(r"C:/Xilinx/Vivado/2024.2/bin/vivado.bat"),
            Path(r"C:/Xilinx/Vivado/2024.1/bin/vivado.bat"),
            Path(r"C:/Xilinx/Vivado/2023.2/bin/vivado.bat"),
            Path(r"C:/Xilinx/2025.1/Vivado/bin/vivado.bat"),
            Path(r"C:/Xilinx/2025.2/Vivado/bin/vivado.bat"),
            Path(r"C:/Xilinx/Vivado_Lab/2024.2/bin/vivado_lab.bat"),
            Path(r"C:/AMDDesignTools/2025.2/Vivado/vivado.bat")
        ])

        search_paths = [
            Path("C:/Xilinx/Vivado"),
            Path("D:/Xilinx/Vivado"),
            Path(os.environ.get("XILINX_VIVADO", "C:/Xilinx/Vivado")),
            Path("C:/Xilinx"),  # cobre Xilinx/<versão>/Vivado
        ]
        executable_pattern = "*/bin/vivado.bat"

    else:
        # Explicit known Linux Vivado paths (legacy + current)
        explicit_candidates.extend([
            Path("/tools/Xilinx/Vivado/2024.2/bin/vivado"),
            Path("/opt/Xilinx/Vivado/2024.2/bin/vivado"),
            Path("/tools/Xilinx/Vivado/2024.1/bin/vivado"),
            Path("/opt/Xilinx/Vivado/2024.1/bin/vivado"),
            Path.home() / "Xilinx/Vivado/2024.2/bin/vivado",
            Path.home() / "Xilinx/Vivado/2025.1/bin/vivado",
            Path.home() / "Xilinx/Vivado/2025.2/bin/vivado",
            Path.home() / "2025.2/Vivado/bin/vivado",
            Path.home() / "2025.1/Vivado/bin/vivado",
            Path.home() / "2024.2/Vivado/bin/vivado",
        ])

        search_paths = [
            Path("/opt/Xilinx/Vivado"),
            Path("/tools/Xilinx/Vivado"),
            Path.home() / "Xilinx/Vivado",
        ]
        executable_pattern = "*/bin/vivado"

    # 1) Prefer explicit known-good paths
    for candidate in explicit_candidates:
        if candidate.exists():
            return str(candidate)

    # 2) Fallback: search newest version in common roots
    for base_path in search_paths:
        if base_path.exists():
            versions = sorted(base_path.glob(executable_pattern), reverse=True)
            if versions:
                return str(versions[0])

    return ""

# ============================================================================
# Configuration File
# ============================================================================

CONFIG_FILE = get_app_dir() / "config.json"


def load_config() -> dict:
    """Load configuration from JSON file."""
    if CONFIG_FILE.exists():
        try:
            with open(CONFIG_FILE, 'r', encoding='utf-8') as f:
                return json.load(f)
        except (json.JSONDecodeError, IOError):
            pass
    return {}


def save_config(fpga_port: str = None, baud_rate: int = None, 
                vivado_path: str = None, bitstream_dir: str = None):
    """Save configuration to JSON file."""
    config = load_config()
    
    if fpga_port is not None:
        config['fpga_port'] = fpga_port
    if baud_rate is not None:
        config['baud_rate'] = baud_rate
    if vivado_path is not None:
        config['vivado_path'] = vivado_path
    if bitstream_dir is not None:
        config['bitstream_dir'] = bitstream_dir
    
    try:
        with open(CONFIG_FILE, 'w', encoding='utf-8') as f:
            json.dump(config, f, indent=2)
    except IOError as e:
        print(f"Warning: Could not save config: {e}")


# ============================================================================
# Default Values
# ============================================================================

_config = load_config()

# Serial Port (platform-specific default)
if IS_WINDOWS:
    DEFAULT_PORT = "COM3"
else:
    DEFAULT_PORT = "/dev/ttyUSB0"

FPGA_PORT = _config.get('fpga_port', DEFAULT_PORT)
SYSTEM_BAUD = _config.get('baud_rate', 115200)

# Vivado Path (auto-detect if not configured)
VIVADO_PATH = _config.get('vivado_path', '') or find_vivado()

# Bitstream Directory (default to out_bitstreams in repo root)
BITSTREAM_DIR = _config.get('bitstream_dir', '') or get_default_bitstream_dir()

# ============================================================================
# Logging Configuration
# ============================================================================

LOG_LEVEL = _config.get('log_level', 'INFO')
LOG_DIR = get_app_dir() / 'logs'
LOG_DIR.mkdir(exist_ok=True)

# ============================================================================
# Experiment Configuration
# ============================================================================

# Default timing values (milliseconds)
DEFAULT_STABILIZATION_TIME_MS = 3000
DEFAULT_COOLDOWN_TIME_MS = 10000

# Default phase step (degrees)
DEFAULT_PHASE_STEP = 5.0

# Clock period for slack calculation (nanoseconds)
# Adjust this based on your FPGA clock frequency
CLOCK_PERIOD_NS = 50.0  # 20 MHz default

# ============================================================================
# UI Configuration
# ============================================================================

# Window settings
WINDOW_TITLE = "CROC FPGA Sensor Monitor & Programmer"
WINDOW_WIDTH = 1400
WINDOW_HEIGHT = 900

# Theme colors
THEME_COLORS = {
    'background': '#1e1e1e',
    'foreground': '#d4d4d4',
    'accent': '#0d6efd',
    'success': '#28a745',
    'warning': '#ffc107',
    'error': '#dc3545',
    'info': '#17a2b8'
}

# ============================================================================
# Debug Mode
# ============================================================================

DEBUG_MODE = _config.get('debug_mode', False)

if DEBUG_MODE:
    print(f"[CONFIG] App Dir: {get_app_dir()}")
    print(f"[CONFIG] Repo Root: {get_repo_root()}")
    print(f"[CONFIG] Bitstream Dir: {BITSTREAM_DIR}")
    print(f"[CONFIG] Vivado Path: {VIVADO_PATH}")
    print(f"[CONFIG] FPGA Port: {FPGA_PORT}")