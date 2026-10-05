@echo off
setlocal
cd /d "%~dp0"

set "PORTA=%~1"
if "%PORTA%"=="" set "PORTA=4280"
set "PY=api\.venv\Scripts\python.exe"

echo.
echo  ============================================================
echo   Timenow GestNow - servidor local
echo  ============================================================
echo.

if not exist "%PY%" (
    echo  Criando o ambiente Python 3.13 em api\.venv...
    where py >nul 2>&1
    if errorlevel 1 (
        where python >nul 2>&1
        if errorlevel 1 (
            echo.
            echo  ERRO: Python 3.13 ou superior nao foi encontrado.
            echo  Instale Python e marque "Add python.exe to PATH".
            echo.
            pause
            exit /b 1
        )
        python -c "import sys; raise SystemExit(sys.version_info < (3, 13))" >nul 2>&1
        if errorlevel 1 (
            echo  ERRO: e necessario Python 3.13 ou superior.
            pause
            exit /b 1
        )
        python -m venv api\.venv
    ) else (
        py -3.13 -m venv api\.venv
    )
    if not exist "%PY%" (
        echo  ERRO: nao foi possivel criar api\.venv com Python 3.13.
        pause
        exit /b 1
    )
)

"%PY%" -c "import sys; raise SystemExit(sys.version_info < (3, 13))" >nul 2>&1
if errorlevel 1 (
    echo  ERRO: api\.venv precisa usar Python 3.13 ou superior.
    pause
    exit /b 1
)

"%PY%" -c "import azure.functions, jinja2" >nul 2>&1
if errorlevel 1 (
    echo  Instalando dependencias da API...
    "%PY%" -m pip install -r api\requirements.txt --quiet
    if errorlevel 1 (
        echo  ERRO: falha ao instalar as dependencias da API.
        pause
        exit /b 1
    )
)

echo  Abrindo http://localhost:%PORTA%
echo  O servidor local nao exige Azure Functions Core Tools.
echo  Para parar, pressione Ctrl+C.
echo.

netstat -ano | findstr /c:":%PORTA% " | findstr /c:"LISTENING" >nul
if not errorlevel 1 (
    echo  ERRO: a porta %PORTA% ja esta em uso.
    pause
    exit /b 1
)

start "" /b "%PY%" scripts\dev_local.py %PORTA%
set "TENTATIVAS=0"

:aguardar_servidor
netstat -ano | findstr /c:":%PORTA% " | findstr /c:"LISTENING" >nul
if not errorlevel 1 goto abrir_navegador
set /a TENTATIVAS+=1
if %TENTATIVAS% GEQ 20 goto erro_servidor
ping -n 2 127.0.0.1 >nul
goto aguardar_servidor

:abrir_navegador
start "" "http://localhost:%PORTA%"
echo  Servidor iniciado. Para parar, pressione Ctrl+C.

:monitorar_servidor
netstat -ano | findstr /c:":%PORTA% " | findstr /c:"LISTENING" >nul
if errorlevel 1 goto servidor_encerrado
ping -n 2 127.0.0.1 >nul
goto monitorar_servidor

:servidor_encerrado
echo  Servidor encerrado.
exit /b 0

:erro_servidor
echo  ERRO: o servidor nao iniciou na porta %PORTA%.
pause
exit /b 1
