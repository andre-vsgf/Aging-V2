# This script was generated automatically by bender.
#set ROOT "/home/tools/Documents/Aging/croc_fpga/croc-main/croc-main"
set ROOT "C:/Projects/croc_fpga/croc_aging_sensors_obi/croc-main/croc-main"
add_files -norecurse -fileset [current_fileset] [list \
    $ROOT/rtl_sensors/tech_cells_generic/fpga/pad_functional_xilinx.sv \
    $ROOT/rtl_sensors/tech_cells_generic/fpga/tc_clk_xilinx.sv \
    $ROOT/rtl_sensors/tech_cells_generic/fpga/tc_sram_xilinx.sv \
    $ROOT/rtl_sensors/tech_cells_generic/tc_sram_impl.sv \
]
add_files -norecurse -fileset [current_fileset] [list \
    $ROOT/rtl_sensors/common_cells/binary_to_gray.sv \
]
add_files -norecurse -fileset [current_fileset] [list \
    $ROOT/rtl_sensors/common_cells/cb_filter_pkg.sv \
    $ROOT/rtl_sensors/common_cells/cc_onehot.sv \
    $ROOT/rtl_sensors/common_cells/cdc_reset_ctrlr_pkg.sv \
    $ROOT/rtl_sensors/common_cells/cf_math_pkg.sv \
    $ROOT/rtl_sensors/common_cells/clk_int_div.sv \
    $ROOT/rtl_sensors/common_cells/credit_counter.sv \
    $ROOT/rtl_sensors/common_cells/delta_counter.sv \
    $ROOT/rtl_sensors/common_cells/ecc_pkg.sv \
    $ROOT/rtl_sensors/common_cells/edge_propagator_tx.sv \
    $ROOT/rtl_sensors/common_cells/exp_backoff.sv \
    $ROOT/rtl_sensors/common_cells/fifo_v3.sv \
    $ROOT/rtl_sensors/common_cells/gray_to_binary.sv \
    $ROOT/rtl_sensors/common_cells/isochronous_4phase_handshake.sv \
    $ROOT/rtl_sensors/common_cells/isochronous_spill_register.sv \
    $ROOT/rtl_sensors/common_cells/lfsr.sv \
    $ROOT/rtl_sensors/common_cells/lfsr_16bit.sv \
    $ROOT/rtl_sensors/common_cells/lfsr_8bit.sv \
    $ROOT/rtl_sensors/common_cells/lossy_valid_to_stream.sv \
    $ROOT/rtl_sensors/common_cells/mv_filter.sv \
    $ROOT/rtl_sensors/common_cells/onehot_to_bin.sv \
    $ROOT/rtl_sensors/common_cells/plru_tree.sv \
    $ROOT/rtl_sensors/common_cells/passthrough_stream_fifo.sv \
    $ROOT/rtl_sensors/common_cells/popcount.sv \
    $ROOT/rtl_sensors/common_cells/rr_arb_tree.sv \
    $ROOT/rtl_sensors/common_cells/rstgen_bypass.sv \
    $ROOT/rtl_sensors/common_cells/serial_deglitch.sv \
    $ROOT/rtl_sensors/common_cells/shift_reg.sv \
    $ROOT/rtl_sensors/common_cells/shift_reg_gated.sv \
    $ROOT/rtl_sensors/common_cells/spill_register_flushable.sv \
    $ROOT/rtl_sensors/common_cells/stream_demux.sv \
    $ROOT/rtl_sensors/common_cells/stream_filter.sv \
    $ROOT/rtl_sensors/common_cells/stream_fork.sv \
    $ROOT/rtl_sensors/common_cells/stream_intf.sv \
    $ROOT/rtl_sensors/common_cells/stream_join_dynamic.sv \
    $ROOT/rtl_sensors/common_cells/stream_mux.sv \
    $ROOT/rtl_sensors/common_cells/stream_throttle.sv \
    $ROOT/rtl_sensors/common_cells/sub_per_hash.sv \
    $ROOT/rtl_sensors/common_cells/sync.sv \
    $ROOT/rtl_sensors/common_cells/sync_wedge.sv \
    $ROOT/rtl_sensors/common_cells/unread.sv \
    $ROOT/rtl_sensors/common_cells/read.sv \
    $ROOT/rtl_sensors/common_cells/addr_decode_dync.sv \
    $ROOT/rtl_sensors/common_cells/cdc_2phase.sv \
    $ROOT/rtl_sensors/common_cells/cdc_4phase.sv \
    $ROOT/rtl_sensors/common_cells/clk_int_div_static.sv \
    $ROOT/rtl_sensors/common_cells/addr_decode.sv \
    $ROOT/rtl_sensors/common_cells/addr_decode_napot.sv \
    $ROOT/rtl_sensors/common_cells/multiaddr_decode.sv \
]
add_files -norecurse -fileset [current_fileset] [list \
    $ROOT/rtl_sensors/common_cells/cb_filter.sv \
    $ROOT/rtl_sensors/common_cells/cdc_fifo_2phase.sv \
    $ROOT/rtl_sensors/common_cells/clk_mux_glitch_free.sv \
    $ROOT/rtl_sensors/common_cells/counter.sv \
    $ROOT/rtl_sensors/common_cells/ecc_decode.sv \
    $ROOT/rtl_sensors/common_cells/ecc_encode.sv \
    $ROOT/rtl_sensors/common_cells/edge_detect.sv \
    $ROOT/rtl_sensors/common_cells/lzc.sv \
    $ROOT/rtl_sensors/common_cells/max_counter.sv \
    $ROOT/rtl_sensors/common_cells/rstgen.sv \
    $ROOT/rtl_sensors/common_cells/spill_register.sv \
    $ROOT/rtl_sensors/common_cells/stream_delay.sv \
    $ROOT/rtl_sensors/common_cells/stream_fifo.sv \
    $ROOT/rtl_sensors/common_cells/stream_fork_dynamic.sv \
    $ROOT/rtl_sensors/common_cells/stream_join.sv \
    $ROOT/rtl_sensors/common_cells/cdc_reset_ctrlr.sv \
    $ROOT/rtl_sensors/common_cells/cdc_fifo_gray.sv \
    $ROOT/rtl_sensors/common_cells/fall_through_register.sv \
    $ROOT/rtl_sensors/common_cells/id_queue.sv \
    $ROOT/rtl_sensors/common_cells/stream_to_mem.sv \
    $ROOT/rtl_sensors/common_cells/stream_arbiter_flushable.sv \
    $ROOT/rtl_sensors/common_cells/stream_fifo_optimal_wrap.sv \
    $ROOT/rtl_sensors/common_cells/stream_register.sv \
    $ROOT/rtl_sensors/common_cells/stream_xbar.sv \
    $ROOT/rtl_sensors/common_cells/cdc_fifo_gray_clearable.sv \
    $ROOT/rtl_sensors/common_cells/cdc_2phase_clearable.sv \
    $ROOT/rtl_sensors/common_cells/mem_to_banks_detailed.sv \
    $ROOT/rtl_sensors/common_cells/stream_arbiter.sv \
    $ROOT/rtl_sensors/common_cells/stream_omega_net.sv \
    $ROOT/rtl_sensors/common_cells/mem_to_banks.sv \
]
add_files -norecurse -fileset [current_fileset] [list \
    $ROOT/rtl_sensors/apb/apb_pkg.sv \
]
add_files -norecurse -fileset [current_fileset] [list \
    $ROOT/rtl_sensors/register_interface/reg_intf.sv \
    $ROOT/rtl_sensors/register_interface/lowrisc_opentitan/prim_subreg_arb.sv \
    $ROOT/rtl_sensors/register_interface/lowrisc_opentitan/prim_subreg_ext.sv \
    $ROOT/rtl_sensors/register_interface/periph_to_reg.sv \
    $ROOT/rtl_sensors/register_interface/reg_to_apb.sv \
    $ROOT/rtl_sensors/register_interface/lowrisc_opentitan/prim_subreg_shadow.sv \
    $ROOT/rtl_sensors/register_interface/lowrisc_opentitan/prim_subreg.sv \
]
add_files -norecurse -fileset [current_fileset] [list \
    $ROOT/rtl_sensors/apb_uart/slib_clock_div.sv \
    $ROOT/rtl_sensors/apb_uart/slib_counter.sv \
    $ROOT/rtl_sensors/apb_uart/slib_edge_detect.sv \
    $ROOT/rtl_sensors/apb_uart/slib_fifo.sv \
    $ROOT/rtl_sensors/apb_uart/slib_input_filter.sv \
    $ROOT/rtl_sensors/apb_uart/slib_input_sync.sv \
    $ROOT/rtl_sensors/apb_uart/slib_mv_filter.sv \
    $ROOT/rtl_sensors/apb_uart/uart_baudgen.sv \
    $ROOT/rtl_sensors/apb_uart/uart_interrupt.sv \
    $ROOT/rtl_sensors/apb_uart/uart_receiver.sv \
    $ROOT/rtl_sensors/apb_uart/uart_transmitter.sv \
    $ROOT/rtl_sensors/apb_uart/apb_uart.sv \
    $ROOT/rtl_sensors/apb_uart/apb_uart_wrap.sv \
    $ROOT/rtl_sensors/apb_uart/reg_uart_wrap.sv \
]
add_files -norecurse -fileset [current_fileset] [list \
    $ROOT/rtl_sensors/cve2/cve2_pkg.sv \
    $ROOT/rtl_sensors/cve2/cve2_alu.sv \
    $ROOT/rtl_sensors/cve2/cve2_compressed_decoder.sv \
    $ROOT/rtl_sensors/cve2/cve2_controller.sv \
    $ROOT/rtl_sensors/cve2/cve2_counter.sv \
    $ROOT/rtl_sensors/cve2/cve2_csr.sv \
    $ROOT/rtl_sensors/cve2/cve2_decoder.sv \
    $ROOT/rtl_sensors/cve2/cve2_fetch_fifo.sv \
    $ROOT/rtl_sensors/cve2/cve2_load_store_unit.sv \
    $ROOT/rtl_sensors/cve2/cve2_multdiv_fast.sv \
    $ROOT/rtl_sensors/cve2/cve2_multdiv_slow.sv \
    $ROOT/rtl_sensors/cve2/cve2_pmp.sv \
    $ROOT/rtl_sensors/cve2/cve2_register_file_ff.sv \
    $ROOT/rtl_sensors/cve2/cve2_wb.sv \
    $ROOT/rtl_sensors/cve2/cve2_cs_registers.sv \
    $ROOT/rtl_sensors/cve2/cve2_ex_block.sv \
    $ROOT/rtl_sensors/cve2/cve2_id_stage.sv \
    $ROOT/rtl_sensors/cve2/cve2_prefetch_buffer.sv \
    $ROOT/rtl_sensors/cve2/cve2_if_stage.sv \
    $ROOT/rtl_sensors/cve2/cve2_core.sv \
]
add_files -norecurse -fileset [current_fileset] [list \
    $ROOT/rtl_sensors/obi/obi_pkg.sv \
    $ROOT/rtl_sensors/obi/obi_intf.sv \
    $ROOT/rtl_sensors/obi/obi_rready_converter.sv \
    $ROOT/rtl_sensors/obi/obi_atop_resolver.sv \
    $ROOT/rtl_sensors/obi/obi_cut.sv \
    $ROOT/rtl_sensors/obi/obi_demux.sv \
    $ROOT/rtl_sensors/obi/obi_err_sbr.sv \
    $ROOT/rtl_sensors/obi/obi_mux.sv \
    $ROOT/rtl_sensors/obi/obi_sram_shim.sv \
    $ROOT/rtl_sensors/obi/obi_xbar.sv \
]
add_files -norecurse -fileset [current_fileset] [list \
    $ROOT/rtl_sensors/riscv-dbg/dm_pkg.sv \
    $ROOT/rtl_sensors/riscv-dbg/debug_rom/debug_rom.sv \
    $ROOT/rtl_sensors/riscv-dbg/debug_rom/debug_rom_one_scratch.sv \
    $ROOT/rtl_sensors/riscv-dbg/dm_csrs.sv \
    $ROOT/rtl_sensors/riscv-dbg/dm_mem.sv \
    $ROOT/rtl_sensors/riscv-dbg/dmi_cdc.sv \
]
add_files -norecurse -fileset [current_fileset] [list \
    $ROOT/rtl_sensors/riscv-dbg/dmi_jtag_tap.sv \
]
add_files -norecurse -fileset [current_fileset] [list \
    $ROOT/rtl_sensors/riscv-dbg/dm_sba.sv \
    $ROOT/rtl_sensors/riscv-dbg/dm_top.sv \
    $ROOT/rtl_sensors/riscv-dbg/dmi_jtag.sv \
    $ROOT/rtl_sensors/riscv-dbg/dm_obi_top.sv \
]
add_files -norecurse -fileset [current_fileset] [list \
    $ROOT/rtl_sensors/timer_unit/timer_unit_counter.sv \
    $ROOT/rtl_sensors/timer_unit/timer_unit_counter_presc.sv \
    $ROOT/rtl_sensors/timer_unit/apb_timer_unit.sv \
    $ROOT/rtl_sensors/timer_unit/timer_unit.sv \
]
add_files -norecurse -fileset [current_fileset] [list \
    $ROOT/rtl_sensors/croc_pkg.sv \
    $ROOT/rtl_sensors/user_pkg.sv \
    $ROOT/rtl_sensors/soc_ctrl/soc_ctrl_reg_pkg.sv \
    $ROOT/rtl_sensors/gpio/gpio_reg_pkg.sv \
]
add_files -norecurse -fileset [current_fileset] [list \
    $ROOT/rtl_sensors/core_wrap.sv \
    $ROOT/rtl_sensors/soc_ctrl/soc_ctrl_reg_top.sv \
    $ROOT/rtl_sensors/gpio/gpio_reg_top.sv \
    $ROOT/rtl_sensors/gpio/gpio.sv \
    $ROOT/rtl_sensors/croc_domain.sv \
    $ROOT/rtl_sensors/user_domain.sv \
    $ROOT/rtl_sensors/croc_soc.sv \
]
add_files -norecurse -fileset [current_fileset] [list \
    $ROOT/xilinx/hw/croc_xilinx_aging_sensors.sv \

]
add_files -norecurse -fileset [current_fileset] $ROOT/rtl_sensors/user_domain/user_sensor_monitor.sv

