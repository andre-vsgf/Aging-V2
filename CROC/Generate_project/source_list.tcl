# ==============================================================================
# Gerenciador de Fontes RTL - CROC Project
# ==============================================================================
# Este script adiciona todos os arquivos fonte (RTL) ao projeto Vivado.
# Funciona de forma recursiva e configura automaticamente os include paths.
# ==============================================================================

# 1. Detectar a raiz da pasta CROC
set script_path [file normalize [info script]]
set croc_root   [file dirname [file dirname $script_path]]

puts "======================================================="
puts " Configurando Fontes RTL"
puts " CROC Root: $croc_root"
puts "======================================================="

# ==============================================================================
# A. ARQUIVOS RTL (SystemVerilog/Verilog)
# ==============================================================================
# Diretórios que contêm código RTL

set rtl_dirs [list \
    "$croc_root/rtl_sensors" \
    "$croc_root/xilinx/hw" \
]

# Função auxiliar: Adiciona arquivos RTL recursivamente
proc add_rtl_files_recursive {base_dir} {
    set extensions {*.sv *.v *.svh *.vh}
    set all_files [list]
    
    foreach ext $extensions {
        set found [glob -nocomplain -directory $base_dir -type f $ext]
        foreach f $found {
            lappend all_files $f
        }
        # Busca recursiva em subpastas
        set subdirs [glob -nocomplain -directory $base_dir -type d *]
        foreach subdir $subdirs {
            set sub_found [glob -nocomplain -directory $subdir -type f $ext]
            foreach f $sub_found {
                lappend all_files $f
            }
            # Mais um nível de profundidade
            set subsubdirs [glob -nocomplain -directory $subdir -type d *]
            foreach subsubdir $subsubdirs {
                set subsub_found [glob -nocomplain -directory $subsubdir -type f $ext]
                foreach f $subsub_found {
                    lappend all_files $f
                }
            }
        }
    }
    return $all_files
}

puts "\n\[RTL\] Adicionando arquivos fonte..."

foreach dir $rtl_dirs {
    if {[file exists $dir]} {
        puts "      Buscando em: $dir"
        set files [add_rtl_files_recursive $dir]
        if {[llength $files] > 0} {
            add_files -norecurse $files
            puts "      -> Adicionados [llength $files] arquivo(s)"
        } else {
            puts "      -> Nenhum arquivo encontrado"
        }
    } else {
        puts "      ERRO: Diretório não encontrado: $dir"
    }
}

# ==============================================================================
# B. INCLUDE PATHS (Headers .svh/.vh)
# ==============================================================================
# Busca automaticamente pastas 'include' dentro de rtl_sensors

puts "\n\[INC\] Configurando Include Paths..."

set include_paths [list]

# Busca padrão: */include dentro de rtl_sensors
set auto_includes [glob -nocomplain -type d "$croc_root/rtl_sensors/*/include"]
foreach p $auto_includes {
    if {[file exists $p]} {
        lappend include_paths $p
        puts "      Auto-detectado: $p"
    }
}

# Include raiz de rtl_sensors (se existir)
set root_include "$croc_root/rtl_sensors/include"
if {[file exists $root_include]} {
    lappend include_paths $root_include
    puts "      Include raiz: $root_include"
}

# Aplica a propriedade include_dirs aos filesets
if {[llength $include_paths] > 0} {
    set_property include_dirs $include_paths [current_fileset]
    set_property include_dirs $include_paths [get_filesets sim_1]
    puts "      OK: [llength $include_paths] include path(s) configurado(s)"
} else {
    puts "      AVISO: Nenhum include path encontrado"
}

# ==============================================================================
# C. CONSTRAINTS (.xdc)
# ==============================================================================
puts "\n\[XDC\] Adicionando Constraints..."
#set_property target_constrs_file $PATH/Aging-V2/CROC/Constraints/fpga_aging_constraints.xdc [current_fileset -constrset]
set constraints_dir "$croc_root/Constraints"
if {[file exists $constraints_dir]} {
    set xdc_files [glob -nocomplain -directory $constraints_dir -type f *.xdc]
    if {[llength $xdc_files] > 0} {
        add_files -fileset constrs_1 -norecurse $xdc_files
        puts "      Adicionados [llength $xdc_files] arquivo(s) XDC:"
        foreach xdc $xdc_files {
            puts "        - [file tail $xdc]"
        }
    } else {
        puts "      AVISO: Nenhum arquivo .xdc encontrado"
    }
} else {
    puts "      ERRO: Pasta Constraints não encontrada: $constraints_dir"
}

# ==============================================================================
# D. TOP MODULE
# ==============================================================================
puts "\n\[TOP\] Definindo módulo Top-Level..."

set_property top croc_xilinx [current_fileset]
puts "      Top Module: croc_xilinx"

# ==============================================================================
# E. RESUMO
# ==============================================================================
puts ""
puts "======================================================="
puts " Fontes configuradas com sucesso!"
puts "======================================================="
puts ""
