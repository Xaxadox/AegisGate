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

# 2. Verificação do Ambiente Virtual (venv)
$rebuildVenv = $false

if (-not (Test-Path ".\venv\Scripts\python.exe")) {
    $rebuildVenv = $true
} else {
    try {
        & ".\venv\Scripts\python.exe" -c "import fastapi, sqlalchemy, sklearn, uvicorn" 2>$null
        if ($LASTEXITCODE -ne 0) {
            $rebuildVenv = $true
        }
    } catch {
        $rebuildVenv = $true
    }
}

if ($rebuildVenv) {
    Write-Host "[*] Configurando ambiente virtual isolado (venv)..." -ForegroundColor Yellow
    python -m venv venv
    if ($LASTEXITCODE -ne 0) {
        Write-Host "[ERRO] Não foi possível criar o ambiente virtual com 'python -m venv venv'." -ForegroundColor Red
        Write-Host "       Verifique se o Python 3.10+ está instalado e no PATH do sistema." -ForegroundColor Red
        Read-Host "Pressione Enter para sair..."
        exit 1
    }

    Write-Host "[*] Instalando dependências do projeto..." -ForegroundColor Yellow
    if (Test-Path "vendor_packages") {
        Write-Host "[*] Instalando pacotes em modo offline a partir de vendor_packages..." -ForegroundColor Yellow
        & ".\venv\Scripts\python.exe" -m pip install --no-index --find-links=vendor_packages -r requirements.txt 2>$null
    }

    & ".\venv\Scripts\python.exe" -c "import fastapi, sqlalchemy, sklearn, uvicorn" 2>$null
    if ($LASTEXITCODE -ne 0) {
        Write-Host "[*] Baixando dependências online complementares..." -ForegroundColor Yellow
        & ".\venv\Scripts\python.exe" -m pip install -r requirements.txt
    }
    Write-Host "[OK] Dependências instaladas e verificadas!" -ForegroundColor Green
}

# 3. Verificação do Modelo de IA
if (-not (Test-Path ".\src\ml\fraud_model.joblib")) {
    Write-Host "[*] Treinando modelo de Inteligência Artificial (RandomForest)..." -ForegroundColor Yellow
    & ".\venv\Scripts\python.exe" scripts\train_ml_model.py
    Write-Host "[OK] Modelo treinado com sucesso!" -ForegroundColor Green
}

# 4. Inicialização do Servidor Uvicorn
Write-Host "`n[*] Iniciando o servidor AegisGate..." -ForegroundColor Cyan
Start-Process -FilePath "powershell.exe" -ArgumentList "-NoExit", "-Command", "Set-Location '$PSScriptRoot'; .\venv\Scripts\python.exe -m uvicorn src.main:app --host 0.0.0.0 --port 8000"

# 5. Aguarda inicialização e abre o navegador
Start-Sleep -Seconds 2
Start-Process "http://localhost:8000/dashboard"

Write-Host "============================================================" -ForegroundColor Green
Write-Host "  RiskBoard iniciado com sucesso!" -ForegroundColor Green
Write-Host "============================================================" -ForegroundColor Green
Write-Host "  - Painel de Risco: http://localhost:8000/dashboard" -ForegroundColor White
Write-Host "  - Documentação:   http://localhost:8000/docs" -ForegroundColor White
Write-Host "`nMantenha a janela do servidor aberta durante a navegação." -ForegroundColor DarkGray
