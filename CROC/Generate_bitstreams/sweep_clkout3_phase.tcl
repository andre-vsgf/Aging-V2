# ============================================================
# sweep_clkout3_phase.tcl
# ============================================================

# ---------------- USER SETTINGS ----------------
set xpr_path  "C:/Projects/Aging-V2/Aging_V2/croc_aging.xpr"
set ip_name   "clk_wiz"
set out_root  "C:/Projects/Aging-V2/out_bitstreams"

set phase_start -330
set phase_end     0
set phase_step    5

set synth_run "synth_1"
set impl_run  "impl_1"

set jobs 14

# pick clock after open_run
set target_clk_pattern "*soc_clk_clk_wiz*"

set artifact_prefix "croc_aging"
set endpoint_substring "gen_sensors"
# ------------------------------------------------

file mkdir $out_root

# ---------------- UTILS ----------------
proc now_str {} {
    return [clock format [clock seconds] -format "%Y-%m-%d %H:%M:%S"]
}

proc fmt_hms {secs} {
    set h [expr {$secs / 3600}]
    set m [expr {($secs % 3600) / 60}]
    set s [expr {$secs % 60}]
    return [format "%02d:%02d:%02d" $h $m $s]
}

proc phase_tag {p} {
    if {$p < 0} {
        return [format "m%03d" [expr {abs($p)}]]
    } else {
        return [format "p%03d" $p]
    }
}

proc newest_file {files} {
    if {[llength $files] == 0} { return "" }
    set newest [lindex $files 0]
    set newest_mtime [file mtime $newest]
    foreach f $files {
        set mt [file mtime $f]
        if {$mt > $newest_mtime} {
            set newest_mtime $mt
            set newest $f
        }
    }
    return $newest
}

proc copy_newest_by_ext {run_dir ext dst_path} {
    set candidates [glob -nocomplain -directory $run_dir *$ext]
    set src [newest_file $candidates]
    if {$src eq ""} { return 0 }
    file copy -force $src $dst_path
    return 1
}

proc pick_clock_by_pattern {pattern} {
    set c [get_clocks -quiet $pattern]
    if {[llength $c] == 0} { return "" }
    return [lindex $c 0]
}
# -----------------------------------------------

# Open project (GUI-safe)
if {[string equal [current_project -quiet] ""]} {
    puts "\n[now_str] - Opening project: $xpr_path"
    open_project $xpr_path
} else {
    puts "\n[now_str] - Project already open: [current_project]"
}

# Project-level checks
if {[llength [get_ips -quiet $ip_name]] == 0} {
    puts "ERROR: IP '$ip_name' not found. Check: get_ips"
    exit 1
}
if {[llength [get_runs -quiet $synth_run]] == 0} {
    puts "ERROR: Run '$synth_run' not found. Check: get_runs"
    exit 1
}
if {[llength [get_runs -quiet $impl_run]] == 0} {
    puts "ERROR: Run '$impl_run' not found. Check: get_runs"
    exit 1
}

# Master log
set global_t0 [clock seconds]
set master_log [file join $out_root "sweep_master_log.txt"]
set flog [open $master_log w]
puts $flog "Sweep master log"
puts $flog "Project: $xpr_path"
puts $flog "IP: $ip_name"
puts $flog "Phase range: $phase_start .. $phase_end (step $phase_step)"
puts $flog "Runs: synth=$synth_run, impl=$impl_run"
puts $flog "Clock pattern: $target_clk_pattern"
puts $flog "Endpoints substring: $endpoint_substring"
puts $flog "Started at: [now_str]"
puts $flog "------------------------------------------------------------"
flush $flog

