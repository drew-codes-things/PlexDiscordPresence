$ErrorActionPreference = "Stop"

$Root = Resolve-Path "$PSScriptRoot/../.."
$Version = (Get-Content "$Root/VERSION").Trim()

pyinstaller --onefile --name PlexDiscordPresence `
  --distpath "$Root/dist" --workpath "$Root/build" --specpath "$Root/build" `
  "$Root/main.py"

$Renamed = "$Root/dist/PlexDiscordPresence-$Version-windows-x86_64.exe"
Move-Item -Force "$Root/dist/PlexDiscordPresence.exe" $Renamed
Write-Host "Built: $Renamed"
