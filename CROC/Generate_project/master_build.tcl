# ==============================================================================
# Master Build Script
# ==============================================================================

# 1. Definições de Caminho
set script_path [file normalize [info script]]
set gen_proj_dir [file dirname $script_path]
# Repo root é 2 níveis acima de Generate_project (CROC/Generate_project -> CROC -> Root)
set repo_root [file dirname [file dirname $gen_proj_dir]]

# Caminho onde o projeto será criado
set build_dir "$repo_root/Aging_V2"

puts "-------------------------------------------------------"
puts " Iniciando geração do projeto CROC"
puts " Output Dir: $build_dir"
puts "-------------------------------------------------------"

# 2. Criar Projeto (XC7A... ajuste o part number para o seu Artix UltraScale+)
# Exemplo: xcau15p-ffvb676-2-i (Verifique seu part number exato)
set part_num "xcau15p-ffvb676-2-i" 

create_project -force croc_aging $build_dir -part $part_num

# 3. Chamar o script de fontes (RTL)
source "$gen_proj_dir/source_list.tcl"

# 4. Chamar o script de IPs e Memória (NOVO)
source "$gen_proj_dir/setup_ips_and_mem.tcl"

# 5. Configurações de Defines Globais (Unificados)
set global_defines [list \
    TARGET_FPGA \
    TARGET_AUP15 \
    TARGET_XILINX \
    WITH_SYSTEM_MONITOR \
    WITH_TELEMETRY_TX \
    WITH_SENSOR \
    WITH_SENSOR_LF \
    WITH_SENSOR_AM \
    COMMON_CELLS_ASSERTS_OFF \
]

set_property verilog_define $global_defines [current_fileset]
set_property verilog_define $global_defines [get_filesets sim_1]

puts "-------------------------------------------------------"
puts " SUCESSO: Projeto criado em Aging_V2/croc_aging.xpr"
puts "-------------------------------------------------------"
