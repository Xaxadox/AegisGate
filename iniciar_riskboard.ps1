# AegisGate - Script de Inicialização 1-Clique para PowerShell
[Console]::OutputEncoding = [System.Text.Encoding]::UTF8

Write-Host "============================================================" -ForegroundColor Cyan
Write-Host "  AegisGate - Inicializador Automático (Risk Intelligence)" -ForegroundColor Cyan
Write-Host "============================================================" -ForegroundColor Cyan

Set-Location -Path $PSScriptRoot

# 1. Configuração do arquivo .env
if (-not (Test-Path ".env")) {
    Write-Host "[*] Arquivo .env não encontrado. Copiando .env.example..." -ForegroundColor Yellow
    Copy-Item ".env.example" ".env"
    Write-Host "[OK] .env criado com sucesso." -ForegroundColor Green
}

# 2. Identificação do Interpretador Python
$pythonExec = $null

# Opção A: Python Portátil embutido (presente no .rar ou pendrive)
if (Test-Path ".\python_portable\python.exe") {
    $pythonExec = ".\python_portable\python.exe"
    Write-Host "[OK] Utilizando Python Portátil embutido (Zero instalação necessária)." -ForegroundColor Green
}
# Opção B: Ambiente virtual venv existente
elseif (Test-Path ".\venv\Scripts\python.exe") {
    $pythonExec = ".\venv\Scripts\python.exe"
    Write-Host "[OK] Utilizando ambiente virtual venv existente." -ForegroundColor Green
}
# Opção C: Clonado do GitHub - Criar venv e instalar dependências
else {
    Write-Host "[*] Configurando ambiente virtual a partir do Python do sistema..." -ForegroundColor Yellow
    
    $sysPython = "python"
    try {
        & python --version 2>$null
    } catch {
        $sysPython = "py"
    }

    & $sysPython -m venv venv
    if ($LASTEXITCODE -ne 0) {
        Write-Host "[ERRO] Não foi possível localizar o Python no sistema nem o Python portátil!" -ForegroundColor Red
        Write-Host "       Para repositórios clonados do GitHub, instale o Python 3.10+ do site python.org" -ForegroundColor Red
        Write-Host "       OU utilize o arquivo AegisGate_Portatil.rar com Python portátil embutido." -ForegroundColor Red
        Read-Host "Pressione Enter para sair..."
        exit 1
    }

    Write-Host "[*] Instalando dependências do projeto via pip..." -ForegroundColor Yellow
    if (Test-Path "vendor_packages") {
        & ".\venv\Scripts\python.exe" -m pip install --no-index --find-links=vendor_packages -r requirements.txt 2>$null
    }
    & ".\venv\Scripts\python.exe" -m pip install -r requirements.txt
    if ($LASTEXITCODE -ne 0) {
        Write-Host "[ERRO] Falha ao instalar as dependências do projeto." -ForegroundColor Red
        Read-Host "Pressione Enter para sair..."
        exit 1
    }

    $pythonExec = ".\venv\Scripts\python.exe"
    Write-Host "[OK] Ambiente virtual configurado com sucesso!" -ForegroundColor Green
}

# 3. Verificação do Modelo de IA
if (-not (Test-Path ".\src\ml\fraud_model.joblib")) {
    Write-Host "[*] Treinando modelo de Inteligência Artificial RandomForest..." -ForegroundColor Yellow
    & $pythonExec scripts\train_ml_model.py
    Write-Host "[OK] Modelo treinado com sucesso!" -ForegroundColor Green
}

# 4. Abertura do Navegador
Write-Host "[*] Abrindo o RiskBoard no navegador..." -ForegroundColor Cyan
Start-Process "http://localhost:8000/dashboard"

# 5. Inicialização do Servidor Uvicorn
Write-Host "[*] Iniciando o servidor AegisGate em http://localhost:8000..." -ForegroundColor Cyan
Write-Host "============================================================" -ForegroundColor Green
Write-Host "  Servidor Ativo! Mantenha esta janela aberta." -ForegroundColor Green
Write-Host "  Pressione CTRL+C para encerrar." -ForegroundColor Green
Write-Host "============================================================" -ForegroundColor Green

& $pythonExec -m uvicorn src.main:app --host 0.0.0.0 --port 8000
