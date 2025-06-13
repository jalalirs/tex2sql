#!/bin/bash
echo "Starting Tex2SQL API Server..."
echo "================================"

source ../venv/bin/activate

echo "Virtual environment activated"

echo "Starting uvicorn server..."
uvicorn app.main:app --port 6020 --reload
