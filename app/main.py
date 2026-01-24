"""
Main FastAPI application for NCSAA Basketball Scheduling System.
"""

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api import routes

app = FastAPI(
    title="NCSAA Basketball Scheduling API",
    description="API for generating and managing basketball game schedules",
    version="1.0.0"
)

# Enable CORS for frontend
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000"],  # Next.js default port
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include API routes
app.include_router(routes.router)


@app.get("/")
async def root():
    """Root endpoint."""
    return {
        "message": "NCSAA Basketball Scheduling API",
        "version": "1.0.0",
        "endpoints": {
            "generate": "/api/schedule",
            "stats": "/api/stats",
            "health": "/api/health"
        }
    }
