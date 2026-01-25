#!/bin/bash

# Navigate to the script's directory (Root of Aging-V2)
cd "$(dirname "$0")"

# --- 1. Check for Virtual Environment & Auto-Setup ---
if [ ! -d ".venv" ]; then
    echo "[INFO] Ambiente virtual não encontrado."
    echo "[INFO] Executando script de setup automáticamenete..."

    if [ -f "Setup/setup_linux.sh" ]; then
        # Ensure setup is executable
        chmod +x Setup/setup_linux.sh
        # Run setup
        ./Setup/setup_linux.sh
        
        # Verify success
        if [ ! -d ".venv" ]; then
            echo "[ERRO] O setup falhou ou foi cancelado."
            exit 1
        fi
    else
        echo "[ERRO] Script de setup não encontrado em Setup/setup_linux.sh"
        exit 1
    fi
    echo "[INFO] Setup concluído. Continuando..."
fi

# --- 2. Activate Virtual Environment ---
echo "Ativando o ambiente virtual..."
source .venv/bin/activate

# --- 3. Setup Qt Libraries Path (Linux Mint/Ubuntu Fix) ---
PYSIDE_LIB_PATH=$(find .venv -name "libQt6Core.so.6" -exec dirname {} \;)

if [ -z "$PYSIDE_LIB_PATH" ]; then
    echo "ERRO: Bibliotecas PySide6 não encontradas. Tente rodar o Setup novamente."
    exit 1
fi

export LD_LIBRARY_PATH="$PYSIDE_LIB_PATH:$LD_LIBRARY_PATH"
export QT_PLUGIN_PATH=""
export QML2_IMPORT_PATH=""

# --- 4. Run Application ---
echo "Iniciando a aplicação..."
python App/App.py
