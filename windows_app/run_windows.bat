@echo off
setlocal
cd /d "%~dp0"

echo [MY_APP] Starte Windows-Version...

where py >nul 2>nul
if errorlevel 1 (
  echo [FEHLER] Python Launcher "py" wurde nicht gefunden.
  echo Installiere Python von https://www.python.org/downloads/windows/
  echo und aktiviere "Add python.exe to PATH" waehrend der Installation.
  pause
  exit /b 1
)

echo [MY_APP] Installiere/aktualisiere Abhaengigkeiten...
py -m pip install -r requirements.txt
if errorlevel 1 (
  echo [FEHLER] Paketinstallation fehlgeschlagen.
  pause
  exit /b 1
)

echo [MY_APP] Starte Streamlit unter http://localhost:8501 ...
py -m streamlit run app.py
if errorlevel 1 (
  echo [FEHLER] Streamlit konnte nicht gestartet werden.
  pause
  exit /b 1
)
