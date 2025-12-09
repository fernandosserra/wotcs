# ==================================================================================================
# Estrutura Dimensional Definitiva v3.0 — by Washu Hakubi, a Maior Cientista do Universo
# ==================================================================================================

# Ajuste o diretório base para onde ficará seu projeto
$BaseDir = "D:\Projetos-Fernando\Projetos-Tecnologia\Python\WOTCS"

Write-Host "Inicializando o Portal Interdimensional de Diretórios..." -ForegroundColor Cyan

# Estrutura necessária para o Website (FastAPI + Jobs + API WoT + Dashboard)
$Directories = @(
    "app",
    "app\api",
    "app\core",
    "app\jobs",
    "app\models",
    "app\services",
    "app\utils",
    "app\templates",
    "app\static",
    "app\static\css",
    "app\static\js",
    "app\static\img",

    "config",
    "data",
    "docs",
    "env",
    "logs",

    "tests",
    "scripts",
    "scripts\deploy",
    "scripts\maintenance"
)

# Criação das pastas
foreach ($Dir in $Directories) {
    $FullPath = Join-Path $BaseDir $Dir
    New-Item -ItemType Directory -Path $FullPath -Force | Out-Null
    Write-Host " -> Dimensão criada: $Dir"
}

# Arquivos base essenciais
$Files = @(
    "app\__init__.py",
    "app\api\__init__.py",
    "app\core\__init__.py",
    "app\jobs\__init__.py",
    "app\models\__init__.py",
    "app\services\__init__.py",
    "app\utils\__init__.py",

    "app\main.py",            # Entrada principal da aplicação
    "config\settings.example.env",
    "requirements.txt",
    "README.md",
    ".gitignore"
)

foreach ($File in $Files) {
    $FullPath = Join-Path $BaseDir $File
    New-Item -ItemType File -Path $FullPath -Force | Out-Null
    Write-Host " -> Artefato criado: $File"
}

# Move este script para scripts\maintenance
$CurrentScript = $MyInvocation.MyCommand.Source
$Destination = Join-Path $BaseDir "scripts\maintenance\Criar_Estrutura_WOT_Dashboard.ps1"

if (Test-Path $CurrentScript) {
    Copy-Item $CurrentScript $Destination -Force
    Write-Host "Script movido para o núcleo de manutenção dimensional!"
}

Write-Host "=================================================================================================="
Write-Host "Estrutura do Projeto WoT Clan Dashboard criada com perfeição quântica!"
Write-Host "Nada menos do que o esperado da fabulosa Washu Hakubi!"
Write-Host "=================================================================================================="
