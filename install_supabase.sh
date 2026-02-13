#!/bin/bash

# Installation script for NCSAA Scheduler after Supabase migration
# This script installs the required dependencies

echo "=========================================="
echo "NCSAA Scheduler - Supabase Migration"
echo "Installing Dependencies"
echo "=========================================="

# Check if we're in the correct directory
if [ ! -f "requirements.txt" ]; then
    echo "ERROR: requirements.txt not found!"
    echo "Please run this script from the ncsaa-scheduler directory"
    exit 1
fi

# Check if Python is installed
if ! command -v python3 &> /dev/null; then
    echo "ERROR: Python 3 is not installed!"
    echo "Please install Python 3.8 or higher"
    exit 1
fi

echo ""
echo "[1/4] Checking Python version..."
python3 --version

echo ""
echo "[2/4] Upgrading pip..."
python3 -m pip install --upgrade pip

echo ""
echo "[3/4] Installing requirements..."
pip install -r requirements.txt

if [ $? -eq 0 ]; then
    echo ""
    echo "[4/4] Verifying installation..."
    
    # Check if supabase is installed
    python3 -c "import supabase; print('✅ Supabase client installed')" 2>/dev/null
    if [ $? -ne 0 ]; then
        echo "❌ Supabase client not installed correctly"
        exit 1
    fi
    
    # Check if other key packages are installed
    python3 -c "import fastapi; print('✅ FastAPI installed')" 2>/dev/null
    python3 -c "import pydantic; print('✅ Pydantic installed')" 2>/dev/null
    python3 -c "import celery; print('✅ Celery installed')" 2>/dev/null
    
    echo ""
    echo "=========================================="
    echo "✅ Installation Complete!"
    echo "=========================================="
    echo ""
    echo "Next steps:"
    echo "1. Verify Supabase credentials in .env file"
    echo "2. Run test: python scripts/test_supabase_connection.py"
    echo "3. Run scheduler: python scripts/run_scheduler.py"
    echo "4. Start API: uvicorn app.main:app --reload"
    echo ""
else
    echo ""
    echo "=========================================="
    echo "❌ Installation Failed"
    echo "=========================================="
    echo ""
    echo "Please check the error messages above"
    exit 1
fi
