@echo off
rem ============================================================================
rem  HERMES - uruchamianie demonstratora (Windows 10 i 11)
rem  Automatycznie: znajduje lub instaluje Pythona 3.10+, tworzy srodowisko .venv,
rem  instaluje biblioteki z requirements.txt, tworzy plik .env, uruchamia serwer
rem  i otwiera przegladarke.
rem  Uzycie:  start.bat              - instalacja (jesli trzeba) i uruchomienie
rem           start.bat --sprawdz    - tylko instalacja i sprawdzenie, bez uruchamiania
rem ============================================================================
setlocal EnableExtensions
title HERMES - demonstrator
cd /d "%~dp0"

echo.
echo  ==========================================================
echo   HERMES - Hazard Evacuation, Response and Mesh Embedded System
echo  ==========================================================
echo.

rem ---------------------------------------------------------------- 1. Python
call :znajdz_python
if defined PYEXE goto :python_ok
call :instaluj_python
call :znajdz_python
if defined PYEXE goto :python_ok
echo.
echo [BLAD] Nie udalo sie automatycznie zainstalowac Pythona.
echo        Zainstaluj Pythona 3.12 ze strony https://www.python.org/downloads/
echo        - w instalatorze zaznacz "Add python.exe to PATH" -
echo        a potem uruchom start.bat ponownie.
goto :blad

:python_ok
echo [OK] Python: %PYEXE%

rem ---------------------------------------------------------------- 2. srodowisko .venv
set "VPY=%CD%\.venv\Scripts\python.exe"
if not exist "%VPY%" goto :tworz_venv
"%VPY%" -c "import sys; sys.exit(0 if sys.version_info >= (3, 10) else 1)" >nul 2>&1
if not errorlevel 1 goto :venv_ok
echo [..] Srodowisko .venv jest uszkodzone albo skopiowane z innego komputera - tworze je od nowa...
rmdir /s /q ".venv"

:tworz_venv
echo [..] Tworze srodowisko wirtualne .venv...
"%PYEXE%" -m venv ".venv"
if errorlevel 1 goto :blad_venv
if not exist "%VPY%" goto :blad_venv

:venv_ok
echo [OK] Srodowisko .venv gotowe

rem ---------------------------------------------------------------- 3. biblioteki
fc /b "requirements.txt" ".venv\hermes-requirements.txt" >nul 2>&1
if errorlevel 1 goto :instaluj_pakiety
"%VPY%" -c "import fastapi, uvicorn, cv2, dotenv, jinja2, requests" >nul 2>&1
if not errorlevel 1 goto :pakiety_ok

:instaluj_pakiety
echo [..] Instaluje biblioteki - przy pierwszym uruchomieniu moze to potrwac kilka minut...
"%VPY%" -m pip install --disable-pip-version-check --quiet --upgrade pip
"%VPY%" -m pip install --disable-pip-version-check -r requirements.txt
if errorlevel 1 goto :blad_pip
"%VPY%" -c "import fastapi, uvicorn, cv2, dotenv, jinja2, requests" >nul 2>&1
if errorlevel 1 goto :blad_pip
copy /y "requirements.txt" ".venv\hermes-requirements.txt" >nul

:pakiety_ok
echo [OK] Biblioteki zainstalowane

rem ---------------------------------------------------------------- 4. konfiguracja .env
if exist ".env" goto :env_ok
if not exist ".env.example" goto :env_ok
copy /y ".env.example" ".env" >nul
echo [OK] Utworzono plik .env z .env.example
echo      Klucz CARTO_API_KEY jest opcjonalny - bez niego nie dzialaja tylko nazwy ulic
echo      na mapie "Orto" i mapa "Ciemna".
:env_ok

if /i "%~1"=="--sprawdz" (
    echo.
    echo [OK] Wszystko gotowe. Uruchom start.bat bez parametrow, aby wlaczyc demonstrator.
    goto :koniec
)

rem ---------------------------------------------------------------- 5. start
echo.
echo [..] Uruchamiam serwer HERMES...
"%VPY%" uruchom.py
if errorlevel 1 goto :blad
goto :koniec


rem ============================================================================ podprogramy

:znajdz_python
rem Kolejnosc: launcher "py", "python" z PATH, typowe katalogi instalacji.
rem (Na Windows 10 "python" bywa tylko skrotem do Microsoft Store - sprawdzamy, czy naprawde dziala.)
set "PYEXE="
call :sprawdz_kandydata py -3
if defined PYEXE exit /b 0
call :sprawdz_kandydata python
if defined PYEXE exit /b 0
for %%V in (313 312 311 310) do (
    if not defined PYEXE if exist "%LOCALAPPDATA%\Programs\Python\Python%%V\python.exe" call :sprawdz_kandydata "%LOCALAPPDATA%\Programs\Python\Python%%V\python.exe"
    if not defined PYEXE if exist "%ProgramFiles%\Python%%V\python.exe" call :sprawdz_kandydata "%ProgramFiles%\Python%%V\python.exe"
)
exit /b 0

:sprawdz_kandydata
%* -c "import sys; sys.exit(0 if sys.version_info >= (3, 10) else 1)" >nul 2>&1
if errorlevel 1 exit /b 1
for /f "usebackq delims=" %%i in (`call %* -c "import sys; print(sys.executable)"`) do set "PYEXE=%%i"
exit /b 0

:instaluj_python
echo [..] Nie znaleziono Pythona 3.10 lub nowszego - instaluje Pythona 3.12 dla tego uzytkownika...
where winget >nul 2>&1
if errorlevel 1 goto :instaluj_python_pobierz
winget install -e --id Python.Python.3.12 --scope user --silent --accept-package-agreements --accept-source-agreements
call :znajdz_python
if defined PYEXE exit /b 0

:instaluj_python_pobierz
echo [..] Pobieram instalator Pythona z python.org...
set "INSTALATOR=%TEMP%\hermes-python-3.12.10-amd64.exe"
powershell -NoProfile -ExecutionPolicy Bypass -Command "[Net.ServicePointManager]::SecurityProtocol = [Net.SecurityProtocolType]::Tls12; $ProgressPreference = 'SilentlyContinue'; Invoke-WebRequest -UseBasicParsing -Uri 'https://www.python.org/ftp/python/3.12.10/python-3.12.10-amd64.exe' -OutFile $env:INSTALATOR"
if not exist "%INSTALATOR%" exit /b 1
echo [..] Instaluje Pythona - moze to potrwac 1-2 minuty...
"%INSTALATOR%" /quiet InstallAllUsers=0 PrependPath=1 Include_launcher=1 InstallLauncherAllUsers=0 Include_test=0
del "%INSTALATOR%" >nul 2>&1
exit /b 0


rem ============================================================================ bledy i koniec

:blad_venv
echo.
echo [BLAD] Nie udalo sie utworzyc srodowiska .venv w katalogu:
echo        %CD%
echo        Sprawdz, czy masz prawo zapisu w tym folderze - np. skopiuj projekt na Pulpit.
goto :blad

:blad_pip
echo.
echo [BLAD] Instalacja bibliotek nie powiodla sie.
echo        Sprawdz polaczenie z internetem i uruchom start.bat ponownie.
goto :blad

:blad
echo.
pause
endlocal
exit /b 1

:koniec
echo.
pause
endlocal
exit /b 0
