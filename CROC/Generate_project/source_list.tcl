# ==============================================================================
# Gerenciador de Fontes Dinâmico - CROC Project
# ==============================================================================

# 1. Detectar a raiz da pasta CROC (sobe um nível a partir de Generate_project)
set script_path [file normalize [info script]]
set croc_root   [file dirname [file dirname $script_path]]

puts "-------------------------------------------------------"
puts " Configurando fontes a partir de: $croc_root"
puts "-------------------------------------------------------"

# 2. Lista de Diretórios de Fontes (RTL)
# Adicionamos a pasta rtl_sensors e a pasta do Top Level (xilinx/hw)
set rtl_dirs [list \
    "$croc_root/rtl_sensors" \
    "$croc_root/xilinx/hw" \
]

# 3. Importação Recursiva
foreach dir $rtl_dirs {
    if {[file exists $dir]} {
        puts " Adicionando: $dir"
        # -scan_for_includes ajuda o Vivado a entender hierarquias
        add_files -norecurse -scan_for_includes $dir
    } else {
        puts " ERRO CRÍTICO: Pasta não encontrada: $dir"
    }
}

# 4. Configuração Explícita de Includes (Headers .svh)
# Precisamos listar todas as subpastas de rtl_sensors que contém headers
# O comando 'glob' abaixo tenta achar pastas 'include' automaticamente dentro de rtl_sensors
set include_search_path [glob -nocomplain -type d "$croc_root/rtl_sensors/*/include"]

# Adiciona manualmente caminhos que podem não seguir o padrão */include
lappend include_search_path "$croc_root/rtl_sensors/include"

# Aplica a propriedade include_dirs
set valid_includes [list]
foreach p $include_search_path {
    if {[file exists $p]} {
        lappend valid_includes $p
    }
}

set_property include_dirs $valid_includes [current_fileset]
set_property include_dirs $valid_includes [get_filesets sim_1]

puts " Includes configurados: $valid_includes"

# 5. Adicionar Constraints
add_files -fileset constrs_1 -norecurse "$croc_root/Constraints"

# 6. Definir Top Module (Importante!)
set_property top croc_xilinx [current_fileset]

puts "-------------------------------------------------------"
