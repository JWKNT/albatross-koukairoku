@echo off
setlocal
cd /d "%~dp0"
where py >nul 2>nul
if not errorlevel 1 (
  py -3 install_albatross_patch.py %*
) else (
  python install_albatross_patch.py %*
)
set STATUS=%ERRORLEVEL%
echo.
if %STATUS% EQU 0 (
  echo Finished.
) else (
  echo The patch was not installed. Review the error above.
)
pause
exit /b %STATUS%
