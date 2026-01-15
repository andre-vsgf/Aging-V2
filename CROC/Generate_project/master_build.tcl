# ==============================================================================
# Master Build Script - CROC FPGA Project
# ==============================================================================
# Este é o script principal para criar o projeto Vivado a partir do zero.
# 
# Uso:
#   Windows: Execute create_project_win.bat
#   Linux:   Execute ./create_project_linux.sh
#
# O projeto será criado em: <repo_root>/Aging_V2/croc_aging.xpr
# ==============================================================================

# ==============================================================================
# 1. DETECÇÃO DE CAMINHOS
# ==============================================================================
set script_path [file normalize [info script]]
set gen_proj_dir [file dirname $script_path]
# Repo root é 2 níveis acima de Generate_project (CROC/Generate_project -> CROC -> Root)
set repo_root [file dirname [file dirname $gen_proj_dir]]

# Caminho onde o projeto será criado
set build_dir "$repo_root/Aging_V2"

puts ""
puts "╔══════════════════════════════════════════════════════════════════╗"
puts "║          CROC FPGA Project - Automated Build System              ║"
puts "╠══════════════════════════════════════════════════════════════════╣"
puts "║  Script Path  : $script_path"
puts "║  Repo Root    : $repo_root"
puts "║  Build Dir    : $build_dir"
puts "╚══════════════════════════════════════════════════════════════════╝"
puts ""

# ==============================================================================
# 2. VERIFICAR ESTRUTURA DE DIRETÓRIOS
# ==============================================================================
puts "\[CHECK\] Verificando estrutura do repositório..."

set required_dirs [list \
    "$repo_root/CROC/rtl_sensors" \
    "$repo_root/CROC/xilinx/hw" \
    "$repo_root/CROC/Constraints" \
]

set missing_dirs 0
foreach dir $required_dirs {
    if {![file exists $dir]} {
        puts "        ERRO: Pasta não encontrada: $dir"
        incr missing_dirs
    }
}

if {$missing_dirs > 0} {
    puts ""
    puts "ERRO FATAL: $missing_dirs pasta(s) obrigatória(s) não encontrada(s)."
    puts "Verifique se a estrutura do repositório está correta."
    exit 1
}

puts "        OK: Estrutura de diretórios válida."

# ==============================================================================
# 3. CONFIGURAÇÃO DO DISPOSITIVO
# ==============================================================================
# Artix UltraScale+ AU15P
# Part Number: xcau15p-ffvb676-2-i
#   - xcau15p  : Artix UltraScale+ AU15P
#   - ffvb676  : Package BGA 676 pinos
#   - 2        : Speed Grade -2
#   - i        : Industrial Temperature (-40°C a +100°C)

set part_num "xcau15p-ffvb676-2-i"

puts ""
puts "\[FPGA\] Dispositivo alvo: $part_num"
puts ""

# ==============================================================================
# 4. CRIAR PROJETO VIVADO
# ==============================================================================
puts "\[PROJ\] Criando projeto Vivado..."

# Cria diretório de build se não existir
file mkdir $build_dir

# Cria o projeto (force = sobrescreve se existir)
create_project -force croc_aging $build_dir -part $part_num

puts "        Projeto criado: $build_dir/croc_aging.xpr"

# ==============================================================================
# 5. ADICIONAR FONTES RTL
# ==============================================================================
puts ""
puts "\[SRC\] Carregando fontes RTL..."
source "$gen_proj_dir/source_list.tcl"

# ==============================================================================
# 6. GERAR IPs E CONFIGURAR MEMÓRIA
# ==============================================================================
puts ""
puts "\[IP\] Gerando IPs Xilinx..."
source "$gen_proj_dir/setup_ips_and_mem.tcl"

# ==============================================================================
# 7. CONFIGURAR DEFINES GLOBAIS
# ==============================================================================
puts ""
puts "\[DEF\] Configurando defines de compilação..."

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

puts "        Defines configurados:"
foreach def $global_defines {
    puts "          - $def"
}

# ==============================================================================
# 8. CONFIGURAÇÕES ADICIONAIS DO PROJETO
# ==============================================================================
puts ""
puts "\[CFG\] Configurações adicionais..."

# Configurar estratégia de síntese para melhor timing
set_property strategy Flow_PerfOptimized_high [get_runs synth_1]
puts "        Estratégia de síntese: Flow_PerfOptimized_high"

# Habilitar mensagens detalhadas
set_property STEPS.SYNTH_DESIGN.ARGS.FLATTEN_HIERARCHY rebuilt [get_runs synth_1]

# ==============================================================================
# 9. RESUMO FINAL
# ==============================================================================
puts ""
puts "╔══════════════════════════════════════════════════════════════════╗"
puts "║                    BUILD CONCLUÍDO COM SUCESSO!                  ║"
puts "╠══════════════════════════════════════════════════════════════════╣"
puts "║  Projeto: $build_dir/croc_aging.xpr"
puts "╠══════════════════════════════════════════════════════════════════╣"
puts "║  Próximos passos:                                                ║"
puts "║    1. Abra o projeto no Vivado GUI                               ║"
puts "║    2. Execute 'Run Synthesis' (F11)                              ║"
puts "║    3. Execute 'Run Implementation'                               ║"
puts "║    4. Execute 'Generate Bitstream'                               ║"
puts "║                                                                  ║"
puts "║  Ou via TCL:                                                     ║"
puts "║    launch_runs synth_1 -jobs 4                                   ║"
puts "║    wait_on_run synth_1                                           ║"
puts "║    launch_runs impl_1 -to_step write_bitstream -jobs 4           ║"
puts "╚══════════════════════════════════════════════════════════════════╝"
puts ""
