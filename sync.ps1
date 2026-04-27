# Senhuang Linebot Synchronization Script
# Source: z:\Senhuang_linebot
# Destination: C:\Users\Administrator\Desktop\Github\Senhuang_linebot

$source = "z:\Senhuang_linebot"
$dest = "C:\Users\Administrator\Desktop\Github\Senhuang_linebot2\Senhuang_linebot"

Write-Host "Syncing files from $source to $dest..."

# Using robocopy for efficient mirroring
# /MIR: Mirrors a directory tree
# /XD: Excludes directories (venv, .git, .gemini)
# /R:0: Number of retries on failed copies
# /W:0: Wait time between retries
robocopy $source $dest /MIR /XD venv .git .gemini /NFL /NDL /NJH /NJS /nc /ns /np /R:0 /W:0

Write-Host "Synchronization complete."
