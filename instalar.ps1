<#
Instalador do Fabric Doc Helper (Windows).

Uso (PowerShell, sem precisar baixar nada antes):
    irm https://raw.githubusercontent.com/leonardo-trindade/fabric-ai-doc-helper/main/instalar.ps1 | iex

Ou, de dentro de um clone:  powershell -ExecutionPolicy Bypass -File instalar.ps1

O que faz:
  1. Instala Git e uv (winget), se faltarem.
  2. Producao: instala/atualiza o app em %LOCALAPPDATA%\Programs\fabric-ai-doc-helper na ultima
     versao publicada (tag vX.Y.Z), no branch local "estavel".
     Desenvolvimento (rodado com -File de dentro de um clone): usa o clone como esta.
  3. Prepara o ambiente (uv sync: Python 3.12, Fabric CLI, interface).
  4. Cria os atalhos "Fabric Doc Helper" (ou "Fabric Doc Helper (dev)") e abre o app.
Rodar de novo atualiza a instalacao. Os projetos (pastas de cada cliente) nao sao afetados.

Versao especifica (ex.: voltar atras):
    $env:FDH_VERSAO = 'v1.0.0'; irm https://raw.githubusercontent.com/leonardo-trindade/fabric-ai-doc-helper/main/instalar.ps1 | iex
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
    $Producao = Join-Path $env:LOCALAPPDATA 'Programs\fabric-ai-doc-helper'
    $Dev = $PSScriptRoot -and (Test-Path (Join-Path $PSScriptRoot 'app\main.py')) -and
           ((Resolve-Path $PSScriptRoot).Path.TrimEnd('\') -ne $Producao)
    if ($Dev) {
        $Destino = (Resolve-Path $PSScriptRoot).Path
        $Nome = "$Nome (dev)"
        Passo "Modo desenvolvimento: usando o clone atual ($Destino) como esta"
        git -C $Destino config http.sslBackend schannel
    } else {
        $Destino = $Producao
        if (Test-Path (Join-Path $Destino '.git')) {
            Passo "Buscando versoes em $Destino"
        } else {
            Passo "Baixando o app para $Destino"
            New-Item -ItemType Directory -Force (Split-Path $Destino) | Out-Null
            # schannel = certificados do Windows (evita erro de SSL com antivirus/proxy com inspecao HTTPS)
            git -c http.sslBackend=schannel clone --quiet $Repo $Destino
            if ($LASTEXITCODE -ne 0) { throw 'Falha no git clone (veja a mensagem acima).' }
        }
        git -C $Destino config http.sslBackend schannel
        git -C $Destino fetch --quiet --tags --force origin
        if ($LASTEXITCODE -ne 0) { throw 'Falha ao buscar versoes no GitHub (veja a mensagem acima).' }

        $Versao = $env:FDH_VERSAO
        if (-not $Versao) { $Versao = git -C $Destino tag -l 'v*' --sort=-v:refname | Select-Object -First 1 }
        if ($Versao) {
            Passo "Instalando a versao $Versao"
            git -C $Destino checkout --quiet -B estavel $Versao
        } else {
            Write-Host 'Aviso: ainda nao ha versao publicada (tag vX.Y.Z); usando a main.' -ForegroundColor Yellow
            git -C $Destino checkout --quiet -B estavel origin/main
        }
        if ($LASTEXITCODE -ne 0) { throw 'Falha ao trocar de versao (a instalacao tem alteracoes locais?).' }
    }

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
