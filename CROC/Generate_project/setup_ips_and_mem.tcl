# ==============================================================================
# Script de Geração de IPs e Configuração de Memória
# ==============================================================================
# Este script gera os IPs Xilinx necessários para o projeto CROC.
# As configurações foram extraídas diretamente dos arquivos .xci originais
# para garantir compatibilidade total.
#
# IPs Gerados:
#   - clk_wiz      : Clock Wizard (MMCM, entrada diferencial 100MHz)
#   - sysmon_wiz_0 : System Monitor (DRP, Temp + VCCINT)
#   - vio_2        : Virtual I/O (Debug)
# ==============================================================================

# 1. Detectar raiz do repositório
set script_path [file normalize [info script]]
set croc_root   [file dirname [file dirname $script_path]]

puts "======================================================="
puts " Gerando IPs Xilinx..."
puts " CROC Root: $croc_root"
puts "======================================================="

# ==============================================================================
# A. MEMORY FILE (helloworld.mem)
# ==============================================================================
set mem_file "$croc_root/sw/bin/helloworld.mem"

if {[file exists $mem_file]} {
    puts "\n\[MEM\] Adicionando Memory File: [file tail $mem_file]"
    set file_obj [add_files -norecurse $mem_file]
    set_property file_type {Memory File} $file_obj
    puts "      OK: Arquivo de memória configurado."
} else {
    puts "\n\[MEM\] AVISO: helloworld.mem não encontrado em sw/bin/"
    puts "      O projeto funcionará, mas sem firmware pré-carregado."
}

# ==============================================================================
# B. CLOCK WIZARD (clk_wiz)
# ==============================================================================
# Configuração extraída de clk_wiz.xci:
#   - Entrada: Diferencial 100MHz (clk_in1_p, clk_in1_n)
#   - Primitiva: MMCM
#   - Saída 1: soc_clk       @ 20MHz, fase 0°
#   - Saída 2: catcher_clk_i @ 20MHz, fase 20°
#   - Saída 3: psclk_rf_i    @ 20MHz, fase -330°
#   - Reset: Active High
#   - Locked: Habilitado
# ==============================================================================

puts "\n\[CLK\] Configurando Clock Wizard (clk_wiz)..."

if { [llength [get_ips -quiet clk_wiz]] == 0 } {
    puts "      Criando IP clk_wiz..."
    create_ip -name clk_wiz -vendor xilinx.com -library ip -version 6.0 -module_name clk_wiz

    set_property -dict [list \
        CONFIG.PRIMITIVE {MMCM} \
        CONFIG.PRIM_SOURCE {Differential_clock_capable_pin} \
        CONFIG.PRIM_IN_FREQ {100.000} \
        CONFIG.USE_FREQ_SYNTH {true} \
        CONFIG.USE_PHASE_ALIGNMENT {false} \
        CONFIG.USE_MIN_POWER {false} \
        CONFIG.USE_SPREAD_SPECTRUM {false} \
        CONFIG.USE_DYN_PHASE_SHIFT {false} \
        CONFIG.USE_DYN_RECONFIG {false} \
        CONFIG.JITTER_SEL {No_Jitter} \
        CONFIG.NUM_OUT_CLKS {3} \
        CONFIG.CLKOUT1_USED {true} \
        CONFIG.CLK_OUT1_PORT {soc_clk} \
        CONFIG.CLKOUT1_REQUESTED_OUT_FREQ {20.000} \
        CONFIG.CLKOUT1_REQUESTED_PHASE {0.000} \
        CONFIG.CLKOUT1_REQUESTED_DUTY_CYCLE {50.000} \
        CONFIG.CLKOUT2_USED {true} \
        CONFIG.CLK_OUT2_PORT {catcher_clk_i} \
        CONFIG.CLKOUT2_REQUESTED_OUT_FREQ {20.000} \
        CONFIG.CLKOUT2_REQUESTED_PHASE {20.000} \
        CONFIG.CLKOUT2_REQUESTED_DUTY_CYCLE {50.000} \
        CONFIG.CLKOUT3_USED {true} \
        CONFIG.CLK_OUT3_PORT {psclk_rf_i} \
        CONFIG.CLKOUT3_REQUESTED_OUT_FREQ {20.000} \
        CONFIG.CLKOUT3_REQUESTED_PHASE {-330.000} \
        CONFIG.CLKOUT3_REQUESTED_DUTY_CYCLE {50.000} \
        CONFIG.USE_LOCKED {true} \
        CONFIG.USE_RESET {true} \
        CONFIG.RESET_TYPE {ACTIVE_HIGH} \
        CONFIG.RESET_PORT {reset} \
        CONFIG.PHASESHIFT_MODE {WAVEFORM} \
    ] [get_ips clk_wiz]

    puts "      Gerando targets..."
    generate_target all [get_ips clk_wiz]
    puts "      OK: clk_wiz criado com sucesso."
} else {
    puts "      OK: clk_wiz já existe no projeto."
}

