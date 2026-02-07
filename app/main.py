from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api import routes

app = FastAPI(
    title="NCSAA Basketball Scheduling API",
    description="API for generating and managing basketball game schedules",
    version="1.0.0"
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
    expose_headers=["*"],
    max_age=600,
)

app.include_router(routes.router)


@app.get("/")
async def root():
    return {
        "message": "NCSAA Basketball Scheduling API",
        "version": "1.0.0",
        "endpoints": {
            "generate": "/api/schedule",
            "stats": "/api/stats",
            "health": "/api/health"
        }
    }
