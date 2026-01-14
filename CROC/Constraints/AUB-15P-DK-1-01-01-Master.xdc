set_property CLOCK_BUFFER_TYPE NONE [get_nets -of [get_pins -filter { DIRECTION == IN } -of [get_cells -hier -filter { ORIG_REF_NAME == tc_clk_mux2 || REF_NAME == tc_clk_mux2 }]]]
####################################################################################################################################################################################
# MASTER PIN MAPPING FILE: AUB-15P-DK-1-01-01-Master-XDC.txt
# BOARD REVISION: 1-01-01
# DATE: 10-28-2024
####################################################################################################################################################################################

####################################################################################################################################################################################
# AMD Artix UltraScale+ Part Number
####################################################################################################################################################################################
#### "xcau15p-ffvb676-2-e"
####################################################################################################################################################################################
# diferencial como primary clock
#create_clock -period 3.333 -name sys_clk -waveform {0.000 1.666} [get_ports sys_clk_p]

#create_generated_clock -name soc_clk -source [get_pins i_clkwiz/inst/clk_in1] [get_pins i_clkwiz/inst/clk_out1]
####################################################################################################################################################################################
# USER SWITCH - BANK 65 - VOLTAGE 1.2V VCCO_64_65 - PULLED DOWN WHEN SWITCH OFF (ACTIVE-HIGH with SWITCH ON)
####################################################################################################################################################################################
# set_property PACKAGE_PIN P19 [get_ports {gpio_i[0]}]
# set_property PACKAGE_PIN N19 [get_ports {gpio_i[1]}]
# set_property PACKAGE_PIN P23 [get_ports {gpio_i[2]}]
# set_property PACKAGE_PIN N23 [get_ports fetch_en_i]

# set_property IOSTANDARD LVCMOS12 [get_ports {gpio_i[0]}]
# set_property IOSTANDARD LVCMOS12 [get_ports {gpio_i[1]}]
# set_property IOSTANDARD LVCMOS12 [get_ports {gpio_i[2]}]
# set_property IOSTANDARD LVCMOS12 [get_ports fetch_en_i]
####################################################################################################################################################################################
# SYSTEM RESET - BANK 65 - VOLTAGE 1.2V VCCO_64_65 - PULLED-UP BY DEFAULT (ACTIVE-LOW with RESET PUSH BUTTON - PB3)
####################################################################################################################################################################################
#set_property PACKAGE_PIN V19 [get_ports sys_resetn]
#set_property IOSTANDARD LVCMOS12 [get_ports sys_resetn]

#set_property CLOCK_DEDICATED_ROUTE FALSE [get_nets sys_resetn]

#set_property CLOCK_DEDICATED_ROUTE FALSE [get_nets -of [get_ports sys_reset*]]
#set_property CLOCK_BUFFER_TYPE NONE [get_nets -of [get_ports sys_reset*]]
# Remove avoid tc_clk_mux2 to use global clock routing
set_property CLOCK_DEDICATED_ROUTE FALSE [get_nets {i_croc_soc/i_rstgen/i_rstgen_bypass/synch_regs_q[3]}]
set_property CLOCK_DEDICATED_ROUTE FALSE [get_nets i_rstgen/i_rstgen_bypass/i_tc_clk_mux2_rst_no/rst_ni]
set_property CLOCK_DEDICATED_ROUTE FALSE [get_nets {i_rstgen/i_rstgen_bypass/synch_regs_q[3]}]
set_property CLOCK_DEDICATED_ROUTE FALSE [get_nets {i_vio/inst/PROBE_OUT_ALL_INST/G_PROBE_OUT[0].PROBE_OUT0_INST/probe_out0[0]}]
####################################################################################################################################################################################
# SYSTEM CLOCK 300MHZ - BANK 64 - VOLTAGE 1.2V VCCO_64_65
####################################################################################################################################################################################
set_property PACKAGE_PIN AD21 [get_ports sys_clk_p]
set_property PACKAGE_PIN AE21 [get_ports sys_clk_n]

set_property IOSTANDARD DIFF_SSTL12 [get_ports sys_clk_n]
set_property IOSTANDARD DIFF_SSTL12 [get_ports sys_clk_p]
####################################################################################################################################################################################
# RED LEDs - BANK 85 - VOLTAGE 3.3V
####################################################################################################################################################################################
#set_property PACKAGE_PIN B10 [get_ports {gpio_o[1]}]
#set_property PACKAGE_PIN B11 [get_ports {gpio_o[2]}]
#set_property PACKAGE_PIN C11 [get_ports {gpio_o[3]}]

#set_property IOSTANDARD LVCMOS33 [get_ports {gpio_o[1]}]
#set_property IOSTANDARD LVCMOS33 [get_ports {gpio_o[2]}]
#set_property IOSTANDARD LVCMOS33 [get_ports {gpio_o[3]}]
####################################################################################################################################################################################
# RGB LED - BANK 84 - VOLTAGE 1.8V VCCO_0_84 - PULLED DOWN BY DEFAULT (ACTIVE-HIGH with GPIO CONTROL)
####################################################################################################################################################################################
#set_property PACKAGE_PIN AE15       [get_ports "LED_RGB_R1"] ;    # Bank 84 - VCCO_0_84 - IO_L3N_AD9N_84  - RGB LED D35 (RED)
#set_property PACKAGE_PIN AD15           [get_ports fetch]
set_property PACKAGE_PIN AF13 [get_ports soc_clk]
#set_property IOSTANDARD LVCMOS18    [get_ports "LED_RGB_R1"] ;    # Bank 84 - VCCO_0_84 - IO_L3N_AD9N_84  - RGB LED D35 (RED)
#set_property IOSTANDARD LVCMOS18        [get_ports fetch]
set_property IOSTANDARD LVCMOS18 [get_ports soc_clk]
####################################################################################################################################################################################
# UART Transmit and Receive - BANK 84 - VOLTAGE 1.8V
####################################################################################################################################################################################
set_property PACKAGE_PIN AF15 [get_ports uart_tx_o]
set_property PACKAGE_PIN AF14 [get_ports uart_rx_i]

set_property IOSTANDARD LVCMOS18 [get_ports uart_tx_o]
set_property IOSTANDARD LVCMOS18 [get_ports uart_rx_i]
####################################################################################################################################################################################
# RGB LED - BANK 65 - VOLTAGE 1.2V VCCO_64_65 - PULLED DOWN BY DEFAULT (ACTIVE-HIGH with GPIO CONTROL)
####################################################################################################################################################################################
set_property PACKAGE_PIN U26 [get_ports status_o]
#set_property PACKAGE_PIN P24        [get_ports ""] ;     # Bank 65 - VCCO_64_65 - IO_L15N_T2L_N5_AD11N_A03_D19_65    - RGB LED D36 (GREEN)
#set_property PACKAGE_PIN N24        [get_ports "LED_RGB_B2"] ;     # Bank 65 - VCCO_64_65 - IO_L15P_T2L_N4_AD11P_A02_D18_65    - RGB LED D36 (BLUE)

set_property IOSTANDARD LVCMOS12 [get_ports status_o]
#set_property IOSTANDARD LVCMOS12    [get_ports ""] ;     # Bank 65 - VCCO_64_65 - IO_L15N_T2L_N5_AD11N_A03_D19_65    - RGB LED D36 (GREEN)
#set_property IOSTANDARD LVCMOS12    [get_ports "LED_RGB_B2"] ;     # Bank 65 - VCCO_64_65 - IO_L15P_T2L_N4_AD11P_A02_D18_65    - RGB LED D36 (BLUE)

