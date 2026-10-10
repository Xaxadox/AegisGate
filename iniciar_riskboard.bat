@echo off
chcp 65001 >nul
title AegisGate - RiskBoard Launcher

echo ============================================================
echo   AegisGate - Inicializador Automatico (Risk Intelligence)
echo ============================================================
echo.

cd /d "%~dp0"

:: 1. Verificacao do arquivo .env
if not exist ".env" (
    echo [*] Arquivo .env nao encontrado. Criando a partir de .env.example...
    copy ".env.example" ".env" >nul
    echo [OK] Arquivo .env configurado com sucesso.
)

:: 2. Identificacao do Interpretador Python do Sistema
set "SYS_PYTHON="
where python >nul 2>&1
if %errorlevel% equ 0 (
    set "SYS_PYTHON=python"
) else (
    where py >nul 2>&1
    if %errorlevel% equ 0 (
        set "SYS_PYTHON=py"
    )
)

:: 3. Verificacao do Ambiente Virtual (venv)
set "REBUILD_VENV=0"

if not exist "venv\Scripts\python.exe" (
    set "REBUILD_VENV=1"
) else (
    :: Testa se o Python do venv executa normalmente ou se os caminhos foram quebrados
    venv\Scripts\python.exe -c "import fastapi, sqlalchemy, sklearn, uvicorn" >nul 2>&1
    if %errorlevel% neq 0 (
        echo [*] O ambiente virtual venv existente precisa de atualizacao/reparo.
        set "REBUILD_VENV=1"
    )
)

if "%REBUILD_VENV%"=="1" (
    if "%SYS_PYTHON%"=="" (
        echo [ERRO] Python nao foi encontrado no sistema!
        echo        Instale o Python 3.10 ou superior e marque a opcao "Add Python to PATH".
        echo.
        pause
        exit /b 1
    )

    echo [*] Configurando ambiente virtual isolado (venv)...
    %SYS_PYTHON% -m venv venv
    if %errorlevel% neq 0 (
        echo [ERRO] Falha ao criar o ambiente virtual venv.
        pause
        exit /b 1
    )

    echo [*] Instalando dependencias do projeto...
    :: Tenta instalar a partir do cache offline local (vendor_packages)
    if exist "vendor_packages" (
        echo [*] Instalando dependencias em modo offline (vendor_packages)...
        venv\Scripts\python.exe -m pip install --no-index --find-links=vendor_packages -r requirements.txt >nul 2>&1
    )

    :: Se faltou algo ou vendor_packages nao estava presente, tenta via pip online
    venv\Scripts\python.exe -c "import fastapi, sqlalchemy, sklearn, uvicorn" >nul 2>&1
    if %errorlevel% neq 0 (
        echo [*] Baixando dependencias complementares via rede...
        venv\Scripts\python.exe -m pip install -r requirements.txt
    )
    echo [OK] Dependencias instaladas e validadas!
)

:: 4. Validacao do Modelo de Machine Learning
if not exist "src\ml\fraud_model.joblib" (
    echo [*] Treinando modelo de Inteligencia Artificial (RandomForest)...
    venv\Scripts\python.exe scripts\train_ml_model.py
    echo [OK] Modelo treinado e serializado!
)

:: 5. Inicializacao do Servidor FastAPI / Uvicorn
echo.
echo [*] Inicializando o servidor AegisGate...
start "AegisGate Backend Server" cmd /c "venv\Scripts\python.exe -m uvicorn src.main:app --host 0.0.0.0 --port 8000"

:: 6. Aguarda 2 segundos para o Uvicorn subir e abre o navegador
timeout /t 2 /nobreak >nul
start http://localhost:8000/dashboard

echo.
echo ============================================================
echo   RiskBoard iniciado com sucesso!
echo ============================================================
echo   - Painel de Risco (RiskBoard): http://localhost:8000/dashboard
echo   - Documentacao da API (Docs):  http://localhost:8000/docs
echo.
echo   Mantenha a janela do servidor aberta durante o uso.
echo ============================================================
echo.
timeout /t 5 >nul
