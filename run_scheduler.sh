#!/bin/bash
# NCSAA Basketball Scheduling System - Unix/Linux/Mac Shell Script
# This script runs the basketball game scheduler

echo "============================================================"
echo "NCSAA Basketball Scheduling System"
echo "============================================================"
echo ""

# Check if Python is installed
if ! command -v python3 &> /dev/null; then
    echo "ERROR: Python 3 is not installed"
    echo "Please install Python 3.8 or higher"
    exit 1
fi

# Check if dependencies are installed
echo "Checking dependencies..."
python3 -c "import gspread, ortools" 2>/dev/null
if [ $? -ne 0 ]; then
    echo "Installing dependencies..."
    pip3 install -r requirements.txt
    if [ $? -ne 0 ]; then
        echo "ERROR: Failed to install dependencies"
        exit 1
    fi
fi

echo ""
echo "Starting scheduler..."
echo ""

# Run the scheduler
python3 main.py "$@"

echo ""
echo "============================================================"
echo "Scheduling process completed"
echo "============================================================"
