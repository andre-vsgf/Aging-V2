#==============================================================================
# soft_reset_vio.tcl - Soft Reset via VIO
#==============================================================================
# This script performs a soft reset of the CROC system using VIO.
#
# Usage:
#   1. Open Vivado Hardware Manager
#   2. Connect to the board
#   3. source soft_reset_vio.tcl
#
# Or run from command line:
#   vivado -mode batch -source soft_reset_vio.tcl
#==============================================================================

puts ""
puts "=============================================="
puts "  CROC Soft Reset via VIO"
puts "=============================================="

#------------------------------------------------------------------------------
# Check if Hardware Manager is connected
#------------------------------------------------------------------------------
if {[catch {current_hw_device}]} {
    puts ""
    puts "ERROR: Not connected to hardware!"
    puts ""
    puts "Please connect first:"
    puts "  1. open_hw_manager"
    puts "  2. connect_hw_server"
    puts "  3. open_hw_target"
    puts "  4. source soft_reset_vio.tcl"
    puts ""
    return
}

set device [current_hw_device]
puts "Connected to: $device"

#------------------------------------------------------------------------------
# Find VIO core
#------------------------------------------------------------------------------
set vios [get_hw_vios -quiet]
if {$vios eq ""} {
    puts ""
    puts "ERROR: No VIO core found!"
    puts ""
    puts "Possible causes:"
    puts "  1. VIO not instantiated in design"
    puts "  2. Debug hub not detected - check clock"
    puts "  3. .ltx file mismatch - regenerate probes"
    puts ""
    return
}

puts "Found VIO: $vios"

#------------------------------------------------------------------------------
# Find reset probe (probe_out0)
#------------------------------------------------------------------------------
set reset_probe [get_hw_probes -quiet */probe_out0 -of_objects $vios]
if {$reset_probe eq ""} {
    puts ""
    puts "ERROR: probe_out0 (reset) not found!"
    puts ""
    return
}

set fetch_probe [get_hw_probes -quiet */probe_out1 -of_objects $vios]

#------------------------------------------------------------------------------
# Read current state
#------------------------------------------------------------------------------
refresh_hw_vio $vios
set current_reset [get_property OUTPUT_VALUE $reset_probe]
puts "Current reset state: $current_reset (1=running, 0=in reset)"

#------------------------------------------------------------------------------
# Perform soft reset
#------------------------------------------------------------------------------
puts ""
puts "Performing soft reset..."

# Enter reset
puts "  Setting probe_out0 = 0 (entering reset)..."
set_property OUTPUT_VALUE 0 $reset_probe
commit_hw_vio $vios
after 100  ;# Wait 100ms

# Exit reset
puts "  Setting probe_out0 = 1 (exiting reset)..."
set_property OUTPUT_VALUE 1 $reset_probe
commit_hw_vio $vios
after 50   ;# Wait 50ms for system to stabilize

#------------------------------------------------------------------------------
# Verify
#------------------------------------------------------------------------------
refresh_hw_vio $vios
set new_reset [get_property OUTPUT_VALUE $reset_probe]

puts ""
if {$new_reset == 1} {
    puts "=============================================="
    puts "  SOFT RESET COMPLETE - System Running!"
    puts "=============================================="
} else {
    puts "WARNING: Reset probe is still 0. System may be stuck."
}

# Read status
set status_probe [get_hw_probes -quiet */probe_in0 -of_objects $vios]
if {$status_probe ne ""} {
    set status [get_property INPUT_VALUE $status_probe]
    puts "  Status (probe_in0): $status"
}

puts ""
