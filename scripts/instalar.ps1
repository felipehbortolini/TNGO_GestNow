<#
.SYNOPSIS
    Instala todas as dependências do Modelo Timenow.

.DESCRIPTION
    Prepara a máquina para rodar o modelo: confere Python e Node.js (não
    instala nenhum dos dois — são pré-requisitos, não algo que um script
    deva alterar no sistema sem pedir), instala o SWA CLI, o Azure
    Functions Core Tools e sincroniza o ambiente Python da API.

    Todos os passos são idempotentes — rodar de novo não quebra nada.

.EXAMPLE
    .\scripts\instalar.ps1

.NOTES
    Escrito e testado no Windows (PowerShell 5.1+). Os passos usam winget e
    npm, que são específicos de plataforma; em macOS/Linux, siga o
    equivalente indicado em cada verificação que falhar.
#>

$ErrorActionPreference = "Stop"
$raiz = Split-Path -Parent $PSScriptRoot

function Escrever-Passo($texto) {
    Write-Host ""
    Write-Host "==> $texto" -ForegroundColor Cyan
}

function Escrever-Ok($texto) {
    Write-Host "    ok  $texto" -ForegroundColor Green
}

function Escrever-Aviso($texto) {
    Write-Host "    !!  $texto" -ForegroundColor Yellow
}

function Comando-Existe($nome) {
    return [bool](Get-Command $nome -ErrorAction SilentlyContinue)
}

$falhas = @()

# ── 1. Python ────────────────────────────────────────────────────────────
Escrever-Passo "Python (pré-requisito — este script não instala)"
if (Comando-Existe "python") {
    $versaoPython = (python --version) 2>&1
    Escrever-Ok "$versaoPython encontrado"
    $major, $minor = (python -c "import sys; print(sys.version_info.major, sys.version_info.minor)") -split " "
    if ([int]$major -lt 3 -or ([int]$major -eq 3 -and [int]$minor -lt 13)) {
        Escrever-Aviso "api/.python-version pede 3.13 — considere instalar essa versão"
    }
} else {
    Escrever-Aviso "Python não encontrado no PATH. Instale em https://www.python.org/downloads/ (>= 3.13) e rode este script de novo."
    $falhas += "python"
}

# ── 2. Node.js / npm ─────────────────────────────────────────────────────
Escrever-Passo "Node.js (pré-requisito — este script não instala)"
if (Comando-Existe "npm") {
    Escrever-Ok "npm $(npm --version) encontrado"
} else {
    Escrever-Aviso "Node.js não encontrado no PATH. Instale em https://nodejs.org/ (LTS) e rode este script de novo."
    $falhas += "node"
}

# ── 3. uv (gerenciador de pacotes Python) ───────────────────────────────
Escrever-Passo "uv"
if (Comando-Existe "uv") {
    Escrever-Ok "uv $(uv --version) já instalado"
} elseif ($falhas -contains "python") {
    Escrever-Aviso "pulado — depende do Python"
} else {
    Write-Host "    instalando via pip..."
    python -m pip install --quiet --upgrade uv
    if (Comando-Existe "uv") {
        Escrever-Ok "uv $(uv --version) instalado"
    } else {
        Escrever-Aviso "instalado, mas não apareceu no PATH desta sessão — abra um terminal novo"
        $falhas += "uv"
    }
}

# ── 4. Azure Static Web Apps CLI ────────────────────────────────────────
Escrever-Passo "SWA CLI (swa)"
if (Comando-Existe "swa") {
    Escrever-Ok "swa $(swa --version) já instalado"
} elseif ($falhas -contains "node") {
    Escrever-Aviso "pulado — depende do Node.js"
} else {
    Write-Host "    instalando via npm..."
    npm install --global "@azure/static-web-apps-cli" 2>&1 | ForEach-Object { Write-Host "      $_" }
    if (Comando-Existe "swa") {
        Escrever-Ok "swa $(swa --version) instalado"
    } else {
        Escrever-Aviso "instalado, mas não apareceu no PATH desta sessão — abra um terminal novo"
        $falhas += "swa"
    }
}

