# ==============================================================================
# Script de Geração de IPs e Configuração de Memória (Corrigido v2)
# ==============================================================================

# 1. Detectar raiz do repositório
set script_path [file normalize [info script]]
set croc_root   [file dirname [file dirname $script_path]]

puts "-------------------------------------------------------"
puts " Gerando IPs (Configuração Atualizada)..."
puts "-------------------------------------------------------"

# ==============================================================================
# A. MEMORY FILE (helloworld.mem)
# ==============================================================================
set mem_file "$croc_root/sw/bin/helloworld.mem"

if {[file exists $mem_file]} {
    puts " Adicionando Memory File: [file tail $mem_file]"
    # Adiciona o arquivo ao projeto
    set file_obj [add_files -norecurse $mem_file]
    # Configura explicitamente como arquivo de memória (essencial para o UpdateMEM)
    set_property file_type {Memory File} $file_obj
} else {
    puts " [AVISO] helloworld.mem não encontrado em sw/bin/."
}

# ==============================================================================
# B. CLOCK WIZARD (clk_wiz)
# ==============================================================================
# Requisitos: 
# - Entrada Diferencial
# - 3 Clocks de Saída (Configurados: 20MHz, 100MHz, 50MHz)
# - Reset Active High, nome "reset"
if { [get_ips -quiet clk_wiz] eq "" } {
    puts " Criando clk_wiz (Diff In, 3 Out, Reset High)..."
    create_ip -name clk_wiz -vendor xilinx.com -library ip -module_name clk_wiz

    set_property -dict [list \
        CONFIG.PRIM_SOURCE {Differential_clock_capable_pin} \
        CONFIG.PRIM_IN_FREQ {100.000} \
        CONFIG.NUM_OUT_CLKS {3} \
        CONFIG.CLKOUT1_REQUESTED_OUT_FREQ {20.000} \
        CONFIG.CLK_OUT1_PORT {soc_clk} \
        CONFIG.CLKOUT1_REQUESTED_PHASE {0.000} \
        CONFIG.CLKOUT2_REQUESTED_OUT_FREQ {20.000} \
        CONFIG.CLK_OUT2_PORT {catcher_clk_i} \
        CONFIG.CLKOUT2_REQUESTED_PHASE {20.000} \
        CONFIG.CLKOUT3_REQUESTED_OUT_FREQ {20.000} \
        CONFIG.CLK_OUT3_PORT {psclk_rf_i} \
        CONFIG.CLKOUT3_REQUESTED_PHASE {-330.000} \
        CONFIG.USE_LOCKED {true} \
        CONFIG.USE_RESET {true} \
        CONFIG.RESET_TYPE {ACTIVE_HIGH} \
        CONFIG.RESET_PORT {reset} \
    ] [get_ips clk_wiz]

    generate_target all [get_ips clk_wiz]
} else {
    puts " clk_wiz já existe."
}

# ==============================================================================
# C. SYSTEM MONITOR (sysmon_wiz_0)
# ==============================================================================
# Requisitos:
# - DRP Interface
# - FIX ERRO: Habilitar VP/VN para evitar erro de porta inexistente na síntese
if { [get_ips -quiet sysmon_wiz_0] eq "" } {
    puts " Criando sysmon_wiz_0 (DRP)..."
    create_ip -name system_management_wiz -vendor xilinx.com -library ip -module_name sysmon_wiz_0

    set_property -dict [list \
        CONFIG.INTERFACE_SELECTION {Enable_DRP} \
        CONFIG.ENABLE_DCLK {true} \
        CONFIG.DCLK_FREQUENCY {20} \
        CONFIG.CHANNEL_ENABLE_TEMPERATURE {true} \
        CONFIG.CHANNEL_ENABLE_VCCINT {true} \
        CONFIG.CHANNEL_ENABLE_VP_VN {false} \
        CONFIG.Sequencer_Mode {Continuous} \
        CONFIG.OT_ALARM {false} \
        CONFIG.USER_TEMP_ALARM {false} \
        CONFIG.VCCINT_ALARM {false} \
    ] [get_ips sysmon_wiz_0]
    
    # Nota: CHANNEL_ENABLE_VP_VN {true} cria as portas .vp e .vn no IP,
    # resolvendo o erro [Synth 8-11365].

    generate_target all [get_ips sysmon_wiz_0]
} else {
    puts " sysmon_wiz_0 já existe."
}

# ==============================================================================
# D. VIO (vio_2)
# ==============================================================================
if { [get_ips -quiet vio_2] eq "" } {
    puts " Criando vio_2..."
    create_ip -name vio -vendor xilinx.com -library ip -module_name vio_2

    set_property -dict [list \
        CONFIG.C_NUM_PROBE_OUT {4} \
        CONFIG.C_NUM_PROBE_IN {1} \
        CONFIG.C_PROBE_OUT0_WIDTH {1} \
        CONFIG.C_PROBE_OUT1_WIDTH {1} \
        CONFIG.C_PROBE_OUT2_WIDTH {4} \
        CONFIG.C_PROBE_OUT3_WIDTH {4} \
        CONFIG.C_PROBE_IN0_WIDTH {1} \
    ] [get_ips vio_2]

    generate_target all [get_ips vio_2]
} else {
    puts " vio_2 já existe."
}

puts "-------------------------------------------------------"
puts " IPs gerados com sucesso."
puts "-------------------------------------------------------"
