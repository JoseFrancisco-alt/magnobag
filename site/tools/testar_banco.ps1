# Abre o teste da senha do banco e repete até funcionar.
Set-Location (Split-Path (Split-Path $PSScriptRoot))
$Host.UI.RawUI.WindowTitle = "Testar senha do banco - Magnobag"
while ($true) {
    python site/tools/testar_banco.py
    if ($LASTEXITCODE -eq 0) { break }
    Write-Host ""
    Read-Host "Aperte Enter para tentar de novo"
    Write-Host ""
}
Write-Host ""
Read-Host "Pode fechar esta janela (Enter)"
