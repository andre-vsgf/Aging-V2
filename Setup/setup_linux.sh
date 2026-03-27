#!/bin/bash

# Define o modo de parada em caso de erro
set -e

echo "[INFO] Configurando Ambiente Python (Linux)..."

# Garante que estamos na raiz do repo (um nível acima de Setup)
cd "$(dirname "$0")/.."

# Verifica se o python3-venv está instalado (comum faltar no Ubuntu/Debian)
if ! dpkg -s python3-venv >/dev/null 2>&1; then
    echo "[AVISO] O pacote python3-venv pode não estar instalado."
    echo "Se falhar, tente: sudo apt install python3-venv"
fi

# Cria o Venv se não existir
if [ ! -d ".venv" ]; then
    echo "[INFO] Criando .venv..."
    python3 -m venv .venv
fi

# Ativa e instala
source .venv/bin/activate
pip install --upgrade pip

if [ -f "requirements.txt" ]; then
    echo "[INFO] Instalando dependencias..."
    pip install -r requirements.txt
else
    echo "[AVISO] requirements.txt não encontrado."
fi

# Permissões de USB (Dialout) para o técnico não ter erro de permissão na Serial
# Opcional, mas recomendado para "blindagem"
if ! groups | grep -q "dialout"; then
    echo "[INFO] Adicionando usuario ao grupo dialout (para acesso Serial/USB)..."
    echo "Voce precisara fazer logout/login para isso surtir efeito."
    sudo usermod -a -G dialout $USER
fi

echo "[SUCESSO] Ambiente configurado."
