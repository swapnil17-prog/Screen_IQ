from fastapi import APIRouter

from app.api.routes import applications, auth, candidates, insights, jobs, public, system, team

api_router = APIRouter()
for module in (system, auth, team, jobs, candidates, applications, insights, public):
    api_router.include_router(module.router)
