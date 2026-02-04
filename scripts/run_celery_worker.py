"""
Run Celery worker for async task processing.
"""

import sys
import os

# Add backend directory to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.core.celery_app import celery_app

if __name__ == "__main__":
    print("=" * 60)
    print("NCSAA Basketball Scheduling - Celery Worker")
    print("=" * 60)
    print("Starting Celery worker...")
    print("Worker will process schedule generation tasks")
    print("=" * 60)
    
    # Start Celery worker
    celery_app.worker_main([
        "worker",
        "--loglevel=info",
        "--concurrency=2",
        "--pool=solo" if os.name == "nt" else "--pool=prefork"  # Use solo pool on Windows
    ])
