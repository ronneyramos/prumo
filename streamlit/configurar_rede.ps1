# ─────────────────────────────────────────────────────
# Prumo ERP — Configuração de Rede para testes internos
# Executar como ADMINISTRADOR uma única vez
# ─────────────────────────────────────────────────────

Write-Host "================================" -ForegroundColor Cyan
Write-Host " Prumo ERP - Configuracao de Rede" -ForegroundColor Cyan
Write-Host "================================" -ForegroundColor Cyan
Write-Host ""

$ip = (Get-NetIPAddress -AddressFamily IPv4 | Where-Object { $_.InterfaceAlias -ne "Loopback*" -and $_.PrefixOrigin -ne "Duplicate" }).IPAddress | Select-Object -First 1
$hostname = [System.Net.Dns]::GetHostName()

Write-Host "Maquina.: $hostname" -ForegroundColor Yellow
Write-Host "IP......: $ip" -ForegroundColor Yellow
Write-Host ""

# ── 1. Firewall ──
Write-Host "[1/4] Liberando porta 8521 no Firewall..." -ForegroundColor Green
New-NetFirewallRule -DisplayName "Prumo ERP 8521" -Direction Inbound -LocalPort 8521 -Protocol TCP -Action Allow -ErrorAction SilentlyContinue 2>$null
New-NetFirewallRule -DisplayName "Prumo ERP 80 (proxy)" -Direction Inbound -LocalPort 80 -Protocol TCP -Action Allow -ErrorAction SilentlyContinue 2>$null
Write-Host "  OK" -ForegroundColor Green

# ── 2. Portproxy 80 → 8521 (URL sem porta) ──
Write-Host "[2/4] Configurando proxy de porta 80 -> 8521..." -ForegroundColor Green
netsh interface portproxy delete v4tov4 listenport=80 listenaddress=0.0.0.0 2>$null
netsh interface portproxy add v4tov4 listenport=80 listenaddress=0.0.0.0 connectport=8521 connectaddress=127.0.0.1
Write-Host "  OK" -ForegroundColor Green

# ── 3. Hosts file (prumoerp -> 127.0.0.1 para acesso local) ──
Write-Host "[3/4] Adicionando entrada no hosts file..." -ForegroundColor Green
$hosts = "$env:SystemRoot\System32\drivers\etc\hosts"
$entry = "127.0.0.1 prumoerp"
if (Select-String -Path $hosts -Pattern $entry -SimpleMatch -Quiet) {
    Write-Host "  Entrada ja existe" -ForegroundColor Yellow
} else {
    Add-Content -Path $hosts -Value "`n$entry"
    Write-Host "  OK" -ForegroundColor Green
}

# ── 4. Mostrar URLs de acesso ──
Write-Host "[4/4] URLs de acesso:" -ForegroundColor Green
Write-Host ""
Write-Host "  ┌─────────────────────────────────────────────────────┐" -ForegroundColor White
Write-Host "  │  ACESSO LOCAL (nesta maquina)                       │" -ForegroundColor White
Write-Host "  │   http://prumoerp                                   │" -ForegroundColor Cyan
Write-Host "  │   http://localhost                                  │" -ForegroundColor Cyan
Write-Host "  │   http://127.0.0.1                                  │" -ForegroundColor Cyan
Write-Host "  ├─────────────────────────────────────────────────────┤" -ForegroundColor White
Write-Host "  │  ACESSO REMOTO (clientes na rede)                   │" -ForegroundColor White
Write-Host "  │   http://$ip                                        │" -ForegroundColor Cyan
Write-Host "  │   http://$hostname                                  │" -ForegroundColor Cyan
Write-Host "  ├─────────────────────────────────────────────────────┤" -ForegroundColor White
Write-Host "  │  COMO ACESSAR DE OUTRO PC:                          │" -ForegroundColor White
Write-Host "  │   Abra o navegador e digite o IP ou hostname acima  │" -ForegroundColor White
Write-Host "  └─────────────────────────────────────────────────────┘" -ForegroundColor White
Write-Host ""
Write-Host "  Para usar o nome 'prumoerp' nos clientes:" -ForegroundColor Yellow
Write-Host "  1. Abra Bloco de Notas como ADMINISTRADOR" -ForegroundColor Yellow
Write-Host "  2. Abra C:\Windows\System32\drivers\etc\hosts" -ForegroundColor Yellow
Write-Host "  3. Adicione a linha: $ip prumoerp" -ForegroundColor Yellow
Write-Host "  4. Salve e acesse http://prumoerp" -ForegroundColor Yellow
Write-Host ""
Write-Host "================================" -ForegroundColor Cyan
Write-Host " Configuracao concluida!" -ForegroundColor Green
Write-Host " Execute run_producao.bat para iniciar o servidor" -ForegroundColor Green
Write-Host "================================" -ForegroundColor Cyan

pause
