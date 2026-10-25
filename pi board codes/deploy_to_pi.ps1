# Copies code to the Pi and starts it, so its web page shows the latest version.
#
#   .\deploy_to_pi.ps1 -Folder "claude codes"                 copy claude codes to ~/claude, start main.py
#   .\deploy_to_pi.ps1 10_presence_confidence.py              copy the hardware tests to ~/hw, start that test
#   .\deploy_to_pi.ps1 -Folder "claude codes" -Pi 192.168.137.50
#
# Only one program runs at a time (they share the camera): the one running before is stopped first.
# Saved data on the Pi (data/, faces, devices, zones) is never overwritten.
# Needs key login and sudo without a password (setup_pi_key.ps1, setup_pi_sudo.ps1, once).

param(
    [string]$Script = "",
    [string]$Folder = "hardware test code",
    [string]$Pi = "192.168.137.207",
    [string]$User = "pi"
)

$remote = @{ "hardware test code" = "hw"; "claude codes" = "claude" }[$Folder]
if (-not $remote) { Write-Host "Unknown folder: $Folder"; exit 1 }
if (-not $Script) { $Script = "main.py" }
$local = Join-Path $PSScriptRoot $Folder
$target = "$User@$Pi"
$ssh = @("-o", "BatchMode=yes", "-o", "ConnectTimeout=8", "-o", "StrictHostKeyChecking=accept-new")

if (-not (Test-Path (Join-Path $local $Script))) { Write-Host "No such file: $Folder\$Script"; exit 1 }

Write-Host "1. Can the laptop reach the Pi ($Pi)?"
ssh @ssh $target "true"
if ($LASTEXITCODE -ne 0) { Write-Host "   No. Is the Pi on and joined to the laptop hotspot? Is key login set up?"; exit 1 }

Write-Host "2. Copying $Folder to ~/$remote ..."
ssh @ssh $target "mkdir -p ~/$remote/models"
$files = Get-ChildItem $local -File | Where-Object { $_.Extension -in ".py", ".md", ".html" } | ForEach-Object { $_.FullName }
scp @ssh -q $files "${target}:$remote/"
if ($LASTEXITCODE -ne 0) { Write-Host "   Copy failed."; exit 1 }
$model = Join-Path $local "models\yolov8n.onnx"
if (Test-Path $model) {                                     # 12 MB: only copied when the Pi doesn't have it
    ssh @ssh $target "test -f ~/$remote/models/yolov8n.onnx"
    if ($LASTEXITCODE -ne 0) { scp @ssh -q $model "${target}:$remote/models/" }
}
ssh @ssh $target "cp -n ~/hw/models/*.onnx ~/$remote/models/ 2>/dev/null; true"    # face models already on the Pi

Write-Host "3. Stopping what was running, starting $Script ..."
ssh @ssh $target "sudo -n true"
if ($LASTEXITCODE -ne 0) { Write-Host "   sudo asks for a password on the Pi: run setup_pi_sudo.ps1 once."; exit 1 }
# It runs as the systemd unit "hwtest": apart from this ssh session (so ssh closes at once), keeps running
# after it, and is easy to stop. [p]ython3 also stops a program started by hand.
ssh @ssh $target "sudo systemctl stop hwtest 2>/dev/null; sudo systemctl reset-failed hwtest 2>/dev/null; sudo pkill -f '[p]ython3 .*(hw/[0-9]+_|claude/main.py)'; sleep 1"
$start = "sudo systemd-run --quiet --unit=hwtest --working-directory=`$HOME/$remote python3 -u `$HOME/$remote/$Script && sleep 8; " +
         "systemctl is-active --quiet hwtest && echo RUNNING || echo STOPPED; sudo journalctl -u hwtest -n 15 --no-pager -o cat"
ssh @ssh $target $start

$port = (Select-String -Path (Join-Path $local "*.py") -Pattern '^PORT = (\d+)' | Select-Object -First 1).Matches.Groups[1].Value
if ($port) { Write-Host ""; Write-Host "Web page:  http://${Pi}:$port" }
