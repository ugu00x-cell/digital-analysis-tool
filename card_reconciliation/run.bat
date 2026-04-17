@echo off
REM ================================================================
REM Card Reconciliation Tool (Windows launcher)
REM
REM Usage:
REM   1. Put bakuraku_*.csv and orders_*.csv into input\
REM   2. Double-click this file
REM   3. Output is written to output\xxx.csv
REM
REM You can also pass args:
REM   run.bat --bakuraku path\to\b.csv --orders path\to\o.csv
REM ================================================================

REM Set UTF-8 codepage so Python emoji/JP output is not garbled
chcp 65001 > nul

REM Move to project root (one level up from this .bat)
cd /d "%~dp0.."

REM Prefer the py launcher, fall back to python on PATH
where py >nul 2>&1
if %errorlevel% equ 0 (
    py -m card_reconciliation %*
) else (
    python -m card_reconciliation %*
)

set RC=%errorlevel%
echo.
if %RC% neq 0 (
    echo [Error exit code: %RC%]
    pause
) else (
    echo Done. Press any key to close...
    pause > nul
)

exit /b %RC%
