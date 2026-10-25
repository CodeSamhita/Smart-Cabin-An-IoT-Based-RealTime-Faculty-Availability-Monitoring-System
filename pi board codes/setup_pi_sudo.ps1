# Once: lets user pi run sudo without a password (the Raspberry Pi OS default for the first user), so
# deploy_to_pi.ps1 can start tests with sudo. It asks for the Pi's password one last time.
param([string]$Pi = "192.168.137.207", [string]$User = "pi")

$rule = "/etc/sudoers.d/010_$User-nopasswd"
$cmd = "echo '$User ALL=(ALL) NOPASSWD: ALL' | sudo tee $rule.new > /dev/null && sudo chmod 440 $rule.new && " +
       "sudo visudo -cf $rule.new && sudo mv $rule.new $rule && echo 'sudo without a password: on'"
Write-Host "Type the Pi's password when asked:"
ssh -t "$User@$Pi" $cmd
ssh -o BatchMode=yes "$User@$Pi" "sudo -n true && echo Checked: works."
