# Smart Cabin v2 - copies the edge app (pi_edge) to the Pi and starts it.
#   .\deploy_to_pi.ps1                         the Pi at 192.168.137.207
#   .\deploy_to_pi.ps1 -Pi 192.168.137.50      another Pi
# The Pi's own files (data/: device key, registered person and face) are never overwritten.
# Needs key login and sudo without a password (pi board codes\setup_pi_key.ps1 and setup_pi_sudo.ps1, once).

param(
    [string]$Pi = "192.168.137.207",
    [string]$User = "pi"
)

$local = Join-Path $PSScriptRoot "pi_edge"
$target = "$User@$Pi"
$ssh = @("-o", "BatchMode=yes", "-o", "ConnectTimeout=8", "-o", "StrictHostKeyChecking=accept-new")

Write-Host "1. Can the laptop reach the Pi ($Pi)?"
ssh @ssh $target "true"
if ($LASTEXITCODE -ne 0) { Write-Host "   No. Is the Pi on and joined to the laptop's hotspot? Is key login set up?"; exit 1 }

Write-Host "2. Copying pi_edge to ~/v2/pi_edge ..."
ssh @ssh $target "rm -rf ~/v2/pi_edge/static ~/v2/pi_edge/pages; mkdir -p ~/v2/pi_edge/pages ~/v2/pi_edge/models"
scp @ssh -q (Get-ChildItem $local -Filter *.py | ForEach-Object { $_.FullName }) "${target}:v2/pi_edge/"
scp @ssh -q (Get-ChildItem (Join-Path $local "pages") -File | ForEach-Object { $_.FullName }) "${target}:v2/pi_edge/pages/"
if ($LASTEXITCODE -ne 0) { Write-Host "   Copy failed."; exit 1 }

Write-Host "3. Stopping what was running (old tests, old run) ..."
ssh @ssh $target "sudo -n true"
if ($LASTEXITCODE -ne 0) { Write-Host "   sudo asks for a password on the Pi: run setup_pi_sudo.ps1 once."; exit 1 }
ssh @ssh $target "sudo systemctl stop hwtest smartcabin 2>/dev/null; sudo systemctl reset-failed hwtest smartcabin 2>/dev/null; sudo pkill -f '[p]ython3 .*main' ; sleep 1"

Write-Host "4. Starting it (installs what is missing the first time; that can take a while) ..."
$start = "if [ -f /etc/systemd/system/smartcabin.service ]; then sudo systemctl restart smartcabin; " +
         "else sudo systemd-run --quiet --unit=smartcabin --working-directory=`$HOME/v2/pi_edge python3 -u `$HOME/v2/pi_edge/main.py; fi; " +
         "sleep 15; systemctl is-active --quiet smartcabin && echo RUNNING || echo STOPPED; sudo journalctl -u smartcabin -n 25 --no-pager -o cat"
ssh @ssh $target $start

Write-Host ""
Write-Host "Device page:  https://${Pi}:8000   (accept the certificate warning once)"
Write-Host "Its log:      ssh $target 'sudo journalctl -u smartcabin -f'"
Write-Host "Start at every boot (once):  ssh $target 'cd ~/v2/pi_edge && sudo python3 main.py --autostart'"
