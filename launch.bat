@echo off
title Marketplace Deals Finder
cd /d "%~dp0"

set "STREAMLIT=%~dp0.venv\Scripts\streamlit.exe"
set "URL=http://localhost:8501"

if not exist "%STREAMLIT%" (
    echo Virtual environment not found. Run setup first:
    echo   python -m venv .venv
    echo   .venv\Scripts\pip install -r requirements.txt
    echo   .venv\Scripts\playwright install chromium
    pause
    exit /b 1
)

:: If Streamlit is already listening on 8501, just open the browser
powershell -NoProfile -Command "try { $c = New-Object Net.Sockets.TcpClient('127.0.0.1', 8501); $c.Close(); exit 0 } catch { exit 1 }"
if %ERRORLEVEL%==0 (
    start "" "%URL%"
    exit /b 0
)

echo Starting Marketplace Deals Finder...
start "Marketplace Deals Finder" "%STREAMLIT%" run app.py --server.headless true

:: Wait until the server is up (max ~30s), then open browser
powershell -NoProfile -Command ^
  "$url='http://localhost:8501'; for ($i=0; $i -lt 30; $i++) { try { $r = Invoke-WebRequest -Uri $url -UseBasicParsing -TimeoutSec 2; if ($r.StatusCode -eq 200) { exit 0 } } catch {} ; Start-Sleep -Seconds 1 }; exit 1"

start "" "%URL%"
