transcript off
onbreak {quit -force}
onerror {quit -force}
transcript on

vlib work
vlib riviera/xpm
vlib riviera/xil_defaultlib

vmap xpm riviera/xpm
vmap xil_defaultlib riviera/xil_defaultlib

vlog -work xpm  -incr  +define+TARGET_FPGA=  +define+TARGET_AUP15=  +define+TARGET_XILINX=  +define+WITH_SYSTEM_MONITOR=  +define+WITH_TELEMETRY_TX=  +define+WITH_SENSOR=  +define+WITH_SENSOR_LF=  +define+WITH_SENSOR_AM=  +define+COMMON_CELLS_ASSERTS_OFF= "+incdir+../../../../../../../../AMD/2025.1/data/rsb/busdef" -l xpm -l xil_defaultlib \
"/home/danilo-alencar/AMD/2025.1/Vivado/data/ip/xpm/xpm_cdc/hdl/xpm_cdc.sv" \
"/home/danilo-alencar/AMD/2025.1/Vivado/data/ip/xpm/xpm_memory/hdl/xpm_memory.sv" \

vcom -work xpm -93  -incr \
"/home/danilo-alencar/AMD/2025.1/data/ip/xpm/xpm_VCOMP.vhd" \

vlog -work xil_defaultlib  -incr -v2k5  +define+TARGET_FPGA=  +define+TARGET_AUP15=  +define+TARGET_XILINX=  +define+WITH_SYSTEM_MONITOR=  +define+WITH_TELEMETRY_TX=  +define+WITH_SENSOR=  +define+WITH_SENSOR_LF=  +define+WITH_SENSOR_AM=  +define+COMMON_CELLS_ASSERTS_OFF= "+incdir+../../../../../../../../AMD/2025.1/data/rsb/busdef" -l xpm -l xil_defaultlib \
"../../../../Aging_V2.gen/sources_1/ip/sysmon_wiz_0/sysmon_wiz_0_sysmon.v" \
"../../../../Aging_V2.gen/sources_1/ip/sysmon_wiz_0/sysmon_wiz_0.v" \

vlog -work xil_defaultlib \
"glbl.v"

