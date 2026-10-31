@echo off
rem MCSerDeLuz - Buscar tinta en el papiro (sin IA). Lanza buscar_tinta_papiro.py con Python.
rem Puedes pasarle opciones, por ejemplo:  buscar_tinta_papiro.bat --barrido
chcp 65001 >nul
cd /d "%~dp0"
set "SCRIPT=%~dp0buscar_tinta_papiro.py"
if not exist "%SCRIPT%" (
  echo No encuentro buscar_tinta_papiro.py junto a este archivo .bat.
  goto fin
)
where py >nul 2>nul
if %errorlevel%==0 (
  py -3 "%SCRIPT%" %*
  goto fin
)
python --version >nul 2>nul
if %errorlevel%==0 (
  python "%SCRIPT%" %*
  goto fin
)
echo.
echo ======================================================================
echo  No encuentro Python en este ordenador.
echo.
echo  Opcion facil: usa MCSerDeLuz-buscar-tinta-papiro.exe (no necesita nada).
echo.
echo  O instala Python 3.12 abriendo PowerShell y escribiendo:
echo      winget install Python.Python.3.12
echo  (o descargalo de https://www.python.org/downloads/ y marca "Add python.exe to PATH")
echo  Despues cierra y abre PowerShell y escribe:
echo      py -m pip install numpy zarr tifffile matplotlib scipy
echo  Mas detalles en MCSerDeLuz-instrucciones-buscar-tinta.txt
echo ======================================================================
:fin
echo.
pause
