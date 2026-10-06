@echo off
rem ============================================================
rem  run.bat - sobe a Programacao Semanal para acesso local e
rem  pela rede local (celular, tablet, outro PC da obra).
rem
rem  Duplo clique, ou "run" no terminal. Sem argumentos.
rem      run              porta 4280
rem      run 8080         outra porta
rem
rem  Escrito em .bat, e nao em .ps1, de proposito: .bat abre com
rem  duplo clique em qualquer Windows, enquanto .ps1 esbarra na
rem  ExecutionPolicy e exige um comando antes de rodar.
rem
rem  Sem acentos neste arquivo: o console do Windows abre em
rem  codepage 850 e acento vira caractere quebrado no meio das
rem  instrucoes que a pessoa precisa ler.
rem ============================================================
setlocal EnableDelayedExpansion
cd /d "%~dp0"

set "PORTA=%~1"
if "%PORTA%"=="" set "PORTA=4280"

set "PY=api\.venv\Scripts\python.exe"

echo.
echo  ============================================================
echo   Programacao Semanal de Servicos - Timenow
echo  ============================================================
echo.

rem ---- 1. Ambiente Python ------------------------------------
rem O venv fica em api\.venv. Se nao existir, e criado na hora com
rem o Python do sistema - a primeira execucao numa maquina nova
rem leva um minuto, as seguintes sao imediatas.
if not exist "%PY%" (
    echo  [1/3] Ambiente Python nao encontrado. Criando...
    where py >nul 2>&1
    if errorlevel 1 (
        where python >nul 2>&1
        if errorlevel 1 (
            echo.
            echo  ERRO: Python nao esta instalado nesta maquina.
            echo  Baixe em https://www.python.org/downloads/
            echo  Marque "Add python.exe to PATH" durante a instalacao.
            echo.
            pause
            exit /b 1
        )
        python -m venv api\.venv
    ) else (
        py -3 -m venv api\.venv
    )
    if not exist "%PY%" (
        echo  ERRO: falha ao criar o ambiente em api\.venv
        pause
        exit /b 1
    )
    echo  [2/3] Instalando dependencias...
    "%PY%" -m pip install --upgrade pip --quiet
    "%PY%" -m pip install -r api\requirements.txt --quiet
    if errorlevel 1 (
        echo  ERRO: falha ao instalar as dependencias.
        pause
        exit /b 1
    )
) else (
    rem Ambiente existe, mas pode estar sem as dependencias - o
    rem caso de quem clonou o repo com a pasta .venv junto.
    "%PY%" -c "import jinja2, openpyxl" >nul 2>&1
    if errorlevel 1 (
        echo  [1/3] Instalando dependencias que faltam...
        "%PY%" -m pip install -r api\requirements.txt --quiet
    ) else (
        echo  [1/3] Ambiente Python pronto.
    )
)

rem ---- 2. Endereco na rede -----------------------------------
rem Pega o IPv4 da maquina para imprimir o endereco que os outros
rem aparelhos devem digitar. Ignora 127.x (loopback) e 169.254.x
rem (APIPA, que so aparece quando a rede nao entregou IP).
set "IP="
for /f "tokens=2 delims=:" %%A in ('ipconfig ^| findstr /c:"IPv4"') do (
    set "CANDIDATO=%%A"
    set "CANDIDATO=!CANDIDATO: =!"
    if "!IP!"=="" (
        echo !CANDIDATO! | findstr /b /c:"127." /c:"169.254." >nul || set "IP=!CANDIDATO!"
    )
)

echo  [2/3] Liberando a porta %PORTA% no Firewall do Windows...
rem Sem esta regra o servidor sobe, o proprio PC abre, e os outros
rem aparelhos dao "nao foi possivel conectar" - o firewall bloqueia
rem a conexao de fora antes de ela chegar no Python. Falha em
rem silencio quando o .bat roda sem privilegio de administrador:
rem nesse caso o acesso local continua funcionando e so o da rede
rem fica bloqueado, e o aviso abaixo explica o que fazer.
netsh advfirewall firewall show rule name="Programacao Semanal %PORTA%" >nul 2>&1
if errorlevel 1 (
    netsh advfirewall firewall add rule name="Programacao Semanal %PORTA%" ^
        dir=in action=allow protocol=TCP localport=%PORTA% >nul 2>&1
    if errorlevel 1 (
        echo        ^(sem permissao - o acesso pela rede pode ficar bloqueado^)
        echo        Para liberar: clique com o botao direito neste arquivo
        echo        e escolha "Executar como administrador", uma vez so.
    ) else (
        echo        Regra criada.
    )
) else (
    echo        Ja liberada.
)

rem ---- 3. Sobe o servidor ------------------------------------
echo  [3/3] Subindo o servidor...
echo.
echo  ------------------------------------------------------------
echo   Neste computador:  http://localhost:%PORTA%
if not "%IP%"=="" (
    echo   Na rede local:     http://%IP%:%PORTA%
    echo.
    echo   Abra o endereco "Na rede local" no celular ou em outro
    echo   PC, desde que estejam no MESMO Wi-Fi / mesma rede.
) else (
    echo   Na rede local:     nao foi possivel descobrir o IP.
    echo                      Rode "ipconfig" e use o IPv4 da sua rede.
)
echo  ------------------------------------------------------------
echo.
echo   Para parar o servidor: Ctrl+C, ou feche esta janela.
echo.

start "" "http://localhost:%PORTA%"
"%PY%" scripts\dev_local.py %PORTA% --rede

echo.
echo  Servidor encerrado.
pause
