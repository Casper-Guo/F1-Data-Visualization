wsl.exe chmod +x /mnt/d/Projects/F1-Visualization/data-refresh.sh
wsl.exe chmod +x /mnt/d/Projects/F1-Visualization/auto-push.exp
wsl.exe /mnt/d/Projects/F1-Visualization/data-refresh.sh
start Notepad "ETL.log"
timeout 60
