# program_fpga.tcl
# Uso:
#   vivado -mode batch -source program_fpga.tcl -tclargs <bit> <ltx> ?device_name?
#
# Ex:
#   vivado -mode batch -source program_fpga.tcl -tclargs \ (Vivado tem que estar no path ou então chamar o path completo aqui já)
#     "C:/Projects/Vivado/aging_obi/aging_obi.runs/impl_1/croc_xilinx.bit" \ (Bitstream)
#     "C:/Projects/Vivado/aging_obi/aging_obi.runs/impl_1/croc_xilinx.ltx" \ (LTX))
#     "xcau15p_0" (Device name)

proc die {msg} { puts "ERROR: $msg"; exit 1 }

if {$argc < 1} { die "Passe o .bit como 1º argumento" }
set bitfile [lindex $argv 0]
set ltxfile ""
if {$argc >= 2} { set ltxfile [lindex $argv 1] }
set devname "xcau15p_0"
if {$argc >= 3} { set devname [lindex $argv 2] }

if {![file exists $bitfile]} { die "Bitstream não encontrado: $bitfile" }
if {$ltxfile ne "" && ![file exists $ltxfile]} { die "LTX não encontrado: $ltxfile" }

# 1) Conecta no Hardware Server (local)
open_hw_manager
connect_hw_server -url localhost:3121

# 2) Abre o target JTAG
open_hw_target

# 3) Seleciona o device
set dev [get_hw_devices $devname]
if {[llength $dev] == 0} {
  puts "Devices visíveis: [get_hw_devices]"
  die "Device '$devname' não encontrado."
}

current_hw_device $dev
refresh_hw_device $dev

# 4) Configura bit/ltx e programa
if {$ltxfile ne ""} {
  set_property PROBES.FILE $ltxfile $dev
  set_property FULL_PROBES.FILE $ltxfile $dev
}
set_property PROGRAM.FILE $bitfile $dev

puts "Programando $devname"
puts "  BIT: $bitfile"
if {$ltxfile ne ""} { puts "  LTX: $ltxfile" }

program_hw_devices $dev

# 5) (opcional) refresh pós-programação
refresh_hw_device $dev

puts "OK: FPGA programada."
exit 0