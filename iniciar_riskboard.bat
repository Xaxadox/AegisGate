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
    echo [*] Criando arquivo .env a partir de .env.example...
    copy ".env.example" ".env" >nul
)

REM 2. Identificar executavel do Python
set "PY_BIN="

REM Opcao A: Python Portatil embutido (presente no .rar e no pendrive)
if exist "python_portable\python.exe" (
    set "PY_BIN=python_portable\python.exe"
    echo [OK] Utilizando Python Portatil embutido.
    goto :executar
)

REM Opcao B: Ambiente virtual venv existente
if exist "venv\Scripts\python.exe" (
    set "PY_BIN=venv\Scripts\python.exe"
    echo [OK] Utilizando ambiente virtual venv existente.
    goto :executar
)

REM Opcao C: Clonado do GitHub - Criar venv e instalar dependencias automaticamente
set "SYS_PY="
where python >nul 2>&1
if %errorlevel% equ 0 set "SYS_PY=python"
if "%SYS_PY%"=="" (
    where py >nul 2>&1
    if %errorlevel% equ 0 set "SYS_PY=py"
)

if "%SYS_PY%"=="" (
    echo [ERRO] Nenhum interpretador Python encontrado no computador!
    echo.
    echo Para executar este projeto clonado do GitHub:
    echo 1. Instale o Python 3.10+ do site https://www.python.org (marque Add Python to PATH); OU
    echo 2. Utilize o arquivo pre-empacotado AegisGate_Portatil.rar (que inclui Python portatil).
    echo.
    pause
    exit /b 1
)

echo [*] Configurando ambiente virtual venv isolado...
%SYS_PY% -m venv venv
if %errorlevel% neq 0 (
    echo [ERRO] Falha ao criar ambiente virtual venv.
    pause
    exit /b 1
)

echo [*] Instalando dependencias do projeto via pip...
if exist "vendor_packages" (
    venv\Scripts\python.exe -m pip install --no-index --find-links=vendor_packages -r requirements.txt >nul 2>&1
)
venv\Scripts\python.exe -m pip install -r requirements.txt
if %errorlevel% neq 0 (
    echo [ERRO] Falha ao instalar dependencias do requirements.txt.
    pause
    exit /b 1
)

set "PY_BIN=venv\Scripts\python.exe"
echo [OK] Ambiente virtual configurado com sucesso!

:executar

REM 3. Garantir que o modelo de IA esta treinado
if not exist "src\ml\fraud_model.joblib" (
    echo [*] Treinando modelo de Inteligencia Artificial RandomForest...
    %PY_BIN% scripts\train_ml_model.py
    echo [OK] Modelo treinado com sucesso!
)

REM 4. Abrir o navegador automaticamente
echo [*] Abrindo o RiskBoard no navegador...
start http://localhost:8000/dashboard

REM 5. Iniciar o servidor Uvicorn em primeiro plano nesta mesma janela
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