set_property include_dirs [list \
    $ROOT/rtl_sensors/apb/include \
    $ROOT/rtl_sensors/common_cells/include \
    $ROOT/rtl_sensors/cve2/include \
    $ROOT/rtl_sensors/obi/include \
    $ROOT/rtl_sensors/register_interface/include \
] [current_fileset]

set_property include_dirs [list \
    $ROOT/rtl_sensors/apb/include \
    $ROOT/rtl_sensors/common_cells/include \
    $ROOT/rtl_sensors/cve2/include \
    $ROOT/rtl_sensors/obi/include \
    $ROOT/rtl_sensors/register_interface/include \
] [current_fileset -simset]

set_property verilog_define [list \
    TARGET_FPGA \
    TARGET_AUP15 \
    TARGET_RTL \
    WITH_SENSOR \
    WITH_SENSOR_LF \
    WITH_SENSOR_CORE \
    WITH_SENSOR_AM \
    WITH_SENSOR_OBI_DMX \
    WITH_SENSOR_UART \
    TARGET_SYNTHESIS \
    TARGET_VIVADO \
    TARGET_XILINX \
    COMMON_CELLS_ASSERTS_OFF \
] [current_fileset]

set_property verilog_define [list \
    TARGET_FPGA \
    TARGET_AUP15 \
    TARGET_RTL \
    WITH_SENSOR \
    WITH_SENSOR_LF \
    WITH_SENSOR_CORE \
    WITH_SENSOR_AM \
    WITH_SENSOR_OBI_DMX \
    WITH_SENSOR_UART \
    TARGET_SYNTHESIS \
    TARGET_VIVADO \
    TARGET_XILINX \
] [current_fileset -simset]

set_property XPM_LIBRARIES XPM_MEMORY [current_project]

#set_property INIT_FILE ../sw/bin/helloworld.mem [get_cells u_xpm_spram]
#set memfile [file normalize C:\Projects\croc_fpga\croc-main\croc-main\sw\bin\helloworld.mem]