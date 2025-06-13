@echo off
echo Starting Tex2SQL API Server...
echo ================================

REM Activate virtual environment
call .venv\Scripts\activate

REM Check if activation worked
echo Virtual environment activated: %VIRTUAL_ENV%

REM Start the server
echo Starting uvicorn server...
uvicorn app.main:app --port 8000 --reload

REM Keep window open if there's an error
if %ERRORLEVEL% neq 0 (
    echo.
    echo Error occurred! Press any key to exit...
    pause > nul
)