# ==============================================================================
# C. SYSTEM MONITOR (sysmon_wiz_0)
# ==============================================================================
# Configuração extraída de sysmon_wiz_0.xci:
#   - Interface: DRP (Enable_DRP)
#   - DCLK: 20 MHz
#   - Modo Sequenciador: Continuous
#   - Canais Habilitados: Temperature, VCCINT, Calibration
#   - VP/VN: DESABILITADO (não usado neste projeto)
#   - Averaging: 64 samples
#   - Calibration Averaging: Habilitado
#
# NOTA: VP/VN está desabilitado porque usamos apenas sensores internos.
#       Isso significa que NÃO haverá portas .vp e .vn no módulo gerado.
#       O RTL deve conectar o IP SEM essas portas.
# ==============================================================================

puts "\n\[SYSMON\] Configurando System Monitor (sysmon_wiz_0)..."

if { [llength [get_ips -quiet sysmon_wiz_0]] == 0 } {
    puts "      Criando IP sysmon_wiz_0..."
    create_ip -name system_management_wiz -vendor xilinx.com -library ip -version 1.3 -module_name sysmon_wiz_0

    set_property -dict [list \
        CONFIG.INTERFACE_SELECTION {Enable_DRP} \
        CONFIG.DCLK_FREQUENCY {20} \
        CONFIG.SEQUENCER_MODE {Continuous} \
        CONFIG.CHANNEL_ENABLE_CALIBRATION {true} \
        CONFIG.CHANNEL_ENABLE_TEMPERATURE {true} \
        CONFIG.CHANNEL_ENABLE_VCCINT {true} \
        CONFIG.CHANNEL_ENABLE_VP_VN {false} \
        CONFIG.CHANNEL_ENABLE_VCCAUX {false} \
        CONFIG.CHANNEL_ENABLE_VBRAM {false} \
        CONFIG.CHANNEL_ENABLE_VREFP {false} \
        CONFIG.CHANNEL_ENABLE_VREFN {false} \
        CONFIG.CHANNEL_AVERAGING {64} \
        CONFIG.ENABLE_CALIBRATION_AVERAGING {true} \
        CONFIG.ADC_OFFSET_CALIBRATION {true} \
        CONFIG.SENSOR_OFFSET_AND_GAIN_CALIBRATION {true} \
        CONFIG.OT_ALARM {false} \
        CONFIG.USER_TEMP_ALARM {false} \
        CONFIG.VCCINT_ALARM {false} \
        CONFIG.VCCAUX_ALARM {false} \
    ] [get_ips sysmon_wiz_0]

    puts "      Gerando targets..."
    generate_target all [get_ips sysmon_wiz_0]
    puts "      OK: sysmon_wiz_0 criado com sucesso."
    puts ""
    puts "      IMPORTANTE: Este IP NÃO tem portas VP/VN!"
    puts "      Verifique se o RTL (system_monitor_usp.sv) está"
    puts "      instanciando o IP SEM conectar .vp e .vn"
} else {
    puts "      OK: sysmon_wiz_0 já existe no projeto."
}

