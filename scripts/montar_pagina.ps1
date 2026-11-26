# Junta o template da página com o simulador.json gerado no Colab e grava o index.html na raiz do repositório
param([string]$json = (Join-Path (Split-Path -Parent $PSScriptRoot) 'dados\modelo\simulador.json'))
$raiz = Split-Path -Parent $PSScriptRoot
$tpl = [IO.File]::ReadAllText((Join-Path $PSScriptRoot 'simulador_template.html'), [Text.Encoding]::UTF8)
$dados = [IO.File]::ReadAllText($json, [Text.Encoding]::UTF8).Trim()
$html = $tpl.Replace('/*__DADOS__*/null', $dados)
[IO.File]::WriteAllText((Join-Path $raiz 'index.html'), $html, (New-Object Text.UTF8Encoding $false))
Write-Host "index.html pronto"
