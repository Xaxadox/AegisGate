@echo off
chcp 65001 >nul
title AegisGate - RiskBoard

cd /d "%~dp0"

echo ============================================================
echo   AegisGate - Inicializador Automatico (Risk Intelligence)
echo ============================================================
echo.

REM 1. Configurar .env se necessario
if not exist ".env" (
    echo [*] Criando .env a partir de .env.example...
    copy ".env.example" ".env" >nul
)

REM 2. Identificar executavel do Python
set "PY_BIN="

if exist "python_portable\python.exe" (
    set "PY_BIN=python_portable\python.exe"
    echo [OK] Utilizando Python Portatil embutido.
    goto :executar
)

if exist "venv\Scripts\python.exe" (
    set "PY_BIN=venv\Scripts\python.exe"
    echo [OK] Utilizando ambiente virtual venv.
    goto :executar
)

where python >nul 2>&1
if %errorlevel% equ 0 (
    set "PY_BIN=python"
    goto :executar
)

where py >nul 2>&1
if %errorlevel% equ 0 (
    set "PY_BIN=py"
    goto :executar
)

echo [ERRO] Nenhum interpretador Python encontrado!
echo Mantenha a pasta python_portable junto ao projeto.
pause
exit /b 1

:executar

REM 3. Abrir o navegador automaticamente
echo [*] Abrindo o RiskBoard no navegador...
start http://localhost:8000/dashboard

REM 4. Iniciar o servidor Uvicorn em primeiro plano nesta mesma janela
echo [*] Iniciando o servidor Uvicorn em http://localhost:8000...
echo.
echo ============================================================
echo   Servidor Ativo! Mantenha esta janela aberta.
echo   Pressione CTRL+C para encerrar.
echo ============================================================
echo.

%PY_BIN% -m uvicorn src.main:app --host 0.0.0.0 --port 8000

if %errorlevel% neq 0 (
    echo.
    echo [ERRO] O servidor foi encerrado com erro.
    pause
)