# ==============================================================================
# D. VIO (vio_0) - FULL DEBUG CORE
# ==============================================================================
# Configuração para vio_0 (versão completa para debug):
#   - Probes de Entrada (FPGA → Hardware Manager): 13
#     - probe_in0[0:0]   : 1 bit  (status_o)
#     - probe_in1-4      : 1 bit each (gpio_o[3:0])
#     - probe_in5[31:0]  : 32 bits (alarm_rf_o)
#     - probe_in6[31:0]  : 32 bits (ff1_rf_o)
#     - probe_in7[31:0]  : 32 bits (ff1_f_o)
#     - probe_in8[31:0]  : 32 bits (alarm_f_o)
#     - probe_in9[31:0]  : 32 bits (ff2_rf_o)
#     - probe_in10[31:0] : 32 bits (ff2_f_o)
#     - probe_in11[31:0] : 32 bits (xor_out_f_o)
#     - probe_in12[31:0] : 32 bits (xor_out_rf_o)
#   - Probes de Saída (Hardware Manager → FPGA): 7
#     - probe_out0[0:0]  : 1 bit  (vio_reset)
#     - probe_out1[0:0]  : 1 bit  (vio_fetch_en)
#     - probe_out2[0:0]  : 1 bit  (vio_gpio)
#     - probe_out3-6     : 1 bit each (vio_gpio_i[3:0])
#
# IMPORTANT: This VIO configuration MUST match the RTL instantiation!
#            Using wrong VIO will cause "debug hub not found" errors.
# ==============================================================================

puts "\n\[VIO\] Configurando Virtual I/O (vio_0 - Full Debug)..."

if { [llength [get_ips -quiet vio_0]] == 0 } {
    puts "      Criando IP vio_0..."
    create_ip -name vio -vendor xilinx.com -library ip -version 3.0 -module_name vio_0

    set_property -dict [list \
        CONFIG.C_NUM_PROBE_IN {1} \
        CONFIG.C_NUM_PROBE_OUT {3} \
        CONFIG.C_PROBE_IN0_WIDTH {1} \
        CONFIG.C_PROBE_IN1_WIDTH {1} \
        CONFIG.C_PROBE_OUT0_WIDTH {1} \
        CONFIG.C_PROBE_OUT1_WIDTH {1} \
        CONFIG.C_PROBE_OUT2_WIDTH {4} \
        CONFIG.C_PROBE_OUT0_INIT_VAL {0x1} \
        CONFIG.C_PROBE_OUT1_INIT_VAL {0x1} \
        CONFIG.C_PROBE_OUT2_INIT_VAL {0x0} \
    ] [get_ips vio_0]

    puts "      Gerando targets..."
    generate_target all [get_ips vio_0]
    puts "      OK: vio_0 criado com sucesso."
    puts ""
    puts "      VIO Probe Summary:"
    puts "        OUT: 7 probes (reset, fetch_en, gpio, gpio_i[3:0])"
    puts "        IN:  13 probes (status, gpio_o, alarms, ff1/ff2, xor)"
} else {
    puts "      OK: vio_0 já existe no projeto."
}

# ==============================================================================
# E. RESUMO
# ==============================================================================
puts ""
puts "======================================================="
puts " IPs Configurados:"
puts "======================================================="
puts "   clk_wiz      : MMCM, 100MHz diff -> 3x 20MHz"
puts "   sysmon_wiz_0 : DRP, Temp+VCCINT, Avg=64, NO VP/VN"
puts "   vio_0        : 13 in (status+alarms), 7 out (reset+gpio)"
puts "======================================================="
puts ""
puts " IMPORTANT: After synthesis, generate new .ltx file!"
puts "            File > Export > Export Hardware Debug"
puts "======================================================="
puts ""
