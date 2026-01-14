#!/bin/bash

echo "[INFO] Gerando Projeto Vivado em ../../Aging_V2..."

# Verifica se o Vivado está no PATH
if ! command -v vivado &> /dev/null; then
    echo "[ERRO] Vivado não encontrado no PATH."
    echo "Por favor, rode 'source /tools/Xilinx/Vivado/202x.x/settings64.sh' antes."
    read -p "Pressione Enter para sair..."
    exit 1
fi

# Navega até a pasta onde este script está
cd "$(dirname "$0")"

# Roda o script TCL Mestre (que é universal!)
vivado -mode batch -source master_build.tcl

if [ $? -eq 0 ]; then
    echo "[SUCESSO] Projeto Criado em Aging_V2/croc_aging.xpr!"
else
    echo "[ERRO] Falha na criação do projeto."
fi
