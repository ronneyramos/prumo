@echo off
REM Backup do Prumo ERP: dois cliques neste arquivo. Resultado em backups\prumo_AAAA-MM-DD_HHMM.zip
cd /d "%~dp0"
set PYTHONIOENCODING=utf-8
".venv\Scripts\python.exe" scripts\backup_supabase.py %*
echo.
pause
