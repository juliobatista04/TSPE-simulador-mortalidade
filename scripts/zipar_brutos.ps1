# Zipa dados\brutos em brutos.zip com caminhos no formato do Linux (estado/x.csv), pra abrir certo no Colab
Add-Type -AssemblyName System.IO.Compression, System.IO.Compression.FileSystem
$raiz = Split-Path -Parent $PSScriptRoot
$origem = Join-Path $raiz 'dados\brutos'
$destino = Join-Path $raiz 'brutos.zip'
if (Test-Path $destino) { Remove-Item $destino }
$zip = [IO.Compression.ZipFile]::Open($destino, 'Create')
Get-ChildItem $origem -Recurse -File | ForEach-Object {
    $rel = $_.FullName.Substring($origem.Length + 1) -replace '\\', '/'
    [IO.Compression.ZipFileExtensions]::CreateEntryFromFile($zip, $_.FullName, $rel) | Out-Null
}
$zip.Dispose()
Write-Host "zip: $destino"
