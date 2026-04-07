#!/bin/bash

echo "Installing dependencies..."
pip install -r requirements.txt

echo "Starting server..."
uvicorn backend.main:app --reload --port 8000