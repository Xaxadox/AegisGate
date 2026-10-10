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

:: 2. Identificacao do Interpretador Python
set "PYTHON_EXEC="

:: Prioridade 1: Python Portatil embutido (Zero instalacao, roda direto sem permissao de admin)
if exist "python_portable\python.exe" (
    python_portable\python.exe -c "import fastapi, uvicorn, sqlalchemy, sklearn" >nul 2>&1
    if %errorlevel% equ 0 (
        set "PYTHON_EXEC=python_portable\python.exe"
        echo [OK] Utilizando Python Portatil embutido (Zero instalacao necessaria).
    )
)

:: Prioridade 2: Ambiente virtual (venv) local
if "%PYTHON_EXEC%"=="" (
    if exist "venv\Scripts\python.exe" (
        venv\Scripts\python.exe -c "import fastapi, uvicorn, sqlalchemy, sklearn" >nul 2>&1
        if %errorlevel% equ 0 (
            set "PYTHON_EXEC=venv\Scripts\python.exe"
            echo [OK] Utilizando ambiente virtual venv existente.
        )
    )
)

:: Prioridade 3: Criar venv usando o Python do sistema caso nao haja portatil
if "%PYTHON_EXEC%"=="" (
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

    if "%SYS_PYTHON%"=="" (
        echo [ERRO] Python nao foi encontrado no sistema nem a pasta portatil foi localizada!
        echo.
        echo        Para rodar nesta maquina:
        echo        1. Mantenha a pasta "python_portable" junto com o projeto; OU
        echo        2. Instale o Python 3.10+ do site python.org marcando "Add Python to PATH".
        echo.
        pause
        exit /b 1
    )

    echo [*] Configurando ambiente virtual venv a partir do Python do sistema...
    %SYS_PYTHON% -m venv venv
    if %errorlevel% neq 0 (
        echo [ERRO] Falha ao criar o ambiente virtual venv.
        pause
        exit /b 1
    )

    echo [*] Instalando dependencias do projeto...
    if exist "vendor_packages" (
        echo [*] Instalando a partir do cache offline local (vendor_packages)...
        venv\Scripts\python.exe -m pip install --no-index --find-links=vendor_packages -r requirements.txt >nul 2>&1
    )
    venv\Scripts\python.exe -c "import fastapi, uvicorn, sqlalchemy, sklearn" >nul 2>&1
    if %errorlevel% neq 0 (
        echo [*] Baixando dependencias complementares via rede...
        venv\Scripts\python.exe -m pip install -r requirements.txt
    )
    set "PYTHON_EXEC=venv\Scripts\python.exe"
    echo [OK] Ambiente configurado com sucesso!
)

:: 3. Validacao do Modelo de Machine Learning
if not exist "src\ml\fraud_model.joblib" (
    echo [*] Treinando modelo de Inteligencia Artificial (RandomForest)...
    %PYTHON_EXEC% scripts\train_ml_model.py
    echo [OK] Modelo treinado e serializado!
)

:: 4. Inicializacao do Servidor FastAPI / Uvicorn
echo.
echo [*] Inicializando o servidor AegisGate...
start "AegisGate Backend Server" cmd /c "%PYTHON_EXEC% -m uvicorn src.main:app --host 0.0.0.0 --port 8000"

:: 5. Aguarda 2 segundos para o Uvicorn subir e abre o navegador
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
