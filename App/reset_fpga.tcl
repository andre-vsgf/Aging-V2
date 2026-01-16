# ==============================================================================
# FPGA Reset Script via VIO (Vivado)
# ==============================================================================
# Usage: vivado -mode batch -source reset_fpga.tcl -tclargs [path_to_probes.ltx]
#
# This script:
#   1. Connects to the FPGA via JTAG
#   2. Loads the debug probes (.ltx) file
#   3. Finds the VIO core
#   4. Pulses the reset signal (0 -> 1)
# ==============================================================================

# --- Argument Parsing ---
if { $argc > 0 } {
    set probes_file [lindex $argv 0]
} else {
    set probes_file ""
}

puts "============================================================"
puts "FPGA Soft Reset via VIO"
if { $probes_file != "" } {
    puts "Probes File: $probes_file"
} else {
    puts "Probes File: (auto-detect)"
}
puts "============================================================"

# ==============================================================================
# 1. OPEN HARDWARE MANAGER
# ==============================================================================
puts ""
puts "Opening Hardware Manager..."
open_hw_manager

# ==============================================================================
# 2. CONNECT TO HARDWARE SERVER
# ==============================================================================
puts "Connecting to hardware server..."

if { [catch {connect_hw_server -url localhost:3121 -allow_non_jtag} err] } {
    if { [catch {connect_hw_server -url localhost:3121} err2] } {
        puts ""
        puts "============================================================"
        puts "ERROR: Failed to connect to hardware server!"
        puts "============================================================"
        puts "Error: $err2"
        puts ""
        puts "Possible causes:"
        puts "  1. hw_server process failed to start"
        puts "  2. Port 3121 is blocked by firewall"
        puts "  3. Another Vivado instance is using the server"
        puts ""
        puts "Solutions:"
        puts "  - Close any open Vivado Hardware Manager windows"
        puts "  - Kill any orphan hw_server processes"
        puts "  - Check firewall settings"
        puts "============================================================"
        exit 1
    }
}

# ==============================================================================
# 3. OPEN HARDWARE TARGET (FIXED!)
# ==============================================================================
puts "Scanning for hardware targets..."

# Get list of available targets
set targets [get_hw_targets]

if { [llength $targets] == 0 } {
    puts ""
    puts "============================================================"
    puts "ERROR: No hardware targets found!"
    puts "============================================================"
    puts ""
    puts "Possible causes:"
    puts "  1. JTAG/USB cable is DISCONNECTED"
    puts "  2. JTAG cable is not properly seated"
    puts "  3. FPGA board is not powered on"
    puts "  4. USB drivers not installed (FTDI/Digilent)"
    puts "  5. Another application is using the JTAG interface"
    puts ""
    puts "Please check the cable connection and try again."
    puts "============================================================"
    close_hw_manager
    exit 1
}

puts "Found [llength $targets] target(s):"
foreach t $targets {
    puts "  - $t"
}

# Open the first available target
set target [lindex $targets 0]
puts "Opening target: $target"

if { [catch {open_hw_target $target} err] } {
    puts "ERROR: Failed to open hardware target: $err"
    close_hw_manager
    exit 1
}

# ==============================================================================
# 4. REDUCE JTAG FREQUENCY FOR STABILITY
# ==============================================================================
# The internal FPGA clock is ~20MHz. JTAG needs to be slower for stable VIO access.
puts ""
puts "Reducing JTAG frequency to 3 MHz for stability..."
set_property PARAM.FREQUENCY 3000000 [current_hw_target]

# ==============================================================================
# 5. SELECT FPGA DEVICE
# ==============================================================================
puts "Scanning for FPGA devices..."

set devices [get_hw_devices]
if { [llength $devices] == 0 } {
    puts "ERROR: No FPGA devices found on target."
    close_hw_target
    close_hw_manager
    exit 1
}

puts "Found [llength $devices] device(s):"
foreach d $devices {
    puts "  - $d"
}

# Select the first FPGA device
set device [lindex $devices 0]
current_hw_device $device
puts "Selected device: $device"

# ==============================================================================
# 6. LOAD DEBUG PROBES (.ltx FILE)
# ==============================================================================
# CRUCIAL: The .ltx file must be associated BEFORE refreshing the device

if { $probes_file != "" && [file exists $probes_file] } {
    puts ""
    puts "Loading probes file: $probes_file"
    set_property PROBES.FILE $probes_file $device
    set_property FULL_PROBES.FILE $probes_file $device
} else {
    if { $probes_file != "" } {
        puts "WARNING: Probes file not found: $probes_file"
    }
    puts "WARNING: No probes file - VIO core names may not match."
    puts "         Trying to auto-detect VIO..."
}

