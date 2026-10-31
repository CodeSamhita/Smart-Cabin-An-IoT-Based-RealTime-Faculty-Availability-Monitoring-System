# Smart Cabin v3 - copies the edge app (pi_edge) to the Pi and starts it.
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

Write-Host "2. Copying pi_edge to ~/smartcabin_v3 ..."
ssh @ssh $target "rm -rf ~/smartcabin_v3/static ~/smartcabin_v3/pages; mkdir -p ~/smartcabin_v3/pages ~/smartcabin_v3/models"
scp @ssh -q (Get-ChildItem $local -Filter *.py | ForEach-Object { $_.FullName }) "${target}:smartcabin_v3/"
scp @ssh -q (Get-ChildItem (Join-Path $local "pages") -File | ForEach-Object { $_.FullName }) "${target}:smartcabin_v3/pages/"
if ($LASTEXITCODE -ne 0) { Write-Host "   Copy failed."; exit 1 }

Write-Host "3. Stopping what was running (old tests, old run) ..."
ssh @ssh $target "sudo -n true"
if ($LASTEXITCODE -ne 0) { Write-Host "   sudo asks for a password on the Pi: run setup_pi_sudo.ps1 once."; exit 1 }
ssh @ssh $target "sudo systemctl stop hwtest smartcabin 2>/dev/null; sudo systemctl reset-failed hwtest smartcabin 2>/dev/null; sudo pkill -f '[p]ython3 .*main' ; sleep 1"

Write-Host "4. Starting it (installs what is missing the first time; that can take a while) ..."
# A service left from an older version (e.g. ~/smartcabin_v2) is pointed at this folder first
$start = "if [ -f /etc/systemd/system/smartcabin.service ] && ! grep -q smartcabin_v3 /etc/systemd/system/smartcabin.service; then " +
         "cd ~/smartcabin_v3 && sudo python3 main.py --autostart; fi; " +
         "if [ -f /etc/systemd/system/smartcabin-blackbox.service ]; then sudo systemctl restart smartcabin-blackbox; fi; " +
         "if [ -f /etc/systemd/system/smartcabin.service ]; then sudo systemctl restart smartcabin; " +
         "else sudo systemd-run --quiet --unit=smartcabin --working-directory=`$HOME/smartcabin_v3 python3 -u `$HOME/smartcabin_v3/main.py; fi; " +
         "sleep 15; systemctl is-active --quiet smartcabin && echo RUNNING || echo STOPPED; sudo journalctl -u smartcabin -n 25 --no-pager -o cat"
ssh @ssh $target $start

Write-Host ""
Write-Host "Device page:  https://${Pi}:8000   (accept the certificate warning once)"
Write-Host "Its log:      ssh $target 'sudo journalctl -u smartcabin -f'"
Write-Host "Start at every boot (once):  ssh $target 'cd ~/smartcabin_v3 && sudo python3 main.py --autostart'"
