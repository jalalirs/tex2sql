@echo off
echo Starting Tex2SQL API Server...
echo ================================

REM Activate virtual environment
call .venv\Scripts\activate

REM Check if activation worked
echo Virtual environment activated: %VIRTUAL_ENV%

REM Start the server
echo Upgrading alembic...
alembic upgrade head

REM Keep window open if there's an error
if %ERRORLEVEL% neq 0 (
    echo.
    echo Error occurred! Press any key to exit...
    pause > nul
)
