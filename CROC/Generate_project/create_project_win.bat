@echo off
echo [INFO] Gerando Projeto Vivado em ../../Aging_V2...
echo [INFO] Certifique-se que o Vivado esta no PATH.

:: Roda o script TCL
vivado -mode batch -source master_build.tcl

if %errorlevel% neq 0 (
    echo [ERRO] Falha na criacao do projeto.
    pause
) else (
    echo [SUCESSO] Projeto Criado!
    timeout /t 3
)
