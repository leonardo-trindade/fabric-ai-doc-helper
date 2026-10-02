<#
Instalador do Fabric Doc Helper (Windows).

Uso (PowerShell, sem precisar baixar nada antes):
    irm https://raw.githubusercontent.com/leonardo-trindade/fabric-ai-doc-helper/main/instalar.ps1 | iex

O que faz:
  1. Instala o uv (winget), se faltar. Nao precisa de Git.
  2. Baixa a ultima versao publicada (tag vX.Y.Z, .zip do GitHub) para
     %LOCALAPPDATA%\Programs\fabric-ai-doc-helper\versoes\<versao> e prepara o ambiente (uv sync).
     O app instalado NAO e um repositorio Git.
  3. Cria os atalhos "Fabric Doc Helper" no Menu Iniciar e na Area de Trabalho e abre o app.
Rodar de novo instala a versao mais nova. Projetos e configuracoes nao sao afetados.
Uma instalacao antiga (v1, baseada em Git) e substituida automaticamente.

Versao especifica (ex.: voltar atras):
    $env:FDH_VERSAO = 'v2.0.0'; irm https://raw.githubusercontent.com/leonardo-trindade/fabric-ai-doc-helper/main/instalar.ps1 | iex

Desenvolvimento (de dentro de um clone do codigo-fonte):
    powershell -ExecutionPolicy Bypass -File instalar.ps1
    -> usa o clone como esta e cria o atalho "Fabric Doc Helper (dev)".
#>
$ErrorActionPreference = 'Stop'
$ProgressPreference = 'SilentlyContinue'   # Invoke-WebRequest muito mais rapido no PowerShell 5.1
[Net.ServicePointManager]::SecurityProtocol = [Net.SecurityProtocolType]::Tls12
$Repo = 'leonardo-trindade/fabric-ai-doc-helper'
$Nome = 'Fabric Doc Helper'
$Minima = [version]'2.0.0'   # versoes anteriores eram clones Git e nao rodam neste formato

function Passo($t) { Write-Host "`n==> $t" -ForegroundColor Cyan }
function Atualizar-Path {
    $env:Path = [Environment]::GetEnvironmentVariable('Path', 'Machine') + ';' +
                [Environment]::GetEnvironmentVariable('Path', 'User') + ';' +
                "$env:USERPROFILE\.local\bin"
}
function Garantir-Uv {
    if (Get-Command uv -ErrorAction SilentlyContinue) { return }
    if (-not (Get-Command winget -ErrorAction SilentlyContinue)) {
        throw 'uv nao encontrado e o winget nao esta disponivel. Instale o uv (https://docs.astral.sh/uv/) e rode o instalador de novo.'
    }
    Passo 'Instalando o uv'
    winget install --id astral-sh.uv -e --silent --accept-package-agreements --accept-source-agreements
    Atualizar-Path
    if (-not (Get-Command uv -ErrorAction SilentlyContinue)) {
        throw 'O uv foi instalado, mas ainda nao aparece no PATH. Feche e abra o PowerShell e rode o instalador de novo.'
    }
}
function Criar-Atalhos($Raiz, $NomeAtalho) {
    $Shell = New-Object -ComObject WScript.Shell
    foreach ($p in @([Environment]::GetFolderPath('Programs'), [Environment]::GetFolderPath('Desktop'))) {
        $a = $Shell.CreateShortcut((Join-Path $p "$NomeAtalho.lnk"))
        $a.TargetPath = Join-Path $Raiz '.venv\Scripts\pythonw.exe'
        $a.Arguments = '"' + (Join-Path $Raiz 'app\main.py') + '"'
        $a.WorkingDirectory = $Raiz
        $a.IconLocation = "$env:SystemRoot\System32\imageres.dll,111"
        $a.Description = 'Projetos de documentacao Microsoft Fabric'
        $a.Save()
    }
}
function Uv-Sync($Pasta) {
    Push-Location $Pasta
    try { uv sync; if ($LASTEXITCODE -ne 0) { throw 'Falha no uv sync.' } } finally { Pop-Location }
}

