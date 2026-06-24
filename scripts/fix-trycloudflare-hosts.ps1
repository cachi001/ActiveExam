# fix-trycloudflare-hosts.ps1
# Agrega (idempotente) una entrada en el archivo hosts para que cloudflared
# pueda resolver api.trycloudflare.com cuando el DNS de la red lo filtra.
# El edge (argotunnel.com) ya resuelve; solo falta el endpoint de registro.
# Revertir: borrar la linea que contiene "api.trycloudflare.com" del hosts.

$hosts = "$env:windir\System32\drivers\etc\hosts"
$entry = "104.16.230.132 api.trycloudflare.com"

$content = Get-Content -Path $hosts -ErrorAction SilentlyContinue
if ($content -match "api\.trycloudflare\.com") {
    Write-Host "Ya existe una entrada para api.trycloudflare.com en hosts. Nada que hacer." -ForegroundColor Yellow
} else {
    Add-Content -Path $hosts -Value "`n$entry"
    Write-Host "Entrada agregada: $entry" -ForegroundColor Green
}

# Verificacion
Write-Host "`nVerificando resolucion..." -ForegroundColor Cyan
Resolve-DnsName api.trycloudflare.com -ErrorAction SilentlyContinue | Select-Object Name, IPAddress | Format-Table -AutoSize
Write-Host "Listo. Volve a la sesion de Claude y avisa para levantar el tunel." -ForegroundColor Green
