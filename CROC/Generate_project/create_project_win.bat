@echo off
setlocal enabledelayedexpansion

:: ==============================================================================
:: CROC FPGA Project - Windows Build Script
:: ==============================================================================
:: Este script cria o projeto Vivado automaticamente.
:: O Vivado será detectado automaticamente ou pode ser configurado manualmente.
:: ==============================================================================

echo.
echo ========================================================
echo    CROC FPGA Project - Automated Build System
echo ========================================================
echo.

:: Navegar para o diretório deste script
cd /d "%~dp0"

:: ==============================================================================
:: 1. DETECTAR VIVADO
:: ==============================================================================
echo [1/3] Detectando Vivado...

:: Primeiro, verificar se já está no PATH
where vivado >nul 2>&1
if %errorlevel% equ 0 (
    echo       OK: Vivado encontrado no PATH
    goto :run_vivado
)

:: Lista de locais comuns de instalação
set "VIVADO_PATHS="
set "VIVADO_PATHS=%VIVADO_PATHS%;C:\Xilinx\Vivado\2025.1\bin"
set "VIVADO_PATHS=%VIVADO_PATHS%;C:\Xilinx\Vivado\2024.2\bin"
set "VIVADO_PATHS=%VIVADO_PATHS%;C:\Xilinx\Vivado\2024.1\bin"
set "VIVADO_PATHS=%VIVADO_PATHS%;C:\Xilinx\Vivado\2023.2\bin"
set "VIVADO_PATHS=%VIVADO_PATHS%;C:\Xilinx\Vivado\2023.1\bin"
set "VIVADO_PATHS=%VIVADO_PATHS%;D:\Xilinx\Vivado\2025.1\bin"
set "VIVADO_PATHS=%VIVADO_PATHS%;D:\Xilinx\Vivado\2024.2\bin"
set "VIVADO_PATHS=%VIVADO_PATHS%;D:\Xilinx\Vivado\2024.1\bin"

:: Buscar Vivado nos locais conhecidos
for %%p in (%VIVADO_PATHS%) do (
    if exist "%%p\vivado.bat" (
        echo       Encontrado: %%p
        set "PATH=%%p;%PATH%"
        goto :run_vivado
    )
)

:: Buscar em C:\Xilinx\Vivado\* dinamicamente
for /d %%d in (C:\Xilinx\Vivado\*) do (
    if exist "%%d\bin\vivado.bat" (
        echo       Encontrado: %%d\bin
        set "PATH=%%d\bin;%PATH%"
        goto :run_vivado
    )
)

:: Se não encontrou, pedir ao usuário
echo.
echo [ERRO] Vivado nao foi encontrado automaticamente.
echo.
echo Por favor, configure o Vivado de uma das formas:
echo   1. Adicione o Vivado ao PATH do sistema
echo   2. Execute o script settings64.bat do Vivado antes de rodar este script
echo.
echo Exemplo:
echo   C:\Xilinx\Vivado\2024.1\settings64.bat
echo   create_project_win.bat
echo.
pause
exit /b 1

:run_vivado
:: ==============================================================================
:: 2. EXECUTAR VIVADO
:: ==============================================================================
echo.
echo [2/3] Executando Vivado em modo batch...
echo       Script: master_build.tcl
echo.

vivado -mode batch -source master_build.tcl -log vivado_build.log -journal vivado_build.jou

if %errorlevel% neq 0 (
    echo.
    echo ========================================================
    echo [ERRO] Falha na criacao do projeto!
    echo ========================================================
    echo.
    echo Verifique o arquivo de log: vivado_build.log
    echo.
    pause
    exit /b 1
)

:: ==============================================================================
:: 3. SUCESSO
:: ==============================================================================
echo.
echo ========================================================
echo [SUCESSO] Projeto criado com sucesso!
echo ========================================================
echo.
echo Projeto: ..\..\Aging_V2\croc_aging.xpr
echo.
echo Para abrir o projeto:
echo   1. Abra o Vivado
echo   2. File ^> Open Project
echo   3. Navegue ate Aging_V2\croc_aging.xpr
echo.
echo Ou execute: vivado ..\..\Aging_V2\croc_aging.xpr
echo.

timeout /t 5
exit /b 0