# ── 5. Azure Functions Core Tools ───────────────────────────────────────
# NÃO instalar via "npm install -g azure-functions-core-tools": o pacote é
# um wrapper que baixa o binário (~588 MB) na primeira execução, e em
# várias redes esse download vem truncado — o func então falha com ENOENT
# ou "application to execute does not exist". Achado e confirmado nesta
# mesma máquina. O winget baixa o instalador completo.
Escrever-Passo "Azure Functions Core Tools (func)"
$funcOk = $false
if (Comando-Existe "func") {
    try {
        $v = & func --version 2>&1
        if ($LASTEXITCODE -eq 0 -and $v -match '^\d+\.\d+') {
            Escrever-Ok "func $v já instalado"
            $funcOk = $true
        } else {
            Escrever-Aviso "func está no PATH mas não respondeu --version (instalação quebrada) — reinstalando"
        }
    } catch {
        Escrever-Aviso "func está no PATH mas falhou ao rodar — reinstalando"
    }
}
if (-not $funcOk) {
    if (Comando-Existe "winget") {
        Write-Host "    instalando via winget (Microsoft.Azure.FunctionsCoreTools)..."
        winget install Microsoft.Azure.FunctionsCoreTools --accept-source-agreements --accept-package-agreements --silent
        Escrever-Aviso "abra um terminal novo para o func entrar no PATH, depois confira com: func --version"
    } else {
        Escrever-Aviso "winget não encontrado. Baixe o instalador manualmente:"
        Escrever-Aviso "  https://go.microsoft.com/fwlink/?linkid=2174087 (MSI, Windows)"
        Escrever-Aviso "  macOS: brew tap azure/functions && brew install azure-functions-core-tools@4"
        $falhas += "func"
    }
}

# ── 6. Dependências Python da API ───────────────────────────────────────
# Traz também o ruff (lint + formatação) e o ty (tipos), que são
# dependências de desenvolvimento declaradas em api/pyproject.toml.
#
# Deliberadamente NÃO instalamos ruff/ty globais pelos scripts do astral.sh:
# a versão passaria a depender da máquina de cada pessoa, e a mesma base de
# código reprovaria num lugar e passaria no outro. Presos no uv.lock, todo
# mundo roda exatamente a mesma versão.
Escrever-Passo "Dependências da API — inclui ruff e ty (uv sync)"
if ($falhas -contains "python" -or $falhas -contains "uv") {
    Escrever-Aviso "pulado — depende do Python/uv"
} else {
    Push-Location (Join-Path $raiz "api")
    try {
        uv sync
        Escrever-Ok "ambiente Python sincronizado (.venv em api/.venv)"
        $ruffExe = Join-Path $raiz "api\.venv\Scripts\ruff.exe"
        $tyExe = Join-Path $raiz "api\.venv\Scripts\ty.exe"
        # `-join` é operador, não cmdlet: funciona no PowerShell 5.1, que é
        # o padrão do Windows. Join-String só existe do PowerShell 7 em diante.
        if (Test-Path $ruffExe) { Escrever-Ok "$(& $ruffExe --version)" }
        if (Test-Path $tyExe) {
            $tyVer = (& $tyExe --version) -split ' '
            Escrever-Ok (($tyVer[0..1]) -join ' ')
        }
    } finally {
        Pop-Location
    }
}

# ── 7. Ferramentas de front (ESLint) ────────────────────────────────────
# ESLint 10 + plugins de CSS e HTML, presos no package-lock.json.
# `npm ci` respeita o lock; `npm install` é o caminho da primeira vez.
Escrever-Passo "Ferramentas de front — ESLint (npm)"
if ($falhas -contains "node") {
    Escrever-Aviso "pulado — depende do Node.js"
} else {
    Push-Location $raiz
    try {
        if (Test-Path (Join-Path $raiz "package-lock.json")) {
            npm ci --no-audit --no-fund 2>&1 | Out-Null
        } else {
            npm install --no-audit --no-fund 2>&1 | Out-Null
        }
        $eslintJs = Join-Path $raiz "node_modules\eslint\bin\eslint.js"
        if (Test-Path $eslintJs) {
            Escrever-Ok "eslint $(& node $eslintJs --version)"
        } else {
            Escrever-Aviso "npm terminou mas o eslint não apareceu em node_modules"
            $falhas += "eslint"
        }
    } finally {
        Pop-Location
    }
}

# ── 8. Conferência final ────────────────────────────────────────────────
Escrever-Passo "Porta de qualidade"
if ($falhas.Count -gt 0) {
    Escrever-Aviso "pulada — há pendências acima"
} else {
    Push-Location $raiz
    try {
        node (Join-Path $raiz "scripts\verificar.mjs")
        if ($LASTEXITCODE -ne 0) {
            Escrever-Aviso "a porta de qualidade reprovou — veja a saída acima"
            $falhas += "qualidade"
        }
    } finally {
        Pop-Location
    }
}

# ── Resumo ───────────────────────────────────────────────────────────────
Write-Host ""
Write-Host "────────────────────────────────────────────────────" -ForegroundColor DarkGray
if ($falhas.Count -eq 0) {
    Write-Host "Tudo instalado e conferido." -ForegroundColor Green
    Write-Host "  Rodar o app:          .\scripts\rodar.ps1"
    Write-Host "  Porta de qualidade:   node scripts\verificar.mjs"
} else {
    Write-Host "Pendências: $($falhas -join ', ')" -ForegroundColor Yellow
    Write-Host "Resolva o que está acima e rode este script de novo."
}
Write-Host "────────────────────────────────────────────────────" -ForegroundColor DarkGray
