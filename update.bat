@echo off
chcp 65001 >nul
set "PYTHONIOENCODING=utf-8"
cd /d "%~dp0"
call config.cmd
call :main > update_log.txt 2>&1
type update_log.txt
echo.
echo (log saved to update_log.txt)
pause
exit /b

:main
echo ===== RUN %date% %time% =====
python build_data.py
if errorlevel 1 (
    echo ERROR: build_data.py failed
    exit /b 1
)
git rm --cached config.cmd >nul 2>nul
git add -A
git commit -m "spec data update"
if errorlevel 1 echo (nothing changed - continuing)
git push
if errorlevel 1 (
    echo ERROR: git push failed
    exit /b 1
)
echo.
echo DONE - the app will show the new version in about 1 minute
echo SITE - https://%GH_USER%.github.io/%GH_REPO%/
exit /b 0
