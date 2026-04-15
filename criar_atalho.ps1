$desktop = [Environment]::GetFolderPath('Desktop')
$WshShell = New-Object -ComObject WScript.Shell
$Shortcut = $WshShell.CreateShortcut("$desktop\Relivia Modelar.lnk")
$Shortcut.TargetPath = 'C:\projetos\relivia-modelar\start.bat'
$Shortcut.WorkingDirectory = 'C:\projetos\relivia-modelar'
$Shortcut.Description = 'Iniciar Relivia Modelar'
$Shortcut.IconLocation = 'C:\Windows\System32\SHELL32.dll,14'
$Shortcut.Save()
Write-Host "Atalho criado em: $desktop\Relivia Modelar.lnk"
