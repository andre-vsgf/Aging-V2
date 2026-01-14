# ==============================================================================
# Script Universal de Importação de Fontes (Windows/Linux)
# ==============================================================================

# 1. DETECÇÃO AUTOMÁTICA DA RAIZ DO REPOSITÓRIO
# Pega o diretório onde este script está e sobe um nível para achar a raiz.
# Funciona independente se é C:/, /home/user ou /mnt/c.
set script_path [file normalize [info script]]
set repo_root [file dirname [file dirname $script_path]]

puts "-------------------------------------------------------"
puts " Configurando fontes para o projeto CROC"
puts " Raiz do Repositório detectada: $repo_root"
puts "-------------------------------------------------------"

# 2. DEFINIÇÃO DAS PASTAS DE CÓDIGO FONTE (RTL)
# Liste aqui as pastas principais onde estão seus .sv, .v e .svh
# Ajuste conforme sua estrutura de pastas real (ex: rtl, rtl_sensors)
set rtl_dirs [list \
    "$repo_root/rtl" \
    "$repo_root/rtl_sensors" \
]

# 3. ADICIONAR ARQUIVOS RECURSIVAMENTE
# Em vez de listar arquivo por arquivo, adicionamos o diretório inteiro.
foreach dir $rtl_dirs {
    if {[file exists $dir]} {
        puts " Adicionando fontes de: $dir"
        # Adiciona tudo que for Verilog/SystemVerilog
        # O [glob] busca recursivamente se o Vivado indexar, mas adicionar a pasta ajuda.
        add_files -norecurse -scan_for_includes $dir
    } else {
        puts " AVISO: Diretório não encontrado: $dir"
    }
}

# 4. CONFIGURAÇÃO CRÍTICA: INCLUDE DIRECTORIES (Headers)
# É aqui que corrigimos o erro de "header not found".
# Precisamos listar explicitamente onde estão os .svh e .h
set include_paths [list \
    "$repo_root/rtl_sensors/apb/include" \
    "$repo_root/rtl_sensors/common_cells/include" \
    "$repo_root/rtl_sensors/cve2/include" \
    "$repo_root/rtl_sensors/obi/include" \
    "$repo_root/rtl_sensors/register_interface/include" \
    "$repo_root/rtl/include" \
]

# Filtra apenas caminhos que existem para evitar warnings
set valid_includes [list]
foreach p $include_paths {
    if {[file exists $p]} {
        lappend valid_includes $p
    }
}

# Aplica os includes tanto para Síntese quanto para Simulação
set_property include_dirs $valid_includes [current_fileset]
set_property include_dirs $valid_includes [get_filesets sim_1]

puts " Include Dirs configurados: $valid_includes"

# 5. DEFINES GLOBAIS (União das duas versões)
# Lista unificada de defines do seu arquivo e do colega
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

puts " Defines configurados."
puts "-------------------------------------------------------"
