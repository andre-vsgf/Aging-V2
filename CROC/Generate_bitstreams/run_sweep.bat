@echo off

set VIVADO_BIN="C:\Xilinx\Vivado\2025.1\bin\vivado.bat"
set SCRIPT_PATH="%~dp0sweep_clkout3_phase.tcl"

echo ============================================
echo Vivado sweep runner
echo Script: %SCRIPT_PATH%
echo Start : %DATE% %TIME%
echo ============================================

vivado -mode batch -source %SCRIPT_PATH%

echo ============================================
echo Finished: %DATE% %TIME%
echo ============================================

pause