# ==============================================================================
# 7. REFRESH DEVICE (Loads VIO Definitions)
# ==============================================================================
puts ""
puts "Refreshing device (loading debug cores)..."
if { [catch {refresh_hw_device $device} err] } {
    puts ""
    puts "============================================================"
    puts "ERROR: Failed to refresh device!"
    puts "============================================================"
    puts "Error details: $err"
    puts ""
    puts "Possible causes:"
    puts "  1. FPGA is not programmed"
    puts "  2. FPGA clock is not running (PLL not locked?)"
    puts "  3. JTAG frequency too high for current clock"
    puts "  4. Bitstream doesn't match the .ltx probes file"
    puts "  5. Debug hub is not accessible"
    puts ""
    puts "Solutions:"
    puts "  - Program the FPGA first, then try reset"
    puts "  - Check that the clock source is active"
    puts "  - Verify PLL lock status"
    puts "============================================================"
    close_hw_target
    close_hw_manager
    exit 1
}

# ==============================================================================
# 8. FIND VIO CORE
# ==============================================================================
puts ""
puts "Searching for VIO cores..."

# Get all VIO cores
set all_vios [get_hw_vios -of_objects $device]

if { [llength $all_vios] == 0 } {
    puts ""
    puts "============================================================"
    puts "ERROR: No VIO cores found in the design!"
    puts "============================================================"
    puts ""
    puts "Possible causes:"
    puts "  1. FPGA is not programmed"
    puts "  2. Bitstream doesn't include VIO debug core"
    puts "  3. Wrong .ltx file (doesn't match bitstream)"
    puts "  4. Debug hub clock is not running"
    puts ""
    puts "Solutions:"
    puts "  - Program the FPGA with a bitstream that has VIO"
    puts "  - Make sure the .ltx file matches the .bit file"
    puts "  - Verify the FPGA clock is running"
    puts "============================================================"
    close_hw_target
    close_hw_manager
    exit 1
}

puts "Found [llength $all_vios] VIO core(s):"
foreach v $all_vios {
    set cell_name [get_property CELL_NAME $v]
    puts "  - $v (CELL_NAME: $cell_name)"
}

# Try to find VIO by common names
set vio ""

# Try different common VIO instance names
set vio_names {"i_vio" "u_vio" "vio_0" "vio_inst" "vio_2"}

foreach name $vio_names {
    set found [get_hw_vios -of_objects $device -filter "CELL_NAME=~*${name}*" -quiet]
    if { $found != "" } {
        set vio [lindex $found 0]
        puts "Found VIO matching '$name': $vio"
        break
    }
}

# If no match, use first available VIO
if { $vio == "" } {
    set vio [lindex $all_vios 0]
    puts "Using first available VIO: $vio"
}

# ==============================================================================
# 9. FIND RESET PROBE
# ==============================================================================
puts ""
puts "Searching for reset probe..."

# Get all probes from the VIO
set all_probes [get_hw_probes -of_objects $vio]
puts "Available probes:"
foreach p $all_probes {
    set dir [get_property TYPE $p]
    set width [get_property WIDTH $p]
    puts "  - $p ($dir, ${width}-bit)"
}

# Try to find reset probe by common names
set reset_probe ""
set reset_names {"vio_reset" "reset" "rst" "probe_out0" "vio_reset_raw"}

foreach name $reset_names {
    set found [get_hw_probes -of_objects $vio -filter "NAME=~*${name}*" -quiet]
    if { $found != "" } {
        # Make sure it's an output probe
        foreach p $found {
            if { [get_property TYPE $p] == "hw_probe_out" } {
                set reset_probe $p
                puts "Found reset probe: $reset_probe"
                break
            }
        }
        if { $reset_probe != "" } {
            break
        }
    }
}

# If no match by name, use first 1-bit output probe (likely reset)
if { $reset_probe == "" } {
    puts "WARNING: Could not find probe named 'reset'."
    puts "         Looking for first 1-bit output probe..."
    
    foreach p $all_probes {
        if { [get_property TYPE $p] == "hw_probe_out" } {
            set width [get_property WIDTH $p]
            if { $width == 1 } {
                set reset_probe $p
                puts "Using 1-bit output probe: $reset_probe"
                break
            }
        }
    }
}

if { $reset_probe == "" } {
    puts "ERROR: No output probes found in VIO."
    close_hw_target
    close_hw_manager
    exit 1
}

# ==============================================================================
# 10. EXECUTE RESET SEQUENCE
# ==============================================================================
puts ""
puts "============================================================"
puts "EXECUTING RESET SEQUENCE"
puts "============================================================"

# Read current value
set current_val [get_property OUTPUT_VALUE $reset_probe]
puts "Current value: $current_val"

# Step 1: Assert reset (drive LOW)
puts "Step 1: Asserting reset (0)..."
set_property OUTPUT_VALUE 0 $reset_probe
commit_hw_vio $reset_probe

# Wait for reset to propagate
after 100

# Step 2: De-assert reset (drive HIGH)
puts "Step 2: De-asserting reset (1)..."
set_property OUTPUT_VALUE 1 $reset_probe
commit_hw_vio $reset_probe

# Wait for system to stabilize
after 50

# Verify final value
set final_val [get_property OUTPUT_VALUE $reset_probe]
puts "Final value: $final_val"

# ==============================================================================
# 11. CLEANUP
# ==============================================================================
puts ""
puts "Closing connections..."
close_hw_target
disconnect_hw_server
close_hw_manager

puts ""
puts "============================================================"
puts "SUCCESS: FPGA Reset Sequence Completed!"
puts "============================================================"
exit 0
