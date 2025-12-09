# scripts/setup_env.ps1
param(
    [string]$PythonPath = "python",
    [string]$VenvDir = "env"
)

Write-Host "Criando ambiente virtual em: $VenvDir"
$Create = & $PythonPath -m venv $VenvDir
if ($LASTEXITCODE -ne 0) {
    Write-Host "Falha ao criar virtualenv. Verifique o caminho do Python." -ForegroundColor Red
    exit 1
}

Write-Host "Ativando virtualenv e instalando dependências..."
$Activate = Join-Path -Path $VenvDir -ChildPath "Scripts\Activate.ps1"
if (Test-Path $Activate) {
    Write-Host "Para ativar agora, execute:`n    .\\$VenvDir\\Scripts\\Activate.ps1" -ForegroundColor Yellow
} else {
    Write-Host "Arquivo de ativação não encontrado. Verifique o venv." -ForegroundColor Red
}

Write-Host "Instalando dependências (requirements.txt)..."
& $VenvDir\\Scripts\\pip.exe install -r requirements.txt

Write-Host "Pronto! Use: .\\$VenvDir\\Scripts\\Activate.ps1 e rode: uvicorn app.main:app --reload --port 8000"
