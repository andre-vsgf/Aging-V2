@echo off
cd ..
echo [INFO] Configurando Ambiente Python...

if not exist ".venv" (
    python -m venv .venv
    echo [INFO] Venv criado.
)

call .venv\Scripts\activate
pip install --upgrade pip
if exist "App/requirements.txt" (
    pip install -r App/requirements.txt
) else (
    echo [AVISO] App/requirements.txt nao encontrado.
)

echo [SUCESSO] Ambiente configurado.
pause
