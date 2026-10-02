<#
Instalador do Fabric Doc Helper (Windows).

Uso (PowerShell, sem precisar baixar nada antes):
    irm https://raw.githubusercontent.com/leonardo-trindade/fabric-ai-doc-helper/main/instalar.ps1 | iex

Ou, de dentro de um clone:  powershell -ExecutionPolicy Bypass -File instalar.ps1

O que faz:
  1. Instala Git e uv (winget), se faltarem.
  2. Instala/atualiza o app em %LOCALAPPDATA%\Programs\fabric-ai-doc-helper (ou usa o clone atual).
  3. Prepara o ambiente (uv sync: Python 3.12, Fabric CLI, interface).
  4. Cria os atalhos "Fabric Doc Helper" no Menu Iniciar e na Área de Trabalho e abre o app.
Rodar de novo atualiza a instalação. Os projetos (pastas de cada cliente) não são afetados.
#>
$ErrorActionPreference = 'Stop'
$Repo = 'https://github.com/leonardo-trindade/fabric-ai-doc-helper.git'
$Nome = 'Fabric Doc Helper'

function Passo($t) { Write-Host "`n==> $t" -ForegroundColor Cyan }
function Atualizar-Path {
    $env:Path = [Environment]::GetEnvironmentVariable('Path', 'Machine') + ';' +
                [Environment]::GetEnvironmentVariable('Path', 'User') + ';' +
                "$env:USERPROFILE\.local\bin"
}
function Garantir($comando, $idWinget, $nomeAmigavel) {
    if (Get-Command $comando -ErrorAction SilentlyContinue) { return }
    if (-not (Get-Command winget -ErrorAction SilentlyContinue)) {
        throw "$nomeAmigavel nao encontrado e o winget nao esta disponivel. Instale $nomeAmigavel manualmente e rode o instalador de novo."
    }
    Passo "Instalando $nomeAmigavel"
    winget install --id $idWinget -e --silent --accept-package-agreements --accept-source-agreements
    Atualizar-Path
    if (-not (Get-Command $comando -ErrorAction SilentlyContinue)) {
        throw "$nomeAmigavel foi instalado, mas ainda nao aparece no PATH. Feche e abra o PowerShell e rode o instalador de novo."
    }
}

try {
    Atualizar-Path
    Garantir git 'Git.Git' 'Git'
    Garantir uv 'astral-sh.uv' 'uv'

    # Clone atual (rodado com -File de dentro do repositório) ou instalação padrão.
    if ($PSScriptRoot -and (Test-Path (Join-Path $PSScriptRoot 'app\main.py'))) {
        $Destino = $PSScriptRoot
        Passo "Usando o clone atual: $Destino"
    } else {
        $Destino = Join-Path $env:LOCALAPPDATA 'Programs\fabric-ai-doc-helper'
        if (Test-Path (Join-Path $Destino '.git')) {
            Passo "Atualizando a instalacao em $Destino"
            git -C $Destino -c http.sslBackend=schannel pull --ff-only
        } else {
            Passo "Baixando o app para $Destino"
            New-Item -ItemType Directory -Force (Split-Path $Destino) | Out-Null
            # schannel = certificados do Windows (evita erro de SSL com antivirus/proxy com inspecao HTTPS)
            git -c http.sslBackend=schannel clone $Repo $Destino
        }
        if ($LASTEXITCODE -ne 0) { throw 'Falha no git (veja a mensagem acima).' }
    }
    git -C $Destino config http.sslBackend schannel

    Passo 'Preparando o ambiente (pode levar alguns minutos na primeira vez)'
    Push-Location $Destino
    try { uv sync; if ($LASTEXITCODE -ne 0) { throw 'Falha no uv sync.' } } finally { Pop-Location }

    Passo 'Criando atalhos'
    $Alvo = Join-Path $Destino '.venv\Scripts\pythonw.exe'
    $Shell = New-Object -ComObject WScript.Shell
    $Pastas = @([Environment]::GetFolderPath('Programs'), [Environment]::GetFolderPath('Desktop'))
    foreach ($p in $Pastas) {
        $a = $Shell.CreateShortcut((Join-Path $p "$Nome.lnk"))
        $a.TargetPath = $Alvo
        $a.Arguments = '"' + (Join-Path $Destino 'app\main.py') + '"'
        $a.WorkingDirectory = $Destino
        $a.IconLocation = "$env:SystemRoot\System32\imageres.dll,111"
        $a.Description = 'Projetos de documentacao Microsoft Fabric'
        $a.Save()
    }

    Passo "Pronto! Abrindo o $Nome"
    Write-Host 'Nas proximas vezes, use o atalho "Fabric Doc Helper" no Menu Iniciar ou na Area de Trabalho.'
    Start-Process -FilePath $Alvo -ArgumentList ('"' + (Join-Path $Destino 'app\main.py') + '"') -WorkingDirectory $Destino
} catch {
    Write-Host "`nERRO: $($_.Exception.Message)" -ForegroundColor Red
    Write-Host 'Consulte a secao "Problemas comuns" do README ou envie esta mensagem para quem mantem o app.'
}
