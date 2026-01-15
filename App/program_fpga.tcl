# ==============================================================================
# FPGA Programming Script for Vivado (JTAG & FLASH Support)
# ==============================================================================
# Usage: 
#   SRAM:  vivado -mode batch -source program_fpga.tcl -tclargs <file.bit>
#   FLASH: vivado -mode batch -source program_fpga.tcl -tclargs <file.bin> -flash
# ==============================================================================

# --- Configuration ---
set FLASH_PART "mt25qu01g-spi-x1_x2_x4"

# --- Argument Parsing ---
if { $argc < 1 } {
    puts "ERROR: File path not provided."
    puts "Usage: vivado -mode batch -source program_fpga.tcl -tclargs <file.bit> \[-flash\]"
    exit 1
}

set file_path [lindex $argv 0]
set mode "sram"

if { $argc > 1 && [lindex $argv 1] == "-flash" } {
    set mode "flash"
}

# Verify file exists
if { ![file exists $file_path] } {
    puts "ERROR: File not found: $file_path"
    exit 1
}

puts "============================================================"
puts "FPGA Programming Script ($mode mode)"
puts "File: $file_path"
puts "============================================================"

# ==============================================================================
# 1. OPEN HARDWARE MANAGER
# ==============================================================================
puts "Opening Hardware Manager..."
open_hw_manager

# ==============================================================================
# 2. CONNECT TO HARDWARE SERVER
# ==============================================================================
puts "Connecting to hardware server..."

# Try to connect, allowing non-JTAG devices (needed for some debug bridges)
if { [catch {connect_hw_server -url localhost:3121 -allow_non_jtag} err] } {
    # Fallback without -allow_non_jtag
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
# 4. SELECT FPGA DEVICE
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

# Initial refresh (without probes to speed up)
refresh_hw_device -update_hw_probes false $device

# ==============================================================================
# 5. PROGRAM FPGA
# ==============================================================================

if { $mode == "sram" } {
    # ==============================================================
    # SRAM Programming (Bitstream .bit) - Volatile
    # ==============================================================
    puts ""
    puts ">>> SRAM Programming (Volatile) <<<"
    puts "Configuring bitstream..."
    set_property PROGRAM.FILE $file_path $device
    
    puts "Programming FPGA..."
    if { [catch {program_hw_devices $device} err] } {
        puts "ERROR: Programming failed: $err"
        close_hw_target
        close_hw_manager
        exit 1
    }
    puts "SRAM programming completed successfully!"

} else {
    # ==============================================================
    # FLASH Programming (Configuration Memory .bin) - Persistent
    # ==============================================================
    puts ""
    puts ">>> FLASH Programming (Persistent) <<<"
    puts "Flash Part: $FLASH_PART"
    
    # 1. CLEANUP: Delete existing cfgmem object if it exists
    set existing_mem [get_property PROGRAM.HW_CFGMEM $device]
    if { $existing_mem != "" } {
        puts "Cleaning up previous memory configuration..."
        delete_hw_cfgmem $existing_mem
    }

    # 2. Create configuration memory device
    puts "Creating configuration memory device..."
    if { [catch {
        create_hw_cfgmem -hw_device $device -mem_dev [lindex [get_cfgmem_parts $FLASH_PART] 0]
    } err] } {
        puts "ERROR: Failed to create cfgmem: $err"
        close_hw_target
        close_hw_manager
        exit 1
    }
    
    # Get the memory object handle
    set mem_obj [get_property PROGRAM.HW_CFGMEM $device]

    if { $mem_obj == "" } {
        puts "ERROR: Failed to get configuration memory object."
        close_hw_target
        close_hw_manager
        exit 1
    }

    # 3. Configure Programming Properties
    puts "Configuring flash programming options..."
    set_property PROGRAM.BLANK_CHECK  0 $mem_obj
    set_property PROGRAM.ERASE        1 $mem_obj
    set_property PROGRAM.CFG_PROGRAM  1 $mem_obj
    set_property PROGRAM.VERIFY       1 $mem_obj
    set_property PROGRAM.CHECKSUM     0 $mem_obj
    
    # 4. Set the file
    set_property PROGRAM.ADDRESS_RANGE {use_file} $mem_obj
    set_property PROGRAM.FILES [list $file_path] $mem_obj
    set_property PROGRAM.PRM_FILE {} $mem_obj
    set_property PROGRAM.UNUSED_PIN_TERMINATION {pull-none} $mem_obj

    # 5. Refresh device before programming
    puts "Refreshing device state..."
    refresh_hw_device $device

    # 6. Program Flash
    puts ""
    puts "Starting Flash Erase/Program/Verify cycle..."
    puts "WARNING: This takes significantly longer than SRAM programming."
    puts "         Please wait and do not disconnect the cable."
    puts ""
    
    if { [catch {program_hw_cfgmem -hw_cfgmem $mem_obj} err] } {
        puts "ERROR: Flash programming failed: $err"
        close_hw_target
        close_hw_manager
        exit 1
    }
    puts "Flash programming completed successfully!"
}

# ==============================================================================
# 6. CLEANUP
# ==============================================================================
puts ""
puts "Verifying final state..."
refresh_hw_device $device

puts "Closing connections..."
close_hw_target
disconnect_hw_server
close_hw_manager

puts ""
puts "============================================================"
puts "SUCCESS: Programming Complete!"
puts "============================================================"
exit 0
