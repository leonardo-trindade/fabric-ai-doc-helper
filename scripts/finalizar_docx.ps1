<#
.SYNOPSIS
  Finaliza um .docx gerado pelo build_doc.py: atualiza sumário e campos no Microsoft Word
  e, opcionalmente, exporta PDF (mesmo nome, extensão .pdf).

.EXAMPLE
  powershell -ExecutionPolicy Bypass -File scripts/finalizar_docx.ps1 "projeto/docs/DT_Cliente_v0.1.docx" -Pdf

.NOTES
  Requer Microsoft Word instalado. Sem Word, o documento continua válido e o sumário
  é atualizado ao abrir no Word (botão direito no sumário > Atualizar campo).
#>
param(
    [Parameter(Mandatory = $true)][string]$Docx,
    [switch]$Pdf
)
$ErrorActionPreference = 'Stop'
$caminho = (Resolve-Path $Docx).Path
$word = New-Object -ComObject Word.Application
$word.Visible = $false
$word.DisplayAlerts = 0
try {
    $d = $word.Documents.Open($caminho, $false, $false)
    foreach ($t in $d.TablesOfContents) { $t.Update() }
    $d.Fields.Update() | Out-Null
    $d.Save()
    if ($Pdf) {
        $pdfPath = [System.IO.Path]::ChangeExtension($caminho, '.pdf')
        $d.ExportAsFixedFormat($pdfPath, 17)
        Write-Output "PDF: $pdfPath"
    }
    Write-Output ("Sumário atualizado. Páginas: " + $d.ComputeStatistics(2))
    $d.Close($false)
}
finally {
    $word.Quit()
    [System.Runtime.InteropServices.Marshal]::ReleaseComObject($word) | Out-Null
}
