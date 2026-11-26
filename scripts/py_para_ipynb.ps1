# Converte um .py com marcadores "# %%" / "# %% [markdown]" em .ipynb (formato do Colab)
param([string]$entrada, [string]$saida)
$texto = [IO.File]::ReadAllText($entrada, [Text.Encoding]::UTF8)
$blocos = [regex]::Split($texto, '(?m)^# %%')
$cells = @()
foreach ($b in $blocos) {
    if (-not $b.Trim()) { continue }
    $md = $b.StartsWith(' [markdown]')
    $corpo = ($b -replace '^ \[markdown\]', '') -replace '^[^\n]*\n', ''
    $corpo = $corpo.TrimEnd()
    $linhas = @($corpo -split "`n")
    if ($md) { $linhas = @($linhas | ForEach-Object { $_ -replace '^# ?', '' }) }
    $src = @()
    for ($i = 0; $i -lt $linhas.Count; $i++) {
        $l = $linhas[$i].TrimEnd("`r")
        if ($i -lt $linhas.Count - 1) { $l += "`n" }
        $src += $l
    }
    if ($md) { $cells += [ordered]@{ cell_type = 'markdown'; metadata = @{}; source = $src } }
    else { $cells += [ordered]@{ cell_type = 'code'; metadata = @{}; execution_count = $null; outputs = @(); source = $src } }
}
$nb = [ordered]@{
    nbformat = 4; nbformat_minor = 0
    metadata = @{ colab = @{ provenance = @() }; kernelspec = @{ name = 'python3'; display_name = 'Python 3' }; language_info = @{ name = 'python' } }
    cells = $cells
}
$json = $nb | ConvertTo-Json -Depth 10
[IO.File]::WriteAllText($saida, $json, (New-Object Text.UTF8Encoding $false))
Write-Host "celulas: $($cells.Count)"
