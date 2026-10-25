# Once: lets the laptop log in to the Pi without a password (needed by deploy_to_pi.ps1).
# It asks for the Pi's password one last time.
param([string]$Pi = "192.168.137.207", [string]$User = "pi")

$key = "$env:USERPROFILE\.ssh\id_ed25519.pub"
if (-not (Test-Path $key)) { ssh-keygen -t ed25519 -N '""' -C "smart-cabin-laptop" -f "$env:USERPROFILE\.ssh\id_ed25519" -q }
Write-Host "Type the Pi's password when asked:"
Get-Content $key | ssh -o StrictHostKeyChecking=accept-new "$User@$Pi" "mkdir -p ~/.ssh && chmod 700 ~/.ssh && cat >> ~/.ssh/authorized_keys && chmod 600 ~/.ssh/authorized_keys"
ssh -o BatchMode=yes "$User@$Pi" "echo Key login works."
