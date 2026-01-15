#!/bin/bash

# ==============================================================================
# CROC FPGA Project - Linux Build Script
# ==============================================================================
# Este script cria o projeto Vivado automaticamente.
# O Vivado será detectado automaticamente ou pode ser configurado manualmente.
# ==============================================================================

echo ""
echo "========================================================"
echo "   CROC FPGA Project - Automated Build System"
echo "========================================================"
echo ""

# Navegar para o diretório deste script
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

# ==============================================================================
# 1. DETECTAR VIVADO
# ==============================================================================
echo "[1/3] Detectando Vivado..."

# Verificar se já está no PATH
if command -v vivado &> /dev/null; then
    echo "      OK: Vivado encontrado no PATH"
    VIVADO_CMD="vivado"
else
    # Lista de locais comuns de instalação no Linux
    VIVADO_LOCATIONS=(
        "/tools/Xilinx/Vivado/2025.1"
        "/tools/Xilinx/Vivado/2024.2"
        "/tools/Xilinx/Vivado/2024.1"
        "/tools/Xilinx/Vivado/2023.2"
        "/tools/Xilinx/Vivado/2023.1"
        "/opt/Xilinx/Vivado/2025.1"
        "/opt/Xilinx/Vivado/2024.2"
        "/opt/Xilinx/Vivado/2024.1"
        "/opt/Xilinx/Vivado/2023.2"
        "/opt/Xilinx/Vivado/2023.1"
        "$HOME/Xilinx/Vivado/2025.1"
        "$HOME/Xilinx/Vivado/2024.2"
        "$HOME/Xilinx/Vivado/2024.1"
    )
    
    VIVADO_FOUND=""
    
    for loc in "${VIVADO_LOCATIONS[@]}"; do
        if [ -f "$loc/bin/vivado" ]; then
            echo "      Encontrado: $loc"
            VIVADO_FOUND="$loc"
            break
        fi
    done
    
    # Busca dinâmica em /tools/Xilinx/Vivado/
    if [ -z "$VIVADO_FOUND" ] && [ -d "/tools/Xilinx/Vivado" ]; then
        for dir in /tools/Xilinx/Vivado/*/; do
            if [ -f "${dir}bin/vivado" ]; then
                echo "      Encontrado: $dir"
                VIVADO_FOUND="${dir%/}"
                break
            fi
        done
    fi
    
    # Busca dinâmica em /opt/Xilinx/Vivado/
    if [ -z "$VIVADO_FOUND" ] && [ -d "/opt/Xilinx/Vivado" ]; then
        for dir in /opt/Xilinx/Vivado/*/; do
            if [ -f "${dir}bin/vivado" ]; then
                echo "      Encontrado: $dir"
                VIVADO_FOUND="${dir%/}"
                break
            fi
        done
    fi
    
    if [ -z "$VIVADO_FOUND" ]; then
        echo ""
        echo "[ERRO] Vivado não foi encontrado automaticamente."
        echo ""
        echo "Por favor, configure o Vivado de uma das formas:"
        echo "  1. Execute 'source /path/to/Vivado/202x.x/settings64.sh'"
        echo "  2. Adicione o Vivado ao PATH"
        echo ""
        echo "Exemplo:"
        echo "  source /tools/Xilinx/Vivado/2024.1/settings64.sh"
        echo "  ./create_project_linux.sh"
        echo ""
        read -p "Pressione Enter para sair..."
        exit 1
    fi
    
    # Carregar o ambiente do Vivado
    echo "      Carregando ambiente: $VIVADO_FOUND/settings64.sh"
    source "$VIVADO_FOUND/settings64.sh"
    VIVADO_CMD="vivado"
fi

# ==============================================================================
# 2. EXECUTAR VIVADO
# ==============================================================================
echo ""
echo "[2/3] Executando Vivado em modo batch..."
echo "      Script: master_build.tcl"
echo ""

$VIVADO_CMD -mode batch -source master_build.tcl -log vivado_build.log -journal vivado_build.jou

if [ $? -ne 0 ]; then
    echo ""
    echo "========================================================"
    echo "[ERRO] Falha na criação do projeto!"
    echo "========================================================"
    echo ""
    echo "Verifique o arquivo de log: vivado_build.log"
    echo ""
    read -p "Pressione Enter para sair..."
    exit 1
fi

# ==============================================================================
# 3. SUCESSO
# ==============================================================================
echo ""
echo "========================================================"
echo "[SUCESSO] Projeto criado com sucesso!"
echo "========================================================"
echo ""
echo "Projeto: ../../Aging_V2/croc_aging.xpr"
echo ""
echo "Para abrir o projeto:"
echo "  1. Abra o Vivado"
echo "  2. File > Open Project"
echo "  3. Navegue até Aging_V2/croc_aging.xpr"
echo ""
echo "Ou execute: vivado ../../Aging_V2/croc_aging.xpr"
echo ""

exit 0
