@echo off
pushd "%~dp0"

if not exist "%~dp0app.py" (
    echo.
    echo [Error] app.py ga mitsukarimasen.
    echo.
    echo -- Debug Info --
    echo kido.bat no basho: %~dp0
    echo ima no folder   : %CD%
    echo ----------------
    echo.
    echo Kono path wo screenshot shite okutte kudasai.
    echo.
    pause
    exit /b 1
)

set PYTHON_CMD=

where streamlit >nul 2>&1
if not errorlevel 1 (
    set PYTHON_CMD=streamlit
    goto :run
)

py -3.11 -c "import streamlit" >nul 2>&1
if not errorlevel 1 (
    set PYTHON_CMD=py -3.11 -m streamlit
    goto :run
)

python -c "import streamlit" >nul 2>&1
if not errorlevel 1 (
    set PYTHON_CMD=python -m streamlit
    goto :run
)

py -c "import streamlit" >nul 2>&1
if not errorlevel 1 (
    set PYTHON_CMD=py -m streamlit
    goto :run
)

echo.
echo [Error] Streamlit ga mitsukarimasen.
echo "shoki-setup.bat" wo saki ni jikko shite kudasai.
echo.
pause
exit /b 1

:run
set PORT=8502

:port_loop
netstat -ano | findstr ":%PORT% " >nul 2>&1
if not errorlevel 1 (
    set /a PORT+=1
    if %PORT% leq 8510 goto :port_loop
    set PORT=8502
)

title Form Auto-Sender (Port %PORT%)
echo ========================================
echo   Form Auto-Sender Starting... Port %PORT%
echo ========================================
echo.
timeout /t 2 /nobreak >nul
start http://localhost:%PORT%
echo Server starting...
echo Do not close this window.
echo.
%PYTHON_CMD% run "%~dp0app.py" --server.headless true --server.port %PORT%
popd
pause
