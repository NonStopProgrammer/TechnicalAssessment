from fastapi import APIRouter

from backend.api.v1.endpoints import audit, auth, health, impact, qa, reports, screening

api_router = APIRouter()
api_router.include_router(health.router)
api_router.include_router(auth.router)
api_router.include_router(qa.router)
api_router.include_router(screening.router)
api_router.include_router(reports.router)
api_router.include_router(impact.router)
api_router.include_router(audit.router)
