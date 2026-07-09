@echo off
cd /d "%~dp0"

echo ============================================
echo  Prumo ERP - Iniciando servidor de producao
echo ============================================
echo.

REM --- Mata qualquer instancia anterior na porta 8521 ---
echo [1/3] Parando instancia anterior (se houver)...
for /f "tokens=5" %%a in ('netstat -ano ^| findstr :8521') do (
    if not "%%a"=="" (
        taskkill /f /pid %%a >nul 2>&1
    )
)

REM --- Ativa venv se existir ---
if exist ..\venv\Scripts\activate.bat (
    call ..\venv\Scripts\activate.bat
)

echo [2/3] Iniciando Streamlit em http://0.0.0.0:8521 ...
echo.
echo     Acessar de OUTRA maquina na rede pelo IP desta maquina:
echo     http://IP_DESTA_MAQUINA:8521
echo.
echo     Exemplo: http://192.168.1.100:8521
echo.
echo     Para descobrir seu IP: ipconfig ^| findstr IPv4
echo.
echo [3/3] Pressione CTRL+C para parar o servidor.
echo ============================================
echo.

streamlit run main.py --server.address 0.0.0.0 --server.port 8521

pause