# Main loop
for {set ph $phase_start} {$ph <= $phase_end} {set ph [expr {$ph + $phase_step}]} {

    set iter_t0 [clock seconds]
    set tag [phase_tag $ph]
    set iter_dir [file join $out_root $tag]
    file mkdir $iter_dir

    set expected_bit [file join $iter_dir "${artifact_prefix}_clkout3phase_${tag}.bit"]
    set expected_bin [file join $iter_dir "${artifact_prefix}_clkout3phase_${tag}.bin"]
    set expected_ltx [file join $iter_dir "${artifact_prefix}_clkout3phase_${tag}.ltx"]

    if {[file exists $expected_bit] && [file exists $expected_bin] && [file exists $expected_ltx]} {
        puts "\n[now_str] - Phase $ph deg already completed. Skipping."
        puts $flog "[now_str] - phase=$ph -> SKIPPED (artifacts exist)"
        flush $flog
        continue
    }

    set iter_log [file join $iter_dir "iteration_log.txt"]
    set ilog [open $iter_log w]
    puts $ilog "Iteration log - CLKOUT3 phase = $ph deg"
    puts $ilog "Started at: [now_str]"
    puts $ilog "------------------------------------------------------------"
    flush $ilog

    puts "\n============================================================"
    puts "[now_str] - Iteration phase = $ph deg"
    puts "============================================================"

    # Update phase
    puts $ilog "[now_str] - Setting clk_wiz CLKOUT3_REQUESTED_PHASE = $ph"
    set_property -dict [list CONFIG.CLKOUT3_REQUESTED_PHASE [format "%.3f" $ph]] [get_ips $ip_name]

    # Regenerate IP
    generate_target all [get_ips $ip_name]
    export_ip_user_files -of_objects [get_ips $ip_name] -no_script -sync -force
    update_compile_order -fileset sources_1

    # Reset runs
    reset_run $synth_run
    reset_run $impl_run

    # Synthesis
    puts $ilog "[now_str] - Launching synthesis jobs=$jobs"
    launch_runs $synth_run -jobs $jobs
    wait_on_run $synth_run
    puts $ilog "[now_str] - Synthesis done"
    flush $ilog

    # Implementation to bitstream
    puts $ilog "[now_str] - Launching implementation to write_bitstream jobs=$jobs"
    launch_runs $impl_run -to_step write_bitstream -jobs $jobs
    wait_on_run $impl_run
    puts $ilog "[now_str] - Implementation/bitstream done"
    flush $ilog

    # Open implemented design
    open_run $impl_run

    # Pick clock now (clocks exist)
    set target_clk [pick_clock_by_pattern $target_clk_pattern]
    if {$target_clk eq ""} {
        puts "ERROR: No clocks match pattern '$target_clk_pattern' (after open_run)."
        puts $ilog "ERROR: No clocks match pattern '$target_clk_pattern' (after open_run)."
        close $ilog
        close $flog
        exit 1
    }
    puts $ilog "[now_str] - Using clock: $target_clk"

    # Collect destination pins safely (avoid brittle quoting)
    set filter_expr [format {NAME =~ *%s* && DIRECTION == IN} $endpoint_substring]
    set dst_pins [get_pins -hier -quiet -filter $filter_expr]

    if {[llength $dst_pins] == 0} {
        puts $ilog "WARNING: No destination pins matched '*$endpoint_substring*' -> timing report skipped."
    } else {
        set timing_compact [file join $iter_dir "timing_setup_${target_clk}_to_${endpoint_substring}_summary.rpt"]
        puts $ilog "[now_str] - Writing compact timing report -> $timing_compact"

        report_timing \
            -from [get_clocks $target_clk] \
            -to   $dst_pins \
            -delay_type max \
            -path_type summary \
            -sort_by slack \
            -max_paths 999999 \
            -file $timing_compact
    }
    flush $ilog

    # Copy artifacts
    set run_dir [get_property DIRECTORY [get_runs $impl_run]]

    set dst_bit [file join $iter_dir "${artifact_prefix}_clkout3phase_${tag}.bit"]
    set dst_bin [file join $iter_dir "${artifact_prefix}_clkout3phase_${tag}.bin"]
    set dst_ltx [file join $iter_dir "${artifact_prefix}_clkout3phase_${tag}.ltx"]

    set ok_bit [copy_newest_by_ext $run_dir ".bit" $dst_bit]
    set ok_bin [copy_newest_by_ext $run_dir ".bin" $dst_bin]
    set ok_ltx [copy_newest_by_ext $run_dir ".ltx" $dst_ltx]

    if {!$ok_bit} {
        puts "ERROR: No .bit found in $run_dir"
        puts $ilog "ERROR: No .bit found in $run_dir"
        close $ilog
        close $flog
        exit 1
    }

    puts $ilog "[now_str] - Copied BIT -> $dst_bit"
    if {$ok_bin} { puts $ilog "[now_str] - Copied BIN -> $dst_bin" }
    if {$ok_ltx} { puts $ilog "[now_str] - Copied LTX -> $dst_ltx" }

    set iter_t1 [clock seconds]
    set iter_dt [expr {$iter_t1 - $iter_t0}]

    puts $ilog "------------------------------------------------------------"
    puts $ilog "Finished at: [now_str]"
    puts $ilog "Iteration duration: [fmt_hms $iter_dt]"
    close $ilog

    puts $flog "[now_str] - phase=$ph -> DONE | iter_time=[fmt_hms $iter_dt] | bit=$dst_bit"
    flush $flog
}

set global_t1 [clock seconds]
set global_dt [expr {$global_t1 - $global_t0}]
puts $flog "------------------------------------------------------------"
puts $flog "Finished at: [now_str]"
puts $flog "Total sweep time: [fmt_hms $global_dt]"
close $flog

puts "\n[now_str] - Sweep completed. Total time: [fmt_hms $global_dt]"
exit 0
