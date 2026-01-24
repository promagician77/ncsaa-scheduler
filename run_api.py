"""
Run the FastAPI backend server.
"""

import uvicorn

if __name__ == "__main__":
    print("=" * 60)
    print("NCSAA Basketball Scheduling API Server")
    print("=" * 60)
    print("Starting server on http://localhost:8000")
    print("API Documentation: http://localhost:8000/docs")
    print("=" * 60)
    
    uvicorn.run(
        "api:app",
        host="0.0.0.0",
        port=8000,
        reload=True,
        log_level="info"
    )
