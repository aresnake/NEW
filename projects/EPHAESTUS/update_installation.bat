@echo off
echo ========================================
echo   Mise a jour Hephaestus
echo ========================================
echo.
echo Fermeture de Claude Desktop en cours...
taskkill /F /IM "Claude.exe" 2>nul
timeout /t 2 /nobreak >nul

echo.
echo Reinstallation de Hephaestus...
python -m pip install -e . --force-reinstall --no-deps

echo.
echo ========================================
echo   Installation terminee !
echo ========================================
echo.
echo Les changements appliques :
echo - Bug bpy.app.timers.time() corrige dans l'addon Blender
echo - Timeout de connexion augmente de 30s a 60s
echo - Configuration MCP ajoutee pour Claude Code
echo.
echo Vous pouvez maintenant relancer Claude Desktop
echo.
pause
