<#
.SYNOPSIS
     Sobe o Timenow GestNow localmente.

.DESCRIPTION
    Caminho preferido: SWA CLI + Azure Functions Core Tools (swa start),
    que é o que mais se aproxima do ambiente real do Azure Static Web
    Apps — serve app/ na porta 4280, encaminha /api/* para o host real do
    Functions na 7071 e simula /.auth/me.

    Se "func" ou "swa" não estiverem instalados OU estiverem quebrados
    (aconteceu nesta máquina: o pacote npm do func baixa um binário
    truncado), cai automaticamente para scripts/dev_local.py — um
    servidor Python equivalente que roteia direto para os handlers dos
    blueprints, sem depender do host do Functions. Serve para desenvolver
    e revisar tela; não substitui o swa start para validar deploy.

.PARAMETER Porta
    Porta HTTP. Padrão 4280 (a mesma do SWA CLI).

.PARAMETER ForcarFallback
    Ignora func/swa mesmo que estejam instalados e usa direto o
    dev_local.py. Útil para depurar o próprio fallback.

.EXAMPLE
    .\scripts\rodar.ps1

.EXAMPLE
    .\scripts\rodar.ps1 -Porta 5000
#>

param(
    [int]$Porta = 4280,
    [switch]$ForcarFallback,
    [switch]$SemVerificar
)

$ErrorActionPreference = "Stop"
$raiz = Split-Path -Parent $PSScriptRoot

# ── Porta de qualidade antes de subir ───────────────────────────────────
# Rodar o app com o código reprovando é como testar o carro sem checar o
# freio: funciona até a hora que importa. A verificação leva poucos
# segundos e falha alto.
#
# -SemVerificar existe para o caso legítimo de precisar ver a tela no meio
# de uma refatoração, com o código ainda em trânsito. É escape consciente,
# não o caminho normal.
if (-not $SemVerificar) {
    Write-Host "Conferindo o padrão antes de subir..." -ForegroundColor Cyan
    node (Join-Path $raiz "scripts\verificar.mjs")
    if ($LASTEXITCODE -ne 0) {
        Write-Host ""
        Write-Host "A porta de qualidade reprovou — o app não subiu." -ForegroundColor Red
        Write-Host "  Corrigir o automático:  node scripts\verificar.mjs --corrigir"
        Write-Host "  Subir mesmo assim:      .\scripts\rodar.ps1 -SemVerificar"
        exit 1
    }
    Write-Host ""
}

function Comando-Funciona($nome) {
    if (-not (Get-Command $nome -ErrorAction SilentlyContinue)) { return $false }
    try {
        & $nome --version *>&1 | Out-Null
        return $LASTEXITCODE -eq 0
    } catch {
        return $false
    }
}

function Rodar-ComSwa {
    Write-Host "Subindo com o SWA CLI (swa start)..." -ForegroundColor Cyan
    Write-Host "  app:  http://localhost:$Porta"
    Write-Host "  api:  encaminhada para o host do Functions (porta 7071)"
    Write-Host ""
    Push-Location $raiz
    try {
        swa start --config swa-cli.config.json --config-name timenow-gestnow
    } finally {
        Pop-Location
    }
}

function Rodar-ComFallback {
    param([string]$Motivo)

    Write-Host "Subindo com o servidor local em Python (scripts/dev_local.py)." -ForegroundColor Yellow
    Write-Host "  motivo: $Motivo"
    Write-Host "  app:    http://localhost:$Porta"
    Write-Host "  aviso:  serve para desenvolver e revisar tela; não valida deploy real."
    Write-Host "          Para isso, resolva o SWA CLI/func e rode este script de novo."
    Write-Host ""

    $venvPython = Join-Path $raiz "api\.venv\Scripts\python.exe"
    $python = if (Test-Path $venvPython) { $venvPython } else { "python" }

    & $python (Join-Path $raiz "scripts\dev_local.py") $Porta
}

if ($ForcarFallback) {
    Rodar-ComFallback -Motivo "forçado por -ForcarFallback"
    exit $LASTEXITCODE
}

$temSwa = Comando-Funciona "swa"
$temFunc = Comando-Funciona "func"

if ($temSwa -and $temFunc) {
    Rodar-ComSwa
} else {
    $faltando = @()
    if (-not $temSwa) { $faltando += "swa" }
    if (-not $temFunc) { $faltando += "func" }
    Rodar-ComFallback -Motivo "$($faltando -join ' e ') não instalado(s) ou não responde(m). Rode .\scripts\instalar.ps1 para corrigir."
}
