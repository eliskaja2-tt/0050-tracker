@echo off
chcp 65001 >nul
cd /d "%~dp0"
where python >nul 2>nul
if %errorlevel%==0 (
  python update_data.py
) else (
  py update_data.py
)
if %errorlevel%==0 (
  start "" "%~dp0index.html"
) else (
  echo.
  echo Update failed. Please check the message above.
  pause
)
