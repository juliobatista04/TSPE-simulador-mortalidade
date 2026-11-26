# Baixa as tabelas do TABNET (SIH/SUS, internações por local de internação, Pernambuco)
# Período: out/2025 a set/2026 (12 últimos meses disponíveis no TABNET em nov/2026)
# Uso: powershell -File scripts\baixar_tabnet.ps1
# Saída: dados\brutos\estado\*.csv e dados\brutos\hospitais\*.csv  (separador ;  codificação UTF-8)

$ErrorActionPreference = 'Stop'
Add-Type -AssemblyName System.Web
$lat  = [Text.Encoding]::GetEncoding('iso-8859-1')
$raiz = Split-Path -Parent $PSScriptRoot
$url  = 'https://tabnet.datasus.gov.br/cgi/tabcgi.exe?sih/cnv/nipe.def'
$meses = '2510','2511','2512','2601','2602','2603','2604','2605','2606','2607','2608','2609'

function Enc($s) { [Web.HttpUtility]::UrlEncode($s, $lat) }

function Get-Tabela {
    param($linha, $coluna, $incremento, $saida, $filtros = @{})
    $destino = Join-Path $raiz "dados\brutos\$saida"
    if (Test-Path $destino) { Write-Host "ja existe: $saida"; return }
    $partes = @("Linha=$(Enc $linha)", "Coluna=$(Enc $coluna)", "Incremento=$(Enc $incremento)")
    foreach ($m in $meses) { $partes += "Arquivos=nipe$m.dbf" }
    foreach ($k in $filtros.Keys) { $partes += "$(Enc $k)=$(Enc $filtros[$k])" }
    $partes += 'formato=prn', 'mostre=Mostra'
    $body = $partes -join '&'
    for ($t = 1; $t -le 4; $t++) {
        try {
            $r = Invoke-WebRequest -Uri $url -Method Post -Body $body -ContentType 'application/x-www-form-urlencoded' -UseBasicParsing -TimeoutSec 180
            $html = $lat.GetString($r.RawContentStream.ToArray())
            $ini = $html.IndexOf('<PRE>'); $fim = $html.IndexOf('</PRE>')
            if ($ini -lt 0) { throw "resposta sem tabela" }
            $txt = [Web.HttpUtility]::HtmlDecode($html.Substring($ini + 5, $fim - $ini - 5)).Trim()
            New-Item -ItemType Directory -Force (Split-Path $destino) | Out-Null
            [IO.File]::WriteAllText($destino, $txt, (New-Object Text.UTF8Encoding $false))
            Write-Host "ok: $saida ($(( $txt -split "`n").Count) linhas)"
            Start-Sleep -Milliseconds 800
            return
        } catch {
            Write-Host "tentativa $t falhou em $saida : $_"
            Start-Sleep -Seconds (3 * $t)
        }
    }
    throw "nao consegui baixar $saida"
}

$metricas = @{ 'internacoes' = 'Internações'; 'obitos' = 'Óbitos'; 'dias' = 'Dias_permanência' }

# ---------- Visão do estado ----------
foreach ($m in $metricas.Keys) {
    Get-Tabela 'Capítulo_CID-10' 'Faixa_Etária_1' $metricas[$m] "estado\capitulo_x_faixa_$m.csv"
    Get-Tabela 'Lista_Morb__CID-10' 'Faixa_Etária_1' $metricas[$m] "estado\doenca_x_faixa_$m.csv"
    Get-Tabela 'Ano/mês_processamento' 'Capítulo_CID-10' $metricas[$m] "estado\mes_x_capitulo_$m.csv"
}
Get-Tabela 'Capítulo_CID-10' 'Faixa_Etária_1' 'Taxa_mortalidade' 'estado\capitulo_x_faixa_taxa_mortalidade.csv'
Get-Tabela 'Capítulo_CID-10' 'Faixa_Etária_1' 'Média_permanência' 'estado\capitulo_x_faixa_media_permanencia.csv'
Get-Tabela 'Lista_Morb__CID-10' 'Capítulo_CID-10' 'Internações' 'estado\doenca_x_capitulo_internacoes.csv'

# ---------- Visão por hospital (estabelecimento) ----------
foreach ($m in $metricas.Keys) {
    Get-Tabela 'Estabelecimento' 'Capítulo_CID-10' $metricas[$m] "hospitais\hospital_x_capitulo_$m.csv"
    Get-Tabela 'Estabelecimento' 'Faixa_Etária_1' $metricas[$m] "hospitais\hospital_x_faixa_$m.csv"
}
Get-Tabela 'Estabelecimento' 'Região_de_Saúde_(CIR)' 'Internações' 'hospitais\hospital_x_regiao_saude.csv'
Get-Tabela 'Estabelecimento' 'Macrorregião_de_Saúde' 'Internações' 'hospitais\hospital_x_macrorregiao.csv'
Get-Tabela 'Estabelecimento' 'Microrregião_IBGE' 'Internações' 'hospitais\hospital_x_microrregiao.csv'
Get-Tabela 'Estabelecimento' 'Caráter_atendimento' 'Internações' 'hospitais\hospital_x_carater.csv'

# Hospital x capítulo, separado por faixa etária (é o cruzamento que o simulador usa)
$faixas = @{ 1='menor1'; 2='1a4'; 3='5a9'; 4='10a14'; 5='15a19'; 6='20a29'; 7='30a39'; 8='40a49'; 9='50a59'; 10='60a69'; 11='70a79'; 12='80mais' }
foreach ($f in ($faixas.Keys | Sort-Object)) {
    $nome = '{0:D2}_{1}' -f $f, $faixas[$f]
    foreach ($m in $metricas.Keys) {
        Get-Tabela 'Estabelecimento' 'Capítulo_CID-10' $metricas[$m] "hospitais\por_faixa\hospital_x_capitulo_${m}_faixa$nome.csv" @{ 'SFaixa_Etária_1' = "$f" }
    }
}
Write-Host 'fim'
