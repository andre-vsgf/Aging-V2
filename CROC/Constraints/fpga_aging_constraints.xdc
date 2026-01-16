# ==============================================================================
# CROC FPGA Constraints - PC UART Integration
# Target: AMD Artix UltraScale+ (xcau15p-ffvb676-1-i)
# ==============================================================================

# ==============================================================================
# 1. SYSTEM CLOCK (Bank 64 - 1.2V)
# ==============================================================================
set_property PACKAGE_PIN AD20 [get_ports sys_clk_p]
set_property PACKAGE_PIN AE20 [get_ports sys_clk_n]
set_property IOSTANDARD DIFF_SSTL12 [get_ports sys_clk_n]
set_property IOSTANDARD DIFF_SSTL12 [get_ports sys_clk_p]

#create_clock -period 10.000 -name sys_clk -waveform {0.000 5.000} [get_ports sys_clk_p]

# ==============================================================================
# 2. PC INTERFACE - USB-UART Bridge (Bank 65 - 1.2V)
# ==============================================================================
# Direct PC connection via onboard USB-UART bridge
set_property PACKAGE_PIN Y26 [get_ports fpga_uart_tx]
set_property IOSTANDARD LVCMOS12 [get_ports fpga_uart_tx]

set_property PACKAGE_PIN W26 [get_ports fpga_uart_rx]
set_property IOSTANDARD LVCMOS12 [get_ports fpga_uart_rx]

# ==============================================================================
# 3. STM32 INTERFACE (Bank 84 - 3.3V)
# ==============================================================================
set_property PACKAGE_PIN W12 [get_ports mcu_usart1_rx]
set_property IOSTANDARD LVCMOS33 [get_ports mcu_usart1_rx]

set_property PACKAGE_PIN AB16 [get_ports mcu_usart1_tx]
set_property IOSTANDARD LVCMOS33 [get_ports mcu_usart1_tx]

# ==============================================================================
# 4. ASYNC INTERFACE CONSTRAINTS
# ==============================================================================
# UART signals are asynchronous - use false paths
set_false_path -from [get_ports fpga_uart_rx]
set_false_path -to [get_ports fpga_uart_tx]
set_false_path -from [get_ports mcu_usart1_tx]
set_false_path -to [get_ports mcu_usart1_rx]

# ==============================================================================
# 5. BITSTREAM CONFIGURATION
# ==============================================================================
set_property BITSTREAM.GENERAL.COMPRESS TRUE [current_design]
set_property CONFIG_MODE SPIx4 [current_design]
set_property BITSTREAM.CONFIG.CONFIGRATE 31.9 [current_design]


set_false_path -from [get_clocks -of_objects [get_pins i_clk_wiz/inst/mmcme4_adv_inst/CLKOUT0]] -to [get_clocks -of_objects [get_pins i_clk_wiz/inst/mmcme4_adv_inst/CLKOUT2]]
#set_property C_CLK_INPUT_FREQ_HZ 100000000 [get_debug_cores dbg_hub]
#set_property C_ENABLE_CLK_DIVIDER false [get_debug_cores dbg_hub]
#set_property C_USER_SCAN_CHAIN 1 [get_debug_cores dbg_hub]
#connect_debug_port dbg_hub/clk [get_nets soc_clk]
