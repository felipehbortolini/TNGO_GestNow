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

rem ── Postgres instalado e rodando ────────────────────────────────────────
powershell -NoProfile -ExecutionPolicy Bypass -Command "$s = Get-Service -Name 'postgresql*' -ErrorAction SilentlyContinue; if (-not $s) { exit 2 }; if ($s | Where-Object { $_.Status -eq 'Running' }) { exit 0 }; exit 1"
if errorlevel 2 goto sem_postgres
if errorlevel 1 goto postgres_parado

rem ── URL de administracao do dono ────────────────────────────────────────
if not defined GESTNOW_PG_ADMIN_URL goto sem_admin_url

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

"%PY%" -c "import azure.functions, jinja2, sqlalchemy, alembic, psycopg" >nul 2>&1
if errorlevel 1 (
    echo  Instalando dependencias da API...
    "%PY%" -m pip install -r api\requirements.txt --quiet
    if errorlevel 1 (
        echo  ERRO: falha ao instalar as dependencias da API.
        pause
        exit /b 1
    )
)

rem ── Banco: papel, bancos gestnow e gestnow_teste, configuracao e migracoes ──
"%PY%" scripts\prepare_database.py
if errorlevel 1 (
    echo.
    echo  ERRO: nao foi possivel preparar o banco. Veja a mensagem acima.
    pause
    exit /b 1
)

rem ── Carga do modo configurado: demonstracao deslocada para hoje ou producao ──
"%PY%" scripts\seed_database.py
if errorlevel 1 (
    echo.
    echo  ERRO: nao foi possivel aplicar a carga. Veja a mensagem acima.
    pause
    exit /b 1
)

echo.
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

:sem_postgres
echo  ERRO: o servico do PostgreSQL nao foi encontrado.
echo  Instale o PostgreSQL pelo instalador oficial do Windows:
echo    https://www.postgresql.org/download/windows/
echo  Mantenha a porta 5432 e o servico automatico, e rode o run.bat de novo.
echo.
pause
exit /b 1

:postgres_parado
echo  ERRO: o servico do PostgreSQL nao esta rodando.
echo  Abra services.msc, ache o servico "postgresql..." e clique em Iniciar.
echo  Pelo prompt (como administrador): net start NOME_DO_SERVICO
echo  Depois rode o run.bat de novo.
echo.
pause
exit /b 1

:sem_admin_url
echo  ERRO: a variavel GESTNOW_PG_ADMIN_URL nao esta definida.
echo  Ela e a URL de administracao do Postgres, criada uma vez como variavel de usuario:
echo    postgresql://postgres:SUA_SENHA@localhost:5432/postgres
echo  O passo a passo esta em docs\issues\spec-migracao-gestnow\PROMPT-EXECUCAO.md (item 2).
echo  Depois de criar, feche e reabra o prompt e rode o run.bat de novo.
echo.
pause
exit /b 1
