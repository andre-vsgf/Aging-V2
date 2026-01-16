# reset_fpga.tcl - Corrected for VIO TYPE mismatch
# 
# Usage: vivado -mode batch -source reset_fpga.tcl -tclargs [optional_probes_file.ltx]

# -------------------------------------------------------------------------
# Configuration
# -------------------------------------------------------------------------
set hw_server_url "localhost:3121"
set vio_names {"i_vio" "u_vio" "vio_0" "vio_inst" "vio_2"}
set reset_names {"vio_reset" "reset" "rst" "probe_out0" "vio_reset_raw"}

# Get arguments
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
puts ""

# -------------------------------------------------------------------------
# Connection
# -------------------------------------------------------------------------
puts "Opening Hardware Manager..."
open_hw_manager

puts "Connecting to hardware server..."
if { [catch {connect_hw_server -url $hw_server_url -allow_non_jtag} err] } {
    if { [catch {connect_hw_server -url $hw_server_url} err2] } {
        puts "ERROR: Failed to connect to hardware server: $err2"
        exit 1
    }
}

puts "Scanning for hardware targets..."
set targets [get_hw_targets]
if { [llength $targets] == 0 } {
    puts "ERROR: No hardware targets found! Check JTAG cable."
    close_hw_manager
    exit 1
}

# Connect to first target
set target [lindex $targets 0]
puts "Opening target: $target"
if { [catch {open_hw_target $target} err] } {
    puts "ERROR: Failed to open hardware target: $err"
    close_hw_manager
    exit 1
}

# Reduce frequency for stability
set_property PARAM.FREQUENCY 3000000 [current_hw_target]

puts "Scanning for FPGA devices..."
set devices [get_hw_devices]
if { [llength $devices] == 0 } {
    puts "ERROR: No FPGA devices found."
    close_hw_target
    close_hw_manager
    exit 1
}

set device [lindex $devices 0]
current_hw_device $device
puts "Selected device: $device"

# Load probes if provided
if { $probes_file != "" && [file exists $probes_file] } {
    puts "Loading probes file: $probes_file"
    set_property PROBES.FILE $probes_file $device
    set_property FULL_PROBES.FILE $probes_file $device
}

puts "Refreshing device..."
if { [catch {refresh_hw_device $device} err] } {
    puts "ERROR: Failed to refresh device: $err"
    close_hw_target
    close_hw_manager
    exit 1
}

# -------------------------------------------------------------------------
# Find VIO Core
# -------------------------------------------------------------------------
puts ""
puts "Searching for VIO cores..."
set all_vios [get_hw_vios -of_objects $device]
if { [llength $all_vios] == 0 } {
    puts "ERROR: No VIO cores found in the design!"
    close_hw_target
    close_hw_manager
    exit 1
}

set vio ""
# Try to find specific VIO by name
foreach name $vio_names {
    set found [get_hw_vios -of_objects $device -filter "CELL_NAME=~*${name}*" -quiet]
    if { $found != "" } {
        set vio [lindex $found 0]
        puts "Found VIO matching '$name': $vio"
        break
    }
}

# Fallback to first VIO
if { $vio == "" } {
    set vio [lindex $all_vios 0]
    puts "Using first available VIO: $vio"
}

# -------------------------------------------------------------------------
# Find Reset Probe
# -------------------------------------------------------------------------
puts ""
puts "Searching for reset probe..."
set reset_probe ""

# FIX: Check for 'vio_output' instead of 'hw_probe_out'
foreach name $reset_names {
    set found [get_hw_probes -of_objects $vio -filter "NAME=~*${name}*" -quiet]
    if { $found != "" } {
        foreach p $found {
            # VIO outputs drive the FPGA (reset)
            if { [get_property TYPE $p] == "vio_output" } {
                set reset_probe $p
                puts "Found reset probe: $reset_probe"
                break
            }
        }
        if { $reset_probe != "" } { break }
    }
}

# Fallback: Find any 1-bit output probe
if { $reset_probe == "" } {
    puts "WARNING: Could not find probe named 'reset'. Looking for first 1-bit output..."
    set all_probes [get_hw_probes -of_objects $vio]
    foreach p $all_probes {
        if { [get_property TYPE $p] == "vio_output" } {
            if { [get_property WIDTH $p] == 1 } {
                set reset_probe $p
                puts "Using 1-bit output probe: $reset_probe"
                break
            }
        }
    }
}

if { $reset_probe == "" } {
    puts "ERROR: No 1-bit output probes found in VIO."
    close_hw_target
    close_hw_manager
    exit 1
}

# -------------------------------------------------------------------------
# Perform Reset Sequence
# -------------------------------------------------------------------------
puts ""
puts "Performing Reset Sequence..."

# 1. Assert Reset (Active High)
puts "  -> Asserting Reset (1)"
set_property OUTPUT_VALUE 0 $reset_probe
commit_hw_vio [get_hw_vios -of_objects $device]
after 100

# 2. Deassert Reset
puts "  -> Deasserting Reset (0)"
set_property OUTPUT_VALUE 1 $reset_probe
commit_hw_vio [get_hw_vios -of_objects $device]
after 100

puts "Reset Complete."
puts "============================================================"

close_hw_target
close_hw_manager
exit 0