try {
    Atualizar-Path
    Garantir-Uv
    $Base = Join-Path $env:LOCALAPPDATA 'Programs\fabric-ai-doc-helper'
    $Versoes = Join-Path $Base 'versoes'

    if ($PSScriptRoot -and (Test-Path (Join-Path $PSScriptRoot 'app\main.py')) -and
        ((Split-Path $PSScriptRoot -Parent) -ne $Versoes)) {
        # ---------------- desenvolvimento: o proprio clone do codigo-fonte
        $Destino = (Resolve-Path $PSScriptRoot).Path
        Passo "Modo desenvolvimento: usando o codigo-fonte em $Destino"
        Passo 'Preparando o ambiente'
        Uv-Sync $Destino
        $NomeAtalho = "$Nome (dev)"
    } else {
        # ---------------- producao: versao publicada, sem Git
        if (Test-Path (Join-Path $Base '.git')) {
            Passo 'Removendo a instalacao antiga (v1, baseada em Git). Projetos e configuracoes sao mantidos.'
            Get-ChildItem $Base -Force | Where-Object { $_.Name -ne 'versoes' } |
                Remove-Item -Recurse -Force -ErrorAction Stop
        }

        Passo 'Consultando as versoes publicadas'
        $Tags = Invoke-RestMethod "https://api.github.com/repos/$Repo/tags?per_page=100" -Headers @{ 'User-Agent' = 'fabric-doc-helper' }
        $Publicadas = @($Tags.name | Where-Object { $_ -match '^v\d+\.\d+\.\d+$' -and [version]$_.Substring(1) -ge $Minima } |
                        Sort-Object { [version]$_.Substring(1) } -Descending)
        $Versao = if ($env:FDH_VERSAO) { $env:FDH_VERSAO } else { $Publicadas | Select-Object -First 1 }
        if (-not $Versao) { throw "Ainda nao ha versao publicada compativel (v$Minima ou mais nova)." }
        if ($Publicadas -notcontains $Versao) { throw "Versao $Versao nao encontrada. Publicadas: $($Publicadas -join ', ')" }

        $Destino = Join-Path $Versoes $Versao
        if (Test-Path (Join-Path $Destino 'app\main.py')) {
            Passo "Versao $Versao ja baixada"
        } else {
            Passo "Baixando a versao $Versao"
            New-Item -ItemType Directory -Force $Versoes | Out-Null
            $Tmp = Join-Path $env:TEMP "fdh-$Versao-$([guid]::NewGuid().ToString('N'))"
            New-Item -ItemType Directory -Force $Tmp | Out-Null
            try {
                $Zip = Join-Path $Tmp 'versao.zip'
                Invoke-WebRequest -UseBasicParsing "https://github.com/$Repo/archive/refs/tags/$Versao.zip" -OutFile $Zip
                Expand-Archive $Zip -DestinationPath $Tmp
                $Pasta = Get-ChildItem $Tmp -Directory | Select-Object -First 1   # fabric-ai-doc-helper-X.Y.Z
                if (Test-Path $Destino) { Remove-Item $Destino -Recurse -Force }
                Move-Item $Pasta.FullName $Destino
            } finally { Remove-Item $Tmp -Recurse -Force -ErrorAction SilentlyContinue }
        }
        Passo 'Preparando o ambiente (pode levar alguns minutos na primeira vez)'
        Uv-Sync $Destino
        Set-Content -Path (Join-Path $Base 'atual.txt') -Value $Versao -Encoding ASCII
        $NomeAtalho = $Nome
    }

    Passo 'Criando atalhos'
    Criar-Atalhos $Destino $NomeAtalho

    Passo "Pronto! Abrindo o $NomeAtalho"
    Write-Host "Nas proximas vezes, use o atalho `"$NomeAtalho`" no Menu Iniciar ou na Area de Trabalho."
    Start-Process -FilePath (Join-Path $Destino '.venv\Scripts\pythonw.exe') `
        -ArgumentList ('"' + (Join-Path $Destino 'app\main.py') + '"') -WorkingDirectory $Destino
} catch {
    Write-Host "`nERRO: $($_.Exception.Message)" -ForegroundColor Red
    Write-Host 'Se o app estiver aberto, feche-o e rode de novo. Veja tambem "Problemas comuns" no README.'
}
